"""
Classe de base pour les plugins de sources audio.
"""
import logging
from abc import ABC
from typing import Dict, Any, Optional

from backend.application.interfaces.audio_source import AudioSourcePlugin
from backend.application.event_bus import EventBus


class BaseAudioPlugin(AudioSourcePlugin, ABC):
    """
    Classe de base qui implémente les fonctionnalités communes à tous les plugins audio.
    """
    
    # États communs standardisés
    STATE_INACTIVE = "inactive"  
    STATE_READY_TO_CONNECT = "ready_to_connect"
    STATE_DEVICE_CHANGE_REQUESTED = "device_change_requested" 
    STATE_CONNECTED = "connected"
    
    # États spécifiques pour plugins avec contrôle de lecture
    STATE_PLAYING = "playing"
    STATE_PAUSED = "paused"
    STATE_STOPPED = "stopped"
    
    def __init__(self, event_bus: EventBus, name: str):
        """
        Initialise le plugin de base avec un bus d'événements et un nom.
        
        Args:
            event_bus: Bus d'événements pour la communication
            name: Nom du plugin pour l'identification et le logging
        """
        self.event_bus = event_bus
        self.name = name
        self.is_active = False
        self.logger = logging.getLogger(f"plugin.{name}")
        self.metadata = {}
    
    async def publish_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        Publie les métadonnées sur le bus d'événements.
        
        Args:
            metadata: Métadonnées à publier
        """
        self.metadata = metadata
        await self.event_bus.publish("audio_metadata_updated", {
            "source": self.name,
            "metadata": metadata
        })
    
    async def publish_plugin_state(self, state: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Publie un état standardisé sur le bus d'événements.
        
        Args:
            state: État standardisé (STATE_INACTIVE, STATE_READY_TO_CONNECT, etc.)
            details: Détails supplémentaires à inclure
        """
        status_data = {
            "source": self.name,
            "plugin_state": state
        }
        
        if details:
            status_data.update(details)
            
        await self.publish_status(state, status_data)
        
    async def publish_status(self, status: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Publie un événement de statut sur le bus d'événements.
        
        Args:
            status: Statut à publier (playing, paused, stopped, etc.)
            details: Détails supplémentaires du statut
        """
        status_data = {
            "source": self.name,
            "status": status
        }
        
        if details:
            status_data.update(details)
            
        await self.event_bus.publish("audio_status_updated", status_data)