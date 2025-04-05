# backend/main.py
"""
Point d'entrée principal de l'application oakOS.
"""
import asyncio
import logging
import uvicorn
import json
import time
import subprocess
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any

# --- Imports Application ---
from backend.config.container import container # Utilisation du container DI
from backend.presentation.websockets.manager import WebSocketManager
from backend.presentation.websockets.events import WebSocketEventHandler
from backend.domain.audio import AudioState, AudioStateMachine # Importer AudioStateMachine

# --- Imports des Routeurs ---
# Modifier les imports pour récupérer les objets router directement
from backend.presentation.api.routes.librespot import router as librespot_router
from backend.presentation.api.routes.snapclient import router as snapclient_router
# Importer aussi le routeur audio générique s'il existe (basé sur les endpoints dans main.py)
# Si les routes /api/audio/* sont dans leur propre fichier, importez-le ici.
# Sinon, on peut les laisser dans main.py pour l'instant.

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__) # Utiliser un logger spécifique au module

# --- Création de l'application FastAPI ---
app = FastAPI(title="oakOS Backend")

# --- Configuration CORS ---
# En production, limitez aux origines spécifiques
origins = ["*"] # Pour le développement. À restreindre en production !
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Initialisation des Services via Container DI ---
# Ces services sont gérés par le container d'injection de dépendances
event_bus = container.event_bus()
audio_state_machine: AudioStateMachine = container.audio_state_machine() # Typage pour l'autocomplétion
ws_manager = WebSocketManager() # Ce manager semble être utilisé directement
ws_event_handler = WebSocketEventHandler(event_bus, ws_manager) # S'abonne aux événements

# --- Stockage des instances importantes dans app.state ---
# Rend ces instances accessibles aux dépendances FastAPI via request.app.state
app.state.event_bus = event_bus
app.state.audio_state_machine = audio_state_machine # IMPORTANT pour dependencies.py
app.state.ws_manager = ws_manager
# Note: Les plugins eux-mêmes sont récupérés via audio_state_machine

# --- Nettoyage Périodique des WebSockets ---
async def periodic_websocket_cleanup():
    """Nettoie périodiquement les connexions WebSocket inactives."""
    while True:
        await asyncio.sleep(30) # Vérifier toutes les 30 secondes
        if app.state.ws_manager: # Utiliser app.state
            try:
                removed_count = await app.state.ws_manager.cleanup_stale_connections()
                if removed_count > 0:
                    logger.info(f"Cleanup: Removed {removed_count} stale WebSocket connections.")
            except Exception as e:
                logger.error(f"Error during WebSocket cleanup task: {e}", exc_info=True)

# --- Événements Startup/Shutdown ---
@app.on_event("startup")
async def startup_event():
    """Initialisation de l'application au démarrage."""
    logger.info("Starting oakOS backend application...")

    # Démarrer la tâche de nettoyage des WebSockets
    # Stocker la tâche pour pouvoir l'annuler proprement au shutdown si nécessaire
    app.state.cleanup_task = asyncio.create_task(periodic_websocket_cleanup())
    logger.info("WebSocket cleanup task started.")

    # Initialisation des plugins (via le container et enregistrement dans la state machine)
    try:
        logger.info("Initializing audio plugins...")
        # S'assurer que le WebSocket manager est propre au démarrage
        if hasattr(app.state.ws_manager, 'cleanup_all_connections'):
            await app.state.ws_manager.cleanup_all_connections()

        # Initialiser et enregistrer Librespot
        librespot_plugin = container.librespot_plugin()
        if await librespot_plugin.initialize():
            audio_state_machine.register_plugin(AudioState.LIBRESPOT, librespot_plugin)
            logger.info(f"Plugin '{AudioState.LIBRESPOT.value}' initialized and registered.")
        else:
            logger.error(f"Failed to initialize plugin '{AudioState.LIBRESPOT.value}'.")

        # Initialiser et enregistrer Snapclient (utilisant la source MACOS)
        snapclient_plugin = container.snapclient_plugin()
        if await snapclient_plugin.initialize():
            # Assurez-vous que AudioState.MACOS est bien l'enum correspondant à snapclient
            audio_state_machine.register_plugin(AudioState.MACOS, snapclient_plugin)
            logger.info(f"Plugin '{AudioState.MACOS.value}' (Snapclient) initialized and registered.")
        else:
            logger.error(f"Failed to initialize plugin '{AudioState.MACOS.value}' (Snapclient).")

        # Ajoutez ici l'initialisation et l'enregistrement d'autres plugins...

        logger.info("Audio plugins initialization complete.")

        # Optionnel: Définir un état initial par défaut pour l'audio si nécessaire
        # await audio_state_machine.transition_to(AudioState.NONE) ou un autre état par défaut

    except Exception as e:
        logger.error(f"Error during application startup: {e}", exc_info=True)
        # On pourrait vouloir arrêter l'application ici si l'initialisation échoue gravement
        # raise RuntimeError("Failed to initialize critical components.") from e

