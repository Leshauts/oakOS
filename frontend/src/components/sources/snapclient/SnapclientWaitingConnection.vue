<template>
  <div class="snapclient-waiting-connection">
    <div class="waiting-header">
        <span class="status-indicator waiting" title="En attente"></span>
        <h3 class="waiting-title">En attente de connexion</h3>
    </div>

    <p class="instruction-text">Sélectionnez un serveur MacOS (Snapcast) disponible sur le réseau :</p>

    <div class="server-list-actions">
        <button @click="discover" class="action-button discover-button" :disabled="snapclientStore.isLoading" title="Rechercher les serveurs">
             <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
                <path d="M12 6.5c-3.79 0-7.17 2.13-8.82 5.5-1.65 3.37-1.65 7.63 0 11C4.83 20.87 8.21 23 12 23s7.17-2.13 8.82-5.5c1.65-3.37 1.65-7.63 0-11C19.17 8.63 15.79 6.5 12 6.5zm0 14c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z"/>
                <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5C21.27 7.61 17 4.5 12 4.5zm0 15c-3.86 0-7-3.14-7-7s3.14-7 7-7 7 3.14 7 7-3.14 7-7 7z"/>
                 <circle cx="12" cy="12" r="3.5"/> <!-- Refresh icon -->
                <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-8 3.58-8 8h2c0-3.31 2.69-6 6-6s6 2.69 6 6h2c0-1.93-.76-3.68-2.04-4.96L17.65 6.35z"/>
             </svg>
             <!-- Rafraîchir -->
        </button>
    </div>

    <div v-if="snapclientStore.isLoading && !snapclientStore.discoveredServers.length" class="loading-servers">
      <div class="loading-spinner small"></div> Recherche en cours...
    </div>

    <ul v-else-if="snapclientStore.discoveredServers.length > 0" class="server-list">
      <li v-for="server in snapclientStore.discoveredServers" :key="server.host" class="server-item">
        <span class="server-name">{{ server.name }} <span class="server-host-ip">({{ server.host }})</span></span>
        <button
          @click="connect(server.host)"
          class="action-button connect-button"
          :disabled="snapclientStore.isLoading"
          title="Se connecter à ce serveur"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
             <path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/> <!-- Power / connect icon -->
             <path d="M9 21.76V16h6v5.76c.81-.21 1.55-.6 2.2-.96V12H3v8.8c.65.36 1.39.75 2.2.96H9zM12 3.5l6 5.72V11h-4v-3H10v3H6V9.22L12 3.5z"/>
          </svg>
           <!-- Connecter -->
        </button>
      </li>
    </ul>

    <p v-else-if="!snapclientStore.isLoading" class="no-servers-found">
      Aucun serveur Snapcast trouvé sur le réseau. Assurez-vous qu'un serveur est lancé sur votre Mac (via `mac-snapserver.sh` par exemple) et réessayez.
    </p>

    <p v-if="connectError" class="error-message">{{ connectError }}</p>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useSnapclientStore } from '@/stores/snapclient';

const snapclientStore = useSnapclientStore();
const connectError = ref(null);

// Action de découverte
async function discover() {
  connectError.value = null; // Reset previous error
  console.log("SnapclientWaitingConnection: Découverte demandée.");
  try {
    await snapclientStore.discoverServers();
  } catch (err) {
    console.error("SnapclientWaitingConnection: Erreur de découverte:", err);
    // L'erreur est déjà dans le store, pas besoin de la dupliquer ici
  }
}

// Action de connexion
async function connect(host) {
  connectError.value = null;
  console.log(`SnapclientWaitingConnection: Connexion demandée à ${host}.`);
  try {
    await snapclientStore.connectToServer(host);
    // Le changement d'état sera géré par SnapclientDisplay via le store
  } catch (err) {
    console.error(`SnapclientWaitingConnection: Erreur de connexion à ${host}:`, err);
    connectError.value = err.message || `Impossible de se connecter à ${host}.`;
  }
}

