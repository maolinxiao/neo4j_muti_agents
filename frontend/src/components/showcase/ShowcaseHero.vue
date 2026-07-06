<template>
  <section id="hero" class="showcase-hero sc-section">
    <div class="hero-bg" aria-hidden="true">
      <HeroGraphFallback v-if="preferStatic" />
      <Suspense v-else>
        <HeroKnowledgeScene />
        <template #fallback>
          <HeroGraphFallback />
        </template>
      </Suspense>
      <div class="hero-bg-shade hero-bg-shade--text" />
      <div class="hero-bg-shade hero-bg-shade--edge" />
    </div>

    <div class="hero-content showcase-container">
      <div class="hero-copy">
        <p
          class="hero-eyebrow"
          v-motion
          :initial="{ opacity: 0, y: 20 }"
          :enter="{ opacity: 1, y: 0, transition: { duration: 550, delay: 80 } }"
        >
          <span class="live-dot" aria-hidden="true" />
          八类知识库 · Neo4j 图谱
        </p>
        <h1
          class="hero-title"
          v-motion
          :initial="{ opacity: 0, y: 28 }"
          :enter="{ opacity: 1, y: 0, transition: { duration: 600, delay: 160 } }"
        >
          <span class="hero-title-grad">多智能体</span>研发协同平台
        </h1>
        <p
          class="hero-lead"
          v-motion
          :initial="{ opacity: 0, y: 24 }"
          :enter="{ opacity: 1, y: 0, transition: { duration: 550, delay: 240 } }"
        >
          以 KB1–KB8 八类知识库为权威源，构建 Neo4j 证据图谱，支撑知识问答、体质辨识与研发协同 Agent 的全链路检索与推理。
        </p>
        <div
          class="hero-tags"
          v-motion
          :initial="{ opacity: 0, y: 18 }"
          :enter="{ opacity: 1, y: 0, transition: { duration: 500, delay: 320 } }"
        >
          <span v-for="tag in tags" :key="tag" class="showcase-tag sc-tag-interactive">{{ tag }}</span>
        </div>
        <div
          class="hero-actions"
          v-motion
          :initial="{ opacity: 0, y: 18 }"
          :enter="{ opacity: 1, y: 0, transition: { duration: 500, delay: 400 } }"
        >
          <router-link :to="{ name: 'login', query: { redirect: '/app' } }" class="showcase-btn showcase-btn-primary sc-btn-shine">
            进入工作台
          </router-link>
          <a href="#capabilities" class="showcase-btn showcase-btn-ghost sc-btn-shine" @click.prevent="goCapabilities">
            查看能力演示
          </a>
        </div>
        <div
          class="hero-capability-rail"
          v-motion
          :initial="{ opacity: 0, y: 16 }"
          :enter="{ opacity: 1, y: 0, transition: { duration: 520, delay: 480 } }"
        >
          <span v-for="item in capabilityRail" :key="item.title" class="hero-capability-pill">
            <i :style="{ background: item.color }" aria-hidden="true" />
            <span>{{ item.title }}</span>
            <small>{{ item.desc }}</small>
          </span>
        </div>
      </div>

      <div
        class="hero-legend"
        v-motion
        :initial="{ opacity: 0, y: 16 }"
        :enter="{ opacity: 1, y: 0, transition: { duration: 500, delay: 520 } }"
      >
        <span v-for="item in graphLegend" :key="item.label" class="legend-chip">
          <i :style="{ background: item.color }" />
          {{ item.label }}
        </span>
      </div>
    </div>

    <button type="button" class="scroll-hint" aria-label="向下滚动" @click="goCapabilities">
      <span class="scroll-hint-text">向下探索</span>
      <span class="scroll-hint-line" />
    </button>
  </section>
</template>

<script setup>
import { defineAsyncComponent } from "vue";

import HeroGraphFallback from "./HeroGraphFallback.vue";
import { HERO_NODE_COLORS } from "../../utils/heroGraphColors";
import { showcaseScrollTo } from "../../composables/useSmoothScroll";
import { useShowcaseMotionPreference } from "../../composables/useShowcaseMotionPreference";

const HeroKnowledgeScene = defineAsyncComponent(() => import("./HeroKnowledgeScene.vue"));

const { preferStatic } = useShowcaseMotionPreference();

