<template>
  <div class="section-decor" aria-hidden="true">
    <div class="decor-blob decor-blob--a" :class="`decor-blob--${tone}`" />
    <div class="decor-blob decor-blob--b" :class="`decor-blob--${tone}`" />
    <svg v-if="pattern === 'mesh'" class="decor-mesh" viewBox="0 0 400 400">
      <defs>
        <pattern id="meshDots" width="24" height="24" patternUnits="userSpaceOnUse">
          <circle cx="2" cy="2" r="1" fill="rgba(107,196,166,0.12)" />
        </pattern>
      </defs>
      <rect width="400" height="400" fill="url(#meshDots)" />
    </svg>
  </div>
</template>

<script setup>
defineProps({
  tone: { type: String, default: "green" },
  pattern: { type: String, default: "mesh" },
});
</script>

<style scoped>
.section-decor {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
}

.decor-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.45;
}

.decor-blob--a {
  width: min(420px, 55vw);
  height: min(420px, 55vw);
  top: -12%;
  right: -8%;
}

.decor-blob--b {
  width: min(320px, 45vw);
  height: min(320px, 45vw);
  bottom: -8%;
  left: -6%;
}

.decor-blob--green.decor-blob--a {
  background: rgba(5, 150, 105, 0.08);
}

.decor-blob--green.decor-blob--b {
  background: rgba(37, 99, 235, 0.06);
}

.decor-blob--gold.decor-blob--a {
  background: rgba(217, 119, 6, 0.08);
}

.decor-blob--gold.decor-blob--b {
  background: rgba(5, 150, 105, 0.06);
}

.decor-blob--blue.decor-blob--a {
  background: rgba(37, 99, 235, 0.08);
}

.decor-blob--blue.decor-blob--b {
  background: rgba(5, 150, 105, 0.06);
}

.decor-mesh {
  position: absolute;
  right: 0;
  top: 10%;
  width: 280px;
  height: 280px;
  opacity: 0.35;
  mask-image: radial-gradient(circle, black 20%, transparent 70%);
}
</style>
