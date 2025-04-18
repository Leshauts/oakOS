<template>
  <div class="home-view">
    <div class="status-panel">
      <h1>oakOS</h1>

      <div class="current-state">
        <h2>Source actuelle: {{ audioStore.stateLabel }}</h2>
        <span v-if="audioStore.isTransitioning" class="transitioning-badge">Transition en cours...</span>
      </div>

      <div class="volume-control">
        <h3>Volume: {{ audioStore.volume }}%</h3>
        <input type="range" min="0" max="100" v-model.number="audioStore.volume" class="volume-slider">
      </div>

      <div class="error-message" v-if="audioStore.error">
        {{ audioStore.error }}
      </div>
    </div>

    <div class="source-buttons">
      <button @click="changeSource('librespot')"
        :disabled="audioStore.isTransitioning || audioStore.currentState === 'librespot'" class="source-button spotify">
        Spotify
      </button>

      <button @click="changeSource('bluetooth')"
        :disabled="audioStore.isTransitioning || audioStore.currentState === 'bluetooth'"
        class="source-button bluetooth">
        Bluetooth
      </button>

      <button @click="changeSource('macos')"
        :disabled="audioStore.isTransitioning || audioStore.currentState === 'macos'" class="source-button macos">
        MacOS
      </button>

      <button @click="changeSource('webradio')"
        :disabled="audioStore.isTransitioning || audioStore.currentState === 'webradio'" class="source-button webradio">
        Web Radio
      </button>
    </div>

    <!-- Affichage conditionnel direct des composants sources -->
    <template v-if="audioStore.currentState !== 'none'">
      <LibrespotDisplay v-if="audioStore.currentState === 'librespot'" />
      <SnapclientComponent v-else-if="audioStore.currentState === 'macos'" />
      <!-- Autres sources peuvent être ajoutées ici -->
      <div v-else class="no-source-error">
        <h2>Source non disponible</h2>
        <p>La source audio "{{ audioStore.currentState }}" n'est pas disponible ou n'est pas encore implémentée.</p>
      </div>
    </template>
  </div>
</template>

<script setup>
import { onMounted } from 'vue';
import { useAudioStore } from '@/stores/index';
import { useSnapclientStore } from '@/stores/snapclient';
import useWebSocket from '@/services/websocket';

// Import direct des composants spécifiques aux sources
import LibrespotDisplay from '@/components/sources/librespot/LibrespotDisplay.vue';
import SnapclientComponent from '@/components/sources/snapclient/SnapclientComponent.vue';

const audioStore = useAudioStore();
const snapclientStore = useSnapclientStore();
const { on } = useWebSocket();

// Changer la source audio
async function changeSource(source) {
  await audioStore.changeSource(source);
}

// Initialiser les données au montage du composant
onMounted(async () => {
  // Récupérer l'état initial
  await audioStore.fetchState();

  // S'abonner aux événements WebSocket standard
  on('audio_state_changed', (data) => {
    audioStore.handleWebSocketUpdate('audio_state_changed', data);
  });

  on('volume_changed', (data) => {
    audioStore.handleWebSocketUpdate('volume_changed', data);
  });

  on('audio_error', (data) => {
    audioStore.handleWebSocketUpdate('audio_error', data);
  });

  on('audio_metadata_updated', (data) => {
    audioStore.handleWebSocketUpdate('audio_metadata_updated', data);
  });

  on('audio_status_updated', (data) => {
    audioStore.handleWebSocketUpdate('audio_status_updated', data);
  });

  on('audio_seek', (data) => {
    audioStore.handleWebSocketUpdate('audio_seek', data);
  });

  // Événements spécifiques à Snapclient
  on('snapclient_connection_request', (data) => {
    audioStore.handleWebSocketUpdate('snapclient_connection_request', data);
  });

  on('snapclient_connection_rejected', (data) => {
    audioStore.handleWebSocketUpdate('snapclient_connection_rejected', data);
  });

  on('snapclient_monitor_connected', (data) => {
    console.log("Moniteur Snapclient connecté:", data);
    // Marquer comme connecté si la source active est snapclient
    if (audioStore.currentState === 'macos') {
      // Rafraîchir le statut pour mettre à jour l'interface
      snapclientStore.fetchStatus();
    }
  });

  on('snapclient_monitor_disconnected', (data) => {
    console.log("Moniteur Snapclient déconnecté:", data);
    // Marquer comme déconnecté si la source active est snapclient
    if (audioStore.currentState === 'macos') {
      // Mise à jour immédiate de l'état dans le store
      snapclientStore.updateFromWebSocketEvent('snapclient_monitor_disconnected', data);
    }
  });

  on('snapclient_server_event', (data) => {
    console.log("Événement serveur Snapclient:", data);
    // Traiter les événements spécifiques au serveur
    if (audioStore.currentState === 'macos') {
      // Analyser et mettre à jour le store si nécessaire
    }
  });
  
  on('snapclient_server_disappeared', (data) => {
    console.log("Serveur Snapclient disparu:", data);
    if (audioStore.currentState === 'macos') {
      snapclientStore.updateFromWebSocketEvent('snapclient_server_disappeared', data);
    }
  });
});
</script>

<style scoped>
.home-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 20px;
}

.status-panel {
  margin-bottom: 2rem;
}

h1 {
  font-size: 2.5rem;
  margin-bottom: 1rem;
}

.current-state {
  display: flex;
  align-items: center;
  margin-bottom: 1.5rem;
}

.transitioning-badge {
  background-color: #ff9800;
  color: white;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  margin-left: 1rem;
  font-size: 0.8rem;
}

.volume-control {
  margin-bottom: 1.5rem;
}

.volume-slider {
  width: 100%;
  max-width: 400px;
}

.error-message {
  background-color: #f44336;
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  margin-bottom: 1rem;
}

.source-buttons {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}

.source-button {
  background-color: #1976d2;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 1rem;
  font-size: 1.2rem;
  cursor: pointer;
  transition: background-color 0.3s;
}

.source-button:hover:not(:disabled) {
  background-color: #1565c0;
}

.source-button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

/* Couleurs spécifiques à chaque source */
.spotify {
  background-color: #1DB954;
}

.bluetooth {
  background-color: #0082FC;
}

.macos {
  background-color: #7D7D7D;
}

.webradio {
  background-color: #FF5722;
}

.no-source-error {
  text-align: center;
  padding: 2rem;
  background-color: #ffebee;
  border: 1px solid #ffcdd2;
  border-radius: 8px;
  margin: 0 auto;
  max-width: 600px;
}
</style>