const tags = ["八类知识库", "图谱证据", "多 Agent", "合规边界"];

const capabilityRail = [
  { title: "图谱证据", desc: "KB1-KB8 先召回", color: HERO_NODE_COLORS.Platform },
  { title: "Agent 协同", desc: "六步研发流", color: HERO_NODE_COLORS.Formula },
  { title: "合规边界", desc: "标签与宣传审查", color: HERO_NODE_COLORS.ComplianceRule },
  { title: "体质食养", desc: "九种体质适配", color: HERO_NODE_COLORS.ConstitutionType },
];

const graphLegend = [
  { label: "KB1 原料合法性", color: HERO_NODE_COLORS.Herb },
  { label: "KB5 名方方剂", color: HERO_NODE_COLORS.Formula },
  { label: "KB2 功效病症", color: HERO_NODE_COLORS.Effect },
  { label: "KB7 食品合规", color: HERO_NODE_COLORS.ComplianceRule },
  { label: "KB8 体质食养", color: HERO_NODE_COLORS.ConstitutionType },
];

const goCapabilities = () => showcaseScrollTo("#capabilities");
</script>

<style scoped>
.showcase-hero {
  position: relative;
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  align-items: center;
  padding: 6.5rem 0 4.25rem;
  overflow: hidden;
  isolation: isolate;
}

.showcase-hero::before {
  display: none;
}

.hero-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  background:
    radial-gradient(ellipse 80% 70% at 78% 45%, rgba(5, 150, 105, 0.2), transparent 55%),
    linear-gradient(90deg, #fdfdfc 0%, #eef8f4 38%, #0b1512 72%);
}

.hero-bg-shade {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 2;
}

/** 仅保护左侧文案区，不遮挡右侧图谱 */
.hero-bg-shade--text {
  background: linear-gradient(
    100deg,
    rgba(253, 253, 252, 0.99) 0%,
    rgba(253, 253, 252, 0.96) 29%,
    rgba(253, 253, 252, 0.68) 42%,
    rgba(253, 253, 252, 0.08) 57%,
    transparent 70%
  );
}

/** 极轻边缘暗角，不压暗主体网络 */
.hero-bg-shade--edge {
  background:
    radial-gradient(ellipse 80% 82% at 72% 50%, transparent 50%, rgba(8, 14, 12, 0.28) 100%),
    linear-gradient(180deg, rgba(253, 253, 252, 0.16), transparent 22%, rgba(8, 14, 12, 0.2));
}

.hero-content {
  position: relative;
  z-index: 3;
  width: min(var(--sc-max-width), calc(100% - 2.5rem));
  margin-inline: auto;
  display: flex;
  flex-direction: column;
  gap: 2.5rem;
}

.hero-copy {
  max-width: 35rem;
  padding-top: 1rem;
}

/* 胶囊徽章样式的 eyebrow */
.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0 0 1.15rem;
  padding: 0.42rem 0.95rem;
  font-size: 0.78rem;
  font-weight: 650;
  letter-spacing: 0.1em;
  color: var(--sc-accent);
  border-radius: 999px;
  border: 1px solid rgba(5, 150, 105, 0.22);
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.9) inset,
    0 4px 16px rgba(5, 150, 105, 0.08);
}

.live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--sc-accent);
  box-shadow: 0 0 12px rgba(5, 150, 105, 0.55);
  animation: livePulse 2s ease-in-out infinite;
}

@keyframes livePulse {
  0%, 100% { opacity: 0.55; transform: scale(0.9); }
  50% { opacity: 1; transform: scale(1.15); }
}

.hero-title {
  margin: 0 0 1.25rem;
  font-family: var(--sc-font-display);
  font-size: clamp(2.5rem, 5.6vw, 4.6rem);
  font-weight: 700;
  line-height: 1.06;
  letter-spacing: -0.02em;
  color: var(--sc-text);
  text-wrap: balance;
}

