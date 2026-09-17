<template>
  <section id="capabilities" class="sc-section sc-section--soft capability-section">
    <ShowcaseSectionDecor tone="green" />
    <ShowcaseReveal3D variant="up" stagger>
      <div class="showcase-container section-inner">
        <ShowcaseSectionHeader
          eyebrow="Capabilities"
          title="三大核心能力"
          lead="面向企业研发与个人食养，以图谱证据串联问答、体质辨识与多 Agent 研发协同。"
        />
        <div class="capability-rows">
          <article
            v-for="(item, index) in capabilities"
            :key="item.key"
            class="reveal-stagger-item capability-card capability-row"
            :class="[`capability-row--${item.key}`, { 'capability-row--reverse': index % 2 === 1 }]"
            :style="{ '--reveal-index': index, '--row-color': item.sceneColor }"
            @mouseenter="onCardHover(item.key, true)"
            @mouseleave="onCardHover(item.key, false)"
          >
            <div class="row-copy">
              <span class="capability-kicker">{{ item.kicker }}</span>
              <h3>{{ item.title }}</h3>
              <p class="capability-desc">
                {{ item.description }}
                <small class="desc-kb">证据底座：{{ item.kbText }}</small>
              </p>
              <blockquote class="capability-example" aria-label="示例问题">
                「{{ typed[item.key] || item.examples[0] }}」<span class="type-cursor" aria-hidden="true" />
              </blockquote>
              <router-link :to="item.route" class="capability-link">
                进入 {{ item.title }}
                <span aria-hidden="true">→</span>
              </router-link>
            </div>
            <div class="row-scene" aria-hidden="true">
              <UseCaseScene v-if="useScene3d" :ref="setSceneRef(item.key)" :variant="item.sceneVariant" :color="item.sceneColor">
                <template #fallback>
                  <component :is="item.icon" />
                  <span class="visual-orbit" />
                </template>
              </UseCaseScene>
              <template v-else>
                <component :is="item.icon" />
                <span class="visual-orbit" />
              </template>
            </div>
          </article>
        </div>
      </div>
    </ShowcaseReveal3D>
  </section>
</template>

<script setup>
import { computed, h, onMounted, onUnmounted, ref } from "vue";

import UseCaseScene from "./UseCaseScene.vue";
import ShowcaseReveal3D from "./ShowcaseReveal3D.vue";
import ShowcaseSectionDecor from "./ShowcaseSectionDecor.vue";
import ShowcaseSectionHeader from "./ShowcaseSectionHeader.vue";
import { useMediaQuery } from "../../composables/useTilt";
import { useShowcaseMotionPreference } from "../../composables/useShowcaseMotionPreference";

const { preferReducedMotion } = useShowcaseMotionPreference();
const isNarrow = useMediaQuery("(max-width: 767px)");
const useScene3d = computed(() => !preferReducedMotion.value && !isNarrow.value);

const iconQa = () =>
  h("svg", { viewBox: "0 0 64 64", class: "cap-icon" }, [
    h("circle", { cx: "32", cy: "32", r: "28", fill: "none", stroke: "currentColor", "stroke-opacity": "0.25", "stroke-width": "1.5" }),
    h("circle", { cx: "22", cy: "26", r: "6", fill: "currentColor", opacity: "0.5" }),
    h("circle", { cx: "44", cy: "22", r: "5", fill: "currentColor", opacity: "0.35" }),
    h("circle", { cx: "38", cy: "42", r: "7", fill: "currentColor", opacity: "0.6" }),
    h("line", { x1: "26", y1: "28", x2: "40", y2: "24", stroke: "currentColor", "stroke-width": "1.2", opacity: "0.4" }),
    h("line", { x1: "28", y1: "30", x2: "34", y2: "38", stroke: "currentColor", "stroke-width": "1.2", opacity: "0.4" }),
  ]);

const iconConstitution = () =>
  h("svg", { viewBox: "0 0 64 64", class: "cap-icon" }, [
    h("path", { d: "M32 8 L52 18 V38 C52 48 32 56 32 56 C32 56 12 48 12 38 V18 Z", fill: "none", stroke: "currentColor", "stroke-width": "1.8", opacity: "0.7" }),
    h("circle", { cx: "32", cy: "30", r: "8", fill: "currentColor", opacity: "0.35" }),
    h("path", { d: "M24 42 Q32 48 40 42", fill: "none", stroke: "currentColor", "stroke-width": "1.5", opacity: "0.5" }),
  ]);

