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
        <div ref="tiltScope" class="capability-grid" @mousemove="tilt.onMove" @mouseleave="tilt.onLeave">
          <div
            v-for="(item, index) in capabilities"
            :key="item.key"
            class="reveal-stagger-item cap-wrap"
            :style="{ '--reveal-index': index }"
          >
            <article class="capability-card sc-glass sc-card-hover sc-card-glow" :class="`capability-card--${item.key}`">
              <span class="cap-glare" aria-hidden="true" />
              <div class="capability-visual" aria-hidden="true">
                <UseCaseScene v-if="useScene3d" :variant="item.sceneVariant" :color="item.sceneColor">
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
              <div class="capability-body">
                <span class="capability-kicker">{{ item.kicker }}</span>
                <h3>{{ item.title }}</h3>
                <p class="capability-desc">{{ item.description }}</p>
                <div class="capability-flow" aria-label="能力流程">
                  <span v-for="step in item.flow" :key="step">{{ step }}</span>
                </div>
                <div class="capability-stats" aria-label="能力数据与知识库">
                  <div class="cap-stat-row">
                    <span v-for="stat in item.statChips" :key="stat" class="cap-stat">{{ stat }}</span>
                  </div>
                  <div class="cap-kb-row" aria-label="关联知识库">
                    <span v-for="kb in item.kbChips" :key="kb" class="cap-kb">{{ kb }}</span>
                  </div>
                </div>
                <blockquote class="capability-example">「{{ item.example }}」</blockquote>
                <router-link :to="item.route" class="capability-link">
                  进入 {{ item.title }}
                  <span aria-hidden="true">→</span>
                </router-link>
              </div>
            </article>
          </div>
        </div>
      </div>
    </ShowcaseReveal3D>
  </section>
</template>

<script setup>
import { computed, h, ref } from "vue";

import UseCaseScene from "./UseCaseScene.vue";
import ShowcaseReveal3D from "./ShowcaseReveal3D.vue";
import ShowcaseSectionDecor from "./ShowcaseSectionDecor.vue";
import ShowcaseSectionHeader from "./ShowcaseSectionHeader.vue";
import { useMediaQuery, useTilt } from "../../composables/useTilt";
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
    description: "跨 KB1–KB7 检索原料、方剂、功效、风味、替代与合规证据，回答附图谱子图与证据摘要。",
    example: "麻黄可以用什么药食同源原料替代",
    flow: ["问题输入", "图谱召回", "证据回答"],
    route: { name: "chat" },
    sceneVariant: "graph",
    sceneColor: "#059669",
    statChips: ["18 类节点", "86,482 节点", "207,354 关系"],
    kbChips: ["KB1", "KB2", "…", "KB7"],
  },
  {
    key: "constitution",
    kicker: "Constitution",
    title: "体质辨识",
    icon: iconConstitution,
    description: "基于 KB8 体质食养规则库，完成九种体质测评、食养方向与慎用原料提醒。",
    example: "我是什么体质",
    flow: ["量表测评", "体质判定", "食养建议"],
    route: { name: "constitution" },
    sceneVariant: "constellation",
    sceneColor: "#ec4899",
    statChips: ["9 种体质", "30 道问卷"],
    kbChips: ["KB8"],
  },
  {
    key: "rnd",
    kicker: "R&D Agents",
    title: "研发协同",
    icon: iconRnd,
    description: "串联 KB4 替代、KB3 风味、KB5 组方等图谱证据，六步 Agent 输出研发方案与合规边界。",
    example: "把四君子汤改造成药食同源代餐粉",
    flow: ["需求拆解", "Agent 协同", "方案输出"],
    route: { name: "rnd" },
    sceneVariant: "pipeline",
    sceneColor: "#d97706",
    statChips: ["6 步工作流", "5 专家 Agent"],
    kbChips: ["KB3", "KB4", "KB5"],
  },
];

// —— 3D 倾斜：卡片组（mousemove 事件委托 + glare 跟随；reduced-motion 自动禁用）——
const tiltScope = ref(null);
const tilt = useTilt(tiltScope, {
  selector: ".capability-card",
  maxDeg: 6,
  perspective: 900,
  liftY: -3,
  hoverScale: 1,
});
</script>