@app.on_event("shutdown")
async def shutdown_event():
    """Nettoyage à l'arrêt de l'application."""
    logger.info("Shutting down oakOS backend application...")

    # Annuler la tâche de nettoyage
    if hasattr(app.state, 'cleanup_task') and app.state.cleanup_task:
        app.state.cleanup_task.cancel()
        try:
            await app.state.cleanup_task
        except asyncio.CancelledError:
            logger.info("WebSocket cleanup task cancelled.")
        except Exception as e:
             logger.error(f"Error during cleanup task shutdown: {e}", exc_info=True)


    # Arrêter tous les plugins enregistrés
    if app.state.audio_state_machine:
        logger.info("Stopping all registered audio plugins...")
        await app.state.audio_state_machine.stop_all_plugins() # Assumer que cette méthode existe
        logger.info("Audio plugins stopped.")

    # Fermer les connexions WebSocket restantes
    if app.state.ws_manager:
        logger.info("Closing remaining WebSocket connections...")
        await app.state.ws_manager.disconnect_all() # Assumer que cette méthode existe
        logger.info("WebSocket connections closed.")

    logger.info("oakOS backend shutdown complete.")


# --- Inclusion des Routeurs ---
# Supprimer les anciens appels setup_*_routes ici s'ils y étaient
# Inclure les routeurs importés
app.include_router(librespot_router, prefix="/api") # Préfixe commun /api
app.include_router(snapclient_router, prefix="/api") # Utiliser le même préfixe /api


# --- Endpoints Généraux (Audio, Statut, WebSocket) ---
# Ces endpoints restent dans main.py car ils sont transverses ou simples

@app.get("/api/status", tags=["General"])
async def status():
    """Endpoint de statut simple pour vérifier que l'API fonctionne."""
    active_connections = len(app.state.ws_manager.active_connections) if app.state.ws_manager else 0
    return {"status": "running", "version": "0.1.0", "ws_connections": active_connections}

@app.get("/api/websocket/status", tags=["WebSocket"])
async def websocket_status():
    """Endpoint pour vérifier l'état des connexions WebSocket."""
    active_connections = len(app.state.ws_manager.active_connections) if app.state.ws_manager else 0
    return {
        "active_connections": active_connections,
        "timestamp": time.time()
    }