const iconRnd = () =>
  h("svg", { viewBox: "0 0 64 64", class: "cap-icon" }, [
    h("rect", { x: "10", y: "14", width: "44", height: "36", rx: "6", fill: "none", stroke: "currentColor", "stroke-width": "1.5", opacity: "0.5" }),
    h("circle", { cx: "22", cy: "32", r: "5", fill: "currentColor", opacity: "0.45" }),
    h("circle", { cx: "32", cy: "24", r: "5", fill: "currentColor", opacity: "0.6" }),
    h("circle", { cx: "42", cy: "32", r: "5", fill: "currentColor", opacity: "0.45" }),
    h("circle", { cx: "32", cy: "40", r: "5", fill: "currentColor", opacity: "0.35" }),
    h("line", { x1: "22", y1: "32", x2: "32", y2: "24", stroke: "currentColor", "stroke-width": "1", opacity: "0.35" }),
    h("line", { x1: "32", y1: "24", x2: "42", y2: "32", stroke: "currentColor", "stroke-width": "1", opacity: "0.35" }),
    h("line", { x1: "42", y1: "32", x2: "32", y2: "40", stroke: "currentColor", "stroke-width": "1", opacity: "0.35" }),
    h("line", { x1: "32", y1: "40", x2: "22", y2: "32", stroke: "currentColor", "stroke-width": "1", opacity: "0.35" }),
  ]);

const capabilities = [
  {
    key: "qa",
    kicker: "Knowledge QA",
    title: "知识问答",
    icon: iconQa,
    description: "跨 KB1–KB7 检索原料、方剂、功效、风味、替代与合规证据——回答附图谱子图与证据摘要，每一句结论都有出处。",
    examples: [
      "麻黄可以用什么药食同源原料替代？",
      "孕妇能不能吃薏苡仁？",
      "这个方子适合做代餐粉吗？",
    ],
    route: { name: "chat" },
    sceneVariant: "graph",
    sceneColor: "#059669",
    kbText: "KB1–KB7",
  },
  {
    key: "constitution",
    kicker: "Constitution",
    title: "体质辨识",
    icon: iconConstitution,
    description: "三十问读懂你的身体——基于 KB8 体质食养规则库完成九种体质测评，给出食养方向与慎用原料提醒。",
    examples: ["我是什么体质？", "痰湿体质平时怎么吃？", "容易过敏该怎么食养？"],
    route: { name: "constitution" },
    sceneVariant: "constellation",
    sceneColor: "#ec4899",
    kbText: "KB8",
  },
  {
    key: "rnd",
    kicker: "R&D Agents",
    title: "研发协同",
    icon: iconRnd,
    description: "六步 Agent 串联 KB4 替代、KB3 风味、KB5 组方等图谱证据——从一句需求到一份可交付的研发方案与合规边界。",
    examples: [
      "把四君子汤改造成药食同源代餐粉",
      "做一款助消化的草本茶饮怎么配？",
      "低糖点心如何选料不苦？",
    ],
    route: { name: "rnd" },
    sceneVariant: "pipeline",
    sceneColor: "#d97706",
    kbText: "KB3 · KB4 · KB5",
  },
];

// —— 示例问题打字机轮播（每卡独立节奏；hover 暂停；reduced-motion 静态展示）——
const typed = ref({ qa: "", constitution: "", rnd: "" });
const hoveredKey = ref(null);
const typeTimers = [];

const startTyping = (key, list) => {
  let li = 0;
  let pos = 0;
  let deleting = false;
  let holdUntil = 0;
  const tick = () => {
    if (hoveredKey.value !== key) {
      const full = list[li];
      if (!deleting) {
        pos += 1;
        typed.value[key] = full.slice(0, pos);
        if (pos >= full.length) {
          deleting = true;
          holdUntil = Date.now() + 1700;
        }
      } else if (Date.now() >= holdUntil) {
        pos -= 1;
        typed.value[key] = full.slice(0, pos);
        if (pos <= 0) {
          deleting = false;
          li = (li + 1) % list.length;
        }
      }
    }
    typeTimers.push(setTimeout(tick, deleting ? 26 : 62));
  };
  tick();
};

onMounted(() => {
  capabilities.forEach((item, i) => {
    typed.value[item.key] = item.examples[0];
    if (preferReducedMotion.value) return; // reduced-motion：静态完整展示
    setTimeout(() => startTyping(item.key, item.examples), 600 + i * 900);
  });
});

onUnmounted(() => {
  typeTimers.forEach((t) => clearTimeout(t));
});

