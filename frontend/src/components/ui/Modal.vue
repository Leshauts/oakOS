<!-- frontend/src/components/ui/Modal.vue -->
<template>
  <div v-if="isVisible" ref="modalOverlay" class="modal-overlay" :class="{ 'fixed-height': heightMode === 'fixed' }"
    @click.self="handleOverlayClick">

    <div ref="modalContainer" class="modal-container" :class="{ 'fixed-height': heightMode === 'fixed' }">
      <IconButtonFloating ref="closeButton" class="close-btn-position" icon-name="close" aria-label="Fermer"
        @click="close" />

      <!-- Contenu -->
      <div ref="modalContent" class="modal-content" @pointerdown="handlePointerDown" @pointermove="handlePointerMove"
        @pointerup="handlePointerUp" @pointercancel="handlePointerUp">
        <slot></slot>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue';
import IconButtonFloating from './IconButtonFloating.vue';

const props = defineProps({
  isOpen: {
    type: Boolean,
    required: true
  },
  closeOnOverlay: {
    type: Boolean,
    default: true
  },
  heightMode: {
    type: String,
    default: 'auto', // 'auto' pour multiroom, 'fixed' pour equalizer
    validator: (value) => ['auto', 'fixed'].includes(value)
  }
});

const emit = defineEmits(['close']);

// Références aux éléments de la modal
const modalContent = ref(null);
const modalContainer = ref(null);
const modalOverlay = ref(null);
const closeButton = ref(null);

// État d'animation
const isVisible = ref(false);
const isAnimating = ref(false);

// Variables pour annuler les timeouts en cours
let animationTimeouts = [];

// Fonction utilitaire pour nettoyer tous les timeouts
function clearAllTimeouts() {
  animationTimeouts.forEach(timeout => clearTimeout(timeout));
  animationTimeouts = [];
}

const ANIMATION_TIMINGS = {
  // Délais d'ouverture
  overlayDelay: 0,
  containerDelay: 100,
  closeButtonDelay: 600,

  // Durées individuelles d'ouverture
  overlayDuration: 400,
  closeButtonDuration: 400,

  // Délais de fermeture
  closeOverlayDelay: 0,
  closeContainerDelay: 0,
  closeButtonDelayOut: 0,

  // Durées individuelles de fermeture
  closeOverlayDuration: 300,
  closeContainerDuration: 200,
  closeButtonDurationOut: 200
};

// Variables pour le pointer scroll
let isDragging = false;
let startY = 0;
let startScrollTop = 0;
let pointerId = null;
let hasMoved = false;

function close() {
  emit('close');
}

function handleOverlayClick() {
  if (props.closeOnOverlay) {
    close();
  }
}

// === ANIMATIONS ===
async function openModal() {
  clearAllTimeouts();

  isAnimating.value = true;
  isVisible.value = true;

  await nextTick();

  if (!modalContainer.value || !modalOverlay.value || !closeButton.value) return;

  // État initial overlay (invisible)
  modalOverlay.value.style.transition = 'none';
  modalOverlay.value.style.opacity = '0';

  // État initial container (invisible et position plus basse comme le dock)
  modalContainer.value.style.transition = 'none';
  modalContainer.value.style.opacity = '0';
  modalContainer.value.style.transform = 'translateY(80px) scale(0.85)';

  // État initial close button (invisible et position haute)
  closeButton.value.$el.style.transition = 'none';
  closeButton.value.$el.style.opacity = '0';
  closeButton.value.$el.style.transform = 'translateX(-50%) translateY(-24px)';

  // Forcer le reflow
  modalContainer.value.offsetHeight;

  // Animation d'entrée overlay (immédiate)
  const overlayTimeout = setTimeout(() => {
    if (!modalOverlay.value) return;
    modalOverlay.value.style.transition = `opacity ${ANIMATION_TIMINGS.overlayDuration}ms ease-out`;
    modalOverlay.value.style.opacity = '1';
  }, ANIMATION_TIMINGS.overlayDelay);
  animationTimeouts.push(overlayTimeout);

  // Animation d'entrée container (utilise --transition-spring comme le dock)
  const containerTimeout = setTimeout(() => {
    if (!modalContainer.value) return;
    modalContainer.value.style.transition = 'transform var(--transition-spring), opacity 400ms ease-out';
    modalContainer.value.style.opacity = '1';
    modalContainer.value.style.transform = 'translateY(0) scale(1)';
  }, ANIMATION_TIMINGS.containerDelay);
  animationTimeouts.push(containerTimeout);

  // Animation retardée du close button (utilise --transition-spring)
  const closeButtonTimeout = setTimeout(() => {
    if (!closeButton.value || !closeButton.value.$el) return;
    closeButton.value.$el.style.transition = `transform var(--transition-spring), opacity ${ANIMATION_TIMINGS.closeButtonDuration}ms ease-out`;
    closeButton.value.$el.style.opacity = '1';
    closeButton.value.$el.style.transform = 'translateX(-50%) translateY(0)';
  }, ANIMATION_TIMINGS.closeButtonDelay);
  animationTimeouts.push(closeButtonTimeout);

  // Attendre la fin de l'animation
  const totalDuration = Math.max(
    ANIMATION_TIMINGS.closeButtonDelay + ANIMATION_TIMINGS.closeButtonDuration,
    ANIMATION_TIMINGS.containerDelay + 600, // Durée approximative de --transition-spring
    ANIMATION_TIMINGS.overlayDelay + ANIMATION_TIMINGS.overlayDuration
  );

  const finalTimeout = setTimeout(() => {
    isAnimating.value = false;
  }, totalDuration);
  animationTimeouts.push(finalTimeout);
}

