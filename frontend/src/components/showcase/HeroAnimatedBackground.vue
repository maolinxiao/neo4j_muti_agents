<template>
  <div class="hero-animated-bg" aria-hidden="true">
    <div class="gradient-blob blob-a" />
    <div class="gradient-blob blob-b" />
    <div class="gradient-blob blob-c" />
    <div class="gradient-mesh" />
  </div>
</template>

<style scoped>
.hero-animated-bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}

.gradient-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.55;
  will-change: transform;
}

.blob-a {
  width: 55vw;
  height: 55vw;
  max-width: 680px;
  max-height: 680px;
  top: -10%;
  right: -8%;
  background: radial-gradient(circle, rgba(74, 222, 128, 0.35) 0%, transparent 70%);
  animation: scBlobDriftA 18s ease-in-out infinite alternate;
}

.blob-b {
  width: 45vw;
  height: 45vw;
  max-width: 560px;
  max-height: 560px;
  bottom: -5%;
  left: -10%;
  background: radial-gradient(circle, rgba(105, 183, 255, 0.32) 0%, transparent 70%);
  animation: scBlobDriftB 22s ease-in-out infinite alternate;
}

.blob-c {
  width: 30vw;
  height: 30vw;
  max-width: 380px;
  max-height: 380px;
  top: 35%;
  left: 40%;
  background: radial-gradient(circle, rgba(251, 191, 36, 0.18) 0%, transparent 70%);
  animation: scBlobDriftC 26s ease-in-out infinite alternate;
}

.gradient-mesh {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    125deg,
    rgba(11, 26, 20, 0.2) 0%,
    rgba(7, 21, 16, 0.55) 45%,
    rgba(10, 20, 24, 0.65) 100%
  );
  animation: scGradientShift 16s ease-in-out infinite alternate;
}

@keyframes scBlobDriftA {
  from { transform: translate(0, 0) scale(1); }
  to { transform: translate(-4%, 6%) scale(1.08); }
}

@keyframes scBlobDriftB {
  from { transform: translate(0, 0) scale(1); }
  to { transform: translate(5%, -4%) scale(1.06); }
}

@keyframes scBlobDriftC {
  from { transform: translate(0, 0) scale(1); }
  to { transform: translate(-3%, 3%) scale(0.95); }
}

@keyframes scGradientShift {
  from { opacity: 0.85; }
  to { opacity: 1; }
}
</style>
