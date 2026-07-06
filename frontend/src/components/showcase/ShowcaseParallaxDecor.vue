<template>
  <div class="parallax-decor" aria-hidden="true">
    <div class="orb orb-a sc-parallax-slow" :style="slowStyle" />
    <div class="orb orb-b sc-parallax-fast" :style="fastStyle" />
  </div>
</template>

<script setup>
import { useParallax } from "../../composables/useParallax";

const { style: slowStyle } = useParallax(0.12);
const { style: fastStyle } = useParallax(0.28);
</script>

<style scoped>
.parallax-decor {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  will-change: transform;
}

.orb-a {
  width: 280px;
  height: 280px;
  top: 10%;
  right: 8%;
  background: rgba(74, 222, 128, 0.07);
}

.orb-b {
  width: 220px;
  height: 220px;
  bottom: 15%;
  left: 5%;
  background: rgba(105, 183, 255, 0.08);
}
</style>
