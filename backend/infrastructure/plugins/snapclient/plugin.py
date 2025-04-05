# backend/infrastructure/plugins/snapclient/plugin.py
"""
Plugin principal Snapclient pour oakOS - Version minimaliste.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional, Set

from backend.application.event_bus import EventBus
from backend.infrastructure.plugins.base import BaseAudioPlugin
# Assurez-vous que les imports correspondent aux classes que vous avez finalisées
from backend.infrastructure.plugins.snapclient.process import SnapclientProcessManager
from backend.infrastructure.plugins.snapclient.discovery import SnapclientDiscovery
from backend.infrastructure.plugins.snapclient.models import SnapclientServer

class SnapclientPlugin(BaseAudioPlugin):
    """
    Plugin minimaliste pour la source audio Snapclient.
    Gère la connexion à un serveur Snapcast et surveille le processus client.
    """
    # --- États Standardisés ---
    STATE_INACTIVE = "inactive"                # Plugin non sélectionné
    STATE_READY_TO_CONNECT = "ready_to_connect" # Plugin sélectionné, prêt mais non connecté
    STATE_CONNECTED = "connected"              # Connecté à un serveur Snapcast

    # --- Transitions d'états autorisées ---
    # De quel état -> Vers quels états
    VALID_TRANSITIONS: Dict[str, Set[str]] = {
        STATE_INACTIVE: {STATE_READY_TO_CONNECT},
        STATE_READY_TO_CONNECT: {STATE_CONNECTED, STATE_INACTIVE},
        STATE_CONNECTED: {STATE_READY_TO_CONNECT, STATE_INACTIVE},
    }

    def __init__(self, event_bus: EventBus, config: Dict[str, Any]):
        """
        Initialise le plugin Snapclient.

        Args:
            event_bus: Le bus d'événements de l'application.
            config: Configuration spécifique au plugin (ex: chemin de l'exécutable).
        """
        super().__init__(event_bus, "snapclient")
        self.logger = logging.getLogger("plugin.snapclient")

        # Configuration
        executable_path = config.get("executable_path", "/usr/bin/snapclient")
        alsa_device = config.get("alsa_device", "default") # Périphérique ALSA par défaut
        self._monitor_interval = config.get("monitor_interval_sec", 5.0) # Intervalle de vérification

        # Composants internes
        self.process_manager = SnapclientProcessManager(executable_path, alsa_device)
        self.discovery = SnapclientDiscovery()

        # État interne
        self._current_state: str = self.STATE_INACTIVE
        self._connected_server: Optional[SnapclientServer] = None
        self._discovered_servers: List[SnapclientServer] = []
        self._monitor_task: Optional[asyncio.Task] = None

        self.logger.info("Plugin Snapclient initialisé.")

    # --- Gestion du Cycle de Vie ---

    async def initialize(self) -> bool:
        """Vérifie les prérequis (ex: exécutable snapclient)."""
        self.logger.info("Initialisation de Snapclient...")
        if not await self.process_manager.check_executable():
            self.logger.error("Prérequis manquant: exécutable snapclient.")
            return False
        if not self.discovery._avahi_cmd: # Vérifie si avahi-browse a été trouvé
             self.logger.warning("La découverte Avahi n'est pas disponible.")
             # On peut continuer mais la découverte ne fonctionnera pas
        self.logger.info("Snapclient initialisé avec succès.")
        return True

    async def start(self) -> bool:
        """
        Active le plugin, passe à l'état READY_TO_CONNECT et lance le monitoring.
        Ne se connecte pas automatiquement.
        """
        if self.is_active:
            self.logger.warning("Plugin Snapclient déjà démarré.")
            return True

        self.logger.info("Démarrage du plugin Snapclient...")
        self.is_active = True
        await self._set_state(self.STATE_READY_TO_CONNECT)

        # Démarrer la surveillance de l'état de la connexion
        self._start_monitoring()

        # Optionnel : lancer une découverte initiale pour peupler la liste
        # Note: Cela peut prendre quelques secondes.
        # asyncio.create_task(self.handle_command("discover", {}))

        self.logger.info("Plugin Snapclient démarré et prêt à connecter.")
        return True

    async def stop(self) -> bool:
        """
        Désactive le plugin, arrête le processus client et le monitoring.
        """
        if not self.is_active:
            # self.logger.debug("Plugin Snapclient déjà arrêté.")
            return True

        self.logger.info("Arrêt du plugin Snapclient...")
        self.is_active = False

        # Arrêter la surveillance
        self._stop_monitoring()

        # Arrêter le processus snapclient s'il tourne
        await self.process_manager.stop()

        # Réinitialiser l'état
        self._connected_server = None
        await self._set_state(self.STATE_INACTIVE)

        self.logger.info("Plugin Snapclient arrêté.")
        return True

    # --- Gestion d'État ---

    @property
    def current_state(self) -> str:
        return self._current_state

    async def _set_state(self, new_state: str, server: Optional[SnapclientServer] = None) -> bool:
        """
        Change l'état interne du plugin et publie l'événement.
        Valide la transition.

        Args:
            new_state: Le nouvel état cible.
            server: Le serveur concerné (pour l'état CONNECTED).

        Returns:
            True si la transition a réussi, False sinon.
        """
        if new_state == self._current_state and new_state != self.STATE_CONNECTED:
             # Pas de changement réel nécessaire sauf si on reconfirme la connexion
             # ou si on passe explicitement les mêmes infos serveur (peu probable)
            return True

        if new_state not in self.VALID_TRANSITIONS.get(self._current_state, set()):
            self.logger.warning(f"Transition d'état invalide demandée: {self._current_state} -> {new_state}")
            # Publier une erreur de transition ?
            # await self.event_bus.publish("audio_transition_error", {...})
            return False

        previous_state = self._current_state
        self._current_state = new_state

        # Mettre à jour le serveur connecté
        if new_state == self.STATE_CONNECTED and server:
            self._connected_server = server
        elif new_state != self.STATE_CONNECTED:
            self._connected_server = None # Assurer la réinitialisation

        self.logger.info(f"Transition d'état: {previous_state} -> {new_state}" +
                         (f" (Serveur: {server.name})" if server and new_state == self.STATE_CONNECTED else ""))

        # Préparer et publier l'état complet
        await self.publish_plugin_state()
        return True

    async def publish_plugin_state(self):
        """Prépare et publie l'état actuel complet via le bus d'événements."""
        status = await self.get_status()
        await self.event_bus.publish("audio_status_updated", status)
        self.logger.debug(f"État Snapclient publié: {status}")


    # --- Commandes et Actions ---

    async def get_status(self) -> Dict[str, Any]:
        """Retourne l'état actuel complet du plugin."""
        is_process_running = await self.process_manager.is_running()
        pid = self.process_manager.get_pid()

        # Logique de cohérence : si on pense être connecté mais que le processus ne tourne plus, corriger.
        # La boucle de monitoring le fait aussi, mais c'est bien d'avoir la synchro ici aussi.
        if self._current_state == self.STATE_CONNECTED and not is_process_running:
             self.logger.warning("Incohérence détectée dans get_status: état CONNECTED mais processus arrêté. Correction...")
             # On ne change pas l'état ici directement pour éviter les effets de bord dans get_status
             # mais on retourne un état cohérent avec la réalité du processus.
             # Le monitor loop fera le changement d'état officiel.
             status = {
                "source": self.source_id,
                "plugin_state": self.STATE_READY_TO_CONNECT, # Etat corrigé
                "is_active": self.is_active,
                "connected": False, # Corrigé
                "deviceConnected": False, # Corrigé
                "host": None, # Corrigé
                "device_name": None, # Corrigé
                "discovered_servers": [s.to_dict() for s in self._discovered_servers],
                "process_running": False, # Corrigé
                "pid": None
             }
             return status

        # Cas normal
        status = {
            "source": self.source_id,
            "plugin_state": self._current_state,
            "is_active": self.is_active,
            "connected": self._current_state == self.STATE_CONNECTED,
            "deviceConnected": self._current_state == self.STATE_CONNECTED, # Alias pour compatibilité ? A voir.
            "host": self._connected_server.host if self._connected_server else None,
            "device_name": self._connected_server.name if self._connected_server else None,
            "discovered_servers": [s.to_dict() for s in self._discovered_servers],
            "process_running": is_process_running,
            "pid": pid
        }
        return status

    async def handle_command(self, command: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Traite les commandes spécifiques à Snapclient."""
        self.logger.info(f"Traitement de la commande Snapclient: {command} avec data: {data}")

        if not self.is_active and command not in ["discover"]: # Autoriser discover même si inactif? A débattre.
             self.logger.warning(f"Plugin inactif, commande '{command}' ignorée.")
             return {"success": False, "error": "Plugin not active"}

        if command == "discover":
            servers = await self.discovery.discover()
            self._discovered_servers = servers # Mettre à jour la liste interne
            return {"success": True, "servers": [s.to_dict() for s in servers]}

        elif command == "connect":
            host = data.get("host")
            if not host:
                return {"success": False, "error": "Host parameter is required."}

            if self._current_state != self.STATE_READY_TO_CONNECT:
                current_host = self._connected_server.host if self._connected_server else "N/A"
                # Si déjà connecté au même host, ne rien faire
                if self._current_state == self.STATE_CONNECTED and current_host == host:
                    self.logger.info(f"Déjà connecté à {host}, commande 'connect' ignorée.")
                    return {"success": True, "message": f"Already connected to {host}."}
                # Sinon, erreur ou déconnexion nécessaire d'abord
                self.logger.warning(f"Commande 'connect' reçue dans un état inapproprié ({self._current_state}). Déconnectez-vous d'abord si connecté à {current_host}.")
                return {"success": False, "error": f"Cannot connect while in state {self._current_state}. Disconnect first if connected."}

            # Trouver le nom du serveur correspondant à l'hôte si possible
            server_to_connect = next((s for s in self._discovered_servers if s.host == host), None)
            if not server_to_connect:
                self.logger.warning(f"Hôte '{host}' non trouvé dans la dernière découverte. Tentative de connexion quand même.")
                # Créer un objet serveur temporaire
                server_to_connect = SnapclientServer(host=host, name=f"Snapserver ({host})") # Nom par défaut

            # Démarrer le processus
            success = await self.process_manager.start(host)
            if success:
                await self._set_state(self.STATE_CONNECTED, server=server_to_connect)
                return {"success": True, "message": f"Successfully connected to {server_to_connect.name} ({host})."}
            else:
                self.logger.error(f"Échec du démarrage du processus snapclient pour {host}.")
                # Assurer qu'on reste dans READY_TO_CONNECT
                await self._set_state(self.STATE_READY_TO_CONNECT)
                return {"success": False, "error": f"Failed to start snapclient process for host {host}."}

        elif command == "disconnect":
            if self._current_state != self.STATE_CONNECTED:
                self.logger.warning(f"Commande 'disconnect' reçue alors que non connecté (état: {self._current_state}).")
                return {"success": True, "message": "Already disconnected."} # Considéré comme succès

            server_name = self._connected_server.name if self._connected_server else "Unknown"
            self.logger.info(f"Déconnexion du serveur {server_name} demandée...")
            success = await self.process_manager.stop()
            if success:
                await self._set_state(self.STATE_READY_TO_CONNECT)
                return {"success": True, "message": f"Successfully disconnected from {server_name}."}
            else:
                # Même si stop échoue, on force l'état car le but est d'être déconnecté
                self.logger.warning("Échec de l'arrêt du processus snapclient, mais passage à READY_TO_CONNECT forcé.")
                await self._set_state(self.STATE_READY_TO_CONNECT)
                return {"success": False, "error": "Failed to cleanly stop snapclient process, but state forced to disconnected."}

        else:
            self.logger.warning(f"Commande Snapclient inconnue: {command}")
            return {"success": False, "error": f"Unknown command: {command}"}

    # --- Monitoring Interne ---

    def _start_monitoring(self):
        """Lance la tâche de surveillance en arrière-plan."""
        if self._monitor_task and not self._monitor_task.done():
            self.logger.warning("Tâche de monitoring déjà en cours.")
            return

        self.logger.info(f"Démarrage du monitoring Snapclient (intervalle: {self._monitor_interval}s).")
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    def _stop_monitoring(self):
        """Arrête la tâche de surveillance."""
        if self._monitor_task and not self._monitor_task.done():
            self.logger.info("Arrêt du monitoring Snapclient...")
            self._monitor_task.cancel()
            # On ne fait pas await ici pour ne pas bloquer stop() si cancel() prend du temps
        self._monitor_task = None

    async def _monitor_loop(self):
        """Boucle de surveillance périodique de l'état du processus."""
        self.logger.debug("Boucle de monitoring démarrée.")
        while self.is_active:
            try:
                await asyncio.sleep(self._monitor_interval)

                if not self.is_active: break # Sortir si désactivé pendant le sleep

                is_running = await self.process_manager.is_running()

                # Scénario 1: On est connecté mais le processus ne tourne plus
                if self._current_state == self.STATE_CONNECTED and not is_running:
                    self.logger.warning(f"MONITOR: Processus snapclient arrêté inopinément (serveur: {self._connected_server.name if self._connected_server else 'N/A'}). Passage à READY_TO_CONNECT.")
                    await self._set_state(self.STATE_READY_TO_CONNECT)
                    # Faut-il tenter de relancer ? Pour l'instant non, on attend une action utilisateur.

                # Scénario 2: On n'est pas connecté mais un processus tourne (ne devrait pas arriver)
                elif self._current_state != self.STATE_CONNECTED and is_running:
                     self.logger.warning(f"MONITOR: Processus snapclient trouvé alors que l'état est {self._current_state}. Arrêt forcé.")
                     await self.process_manager.stop()
                     # S'assurer que l'état est correct après l'arrêt forcé
                     if self._current_state == self.STATE_CONNECTED: # Si l'état a changé entretemps
                          await self._set_state(self.STATE_READY_TO_CONNECT)


            except asyncio.CancelledError:
                self.logger.info("Boucle de monitoring annulée.")
                break
            except Exception as e:
                self.logger.error(f"Erreur dans la boucle de monitoring Snapclient: {e}", exc_info=True)
                # Attendre un peu plus longtemps avant de réessayer en cas d'erreur
                await asyncio.sleep(self._monitor_interval * 2)

        self.logger.debug("Boucle de monitoring terminée.")