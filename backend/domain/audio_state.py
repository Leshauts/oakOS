# backend/domain/audio_state.py
"""
Modèle d'état unifié pour le système audio - Étendu pour l'equalizer.
"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any


class AudioSource(Enum):
    """Sources audio disponibles dans le système"""
    NONE = "none"
    LIBRESPOT = "librespot"
    BLUETOOTH = "bluetooth"
    ROC = "roc"
    WEBRADIO = "webradio"


class PluginState(Enum):
    """États opérationnels possibles pour un plugin"""
    INACTIVE = "inactive"      # Plugin arrêté
    READY = "ready"           # Plugin démarré, en attente de connexion
    CONNECTED = "connected"   # Plugin connecté et opérationnel
    ERROR = "error"          # Plugin en erreur


@dataclass
class SystemAudioState:
    """
    État complet du système audio combinant :
    - La source active
    - L'état opérationnel du plugin actif
    - Les métadonnées associées
    - L'état du routage audio
    - L'état de l'equalizer
    """
    active_source: AudioSource = AudioSource.NONE
    plugin_state: PluginState = PluginState.INACTIVE
    transitioning: bool = False
    metadata: Dict[str, Any] = None
    error: Optional[str] = None
    routing_mode: str = "multiroom"  # Mode de routage audio
    equalizer_enabled: bool = False  # Nouveau champ pour l'equalizer
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'état en dictionnaire pour la sérialisation"""
        return {
            "active_source": self.active_source.value,
            "plugin_state": self.plugin_state.value,
            "transitioning": self.transitioning,
            "metadata": self.metadata,
            "error": self.error,
            "routing_mode": self.routing_mode,
            "equalizer_enabled": self.equalizer_enabled
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SystemAudioState':
        """Crée un état à partir d'un dictionnaire"""
        return cls(
            active_source=AudioSource(data.get("active_source", "none")),
            plugin_state=PluginState(data.get("plugin_state", "inactive")),
            transitioning=data.get("transitioning", False),
            metadata=data.get("metadata", {}),
            error=data.get("error"),
            routing_mode=data.get("routing_mode", "multiroom"),
            equalizer_enabled=data.get("equalizer_enabled", False)
        )