/* 关键词渐变强调 */
.hero-title-grad {
  background: linear-gradient(118deg, #047857 0%, #10b981 52%, #5b8fc7 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}

.hero-lead {
  margin: 0 0 1.5rem;
  font-size: 1.0625rem;
  line-height: 1.85;
  color: var(--sc-text-secondary);
  max-width: 34rem;
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 2rem;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.hero-capability-rail {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.65rem;
  margin-top: 1.35rem;
  max-width: 35rem;
}

.hero-capability-pill {
  display: grid;
  grid-template-columns: auto 1fr;
  column-gap: 0.55rem;
  row-gap: 0.05rem;
  align-items: center;
  min-height: 58px;
  padding: 0.72rem 0.85rem;
  border-radius: 14px;
  border: 1px solid rgba(5, 150, 105, 0.14);
  background: rgba(255, 255, 255, 0.68);
  box-shadow: 0 10px 32px rgba(15, 23, 42, 0.06);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.3s ease, box-shadow 0.3s ease;
}

.hero-capability-pill:hover {
  transform: translateY(-2px);
  border-color: rgba(5, 150, 105, 0.3);
  box-shadow: 0 14px 40px rgba(15, 23, 42, 0.1);
}

.hero-capability-pill i {
  grid-row: span 2;
  width: 9px;
  height: 9px;
  border-radius: 999px;
  box-shadow: 0 0 16px currentColor;
}

.hero-capability-pill span {
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--sc-text);
  line-height: 1.1;
}

.hero-capability-pill small {
  font-size: 0.72rem;
  color: var(--sc-text-secondary);
  line-height: 1.25;
}

.hero-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem 1rem;
  padding: 0.75rem 1rem;
  border-radius: var(--sc-radius-md);
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid var(--sc-border-subtle);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.06);
  width: fit-content;
  max-width: 100%;
  margin-top: 0.75rem;
}

.legend-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.75rem;
  color: var(--sc-text-secondary);
  font-weight: 500;
}

.legend-chip i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  box-shadow: 0 0 8px currentColor;
}

.scroll-hint {
  position: absolute;
  bottom: 1.5rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 4;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.55rem;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--sc-muted);
  padding: 0.5rem;
  transition: color 0.25s ease;
}

.scroll-hint:hover {
  color: var(--sc-accent);
}

.scroll-hint-text {
  font-size: 0.72rem;
  font-weight: 550;
  letter-spacing: 0.12em;
}

/* 细线 + 下移光点 */
.scroll-hint-line {
  position: relative;
  width: 1px;
  height: 40px;
  background: linear-gradient(180deg, rgba(10, 124, 92, 0.4), transparent);
  overflow: visible;
}

.scroll-hint-line::after {
  content: "";
  position: absolute;
  left: 50%;
  top: 0;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--sc-accent);
  box-shadow: 0 0 8px rgba(10, 124, 92, 0.6);
  transform: translateX(-50%);
  animation: scrollHintDot 2.2s cubic-bezier(0.45, 0, 0.55, 1) infinite;
}

.scroll-hint:hover .scroll-hint-line::after {
  animation-duration: 1.1s;
}

@keyframes scrollHintDot {
  0% { top: -4px; opacity: 0; }
  18% { opacity: 1; }
  78% { opacity: 1; }
  100% { top: 38px; opacity: 0; }
}

@media (max-width: 768px) {
  .hero-bg-shade--text {
    background: linear-gradient(
      180deg,
      rgba(253, 253, 252, 0.95) 0%,
      rgba(253, 253, 252, 0.72) 38%,
      transparent 58%
    );
  }

  .hero-bg-shade--edge {
    background: radial-gradient(ellipse 100% 80% at 50% 65%, transparent 50%, rgba(8, 14, 12, 0.15) 100%);
  }

  .hero-copy {
    max-width: none;
  }

  .hero-title {
    font-size: clamp(2.2rem, 12vw, 3.25rem);
  }

  .hero-capability-rail {
    grid-template-columns: 1fr;
  }

  .hero-legend {
    display: none;
  }

  .scroll-hint {
    display: none;
  }
}

@media (min-width: 769px) and (max-width: 1080px) {
  .hero-bg-shade--text {
    background: linear-gradient(
      100deg,
      rgba(253, 253, 252, 0.99) 0%,
      rgba(253, 253, 252, 0.96) 38%,
      rgba(253, 253, 252, 0.56) 55%,
      transparent 76%
    );
  }

  .hero-copy {
    max-width: 34rem;
  }

  .hero-title {
    font-size: clamp(2.55rem, 7vw, 4rem);
  }
}
</style>