// Lancer une découverte initiale au montage si la liste est vide
onMounted(() => {
    if (snapclientStore.discoveredServers.length === 0 && !snapclientStore.isLoading) {
        console.log("SnapclientWaitingConnection: Lancement découverte initiale.");
        discover();
    }
});

</script>

<style scoped>
.snapclient-waiting-connection {
  width: 100%;
  max-width: 500px;
  margin: 0 auto;
  padding: 1rem 0.5rem;
  text-align: center; /* Centrer le texte par défaut */
  background-color: #f9f9f9; /* Fond légèrement différent */
  border: 1px solid #eeeeee;
  border-radius: 8px;
}

.waiting-header {
    display: flex;
    align-items: center;
    justify-content: center; /* Centrer le titre */
    margin-bottom: 1rem;
    color: #555;
}

.status-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-right: 0.8rem;
  flex-shrink: 0;
}

.status-indicator.waiting {
  background-color: #FFC107; /* Jaune pour attente */
  border: 2px solid #ffe082;
}

.waiting-title {
    margin: 0;
    font-size: 1.2rem;
    font-weight: 500;
}

.instruction-text {
  font-size: 0.95rem;
  color: #666;
  margin-bottom: 1rem;
}

.server-list-actions {
    margin-bottom: 1rem;
    text-align: center; /* Centrer le bouton rafraîchir */
}

.loading-servers {
    display: flex;
    align-items: center;
    justify-content: center;
    color: #757575;
    padding: 1rem 0;
    font-size: 0.9rem;
}

.loading-spinner.small {
    width: 18px;
    height: 18px;
    border-width: 2px;
    margin-right: 0.5rem;
    border-top-color: #757575; /* Couleur adaptée */
}

.server-list {
  list-style: none;
  padding: 0;
  margin: 0;
  max-height: 250px; /* Limiter la hauteur et ajouter scroll si besoin */
  overflow-y: auto; /* Scroll vertical */
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background-color: #ffffff;
}

.server-item {
  display: flex;
  align-items: center;
  justify-content: space-between; /* Espace entre nom et bouton */
  padding: 0.6rem 0.8rem; /* Padding interne réduit */
  border-bottom: 1px solid #f0f0f0; /* Séparateur plus léger */
  text-align: left; /* Aligner le texte à gauche */
}

.server-item:last-child {
  border-bottom: none;
}

.server-name {
  font-weight: 500;
  color: #444;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-right: 0.5rem; /* Espace avant le bouton */
}
.server-host-ip {
    font-size: 0.8rem;
    color: #888;
    margin-left: 0.3rem;
}

.action-button {
  background-color: transparent;
  border: none;
  color: #757575;
  padding: 0.4rem; /* Padding réduit */
  cursor: pointer;
  border-radius: 50%;
  transition: background-color 0.2s, color 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.action-button:hover:not(:disabled) {
  background-color: #f0f0f0;
}

.discover-button {
    color: #1e88e5; /* Bleu pour découverte */
    padding: 0.6rem; /* Plus grand car seul */
    /* margin: 0 auto; */ /* Centré par son parent */
}
.discover-button:hover:not(:disabled) {
    background-color: #e3f2fd;
    color: #1565c0;
}

.connect-button {
  color: #4CAF50; /* Vert pour connexion */
}

.connect-button:hover:not(:disabled) {
  background-color: #e8f5e9; /* Fond vert pâle */
  color: #388E3C; /* Vert plus foncé */
}

.action-button:disabled {
  color: #bdbdbd;
  cursor: not-allowed;
}

.action-button svg {
    display: block;
}

.no-servers-found {
  color: #757575;
  font-style: italic;
  padding: 1.5rem 1rem; /* Plus d'espace */
  font-size: 0.9rem;
  background-color: #ffffff;
   border: 1px dashed #e0e0e0; /* Bordure pointillée */
   border-radius: 4px;
}

.error-message {
  color: #d32f2f;
  font-size: 0.85rem;
  text-align: center;
  margin-top: 1rem;
}

/* Animation pour le spinner */
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>