<style scoped>
.capability-section {
  position: relative;
}

.section-inner {
  position: relative;
  z-index: 1;
}

.capability-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1.5rem;
}

.cap-wrap {
  display: flex;
}

.capability-card {
  position: relative;
  border-radius: var(--sc-radius-md);
  overflow: hidden;
  height: 100%;
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--sc-bg-panel);
  border: 1px solid rgba(15, 23, 42, 0.08);
  transform-style: preserve-3d;
  will-change: transform;
}

/* —— 渐变描边（hover 淡入，mask 勾勒 1.5px 环线）—— */
.capability-card::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 1.5px;
  background: linear-gradient(135deg, var(--cap-border-a, rgba(5, 150, 105, 0.55)), rgba(255, 255, 255, 0.08) 38%, var(--cap-border-b, rgba(217, 119, 6, 0.45)));
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  mask-composite: exclude;
  opacity: 0;
  transition: opacity 0.4s ease;
  pointer-events: none;
  z-index: 2;
}

.capability-card:hover::after {
  opacity: 1;
}

.capability-card--qa {
  --cap-border-a: rgba(5, 150, 105, 0.62);
  --cap-border-b: rgba(52, 211, 153, 0.28);
  border-top: 3px solid rgba(5, 150, 105, 0.55);
}

.capability-card--constitution {
  --cap-border-a: rgba(236, 72, 153, 0.55);
  --cap-border-b: rgba(244, 114, 182, 0.3);
  border-top: 3px solid rgba(236, 72, 153, 0.45);
}

.capability-card--rnd {
  --cap-border-a: rgba(217, 119, 6, 0.6);
  --cap-border-b: rgba(251, 191, 36, 0.3);
  border-top: 3px solid rgba(217, 119, 6, 0.55);
}

/* —— 高光 glare（--tilt-gx / --tilt-gy 由 useTilt 每帧更新）—— */
.cap-glare {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  border-radius: inherit;
  background: radial-gradient(
    300px circle at var(--tilt-gx, 50%) var(--tilt-gy, 50%),
    rgba(255, 255, 255, 0.32),
    rgba(255, 255, 255, 0) 55%
  );
  mix-blend-mode: overlay;
  opacity: 0;
  transition: opacity 0.35s ease;
}

.capability-card.tilt-hover .cap-glare {
  opacity: 1;
}

.capability-visual {
  position: relative;
  height: 140px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--sc-accent);
  background:
    radial-gradient(circle at 50% 80%, rgba(5, 150, 105, 0.08), transparent 65%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.4), transparent);
}

.capability-card--constitution .capability-visual {
  color: #ec4899;
  background:
    radial-gradient(circle at 50% 80%, rgba(236, 72, 153, 0.06), transparent 65%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.4), transparent);
}

.capability-card--rnd .capability-visual {
  color: var(--sc-highlight);
  background:
    radial-gradient(circle at 50% 80%, rgba(217, 119, 6, 0.08), transparent 65%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.4), transparent);
}

/* 视觉区径向光晕呼吸（场景 canvas 之下，SVG 回退时同样生效） */
.capability-visual::before {
  content: "";
  position: absolute;
  inset: -20%;
  z-index: 0;
  pointer-events: none;
  background: radial-gradient(circle at 50% 62%, var(--cap-visual-glow, rgba(5, 150, 105, 0.14)), transparent 58%);
  animation: capGlowBreathe 5.2s ease-in-out infinite;
}

.capability-card--qa {
  --cap-visual-glow: rgba(5, 150, 105, 0.16);
}

.capability-card--constitution {
  --cap-visual-glow: rgba(236, 72, 153, 0.13);
}

.capability-card--rnd {
  --cap-visual-glow: rgba(217, 119, 6, 0.15);
}

@keyframes capGlowBreathe {
  0%, 100% { opacity: 0.45; transform: scale(0.96); }
  50% { opacity: 1; transform: scale(1.06); }
}

/* 场景容器占满视觉区；WebGL 回退时 slot 图标在其内居中 */
.capability-visual :deep(.use-case-scene) {
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100%;
}

