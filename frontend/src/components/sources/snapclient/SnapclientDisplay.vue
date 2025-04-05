<template>
  <div class="snapclient-display">
    <!-- État de chargement initial (uniquement si la source est active) -->
    <div v-if="audioStore.currentState === 'snapclient' && initialLoading" class="loading-state">
      <div class="loading-spinner"></div>
      <p>Chargement Snapclient...</p>
    </div>

    <!-- État d'erreur persistant -->
    <div v-else-if="snapclientStore.error" class="error-state">
      <h3>Erreur Snapclient</h3>
      <p>{{ snapclientStore.error }}</p>
      <button @click="retryFetchStatus" class="retry-button" :disabled="snapclientStore.isLoading">
        Réessayer
      </button>
    </div>

    <!-- États normaux (seulement si la source est active) -->
    <template v-else-if="audioStore.currentState === 'snapclient' && snapclientStore.isActive">
      <!-- Afficher l'état connecté -->
      <SnapclientConnectionInfo v-if="snapclientStore.showConnectedState" />
      <!-- Afficher l'état en attente -->
      <SnapclientWaitingConnection v-else-if="snapclientStore.showWaitingState" />
       <!-- Fallback si aucun état ne correspond (ne devrait pas arriver) -->
      <div v-else class="info-state">
        <p>État Snapclient indéterminé ({{ snapclientStore.pluginState }}).</p>
         <button @click="retryFetchStatus" class="retry-button" :disabled="snapclientStore.isLoading">
            Rafraîchir
        </button>
      </div>
    </template>

     <!-- Message si la source n'est pas active -->
    <div v-else class="info-state">
        <p>Sélectionnez la source "MacOS (Snapcast)" pour l'activer.</p>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue';
import { useAudioStore } from '@/stores/index';
import { useSnapclientStore } from '@/stores/snapclient';
import SnapclientWaitingConnection from './SnapclientWaitingConnection.vue';
import SnapclientConnectionInfo from './SnapclientConnectionInfo.vue';
import useWebSocket from '@/services/websocket'; // Pour écouter les mises à jour

// Stores
const audioStore = useAudioStore();
const snapclientStore = useSnapclientStore();

// Service WebSocket
const { on } = useWebSocket();

// État local
const initialLoading = ref(false);
let unsubscribeAudioStatus = null;

// --- Fonctions ---

async function initializeSource() {
    if (audioStore.currentState === 'snapclient') {
        console.log("SnapclientDisplay: Initialisation car la source MacOS est active.");
        initialLoading.value = true;
        snapclientStore.error = null; // Reset error on init
        try {
            await snapclientStore.fetchStatus(false); // Ne pas montrer le loader global ici
        } catch (err) {
            console.error("SnapclientDisplay: Erreur lors de l'initialisation", err);
            // L'erreur est déjà dans snapclientStore.error
        } finally {
            initialLoading.value = false;
        }
    } else {
         // Si la source n'est pas active, s'assurer que le store est reset
         // snapclientStore.reset(); // Déplacé dans le watcher audioStore.currentState
         console.log("SnapclientDisplay: Initialisation ignorée, source non active.");
    }
}

async function retryFetchStatus() {
    console.log("SnapclientDisplay: Tentative de rechargement du statut...");
    initialLoading.value = true; // Montrer le loader local
    await initializeSource(); // Réutilise la logique d'initialisation
}

// --- Watchers ---

// Surveiller le changement de source audio
watch(() => audioStore.currentState, (newState, oldState) => {
    console.log(`SnapclientDisplay: Changement de source audio de ${oldState} vers ${newState}`);
    if (newState === 'snapclient') {
        // Initialiser quand on active la source
        initializeSource();
    } else if (oldState === 'snapclient') {
        // Nettoyer quand on quitte la source
        console.log("SnapclientDisplay: Nettoyage de l'état Snapclient car source désactivée.");
        snapclientStore.reset(); // Réinitialiser le store Snapclient
    }
}, { immediate: false }); // Ne pas lancer à la création, on le fait dans onMounted

// --- Cycle de vie ---

onMounted(() => {
    console.log("SnapclientDisplay: Composant monté.");
    // Initialisation si la source est déjà active au montage
    initializeSource();

    // S'abonner aux mises à jour d'état globales via WebSocket
    unsubscribeAudioStatus = on('audio_status_updated', (data) => {
        if (data.source === 'snapclient') {
            console.log("SnapclientDisplay: Mise à jour reçue via WebSocket", data.plugin_state);
            // Utiliser l'action du store pour mettre à jour l'état
            snapclientStore._updateState(data);
        }
    });
});

onUnmounted(() => {
    console.log("SnapclientDisplay: Composant démonté.");
    // Se désabonner des événements WebSocket
    if (unsubscribeAudioStatus) {
        unsubscribeAudioStatus();
        unsubscribeAudioStatus = null;
        console.log("SnapclientDisplay: Désabonné de 'audio_status_updated'.");
    }
     // Optionnel: reset le store si on quitte complètement la vue ?
     // Non, le watcher sur currentState s'en occupe mieux.
});

</script>

<style scoped>
.snapclient-display {
  width: 100%;
  padding: 1rem 0; /* Moins de padding latéral par défaut */
  display: flex;
  flex-direction: column;
  align-items: center;
}

.loading-state, .error-state, .info-state {
  text-align: center;
  padding: 1rem; /* Réduit le padding */
  margin: 1rem auto;
  max-width: 500px;
  width: 90%; /* Utiliser un pourcentage pour la largeur */
  border-radius: 8px; /* Bords arrondis */
}

.loading-state {
    color: #555;
}

.loading-spinner {
  width: 30px; /* Réduit la taille */
  height: 30px;
  margin: 0 auto 0.8rem; /* Réduit la marge */
  border: 3px solid rgba(0, 0, 0, 0.1);
  border-radius: 50%;
  border-top-color: #3498db; /* Garder la couleur */
  animation: spin 1s linear infinite;
}

.error-state {
  background-color: #ffebee;
  border: 1px solid #e57373; /* Couleur de bordure plus douce */
  color: #c62828; /* Texte d'erreur plus foncé */
}

.info-state {
    background-color: #e3f2fd;
    border: 1px solid #90caf9;
    color: #1e88e5;
}

.retry-button {
  background-color: #2196F3;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 8px 16px;
  cursor: pointer;
  margin-top: 0.8rem; /* Réduit la marge */
  transition: background-color 0.2s, box-shadow 0.2s;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.retry-button:hover:not(:disabled) {
  background-color: #1976D2;
   box-shadow: 0 4px 8px rgba(0,0,0,0.15);
}

.retry-button:disabled {
  background-color: #90a4ae; /* Couleur désactivée plus claire */
  cursor: not-allowed;
   box-shadow: none;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>