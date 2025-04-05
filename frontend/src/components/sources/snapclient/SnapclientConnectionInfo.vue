<template>
  <div class="snapclient-connection-info">
    <div class="connection-card">
      <span class="status-indicator connected" title="Connecté"></span>
      <div class="server-details">
        <h3 class="server-name">{{ formattedServerName }}</h3>
        <p class="server-host">{{ snapclientStore.host }}</p>
      </div>
      <button
        @click="disconnect"
        class="action-button disconnect-button"
        :disabled="snapclientStore.isLoading"
        title="Se déconnecter du serveur"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z"/>
           <path d="M10.59 12L6 7.41 7.41 6 12 10.59 16.59 6 18 7.41 13.41 12 18 16.59 16.59 18 12 13.41 7.41 18 6 16.59z"/> <!-- Simple X -->
        </svg>
        <!-- Déconnexion -->
      </button>
    </div>
     <!-- Afficher une erreur spécifique à la déconnexion si nécessaire -->
     <p v-if="disconnectError" class="error-message">{{ disconnectError }}</p>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import { useSnapclientStore } from '@/stores/snapclient';

const snapclientStore = useSnapclientStore();
const disconnectError = ref(null); // Erreur spécifique à cette action

// Formate le nom du serveur pour l'affichage
const formattedServerName = computed(() => {
  const name = snapclientStore.deviceName || 'Serveur Inconnu';
  // Capitaliser la première lettre, etc.
  return name.charAt(0).toUpperCase() + name.slice(1);
});

// Action de déconnexion
async function disconnect() {
  disconnectError.value = null; // Reset error
  console.log("SnapclientConnectionInfo: Déconnexion demandée.");
  try {
    await snapclientStore.disconnectFromServer();
    // Pas besoin de faire autre chose, l'état sera mis à jour par fetchStatus ou WS
  } catch (err) {
    console.error('SnapclientConnectionInfo: Erreur de déconnexion:', err);
    disconnectError.value = err.message || "La déconnexion a échoué.";
  }
}

</script>

<style scoped>
.snapclient-connection-info {
  width: 100%;
  max-width: 450px; /* Largeur max pour la carte */
  margin: 0 auto; /* Centrer */
  padding: 0 0.5rem; /* Léger padding horizontal */
}

.connection-card {
  display: flex;
  align-items: center;
  background-color: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 0.8rem 1rem; /* Padding interne */
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
  transition: box-shadow 0.3s ease;
}

.connection-card:hover {
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
}

.status-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-right: 1rem;
  flex-shrink: 0; /* Empêche le rétrécissement */
}

.status-indicator.connected {
  background-color: #4CAF50; /* Vert pour connecté */
  border: 2px solid #a5d6a7;
}

.server-details {
  flex-grow: 1; /* Prend l'espace disponible */
  min-width: 0; /* Permet au texte de passer à la ligne */
}

.server-name {
  margin: 0 0 0.1rem 0;
  font-size: 1.1rem; /* Taille légèrement augmentée */
  font-weight: 600; /* Un peu plus gras */
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis; /* Ajoute ... si trop long */
}

.server-host {
  margin: 0;
  font-size: 0.85rem;
  color: #757575; /* Gris plus doux */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.action-button {
  background-color: transparent;
  border: none;
  color: #757575;
  padding: 0.5rem;
  margin-left: 0.5rem; /* Espace par rapport aux détails */
  cursor: pointer;
  border-radius: 50%;
  transition: background-color 0.2s, color 0.2s;
  display: flex; /* Pour centrer l'icône */
  align-items: center;
  justify-content: center;
  flex-shrink: 0; /* Empêche le rétrécissement */
}

.action-button:hover:not(:disabled) {
  background-color: #f5f5f5; /* Léger fond au survol */
}

.disconnect-button {
  color: #e57373; /* Rouge doux pour déconnexion */
}

.disconnect-button:hover:not(:disabled) {
  background-color: #ffebee; /* Fond rouge très pâle */
  color: #d32f2f; /* Rouge plus foncé */
}

.action-button:disabled {
  color: #bdbdbd; /* Gris désactivé */
  cursor: not-allowed;
}

.action-button svg {
    display: block; /* Empêche espace sous l'icône */
}

.error-message {
  color: #d32f2f;
  font-size: 0.85rem;
  text-align: center;
  margin-top: 0.8rem;
}
</style>