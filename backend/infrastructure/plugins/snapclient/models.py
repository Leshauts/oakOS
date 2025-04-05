# backend/infrastructure/plugins/snapclient/models.py
"""
Modèles de données pour le plugin Snapclient minimaliste.
"""
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class SnapclientServer:
    """
    Représente un serveur Snapcast découvert sur le réseau.
    Utilise field pour s'assurer que le port a une valeur par défaut.
    """
    host: str
    name: str
    port: int = field(default=1704)  # Port de contrôle Snapcast par défaut

    def to_dict(self) -> Dict[str, Any]:
        """
        Convertit le serveur en dictionnaire sérialisable.

        Returns:
            Dict[str, Any]: Représentation du serveur en dictionnaire.
        """
        return {
            "host": self.host,
            "name": self.name,
            "port": self.port
        }

    def __eq__(self, other):
        """Permet de comparer les serveurs par leur hôte."""
        if not isinstance(other, SnapclientServer):
            return NotImplemented
        return self.host == other.host

    def __hash__(self):
        """Permet d'utiliser les serveurs dans des sets basés sur l'hôte."""
        return hash(self.host)