.capability-visual :deep(.cap-icon) {
  position: relative;
  z-index: 1;
  width: 72px;
  height: 72px;
}

.visual-orbit {
  position: absolute;
  width: 112px;
  height: 112px;
  border: 1px dashed currentColor;
  border-radius: 50%;
  opacity: 0.16;
  animation: capOrbit 18s linear infinite;
}

@keyframes capOrbit {
  to { transform: rotate(360deg); }
}

.capability-body {
  padding: 1.5rem 1.75rem 2rem;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.capability-kicker {
  display: block;
  margin-bottom: 0.5rem;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--sc-muted);
}

.capability-body h3 {
  margin: 0 0 0.85rem;
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--sc-text);
}

.capability-desc {
  margin: 0 0 auto;
  color: var(--sc-text-secondary);
  font-size: 0.95rem;
  line-height: 1.7;
}

.capability-flow {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.35rem;
  margin: 1.35rem 0 0;
}

.capability-flow span {
  position: relative;
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.4rem 0.45rem;
  border-radius: 999px;
  background: rgba(5, 150, 105, 0.075);
  color: var(--sc-accent);
  font-size: 0.75rem;
  font-weight: 700;
  white-space: nowrap;
}

.capability-card--constitution .capability-flow span {
  background: rgba(236, 72, 153, 0.075);
  color: #db2777;
}

.capability-card--rnd .capability-flow span {
  background: rgba(217, 119, 6, 0.08);
  color: var(--sc-highlight);
}

/* —— stat chips 行（flow 下方数据与 KB 标签区）—— */
.capability-stats {
  margin: 1.15rem 0 0;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.cap-stat-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.cap-stat {
  display: inline-flex;
  align-items: center;
  padding: 0.32rem 0.62rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 650;
  letter-spacing: 0.01em;
  background: rgba(5, 150, 105, 0.07);
  color: var(--sc-accent);
  border: 1px solid rgba(5, 150, 105, 0.16);
  white-space: nowrap;
}

.capability-card--constitution .cap-stat {
  background: rgba(236, 72, 153, 0.06);
  color: #db2777;
  border-color: rgba(236, 72, 153, 0.18);
}

.capability-card--rnd .cap-stat {
  background: rgba(217, 119, 6, 0.07);
  color: var(--sc-highlight);
  border-color: rgba(217, 119, 6, 0.18);
}

.cap-kb-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.cap-kb {
  display: inline-flex;
  align-items: center;
  padding: 0.22rem 0.52rem;
  border-radius: 7px;
  font-size: 0.68rem;
  font-weight: 700;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: 0.04em;
  background: rgba(15, 23, 42, 0.05);
  color: var(--sc-text-secondary);
  border: 1px solid rgba(15, 23, 42, 0.07);
}

.capability-card--constitution .cap-kb {
  background: rgba(236, 72, 153, 0.06);
  color: #be185d;
  border-color: rgba(236, 72, 153, 0.16);
}

.capability-card--rnd .cap-kb {
  background: rgba(217, 119, 6, 0.06);
  color: #b45309;
  border-color: rgba(217, 119, 6, 0.16);
}

.capability-example {
  margin: 1.5rem 0 1.5rem;
  padding: 0.85rem 1rem;
  border-left: 3px solid var(--sc-accent);
  background: rgba(0, 0, 0, 0.03);
  color: var(--sc-text-secondary);
  font-size: 0.9rem;
  border-radius: 0 var(--sc-radius-sm) var(--sc-radius-sm) 0;
}

.capability-card--rnd .capability-example {
  border-left-color: var(--sc-highlight);
  background: rgba(217, 119, 6, 0.04);
}

.capability-card--constitution .capability-example {
  border-left-color: #ec4899;
  background: rgba(236, 72, 153, 0.04);
}

.capability-link {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  color: var(--sc-accent);
  text-decoration: none;
  font-size: 0.875rem;
  font-weight: 600;
  transition: gap 0.25s ease;
}

.capability-link:hover {
  gap: 0.55rem;
}

@media (max-width: 900px) {
  .capability-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .capability-grid {
    grid-template-columns: 1fr;
  }

  .capability-flow {
    grid-template-columns: 1fr;
  }
}
</style>
