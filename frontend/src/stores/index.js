// frontend/src/stores/index.js
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import axios from 'axios';
import { useLibrespotStore } from './librespot';
import { useSnapclientStore } from './snapclient';
import { useStateStore } from './state';
import { useVolumeStore } from './volume';

export const useAudioStore = defineStore('audio', () => {
  // Sous-stores
  const librespotStore = useLibrespotStore();
  const snapclientStore = useSnapclientStore();
  const stateStore = useStateStore();
  const volumeStore = useVolumeStore();
  
  // État local du store principal
  const error = ref(null);
  
  // Proxys pour accéder rapidement aux états importants
  const currentState = computed(() => stateStore.currentState);
  const isTransitioning = computed(() => stateStore.isTransitioning);
  const volume = computed({
    get: () => volumeStore.volume,
    set: (value) => volumeStore.setVolume(value)
  });
  
  // Métadonnées actives (sélection en fonction de la source active)
  const metadata = computed(() => {
    if (currentState.value === 'librespot') {
      return librespotStore.metadata;
    } else if (currentState.value === 'macos') {
      return snapclientStore.deviceInfo;
    }
    return {};
  });
  
  // Proxys pour l'état de lecture
  const isPlaying = computed(() => {
    if (currentState.value === 'librespot') {
      return librespotStore.isPlaying;
    }
    return false;
  });
  
  const isDisconnected = computed(() => {
    if (currentState.value === 'librespot') {
      return librespotStore.isDisconnected;
    } else if (currentState.value === 'macos') {
      return !snapclientStore.isConnected;
    }
    return true;
  });
  
  // Labels pour l'UI
  const stateLabel = computed(() => {
    switch (currentState.value) {
      case 'librespot': return 'Spotify';
      case 'bluetooth': return 'Bluetooth';
      case 'macos': return 'MacOS';
      case 'webradio': return 'Web Radio';
      default: return 'Aucune source';
    }
  });
  
  // Récupération de l'état depuis l'API
  async function fetchState() {
    try {
      const response = await axios.get('/api/audio/state');
      stateStore.updateState(response.data.state, response.data.transitioning);
      
      // Mettre à jour le sous-store approprié
      if (response.data.state === 'librespot') {
        librespotStore.updateMetadata(response.data.metadata || {});
      } else if (response.data.state === 'macos') {
        // Pour snapclient, vérifier le statut actuel
        await snapclientStore.checkStatus();
      }
      
      // Mettre à jour le volume
      if (response.data.volume !== undefined) {
        volumeStore.setVolume(response.data.volume);
      }
      
      return response.data;
    } catch (err) {
      error.value = 'Erreur lors de la récupération de l\'état audio';
      console.error(error.value, err);
    }
  }
  
  // Changement de source
  async function changeSource(source) {
    try {
      error.value = null;
      stateStore.startTransition();
      const response = await axios.post(`/api/audio/source/${source}`);
      if (response.data.status === 'error') {
        throw new Error(response.data.message);
      }
      return true;
    } catch (err) {
      error.value = `Erreur lors du changement de source: ${err.message}`;
      console.error(error.value);
      return false;
    } finally {
      // L'état sera mis à jour via WebSocket
    }
  }
  
  // Méthode pour contrôler une source audio
  async function controlSource(source, command, data = {}) {
    try {
      error.value = null;
      console.log(`Envoi de la commande "${command}" à la source "${source}"`, data);
      
      // Déléguer au sous-store approprié
      if (source === 'librespot') {
        return await librespotStore.handleCommand(command, data);
      } else if (source === 'macos') {
        return await snapclientStore.handleCommand(command, data);
      }
      
      // Fallback à l'API générique
      const response = await axios.post(`/api/audio/control/${source}`, {
        command,
        data
      });
      
      if (response.data.status === 'error') {
        throw new Error(response.data.message);
      }
      
      return true;
    } catch (err) {
      error.value = `Erreur lors du contrôle de la source ${source}: ${err.message}`;
      console.error(error.value);
      return false;
    }
  }
  
  // Vérifier l'état de connexion pour la source active
  async function checkConnectionStatus() {
    if (currentState.value === 'librespot') {
      return await librespotStore.checkConnectionStatus();
    } else if (currentState.value === 'macos') {
      return await snapclientStore.checkStatus();
    }
    return false;
  }
  
  // Fonction pour la validité des métadonnées - pour compatibilité
  function hasValidMetadata(meta) {
    if (currentState.value === 'librespot') {
      return librespotStore.hasValidMetadata(meta);
    }
    return !!meta && Object.keys(meta).length > 0;
  }
  
  // Fonction pour effacer les métadonnées - pour compatibilité
  function clearMetadata() {
    if (currentState.value === 'librespot') {
      librespotStore.clearMetadata();
    } else if (currentState.value === 'macos') {
      snapclientStore.deviceInfo = {};
    }
  }
  
  // Mettre à jour les métadonnées d'après un statut - pour compatibilité
  function updateMetadataFromStatus(metadataFromStatus) {
    if (currentState.value === 'librespot') {
      librespotStore.updateMetadata(metadataFromStatus);
    } else if (currentState.value === 'macos' && metadataFromStatus) {
      snapclientStore.deviceInfo = { ...metadataFromStatus };
    }
  }
  
  // Traitement des événements WebSocket
  function handleWebSocketUpdate(eventType, data) {
    console.log(`WebSocket event received: ${eventType}`, data);
    
    // Traiter les événements d'état global
    if (eventType === 'audio_state_changed') {
      stateStore.updateState(data.current_state, data.transitioning);
      
      // Si l'état change à 'none', effacer les métadonnées
      if (data.current_state === 'none') {
        librespotStore.clearMetadata();
        snapclientStore.deviceInfo = {};
      }
    } 
    else if (eventType === 'volume_changed') {
      volumeStore.setVolume(data.volume);
    } 
    else if (eventType === 'audio_error') {
      error.value = data.error;
    } 
    else if (eventType === 'snapclient_connection_request') {
      // Router l'événement vers le store snapclient
      snapclientStore.handleEvent(eventType, data);
    }
    else {
      // Router les événements au store approprié
      if (data.source === 'librespot' || currentState.value === 'librespot') {
        librespotStore.handleEvent(eventType, data);
      } else if (data.source === 'snapclient' || currentState.value === 'macos') {
        snapclientStore.handleEvent(eventType, data);
      }
    }
  }
  
  return {
    // État
    currentState,
    isTransitioning,
    metadata,
    volume,
    error,
    isDisconnected,
    
    // Getters
    isPlaying,
    stateLabel,
    
    // Actions
    fetchState,
    changeSource,
    controlSource,
    handleWebSocketUpdate,
    checkConnectionStatus,
    
    // Fonctions de compatibilité avec l'ancien code
    hasValidMetadata,
    clearMetadata,
    updateMetadataFromStatus
  };
});