async function closeModal() {
  clearAllTimeouts();

  isAnimating.value = true;

  if (!modalContainer.value || !modalOverlay.value || !closeButton.value) return;

  // Animation de sortie avec ease-out pour fermeture
  const overlayCloseTimeout = setTimeout(() => {
    if (!modalOverlay.value) return;
    modalOverlay.value.style.transition = `opacity ${ANIMATION_TIMINGS.closeOverlayDuration}ms ease-out`;
    modalOverlay.value.style.opacity = '0';
  }, ANIMATION_TIMINGS.closeOverlayDelay);
  animationTimeouts.push(overlayCloseTimeout);

  const containerCloseTimeout = setTimeout(() => {
    if (!modalContainer.value) return;
    modalContainer.value.style.transition = `transform ${ANIMATION_TIMINGS.closeContainerDuration}ms ease-out, opacity ${ANIMATION_TIMINGS.closeContainerDuration}ms ease-out`;
    modalContainer.value.style.opacity = '0';
    modalContainer.value.style.transform = 'translateY(var(--space-08)) scale(0.95)';
  }, ANIMATION_TIMINGS.closeContainerDelay);
  animationTimeouts.push(containerCloseTimeout);

  const closeButtonCloseTimeout = setTimeout(() => {
    if (!closeButton.value || !closeButton.value.$el) return;
    closeButton.value.$el.style.transition = `opacity ${ANIMATION_TIMINGS.closeButtonDurationOut}ms ease-out`;
    closeButton.value.$el.style.opacity = '0';
    // Pas de translateY - garde juste la position horizontale
    closeButton.value.$el.style.transform = 'translateX(-50%)';
  }, ANIMATION_TIMINGS.closeButtonDelayOut);
  animationTimeouts.push(closeButtonCloseTimeout);

  // Attendre la fin de l'animation
  const totalCloseDuration = Math.max(
    ANIMATION_TIMINGS.closeOverlayDelay + ANIMATION_TIMINGS.closeOverlayDuration,
    ANIMATION_TIMINGS.closeContainerDelay + ANIMATION_TIMINGS.closeContainerDuration,
    ANIMATION_TIMINGS.closeButtonDelayOut + ANIMATION_TIMINGS.closeButtonDurationOut
  );

  const finalCloseTimeout = setTimeout(() => {
    isVisible.value = false;
    isAnimating.value = false;
  }, totalCloseDuration);
  animationTimeouts.push(finalCloseTimeout);
}

// Gestion du pointer scroll
function handlePointerDown(event) {
  if (!modalContent.value) return;

  // Exclure les sliders et autres contrôles interactifs
  const isSlider = event.target.closest('input[type="range"]');
  const isButton = event.target.closest('button');
  const isInput = event.target.closest('input, select, textarea');

  if (isSlider || isButton || isInput) {
    return;
  }

  isDragging = true;
  hasMoved = false;
  pointerId = event.pointerId;
  startY = event.clientY;
  startScrollTop = modalContent.value.scrollTop;
}

