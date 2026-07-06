<template>
  <section id="knowledge-bases" class="sc-section sc-section--deep kb-section">
    <ShowcaseSectionDecor tone="blue" />
    <ShowcaseReveal3D variant="up" stagger>
      <div class="showcase-container kb-container">
        <ShowcaseSectionHeader
          eyebrow="Knowledge Graph"
          title="八类知识库 · 证据底座"
          lead="每张知识库表回答一类核心问题——原料能不能用、功效如何关联、风味是否可接受、如何替代、方剂怎样组成、产品处于什么市场、宣传是否合规、体质如何食养。"
        />
        <div class="kb-layout">
          <div class="kb-graph-panel sc-glass" aria-hidden="true">
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
              <g v-for="(kb, i) in knowledgeBases" :key="kb.id">
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
            <p class="kb-panel-caption">悬停右侧卡片，查看知识库关联</p>
            <transition name="kb-detail-fade">
              <div v-if="activeKb" class="kb-detail">
                <span :style="{ color: activeKb.color }">{{ activeKb.id }} Evidence</span>
                <strong>{{ activeKb.name }}</strong>
                <p>{{ activeKb.detail }}</p>
              </div>
            </transition>
          </div>
          <div class="kb-list">
            <button
              v-for="(kb, index) in knowledgeBases"
              :key="kb.id"
              type="button"
              class="reveal-stagger-item kb-item sc-glass-subtle sc-card-hover sc-card-glow"
              :class="{ active: activeId === kb.id }"
              :style="{ '--reveal-index': index }"
              @mouseenter="activeId = kb.id"
              @focus="activeId = kb.id"
            >
              <span class="kb-id" :style="{ color: kb.color }">{{ kb.id }}</span>
              <span class="kb-name">{{ kb.name }}</span>
              <span class="kb-purpose">{{ kb.purpose }}</span>
            </button>
          </div>
        </div>
      </div>
    </ShowcaseReveal3D>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";

import ShowcaseReveal3D from "./ShowcaseReveal3D.vue";
import ShowcaseSectionDecor from "./ShowcaseSectionDecor.vue";
import ShowcaseSectionHeader from "./ShowcaseSectionHeader.vue";

const activeId = ref("KB1");

const palette = ["#6bc4a6", "#6a9ec4", "#c9a962", "#ec4899"];

const knowledgeBases = [
  {
    id: "KB1",
    name: "药食同源原料合法性库",
    purpose: "哪些原料能用",
    color: palette[0],
    detail: "定义原料是否进入药食同源目录、合法使用边界、毒性风险与配伍禁忌，是合规审查与风险提示的入口表。",
  },
  {
    id: "KB2",
    name: "功效-病症-性味归经库",
    purpose: "功效如何关联病症",
    color: palette[1],
    detail: "组织功效分类、病症主治、中医性味归经与禁忌规则，支撑功效预测、方剂分析与证据召回。",
  },
  {
    id: "KB3",
    name: "风味评价库",
    purpose: "风味是否可接受",
    color: palette[2],
    detail: "记录苦味、涩感、药味风险、香气层次与综合接受度，支撑产品风味评估与优化决策。",
  },
  {
    id: "KB4",
    name: "单味药替代评分库",
    purpose: "非同源原料如何替",
    color: palette[0],
    detail: "维护 CAN_REPLACE 替代评分与多维映射关系，支撑方剂药食同源化改造时的取舍说明。",
  },
  {
    id: "KB5",
    name: "名方/方剂知识库",
    purpose: "经典方如何组成",
    color: palette[1],
    detail: "收录名方来源、方剂组成、君臣佐使结构与功效主治，是组方设计与改造的结构化依据。",
  },
  {
    id: "KB6",
    name: "产品与市场库",
    purpose: "产品处于什么市场",
    color: palette[2],
    detail: "覆盖产品档案、品牌剂型、消费场景、卖点标签与竞品对照，支撑市场分析与定位判断。",
  },
  {
    id: "KB7",
    name: "食品标准合规库",
    purpose: "宣传与标签是否合规",
    color: palette[3],
    detail: "汇聚药食同源目录、GB2760/GB7718 与宣传边界规则，定义禁用、慎用表述与审查依据。",
  },
  {
    id: "KB8",
    name: "体质辨识与食养规则库",
    purpose: "不同体质如何食养",
    color: palette[1],
    detail: "包含九种体质问卷、评分规则、食养方向与慎用原料清单，支撑个体化辨识与推荐。",
  },
];

