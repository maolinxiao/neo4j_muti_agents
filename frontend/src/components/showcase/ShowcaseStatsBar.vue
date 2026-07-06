<template>
  <ShowcaseReveal3D variant="scale" :delay="80" stagger>
    <div class="showcase-stats">
      <div class="showcase-container stats-grid">
        <div
          v-for="(stat, index) in stats"
          :key="stat.label"
          class="reveal-stagger-item stat-item sc-glass-subtle sc-card-hover"
          :style="{ '--reveal-index': index }"
        >
          <span class="stat-value">{{ stat.value }}</span>
          <span class="stat-label">{{ stat.label }}</span>
        </div>
      </div>
    </div>
  </ShowcaseReveal3D>
</template>

<script setup>
import ShowcaseReveal3D from "./ShowcaseReveal3D.vue";

const stats = [
  { value: "8", label: "类知识库 KB1–KB8" },
  { value: "6", label: "研发协同 Agent 步骤" },
  { value: "9", label: "种体质辨识模型" },
  { value: "3", label: "大核心工作台能力" },
];
</script>

<style scoped>
.showcase-stats {
  padding: 0 0 1.4rem;
  margin-top: -3.5rem;
  position: relative;
  z-index: 3;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.85rem;
}

/* 浮在 Hero 3D 之上的玻璃条，承接深色到浅色 */
.stat-item {
  padding: 1.1rem 1.2rem;
  border-radius: var(--sc-radius-md);
  text-align: center;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(10px) saturate(1.2);
  -webkit-backdrop-filter: blur(10px) saturate(1.2);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.95) inset,
    0 12px 36px rgba(0, 0, 0, 0.10),
    0 3px 10px rgba(0, 0, 0, 0.05);
}

.stat-value {
  display: block;
  font-family: var(--sc-font-display);
  font-size: 1.75rem;
  font-weight: 800;
  color: var(--sc-accent);
  line-height: 1.2;
  background: linear-gradient(135deg, var(--sc-accent) 0%, #10b981 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.stat-label {
  display: block;
  margin-top: 0.35rem;
  font-size: 0.8125rem;
  color: var(--sc-muted);
  letter-spacing: 0.02em;
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