@app.post("/api/websocket/cleanup", tags=["WebSocket"])
async def force_websocket_cleanup():
    """Force le nettoyage des connexions WebSocket inactives."""
    removed_count = 0
    if app.state.ws_manager:
        try:
            removed_count = await app.state.ws_manager.cleanup_stale_connections()
        except Exception as e:
            logger.error(f"Error during forced WebSocket cleanup: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    remaining = len(app.state.ws_manager.active_connections) if app.state.ws_manager else 0
    return {
        "status": "success",
        "removed": removed_count,
        "remaining": remaining
    }

@app.get("/api/audio/state", tags=["Audio"])
async def get_audio_state():
    """Récupère l'état actuel du système audio."""
    # Utilise la machine à états stockée dans app.state
    if not app.state.audio_state_machine:
         raise HTTPException(status_code=503, detail="Audio State Machine not available")
    return await app.state.audio_state_machine.get_current_state_details() # Utiliser une méthode qui retourne plus de détails

@app.post("/api/audio/source/{source}", tags=["Audio"])
async def change_audio_source(source: str):
    """Change la source audio active."""
    if not app.state.audio_state_machine:
         raise HTTPException(status_code=503, detail="Audio State Machine not available")
    try:
        target_state = AudioState(source) # Valide si 'source' est un membre de AudioState
        success = await app.state.audio_state_machine.transition_to(target_state)
        if success:
            # Retourner le nouvel état après la transition
            new_state_details = await app.state.audio_state_machine.get_current_state_details()
            return new_state_details
            # return {"status": "success", "message": f"Switched to {source}"}
        else:
            # Fournir plus de détails sur l'échec si possible
            current_state_details = await app.state.audio_state_machine.get_current_state_details()
            raise HTTPException(status_code=409, detail=f"Failed to switch to {source} from state {current_state_details.get('state')}")
    except ValueError:
        # L'ID source n'est pas dans l'enum AudioState
        valid_sources = [s.value for s in AudioState if s != AudioState.NONE and s != AudioState.TRANSITIONING]
        raise HTTPException(status_code=400, detail=f"Invalid audio source: '{source}'. Valid sources are: {valid_sources}")
    except Exception as e:
         logger.error(f"Error changing audio source to '{source}': {e}", exc_info=True)
         raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@app.post("/api/audio/control/{source}", tags=["Audio"])
async def control_audio_source(source: str, command_data: Dict[str, Any]):
    """Contrôle une source audio spécifique en appelant handle_command sur le plugin."""
    if not app.state.audio_state_machine:
         raise HTTPException(status_code=503, detail="Audio State Machine not available")

    # Valider la source
    try:
        target_state = AudioState(source)
        if target_state in [AudioState.NONE, AudioState.TRANSITIONING]:
            raise ValueError("Cannot control NONE or TRANSITIONING state.")
    except ValueError:
        valid_sources = [s.value for s in AudioState if s != AudioState.NONE and s != AudioState.TRANSITIONING]
        raise HTTPException(status_code=400, detail=f"Invalid audio source for control: '{source}'. Valid sources are: {valid_sources}")

    # Valider la commande
    command = command_data.get("command")
    data = command_data.get("data", {})
    if not command:
        raise HTTPException(status_code=400, detail="'command' field is required in the request body.")

    # Récupérer le plugin
    plugin = app.state.audio_state_machine.get_plugin_by_state(target_state)
    if not plugin:
        # Cela pourrait arriver si le plugin n'a pas été initialisé correctement
        raise HTTPException(status_code=503, detail=f"Plugin for source '{source}' is not available or not initialized.")

    # Exécuter la commande
    try:
        logger.info(f"Executing command '{command}' for source '{source}' with data: {data}")
        result = await plugin.handle_command(command, data)

        # Vérifier si le plugin a retourné une erreur interne
        if isinstance(result, dict) and result.get("success") is False:
             error_detail = result.get("error", "Plugin command failed.")
             # Retourner une erreur HTTP basée sur l'échec du plugin
             # On pourrait mapper les erreurs plugin à des codes HTTP, mais 400 est souvent suffisant
             raise HTTPException(status_code=400, detail=error_detail)

        # Si tout va bien, retourner le résultat du plugin
        # Peut-être envelopper dans une structure standard ?
        return {"status": "success", "command": command, "result": result}

    except HTTPException as http_exc:
         raise http_exc # Renvoyer les erreurs HTTP déjà formatées
    except Exception as e:
        logger.error(f"Error executing command '{command}' for source '{source}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing command '{command}': {str(e)}")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Endpoint WebSocket pour la communication en temps réel."""
    # Utiliser le manager stocké dans app.state
    ws_manager_instance = app.state.ws_manager
    if not ws_manager_instance:
        # Gérer le cas où le manager n'est pas prêt (ne devrait pas arriver si startup est ok)
        await websocket.close(code=1011, reason="WebSocket Manager not available")
        logger.error("WebSocket connection attempt failed: WS Manager not initialized.")
        return

    client_id = f"client_{int(time.time()*1000)}_{websocket.client.port}" # ID plus unique
    await ws_manager_instance.connect(websocket, client_id) # Passer l'ID à connect
    logger.info(f"WebSocket connected: {client_id} (Total: {len(ws_manager_instance.active_connections)})")

    try:
        # Envoyer un message de bienvenue/confirmation
        await ws_manager_instance.send_to_client(websocket, {
            "type": "connection_ack",
            "data": {"clientId": client_id, "message": "Connection successful."}
        })

        while True:
            try:
                # Attendre un message avec un timeout raisonnable
                raw_data = await asyncio.wait_for(websocket.receive_text(), timeout=90.0) # Augmenté à 90s
                message = json.loads(raw_data)
                msg_type = message.get("type")

                if msg_type == "heartbeat":
                    # Répondre au heartbeat pour confirmer que le serveur est vivant
                    await ws_manager_instance.send_to_client(websocket, {
                        "type": "heartbeat_ack",
                        "data": {"timestamp": time.time()}
                    })
                # Gérer d'autres types de messages du client si nécessaire
                # elif msg_type == "some_client_action":
                #    await handle_client_action(message.get("data"))
                else:
                     logger.debug(f"Received WebSocket message from {client_id}: type='{msg_type}'")
                     # Accusé de réception générique (optionnel)
                     # await ws_manager_instance.send_to_client(websocket, {"type": "ack", "received_type": msg_type})


            except asyncio.TimeoutError:
                # Si aucun message (y compris heartbeat) n'est reçu pendant le timeout,
                # envoyer un ping pour vérifier si le client est toujours là.
                try:
                    # Utiliser le ping WebSocket standard si possible, sinon un message JSON
                    await asyncio.wait_for(websocket.send_text(json.dumps({"type": "ping"})), timeout=5.0)
                except (asyncio.TimeoutError, Exception) as ping_error:
                    logger.warning(f"WebSocket {client_id} did not respond to ping. Closing connection. Error: {ping_error}")
                    break # Sortir de la boucle pour déconnecter

            except WebSocketDisconnect:
                logger.info(f"WebSocket {client_id} disconnected (client closed).")
                break # Sortir de la boucle while

            except json.JSONDecodeError:
                logger.warning(f"Received invalid JSON from WebSocket {client_id}. Data: {raw_data[:100]}...")
                # Envoyer une erreur au client ? Optionnel.

            except Exception as loop_error:
                 logger.error(f"Unexpected error in WebSocket loop for {client_id}: {loop_error}", exc_info=True)
                 # Attendre un peu avant de continuer pour éviter boucle d'erreur rapide
                 await asyncio.sleep(1)


    except Exception as e:
        # Gérer les erreurs qui se produisent en dehors de la boucle principale (ex: connexion initiale)
        logger.error(f"Unhandled error for WebSocket {client_id}: {e}", exc_info=True)
    finally:
        # S'assurer que la déconnexion est enregistrée
        ws_manager_instance.disconnect(websocket)
        logger.info(f"WebSocket connection closed for {client_id}. (Total: {len(ws_manager_instance.active_connections)})")


# --- Point d'Entrée Uvicorn ---
if __name__ == "__main__":
    # Utiliser les logs Uvicorn pour plus de détails sur les requêtes
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info" # ou "debug" pour plus de détails
    )