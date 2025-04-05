# backend/presentation/api/routes/snapclient.py
"""
Routes API minimalistes pour le plugin snapclient.
"""
from fastapi import APIRouter, HTTPException, Depends, Body, status as http_status
from typing import Dict, Any

# Importer la dépendance spécifique depuis le fichier dependencies.py
# Assurez-vous que le fichier backend/presentation/api/dependencies.py existe
# et contient la fonction get_snapclient_plugin_instance définie précédemment.
from backend.presentation.api.dependencies import get_snapclient_plugin_instance

# Créer un router dédié pour snapclient
router = APIRouter(
    prefix="/snapclient",
    tags=["Snapclient"], # Tag pour Swagger UI
    responses={
        404: {"description": "Not found"},
        503: {"description": "Service Unavailable (Plugin not ready)"}
    },
)

# Récupérer une instance du logger depuis le plugin (via dépendance) pour logguer les erreurs API
async def get_logger_from_plugin(plugin = Depends(get_snapclient_plugin_instance)):
    return plugin.logger

@router.get("/status",
            summary="Get Snapclient Status",
            description="Retrieves the current status of the Snapclient plugin, including connection state and discovered servers.")
async def get_snapclient_status(
    plugin = Depends(get_snapclient_plugin_instance) # Correction: Pas de () ici
):
    """Récupère le statut actuel du client Snapcast."""
    logger = await get_logger_from_plugin(plugin) # Obtenir le logger
    try:
        status_data = await plugin.get_status()
        return status_data
    except Exception as e:
        logger.error(f"API Error in GET /status: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Snapclient status: {str(e)}"
        )

@router.post("/discover",
             summary="Discover Snapcast Servers",
             description="Triggers a network discovery for available Snapcast servers using Avahi/mDNS.")
async def discover_snapcast_servers(
    plugin = Depends(get_snapclient_plugin_instance) # Correction: Pas de () ici
):
    """Force une découverte des serveurs Snapcast sur le réseau."""
    logger = await get_logger_from_plugin(plugin)
    try:
        result = await plugin.handle_command("discover", {})
        if result.get("success"):
            # Retourne directement la liste des serveurs comme attendu par le frontend
            return {"servers": result.get("servers", [])}
        else:
            # Si handle_command retourne une erreur spécifique
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Discovery failed for an unknown reason.")
            )
    except Exception as e:
        logger.error(f"API Error in POST /discover: {e}", exc_info=True)
        # Renvoyer l'exception si c'est déjà une HTTPException (levée par handle_command par ex.)
        if isinstance(e, HTTPException): raise e
        # Sinon, erreur serveur générique
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to discover servers: {str(e)}"
        )

@router.post("/connect",
             status_code=http_status.HTTP_200_OK, # Retourne 200 OK avec le nouveau statut
             summary="Connect to Snapcast Server",
             description="Connects the Snapclient plugin to the specified Snapcast server host.")
async def connect_to_snapcast_server(
    payload: Dict[str, str] = Body(..., example={"host": "192.168.1.100"}),
    plugin = Depends(get_snapclient_plugin_instance) # Correction: Pas de () ici
):
    """Se connecte à un serveur Snapcast spécifique via son hôte."""
    logger = await get_logger_from_plugin(plugin)
    host = payload.get("host")
    if not host:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="'host' field is required in the request body."
        )
    try:
        result = await plugin.handle_command("connect", {"host": host})
        if result.get("success"):
            # Retourner le statut mis à jour après la connexion réussie
            updated_status = await plugin.get_status()
            return updated_status
        else:
            # Analyser l'erreur retournée par handle_command
            error_detail = result.get("error", f"Failed to connect to host {host}.")
            # Choisir un code d'erreur plus spécifique si possible
            status_code = http_status.HTTP_409_CONFLICT if "Cannot connect while in state" in error_detail else http_status.HTTP_400_BAD_REQUEST
            raise HTTPException(status_code=status_code, detail=error_detail)

    except Exception as e:
        logger.error(f"API Error in POST /connect for host {host}: {e}", exc_info=True)
        if isinstance(e, HTTPException): raise e
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect to server {host}: {str(e)}"
        )

@router.post("/disconnect",
             status_code=http_status.HTTP_200_OK, # Retourne 200 OK avec le nouveau statut
             summary="Disconnect from Snapcast Server",
             description="Disconnects from the currently connected Snapcast server.")
async def disconnect_from_snapcast_server(
    plugin = Depends(get_snapclient_plugin_instance) # Correction: Pas de () ici
):
    """Se déconnecte du serveur Snapcast actuel."""
    logger = await get_logger_from_plugin(plugin)
    try:
        result = await plugin.handle_command("disconnect", {})
        # Considérer le succès si la commande réussit OU si on était déjà déconnecté
        if result.get("success") or "Already disconnected" in result.get("message", ""):
             # Retourner le statut mis à jour après la déconnexion réussie (ou si déjà déconnecté)
            updated_status = await plugin.get_status()
            return updated_status
        else:
            # Si handle_command échoue explicitement
             raise HTTPException(
                 status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, # Ou 400 si l'erreur vient du plugin
                 detail=result.get("error", "Failed to disconnect.")
             )
    except Exception as e:
        logger.error(f"API Error in POST /disconnect: {e}", exc_info=True)
        if isinstance(e, HTTPException): raise e
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect from server: {str(e)}"
        )

# Notes finales :
# - Ce fichier dépend de `backend/presentation/api/dependencies.py` pour la fonction `get_snapclient_plugin_instance`.
# - Il utilise l'instance du plugin injectée pour appeler `handle_command` et `get_status`.
# - Les réponses d'erreur sont gérées via `HTTPException`.
# - Les réponses de succès pour connect/disconnect retournent le nouveau statut complet.