<template>
  <div class="hero-graph-fallback" aria-hidden="true">
    <svg class="fallback-svg" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice">
      <defs>
        <radialGradient id="hgDark" cx="68%" cy="50%" r="55%">
          <stop offset="0%" stop-color="#1a2e28" />
          <stop offset="100%" stop-color="#060a09" />
        </radialGradient>
        <linearGradient id="hgEdge" x1="0%" x2="100%">
          <stop offset="0%" stop-color="#6ee7b7" stop-opacity="0.35" />
          <stop offset="50%" stop-color="#e2e8f0" stop-opacity="0.85" />
          <stop offset="100%" stop-color="#a5b4fc" stop-opacity="0.35" />
        </linearGradient>
        <filter id="hgBlur" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="5" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <rect width="1440" height="900" fill="url(#hgDark)" />
      <circle cx="920" cy="430" r="300" fill="none" stroke="rgba(110,231,183,0.18)" stroke-width="1.5" stroke-dasharray="6 10" class="orbit" />
      <circle cx="920" cy="430" r="360" fill="none" stroke="rgba(129,140,248,0.12)" stroke-width="1" class="orbit slow" />

      <g class="graph-spin" transform-origin="920 430">
        <line v-for="(e, i) in edges" :key="'e' + i" :x1="e.x1" :y1="e.y1" :x2="e.x2" :y2="e.y2" class="edge" />
        <g v-for="node in nodes" :key="node.id" class="node-wrap">
          <circle :cx="node.x" :cy="node.y" :r="node.r * 2" :fill="node.color" opacity="0.15" />
          <circle :cx="node.x" :cy="node.y" :r="node.r" :fill="node.color" filter="url(#hgBlur)" />
          <text :x="node.x" :y="node.y + node.r + 18" text-anchor="middle" class="node-label">{{ node.name }}</text>
          <text :x="node.x" :y="node.y + node.r + 34" text-anchor="middle" class="node-tag">{{ node.tag }}</text>
        </g>
      </g>
    </svg>
  </div>
</template>

<script setup>
import { HERO_NODE_COLORS } from "../../utils/heroGraphColors";

const cx = 920;
const cy = 430;
const R = 250;

const nodes = [
  { id: "platform", name: "知识图谱", tag: "八库联动", x: cx, y: cy, r: 24, color: HERO_NODE_COLORS.Platform },
  { id: "herb1", name: "原料合法性库", tag: "KB1", x: cx - R * 0.7, y: cy - R * 0.35, r: 14, color: HERO_NODE_COLORS.Herb },
  { id: "formula1", name: "名方方剂库", tag: "KB5", x: cx + R * 0.75, y: cy + R * 0.1, r: 15, color: HERO_NODE_COLORS.Formula },
  { id: "effect1", name: "功效病症库", tag: "KB2", x: cx - R * 0.4, y: cy + R * 0.65, r: 13, color: HERO_NODE_COLORS.Effect },
  { id: "constitution1", name: "体质食养库", tag: "KB8", x: cx + R * 0.3, y: cy - R * 0.72, r: 13, color: HERO_NODE_COLORS.ConstitutionType },
  { id: "compliance1", name: "食品合规库", tag: "KB7", x: cx - R * 0.8, y: cy + R * 0.1, r: 13, color: HERO_NODE_COLORS.ComplianceRule },
];

const edges = [
  { x1: cx, y1: cy, x2: nodes[1].x, y2: nodes[1].y },
  { x1: cx, y1: cy, x2: nodes[2].x, y2: nodes[2].y },
  { x1: cx, y1: cy, x2: nodes[3].x, y2: nodes[3].y },
  { x1: cx, y1: cy, x2: nodes[4].x, y2: nodes[4].y },
  { x1: cx, y1: cy, x2: nodes[5].x, y2: nodes[5].y },
  { x1: nodes[1].x, y1: nodes[1].y, x2: nodes[2].x, y2: nodes[2].y },
  { x1: nodes[2].x, y1: nodes[2].y, x2: nodes[3].x, y2: nodes[3].y },
];
</script>

<style scoped>
.hero-graph-fallback {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}

.fallback-svg {
  width: 100%;
  height: 100%;
}

.orbit {
  transform-origin: 920px 430px;
  animation: spin 72s linear infinite;
}

.orbit.slow {
  animation-duration: 96s;
  animation-direction: reverse;
}

.graph-spin {
  animation: spin 72s linear infinite;
}

.edge {
  stroke: url(#hgEdge);
  stroke-width: 2.2;
  stroke-linecap: round;
}

.node-label {
  fill: #f8fafc;
  font-size: 14px;
  font-weight: 600;
}

.node-tag {
  fill: #94a3b8;
  font-size: 11px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