function handlePointerMove(event) {
  if (!isDragging || event.pointerId !== pointerId || !modalContent.value) return;

  const deltaY = Math.abs(startY - event.clientY);

  if (deltaY > 5) {
    hasMoved = true;

    if (!modalContent.value.hasPointerCapture(event.pointerId)) {
      modalContent.value.setPointerCapture(event.pointerId);
    }

    event.preventDefault();

    const scrollDelta = startY - event.clientY;
    modalContent.value.scrollTop = startScrollTop + scrollDelta;
  }
}

function handlePointerUp(event) {
  if (event.pointerId === pointerId) {
    isDragging = false;
    pointerId = null;
    hasMoved = false;

    if (modalContent.value && modalContent.value.hasPointerCapture(event.pointerId)) {
      modalContent.value.releasePointerCapture(event.pointerId);
    }
  }
}

// Gestion de l'échappement
function handleKeydown(event) {
  if (event.key === 'Escape' && props.isOpen) {
    close();
  }
}

// Bloquer le scroll du body quand modal ouverte
function toggleBodyScroll(isOpen) {
  if (isOpen) {
    document.body.style.overflow = 'hidden';
  } else {
    document.body.style.overflow = '';
  }
}

// Watcher pour les animations
watch(() => props.isOpen, async (newValue) => {
  if (newValue) {
    toggleBodyScroll(true);
    await openModal();
  } else {
    await closeModal();
    toggleBodyScroll(false);
  }
});

onMounted(() => {
  document.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown);
  document.body.style.overflow = '';
  clearAllTimeouts();
});
</script>

<style scoped>
::-webkit-scrollbar {
  display: none;
}

/* Overlay - comportement par défaut (auto) */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--color-background-contrast-64);
  backdrop-filter: blur(32px);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  z-index: 1000;
  padding: 48px var(--space-04) var(--space-07) var(--space-04);
  /* État initial pour l'animation */
  opacity: 0;
}

/* Overlay mode fixed (equalizer) */
.modal-overlay.fixed-height {
  align-items: center;
}

/* Wrapper pour contenir modal-container et close button */
.modal-wrapper {
  position: relative;
  display: flex;
  justify-content: center;
  width: 100%;
  max-width: 700px;
}

/* Container - comportement par défaut (auto) */
.modal-container {
  position: relative;
  background: var(--color-background-neutral-50);
  border-radius: var(--radius-06);
  width: 100%;
  max-width: 680px;
  max-height: 100%;
  display: flex;
  flex-direction: column;
  /* État initial pour l'animation - OPTIM : valeurs similaires au dock */
  opacity: 0;
}

.modal-container::before {
  content: '';
  position: absolute;
  inset: 0;
  padding: 2px;
  opacity: 0.8;
  background: var(--stroke-glass);
  border-radius: var(--radius-06);
  -webkit-mask:
    linear-gradient(#000 0 0) content-box,
    linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  z-index: -1;
  pointer-events: none;
}

/* Container mode fixed (equalizer) */
.modal-container.fixed-height {
  height: 100%;
}

/* Positionnement du bouton close - DESKTOP : en haut à droite à l'extérieur du modal-container */
.close-btn-position {
  position: absolute;
  top: 0;
  right: calc(-96px - var(--space-04));
  opacity: 0;
  transform: translateY(-24px);
}

/* Contenu - comportement par défaut (auto) */
.modal-content {
  overflow-y: auto;
  padding: var(--space-04);
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-radius: var(--radius-06);
  /* Configuration pour PointerEvents - permet le scroll vertical seulement */
  touch-action: pan-y;
}

/* Contenu mode fixed (equalizer) */
.modal-container.fixed-height .modal-content {
  flex: 1;
  height: 100%;
}

/* Responsive - MOBILE : bouton centré en haut */
@media (max-aspect-ratio: 4/3) {
  ::-webkit-scrollbar {
    display: none;
  }

  .modal-wrapper {
    width: 100%;
    max-width: none;
  }

  .close-btn-position {
    position: fixed;
    top: calc(-48px - var(--space-04));
    left: 50%;
    transform: translateX(-50%) translateY(-24px);
  }

  .modal-overlay,
  .modal-overlay.fixed-height {
    align-items: flex-start;
    padding: 80px var(--space-02) var(--space-02) var(--space-02);
  }

  .modal-container {
    max-width: none;
  }

  .modal-container.fixed-height {
    height: min-content;
  }
}

.ios-app .modal-overlay,
.ios-app .modal-overlay.fixed-height {
  padding: 112px var(--space-02) var(--space-02) var(--space-02);
}

</style>