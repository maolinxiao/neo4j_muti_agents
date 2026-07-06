<template>
  <div class="scroll-progress" :style="{ transform: `scaleX(${progress})` }" aria-hidden="true" />
</template>

<script setup>
import { onMounted, onUnmounted, ref } from "vue";

import { getLenis } from "../../composables/useSmoothScroll";

const progress = ref(0);
let rafId = null;

const tick = () => {
  const lenis = getLenis();
  if (lenis) {
    progress.value = lenis.progress;
  } else {
    const doc = document.documentElement;
    const max = doc.scrollHeight - doc.clientHeight;
    progress.value = max > 0 ? window.scrollY / max : 0;
  }
  rafId = requestAnimationFrame(tick);
};

onMounted(() => {
  rafId = requestAnimationFrame(tick);
});

onUnmounted(() => {
  if (rafId) cancelAnimationFrame(rafId);
});
</script>

<style scoped>
.scroll-progress {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  z-index: 200;
  transform-origin: left center;
  background: linear-gradient(90deg, var(--sc-accent), var(--sc-highlight));
  pointer-events: none;
}
</style>
