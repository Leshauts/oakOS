// frontend/src/stores/snapclient.js
/**
 * Store Pinia minimaliste pour la gestion de l'état de Snapclient.
 * Réagit uniquement à l'état fourni par le backend via /status et l'événement
 * WebSocket 'audio_status_updated'.
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import axios from 'axios';
import { useAudioStore } from '@/stores/index'; // Pour vérifier si la source est active

export const useSnapclientStore = defineStore('snapclient', () => {
    // Référence au store audio principal
    const audioStore = useAudioStore();

    // --- État Réactif ---
    const pluginState = ref('inactive'); // 'inactive', 'ready_to_connect', 'connected'
    const isActive = ref(false);      // Le plugin est-il sélectionné comme source audio ?
    const isConnected = ref(false);   // Le client est-il connecté à un serveur ?
    const host = ref(null);           // Hôte du serveur connecté
    const deviceName = ref(null);     // Nom du serveur connecté
    const discoveredServers = ref([]); // Liste des serveurs découverts [{ host, name, port }]
    const processRunning = ref(false); // Le processus snapclient tourne-t-il ? (info indicative)
    const isLoading = ref(false);     // Indicateur pour les appels API
    const error = ref(null);          // Stockage des erreurs API ou de logique

    // --- Getters Calculés ---
    const currentServer = computed(() => {
        if (isConnected.value && host.value) {
            return { name: deviceName.value, host: host.value };
        }
        return null;
    });

    // Indique si l'UI doit afficher l'état "connecté"
    const showConnectedState = computed(() => isActive.value && isConnected.value && pluginState.value === 'connected');
     // Indique si l'UI doit afficher l'état "en attente"
    const showWaitingState = computed(() => isActive.value && !isConnected.value && pluginState.value === 'ready_to_connect');

    // --- Actions ---

    /**
     * Met à jour l'état interne depuis les données reçues (API status ou WS event).
     * C'est la fonction centrale de mise à jour.
     * @param {object} statusData - Les données d'état reçues du backend.
     */
    function _updateState(statusData) {
        if (!statusData || statusData.source !== 'snapclient') {
            console.warn("Snapclient store: Données invalides reçues pour _updateState", statusData);
            return;
        }

        try {
            pluginState.value = statusData.plugin_state ?? 'inactive';
            isActive.value = statusData.is_active ?? false;
            isConnected.value = statusData.connected ?? false; // Utiliser 'connected' du backend
            host.value = statusData.host ?? null;
            deviceName.value = statusData.device_name ?? null;
            // S'assurer que la liste est toujours un tableau
            discoveredServers.value = Array.isArray(statusData.discovered_servers) ? statusData.discovered_servers : [];
            processRunning.value = statusData.process_running ?? false;

            // Effacer l'erreur si la mise à jour réussit
            error.value = null;

            // Log de l'état mis à jour (optionnel, utile pour debug)
            // console.debug('Snapclient store state updated:', {
            //     pluginState: pluginState.value,
            //     isActive: isActive.value,
            //     isConnected: isConnected.value,
            //     host: host.value,
            //     deviceName: deviceName.value,
            //     servers: discoveredServers.value.length,
            // });

        } catch (e) {
             console.error("Snapclient store: Erreur lors de la mise à jour de l'état:", e, "Data:", statusData);
             error.value = "Erreur interne lors de la mise à jour de l'état Snapclient.";
        }
    }

    /**
     * Récupère le statut actuel depuis l'API /status.
     * Utilise _updateState pour mettre à jour l'état interne.
     * @param {boolean} showLoading - Afficher l'indicateur de chargement global ?
     */
    async function fetchStatus(showLoading = true) {
        if (showLoading) isLoading.value = true;
        error.value = null; // Reset error before fetch
        try {
            console.debug("Snapclient store: Appel fetchStatus");
            const response = await axios.get('/api/snapclient/status');
            _updateState(response.data); // Mettre à jour l'état avec la réponse
            return response.data;
        } catch (err) {
            console.error('Snapclient store: Erreur fetchStatus:', err);
            error.value = err.response?.data?.detail || err.message || 'Erreur de communication avec le serveur.';
            // En cas d'erreur sévère, on pourrait réinitialiser certains états ?
            // Exemple : si erreur 500, on n'est probablement pas connecté
             if (err.response?.status >= 500) {
                 _updateState({ // Forcer un état de base
                     source: 'snapclient',
                     plugin_state: 'inactive', // Ou ready_to_connect si on sait que le plugin est actif
                     is_active: audioStore.currentState === 'snapclient', // Utiliser le store audio comme référence
                     connected: false,
                     host: null,
                     device_name: null,
                     discovered_servers: [],
                     process_running: false,
                 });
             }
            throw err; // Renvoyer l'erreur pour que l'appelant puisse réagir
        } finally {
            if (showLoading) isLoading.value = false;
        }
    }

    /**
     * Déclenche une découverte des serveurs via l'API.
     * Met à jour discoveredServers via _updateState si l'API retourne le statut.
     * (Actuellement, l'API discover retourne juste la liste, donc mise à jour manuelle)
     */
    async function discoverServers() {
        isLoading.value = true;
        error.value = null;
        try {
            console.debug("Snapclient store: Appel discoverServers");
            const response = await axios.post('/api/snapclient/discover');
            // L'API /discover retourne maintenant { servers: [...] }
            if (Array.isArray(response.data.servers)) {
                 discoveredServers.value = response.data.servers;
                 console.info(`Snapclient store: Découverte terminée, ${discoveredServers.value.length} serveurs trouvés.`);
            } else {
                 console.warn("Snapclient store: Réponse inattendue de /discover", response.data);
                 discoveredServers.value = [];
            }
             // Optionnel: rafraîchir l'état complet après la découverte
             // await fetchStatus(false);
            return discoveredServers.value; // Retourner la liste directement
        } catch (err) {
            console.error('Snapclient store: Erreur discoverServers:', err);
            error.value = err.response?.data?.detail || err.message || 'Erreur lors de la découverte des serveurs.';
            discoveredServers.value = []; // Vider la liste en cas d'erreur
            throw err;
        } finally {
            isLoading.value = false;
        }
    }

    /**
     * Se connecte à un serveur Snapcast via l'API.
     * Met à jour l'état complet via _updateState basé sur la réponse de l'API.
     * @param {string} serverHost - L'hôte du serveur auquel se connecter.
     */
    async function connectToServer(serverHost) {
        // Vérifier si on est déjà connecté à ce serveur pour éviter appel inutile
        if (isConnected.value && host.value === serverHost) {
             console.log(`Snapclient store: Déjà connecté à ${serverHost}.`);
             return { success: true, message: "Already connected." };
        }

        isLoading.value = true;
        error.value = null;
        try {
            console.info(`Snapclient store: Tentative de connexion à ${serverHost}`);
            const response = await axios.post('/api/snapclient/connect', { host: serverHost });
            // L'API connect retourne le nouveau statut complet en cas de succès
            _updateState(response.data);
            console.info(`Snapclient store: Connecté avec succès à ${deviceName.value} (${host.value})`);
            return response.data;
        } catch (err) {
            console.error(`Snapclient store: Erreur connexion à ${serverHost}:`, err);
            error.value = err.response?.data?.detail || err.message || `Erreur de connexion à ${serverHost}.`;
             // Si la connexion échoue, rafraîchir l'état pour être sûr
             await fetchStatus(false);
            throw err;
        } finally {
            isLoading.value = false;
        }
    }

    /**
     * Se déconnecte du serveur actuel via l'API.
     * Met à jour l'état complet via _updateState basé sur la réponse de l'API.
     */
    async function disconnectFromServer() {
        // Vérifier si on est déjà déconnecté
         if (!isConnected.value) {
             console.log("Snapclient store: Déjà déconnecté.");
             return { success: true, message: "Already disconnected." };
         }

        isLoading.value = true;
        error.value = null;
        const serverNameToLog = deviceName.value || host.value; // Pour le log
        try {
            console.info(`Snapclient store: Tentative de déconnexion de ${serverNameToLog}`);
            const response = await axios.post('/api/snapclient/disconnect');
            // L'API disconnect retourne le nouveau statut complet en cas de succès
            _updateState(response.data);
            console.info(`Snapclient store: Déconnecté avec succès de ${serverNameToLog}`);
            return response.data;
        } catch (err) {
            console.error(`Snapclient store: Erreur déconnexion de ${serverNameToLog}:`, err);
            error.value = err.response?.data?.detail || err.message || 'Erreur lors de la déconnexion.';
            // Même si l'API échoue, forcer un état déconnecté dans l'UI peut être une bonne idée
            // ou au moins rafraîchir pour obtenir l'état réel du backend.
            await fetchStatus(false);
            throw err;
        } finally {
            isLoading.value = false;
        }
    }

    /**
     * Réinitialise l'état du store à ses valeurs par défaut.
     * Typiquement appelé lors du changement de source audio.
     */
    function reset() {
        console.debug("Snapclient store: Réinitialisation de l'état.");
        pluginState.value = 'inactive';
        isActive.value = false;
        isConnected.value = false;
        host.value = null;
        deviceName.value = null;
        discoveredServers.value = [];
        processRunning.value = false;
        isLoading.value = false;
        error.value = null;
    }

    // --- Export ---
    return {
        // State properties
        pluginState,
        isActive,
        isConnected,
        host,
        deviceName,
        discoveredServers,
        processRunning,
        isLoading,
        error,

        // Getters
        currentServer,
        showConnectedState,
        showWaitingState,

        // Actions
        _updateState, // Exposer pour le listener WebSocket global
        fetchStatus,
        discoverServers,
        connectToServer,
        disconnectFromServer,
        reset,
    };
});