const activeKb = computed(() => knowledgeBases.find((kb) => kb.id === activeId.value));

const nodePos = (index) => {
  const angle = (index / knowledgeBases.length) * Math.PI * 2 - Math.PI / 2;
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
.kb-section {
  position: relative;
}

.kb-container {
  position: relative;
  z-index: 1;
}

.kb-layout {
  display: grid;
  grid-template-columns: minmax(300px, 420px) 1fr;
  gap: 1.75rem;
  align-items: start;
}

.kb-graph-panel {
  position: sticky;
  top: 6rem;
  padding: 1.5rem;
  border-radius: var(--sc-radius-lg);
  text-align: center;
  color: #e5f8f1;
  background:
    radial-gradient(circle at 50% 40%, rgba(94, 234, 212, 0.16), transparent 42%),
    linear-gradient(145deg, rgba(5, 24, 20, 0.94), rgba(10, 18, 17, 0.9));
  border: 1px solid rgba(148, 216, 198, 0.2);
  box-shadow: 0 28px 70px rgba(10, 18, 17, 0.22);
  overflow: hidden;
}

.kb-graph-panel::before {
  content: "";
  position: absolute;
  inset: 0;
  background:
    linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.045) 1px, transparent 1px);
  background-size: 34px 34px;
  mask-image: radial-gradient(circle at 50% 42%, #000 0%, transparent 75%);
  pointer-events: none;
}

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

/* 中心核呼吸光晕 */
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

/* active 弧线：dashoffset 流动 */
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

.kb-panel-caption {
  margin: 0.75rem 0 0;
  font-size: 0.75rem;
  color: rgba(229, 248, 241, 0.58);
}

.kb-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.kb-item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.35rem;
  width: 100%;
  min-height: 118px;
  padding: 1.2rem 1.25rem;
  border-radius: var(--sc-radius-md);
  color: var(--sc-text);
  text-align: left;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(15, 23, 42, 0.06);
  overflow: hidden;
  transition: border-color 0.25s ease, background 0.25s ease, transform 0.3s ease, box-shadow 0.3s ease;
}

/* active 卡片左侧 accent 竖条 */
.kb-item::after {
  content: "";
  position: absolute;
  left: 0;
  top: 12%;
  bottom: 12%;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--sc-accent);
  transform: scaleY(0);
  transform-origin: center;
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.kb-item.active::after {
  transform: scaleY(1);
}

.kb-item:hover,
.kb-item:focus,
.kb-item.active {
  outline: none;
  border-color: rgba(5, 150, 105, 0.2);
  background: rgba(5, 150, 105, 0.04);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.05);
}

.kb-id {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.05em;
}

.kb-name {
  font-size: 1.05rem;
  font-weight: 700;
}

.kb-purpose {
  font-size: 0.85rem;
  color: var(--sc-text-secondary);
}

.kb-detail {
  margin-top: 1.25rem;
  padding: 1rem 1.1rem;
  border-radius: 14px;
  text-align: left;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.11);
}

.kb-detail span {
  display: block;
  margin-bottom: 0.35rem;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.kb-detail strong {
  display: block;
  margin-bottom: 0.45rem;
  color: #f8fafc;
  font-size: 1rem;
}

.kb-detail p {
  margin: 0;
  color: rgba(229, 248, 241, 0.72);
  font-size: 0.86rem;
  line-height: 1.65;
}

.kb-detail-fade-enter-active,
.kb-detail-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.kb-detail-fade-enter-from,
.kb-detail-fade-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

@keyframes kbOrbitSpin {
  to { transform: rotate(360deg); }
}

@keyframes kbCorePulse {
  0%, 100% { opacity: 0.85; }
  50% { opacity: 1; }
}

@media (max-width: 900px) {
  .kb-layout {
    grid-template-columns: 1fr;
  }

  .kb-graph-panel {
    position: static;
  }

  .kb-list {
    grid-template-columns: 1fr;
  }
}
</style>