// —— 场景 hover 增强态：微场景加速 + 视差启用（由 UseCaseScene.setBoost 门控）——
const sceneRefs = {};
const setSceneRef = (key) => (el) => {
  if (el) sceneRefs[key] = el;
};
const onCardHover = (key, entering) => {
  hoveredKey.value = entering ? key : null;
  sceneRefs[key]?.setBoost?.(entering);
};
</script>

<style scoped>
.capability-section {
  position: relative;
}

.section-inner {
  position: relative;
  z-index: 1;
}

/* —— 全宽交错横排：每条能力一行，场景左右交替 —— */
.capability-rows {
  margin-top: 0.5rem;
}

.capability-row {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  gap: clamp(2rem, 5vw, 4.5rem);
  align-items: center;
  padding: 2.9rem 0.5rem;
}

.capability-row + .capability-row {
  border-top: 1px solid rgba(15, 23, 42, 0.06);
}

/* 奇数行场景在左（交错） */
.capability-row--reverse .row-scene {
  order: -1;
}

.row-copy {
  max-width: 34rem;
}

.capability-kicker {
  display: block;
  margin-bottom: 0.55rem;
  font-size: 0.74rem;
  font-weight: 750;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--row-color, var(--sc-accent));
  opacity: 0.85;
}

.row-copy h3 {
  margin: 0 0 0.9rem;
  font-family: var(--sc-font-display);
  font-size: clamp(1.5rem, 2.4vw, 2rem);
  font-weight: 720;
  letter-spacing: -0.01em;
  color: var(--sc-text);
}

.capability-desc {
  margin: 0;
  font-size: 1rem;
  line-height: 1.85;
  color: var(--sc-text-secondary);
}

.desc-kb {
  display: block;
  margin-top: 0.55rem;
  font-size: 0.76rem;
  letter-spacing: 0.04em;
  color: var(--sc-muted);
}

.capability-example {
  margin: 1.5rem 0 1.4rem;
  padding: 0.9rem 1.1rem;
  border-left: 3px solid var(--row-color, var(--sc-accent));
  border-radius: 0 var(--sc-radius-sm) var(--sc-radius-sm) 0;
  background: color-mix(in srgb, var(--row-color, var(--sc-accent)) 5%, transparent);
  color: var(--sc-text);
  font-size: 0.98rem;
  font-weight: 550;
}

.type-cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  margin-left: 2px;
  vertical-align: -0.15em;
  background: var(--row-color, var(--sc-accent));
  opacity: 0.55;
  animation: typeCursorBlink 1.05s steps(1) infinite;
}

@keyframes typeCursorBlink {
  0%, 55% { opacity: 0.55; }
  56%, 100% { opacity: 0; }
}

.capability-link {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  color: var(--row-color, var(--sc-accent));
  text-decoration: none;
  font-size: 0.9rem;
  font-weight: 650;
  transition: gap 0.25s ease;
}

.capability-link:hover {
  gap: 0.6rem;
}

/* —— 场景区：大画布 + 主题色柔光底 —— */
.row-scene {
  position: relative;
  height: 320px;
  border-radius: var(--sc-radius-lg);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--row-color, var(--sc-accent));
  background: radial-gradient(circle at 50% 62%, color-mix(in srgb, var(--row-color, var(--sc-accent)) 9%, transparent), transparent 68%);
}

.row-scene::before {
  content: "";
  position: absolute;
  inset: 12%;
  border-radius: 50%;
  border: 1px dashed color-mix(in srgb, var(--row-color, var(--sc-accent)) 28%, transparent);
  animation: rowOrbit 26s linear infinite;
}

@keyframes rowOrbit {
  to { transform: rotate(360deg); }
}

.row-scene :deep(.use-case-scene) {
  position: absolute;
  inset: 0;
  z-index: 1;
}

.row-scene :deep(.cap-icon) {
  position: relative;
  z-index: 1;
  width: 84px;
  height: 84px;
}

.visual-orbit {
  position: absolute;
  width: 118px;
  height: 118px;
  border: 1px dashed currentColor;
  border-radius: 50%;
  opacity: 0.18;
  animation: rowOrbit 18s linear infinite reverse;
}

@media (max-width: 1080px) {
  .capability-row {
    grid-template-columns: 1fr;
    gap: 1.6rem;
    padding: 2.4rem 0.25rem;
  }

  /* 窄屏：场景统一放下方 */
  .capability-row--reverse .row-scene {
    order: 2;
  }

  .row-scene {
    height: 250px;
  }

  .row-copy {
    max-width: none;
  }
}

@media (max-width: 680px) {
  .capability-row {
    padding: 2rem 0.1rem;
  }

  .row-scene {
    height: 210px;
  }
}
</style>
