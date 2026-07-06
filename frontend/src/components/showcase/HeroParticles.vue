<template>
  <canvas ref="canvasRef" class="hero-particles" aria-hidden="true" />
</template>

<script setup>
import { onMounted, onUnmounted, ref } from "vue";

const canvasRef = ref(null);
let rafId = null;
let particles = [];
let width = 0;
let height = 0;

const createParticles = (count) => {
  particles = Array.from({ length: count }, () => ({
    x: Math.random() * width,
    y: Math.random() * height,
    vx: (Math.random() - 0.5) * 0.35,
    vy: (Math.random() - 0.5) * 0.35,
    r: Math.random() * 1.8 + 0.6,
    color: Math.random() > 0.5 ? "rgba(120, 216, 183, 0.55)" : "rgba(105, 183, 255, 0.45)",
  }));
};

const resize = () => {
  const canvas = canvasRef.value;
  if (!canvas) return;
  width = canvas.offsetWidth;
  height = canvas.offsetHeight;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.floor(width * dpr);
  canvas.height = Math.floor(height * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  if (!particles.length) {
    createParticles(Math.min(55, Math.floor((width * height) / 18000)));
  }
};

const draw = () => {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, width, height);

  for (const p of particles) {
    p.x += p.vx;
    p.y += p.vy;
    if (p.x < 0 || p.x > width) p.vx *= -1;
    if (p.y < 0 || p.y > height) p.vy *= -1;

    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    ctx.fillStyle = p.color;
    ctx.fill();
  }

  for (let i = 0; i < particles.length; i += 1) {
    for (let j = i + 1; j < particles.length; j += 1) {
      const a = particles[i];
      const b = particles[j];
      const dx = a.x - b.x;
      const dy = a.y - b.y;
      const dist = Math.hypot(dx, dy);
      if (dist < 110) {
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = `rgba(105, 183, 255, ${0.14 * (1 - dist / 110)})`;
        ctx.lineWidth = 0.6;
        ctx.stroke();
      }
    }
  }

  rafId = requestAnimationFrame(draw);
};

onMounted(() => {
  resize();
  window.addEventListener("resize", resize);
  rafId = requestAnimationFrame(draw);
});

onUnmounted(() => {
  window.removeEventListener("resize", resize);
  if (rafId) cancelAnimationFrame(rafId);
});
</script>

<style scoped>
.hero-particles {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  opacity: 0.75;
}
</style>
