# backend/presentation/api/dependencies.py
"""
Fonctions de dépendance pour les routes API FastAPI.
"""
from fastapi import Request, HTTPException, status

def get_plugin(source_id: str):
    """
    Fonction de dépendance FastAPI pour récupérer une instance de plugin.

    Args:
        source_id: L'identifiant unique du plugin (ex: "snapclient", "librespot").

    Returns:
        L'instance du plugin demandée.

    Raises:
        HTTPException(503): Si le plugin n'est pas trouvé ou non initialisé.
    """
    def dependency(request: Request):
        # Accéder au gestionnaire de plugins (ou à l'endroit où ils sont stockés)
        # Ceci est un exemple, adaptez-le à votre structure réelle.
        # Si vous stockez les plugins dans app.state.plugins:
        # plugin_manager = getattr(request.app.state, 'plugins', None)

        # Si vous avez un objet PluginManager dédié stocké dans app.state:
        plugin_manager = getattr(request.app.state, 'plugin_manager', None)

        if not plugin_manager:
             raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Plugin manager not available in application state."
            )

        # Récupérer le plugin spécifique
        plugin_instance = plugin_manager.get_plugin(source_id) # Assurez-vous que votre manager a cette méthode

        if not plugin_instance:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Plugin '{source_id}' not found or not initialized."
            )
        return plugin_instance
    return dependency

# Créer des dépendances spécifiques pour faciliter l'utilisation (optionnel mais pratique)
def get_snapclient_plugin_instance():
    """Dépendance spécifique pour obtenir le plugin Snapclient."""
    # Réutilise la fonction générique get_plugin
    return get_plugin("snapclient")

def get_librespot_plugin_instance():
    """Dépendance spécifique pour obtenir le plugin Librespot."""
     # Réutilise la fonction générique get_plugin
    return get_plugin("librespot") # Assurez-vous que l'ID est correct

# Ajoutez d'autres dépendances de plugin ici si nécessaire...