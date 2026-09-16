<template>
  <svg viewBox="0 0 420 420" class="kb-svg">
    <defs>
      <radialGradient id="kbCoreGlow" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="#6bc4a6" stop-opacity="0.35" />
        <stop offset="100%" stop-color="#6bc4a6" stop-opacity="0" />
      </radialGradient>
      <filter id="svgGlow" x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
        <feMerge>
          <feMergeNode in="coloredBlur"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>
    </defs>
    <circle cx="210" cy="210" r="160" fill="url(#kbCoreGlow)" />
    <circle cx="210" cy="210" r="155" fill="none" stroke="rgba(106,158,196,0.15)" stroke-width="1" stroke-dasharray="5 9" class="kb-orbit" />
    <circle cx="210" cy="210" r="115" fill="none" stroke="rgba(107,196,166,0.12)" stroke-width="1" />
    <circle cx="210" cy="210" r="26" fill="none" stroke="rgba(107,196,166,0.35)" stroke-width="1.4" class="kb-core-halo" />
    <circle cx="210" cy="210" r="16" fill="#6bc4a6" class="kb-core" filter="url(#svgGlow)" />
    <g v-for="(kb, i) in items" :key="kb.id">
      <path
        :d="arcPath(i)"
        fill="none"
        :stroke="activeId === kb.id ? kb.color : 'rgba(106,158,196,0.26)'"
        :stroke-width="activeId === kb.id ? 2.2 : 1.2"
        class="kb-line"
        :class="{ 'kb-line--active': activeId === kb.id }"
      />
      <circle
        :cx="nodePos(i).x"
        :cy="nodePos(i).y"
        :r="activeId === kb.id ? 11 : 8"
        :fill="activeId === kb.id ? kb.color : 'rgba(148,163,184,0.45)'"
        class="kb-node"
        :filter="activeId === kb.id ? 'url(#svgGlow)' : 'none'"
      />
      <circle
        v-if="activeId === kb.id"
        :cx="nodePos(i).x"
        :cy="nodePos(i).y"
        :r="15"
        fill="none"
        :stroke="kb.color"
        stroke-width="1"
        class="kb-node-halo"
      />
      <text
        :x="nodePos(i).x"
        :y="nodePos(i).y + 24"
        text-anchor="middle"
        class="kb-label"
        :fill="activeId === kb.id ? kb.color : 'rgba(139,157,148,0.8)'"
      >
        {{ kb.id }}
      </text>
    </g>
  </svg>
</template>

<script setup>
const props = defineProps({
  activeId: { type: String, default: "KB1" },
  items: { type: Array, required: true },
});

const nodePos = (index) => {
  const angle = (index / props.items.length) * Math.PI * 2 - Math.PI / 2;
  const radius = 138;
  return {
    x: 210 + Math.cos(angle) * radius,
    y: 210 + Math.sin(angle) * radius,
  };
};

/** 中心到节点的二次贝塞尔弧线，控制点沿切向偏移形成柔和弧度 */
const arcPath = (index) => {
  const { x, y } = nodePos(index);
  const midX = (210 + x) / 2;
  const midY = (210 + y) / 2;
  const dx = x - 210;
  const dy = y - 210;
  const len = Math.sqrt(dx * dx + dy * dy) || 1;
  const ctrlX = midX - (dy / len) * 18;
  const ctrlY = midY + (dx / len) * 18;
  return `M 210 210 Q ${ctrlX.toFixed(1)} ${ctrlY.toFixed(1)} ${x.toFixed(1)} ${y.toFixed(1)}`;
};
</script>

<style scoped>
.kb-svg {
  width: 100%;
  max-width: 340px;
  margin-inline: auto;
  display: block;
}

.kb-orbit {
  transform-origin: 210px 210px;
  animation: kbOrbitSpin 48s linear infinite;
}

.kb-core {
  animation: kbCorePulse 3s ease-in-out infinite;
}

.kb-core-halo {
  transform-origin: 210px 210px;
  animation: kbCoreHalo 3s ease-in-out infinite;
}

@keyframes kbCoreHalo {
  0%, 100% { transform: scale(0.92); opacity: 0.5; }
  50% { transform: scale(1.12); opacity: 1; }
}

.kb-line {
  transition: stroke 0.3s ease, stroke-width 0.3s ease;
}

.kb-line--active {
  stroke-dasharray: 6 10;
  animation: kbLineFlow 1.4s linear infinite;
}

@keyframes kbLineFlow {
  to { stroke-dashoffset: -32; }
}

.kb-node {
  transition: r 0.3s ease, fill 0.3s ease;
}

.kb-node-halo {
  opacity: 0.7;
  transform-origin: center;
  animation: kbHaloPulse 2s ease-out infinite;
}

@keyframes kbHaloPulse {
  0% { opacity: 0.7; r: 13; }
  100% { opacity: 0; r: 22; }
}

.kb-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.05em;
}

@keyframes kbOrbitSpin {
  to { transform: rotate(360deg); }
}

@keyframes kbCorePulse {
  0%, 100% { opacity: 0.85; }
  50% { opacity: 1; }
}
</style>
