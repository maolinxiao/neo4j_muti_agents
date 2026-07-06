<template>
  <div class="showcase-marquee" :class="`showcase-marquee--${variant}`" aria-hidden="true">
    <div class="marquee-track">
      <span v-for="(item, i) in loopItems" :key="`${item}-${i}`" class="marquee-item">
        <span class="marquee-dot" />
        {{ item }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  items: {
    type: Array,
    default: () => [
      "知识图谱证据底座",
      "九种体质食养",
      "方剂药食同源化",
      "功效与风味预测",
      "食品合规审查",
      "多 Agent 研发协同",
      "KB1–KB8 八类知识库",
      "图谱问答与证据子图",
    ],
  },
  variant: {
    type: String,
    default: "dark",
  },
});

const loopItems = computed(() => [...props.items, ...props.items]);
</script>

<style scoped>
.showcase-marquee {
  position: relative;
  overflow: hidden;
  mask-image: linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent);
}

/* 暗色：作为 Hero 3D 区的视觉延伸（低饱和） */
.showcase-marquee--dark {
  border-block: 1px solid var(--sc-border-subtle);
  background:
    radial-gradient(circle at 25% 50%, rgba(94, 234, 212, 0.07), transparent 28%),
    linear-gradient(90deg, rgba(10, 21, 18, 0.94), rgba(14, 26, 22, 0.88), rgba(10, 21, 18, 0.94));
}

/* 浅色玻璃：正文段落间的轻量过渡条 */
.showcase-marquee--light {
  border-block: 1px solid var(--sc-border-subtle);
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.marquee-track {
  display: flex;
  width: max-content;
  gap: 2.5rem;
  padding: 0.85rem 0;
  animation: marqueeScroll 42s linear infinite;
}

.marquee-item {
  display: inline-flex;
  align-items: center;
  gap: 0.65rem;
  white-space: nowrap;
  font-size: 0.8125rem;
  font-weight: 500;
  letter-spacing: 0.04em;
}

.showcase-marquee--dark .marquee-item {
  color: rgba(229, 248, 241, 0.55);
}

.showcase-marquee--light .marquee-item {
  color: var(--sc-text-tertiary);
}

.marquee-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--sc-accent);
  opacity: 0.55;
}

@keyframes marqueeScroll {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}

@media (prefers-reduced-motion: reduce) {
  .marquee-track {
    animation: none;
    flex-wrap: wrap;
    width: 100%;
    justify-content: center;
    padding: 1rem;
  }
}
</style>
