# backend/config/container.py
"""
Conteneur d'injection de dépendances pour l'application.
"""
from dependency_injector import containers, providers
from backend.application.event_bus import EventBus
from backend.infrastructure.state.state_machine import AudioStateMachine
from backend.infrastructure.plugins.librespot import LibrespotPlugin
from backend.infrastructure.plugins.snapclient import SnapclientPlugin
from backend.domain.audio import AudioState


class Container(containers.DeclarativeContainer):
    """Conteneur d'injection de dépendances pour l'application oakOS"""
    
    config = providers.Configuration()
    
    # Services centraux
    event_bus = providers.Singleton(EventBus)
    
    # Gestionnaires d'état
    audio_state_machine = providers.Singleton(
        AudioStateMachine,
        event_bus=event_bus
    )
    
    # Plugins audio
    librespot_plugin = providers.Singleton(
        LibrespotPlugin,
        event_bus=event_bus,
        config=providers.Dict({
            "config_path": "~/.config/go-librespot/config.yml",
            "executable_path": "~/oakOS/go-librespot/go-librespot",
            "polling_interval": 1.0
        })
    )
    
    # Plugin Snapclient (MacOS via Snapcast)
    snapclient_plugin = providers.Singleton(
        SnapclientPlugin,
        event_bus=event_bus,
        config=providers.Dict({
            "executable_path": "/usr/bin/snapclient",
            "polling_interval": 5.0,
            "auto_discover": True, 
            "auto_connect": True
        })
    )


# Création d'une instance du conteneur
container = Container()