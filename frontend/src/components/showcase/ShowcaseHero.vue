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
        <!-- 升华金句：打字机 + 句子轮换 -->
        <p class="hero-quote" :aria-label="currentQuoteText">
          <template v-for="(seg, si) in visibleSegments" :key="quoteIndex + '-' + si">
            <span :class="{ 'hero-quote-grad': seg.grad }">{{ seg.text }}</span>
          </template>
          <span class="hero-cursor" aria-hidden="true" />
        </p>
        <p
          class="hero-quote-sub"
          v-motion
          :initial="{ opacity: 0, y: 14 }"
          :enter="{ opacity: 1, y: 0, transition: { duration: 520, delay: 900 } }"
        >
          从一句提问到一份研发方案——证据先行，智能体同行。
        </p>
      </div>

      <div
        class="hero-trust"
        v-motion
        :initial="{ opacity: 0, y: 12 }"
        :enter="{ opacity: 1, y: 0, transition: { duration: 520, delay: 1440 } }"
      >
        <span>八类知识库</span>
        <i aria-hidden="true" />
        <span>Neo4j 证据图谱</span>
        <i aria-hidden="true" />
        <span>多 Agent 协同</span>
      </div>
    </div>

    <button type="button" class="scroll-hint" aria-label="向下滚动" @click="goCapabilities">
      <span class="scroll-hint-text">向下探索</span>
      <span class="scroll-hint-line" />
    </button>
  </section>
</template>

<script setup>
import { computed, defineAsyncComponent, onMounted, onUnmounted, ref } from "vue";

import HeroGraphFallback from "./HeroGraphFallback.vue";
import { showcaseScrollTo } from "../../composables/useSmoothScroll";
import { useShowcaseMotionPreference } from "../../composables/useShowcaseMotionPreference";

const HeroKnowledgeScene = defineAsyncComponent(() => import("./HeroKnowledgeScene.vue"));

const { preferStatic } = useShowcaseMotionPreference();

const tags = ["八类知识库", "图谱证据", "多 Agent", "合规边界"];

// 升华金句库：打字机轮换；grad 段为渐变强调词
const quotes = [
  [
    { t: "一株本草的答案，藏在" },
    { t: "两千年方剂智慧", grad: true },
    { t: "与" },
    { t: "八库证据", grad: true },
    { t: "之间。" },
  ],
  [
    { t: "让每一次提问都" },
    { t: "落在证据", grad: true },
    { t: "上，让每一个方案都" },
    { t: "经得起追溯", grad: true },
    { t: "。" },
  ],
  [
    { t: "从经典名方到现代产品——" },
    { t: "本草的旅程", grad: true },
    { t: "，由智能体与你同行。" },
  ],
];

const TYPE_MS = 85;
const HOLD_MS = 2400;
const ERASE_MS = 24;

const quoteIndex = ref(0);
const typedCount = ref(0);

const quoteLength = (segs) => segs.reduce((n, s) => n + s.t.length, 0);
const currentQuoteText = computed(() => quotes[quoteIndex.value].map((s) => s.t).join(""));

/** 已打出的分段（跨段推进，渐变段保持渐变） */
const visibleSegments = computed(() => {
  let remain = typedCount.value;
  const out = [];
  for (const seg of quotes[quoteIndex.value]) {
    if (remain <= 0) break;
    out.push({ text: seg.t.slice(0, remain), grad: seg.grad });
    remain -= seg.t.length;
  }
  return out;
});

let quoteTimer = null;
let deleting = false;

const tickQuote = () => {
  const total = quoteLength(quotes[quoteIndex.value]);
  if (!deleting) {
    typedCount.value = Math.min(total, typedCount.value + 1);
    if (typedCount.value >= total) {
      deleting = true;
      quoteTimer = setTimeout(tickQuote, HOLD_MS);
      return;
    }
    quoteTimer = setTimeout(tickQuote, TYPE_MS);
  } else {
    typedCount.value = Math.max(0, typedCount.value - 1);
    if (typedCount.value <= 0) {
      deleting = false;
      quoteIndex.value = (quoteIndex.value + 1) % quotes.length;
      quoteTimer = setTimeout(tickQuote, 420);
      return;
    }
    quoteTimer = setTimeout(tickQuote, ERASE_MS);
  }
};

onMounted(() => {
  if (preferStatic.value) {
    // reduced-motion / 窄屏：静态完整显示第一句
    typedCount.value = quoteLength(quotes[0]);
    return;
  }
  quoteTimer = setTimeout(tickQuote, 500);
});

onUnmounted(() => {
  clearTimeout(quoteTimer);
});

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

/* —— 升华金句（打字机 + 轮换）—— */
.hero-quote {
  margin: 1.4rem 0 0;
  min-height: 5.2rem;
  font-family: var(--sc-font-display);
  font-size: clamp(1.28rem, 2.1vw, 1.66rem);
  font-weight: 680;
  line-height: 1.55;
  letter-spacing: 0.005em;
  color: var(--sc-text);
}

.hero-quote-grad {
  background: linear-gradient(118deg, #047857 8%, #10b981 55%, #d97706 105%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}

.hero-cursor {
  display: inline-block;
  width: 3px;
  height: 1.05em;
  margin-left: 3px;
  vertical-align: -0.16em;
  border-radius: 2px;
  background: var(--sc-accent);
  box-shadow: 0 0 10px rgba(5, 150, 105, 0.55);
  animation: heroCursorBlink 1.05s steps(1) infinite;
}

@keyframes heroCursorBlink {
  0%, 55% { opacity: 0.85; }
  56%, 100% { opacity: 0; }
}

.hero-quote-sub {
  margin: 0.7rem 0 0;
  font-size: 0.98rem;
  line-height: 1.75;
  color: var(--sc-text-secondary);
}

/* —— 极简信任线 —— */
.hero-trust {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  margin-top: 2.1rem;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--sc-text-secondary);
  width: fit-content;
}

.hero-trust i {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: rgba(5, 150, 105, 0.55);
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

  .hero-trust {
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
