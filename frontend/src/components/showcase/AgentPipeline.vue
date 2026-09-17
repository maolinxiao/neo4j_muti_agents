<template>
  <section id="agents" class="sc-section sc-section--deep agent-section">
    <ShowcaseSectionDecor tone="gold" />
    <ShowcaseReveal3D variant="up" stagger>
      <div class="showcase-container section-inner">
      <ShowcaseSectionHeader
        eyebrow="Agent Pipeline"
        title="研发协同流程"
        lead="需求进入后，主控 Agent 调度方剂生成、功效预测、风味预测与替代映射，最终汇总为可交付方案。"
      />
      <div class="pipeline-toolbar">
        <button type="button" class="mission-btn" :class="{ active: missionActive }" @click="toggleMission">
          <span class="mission-dot" aria-hidden="true" />
          {{ missionActive ? "停止演示" : "演示一轮研发任务" }}
        </button>
        <span class="mission-hint">{{
          missionActive
            ? "任务执行中——依次点亮六站"
            : "进度将依次点亮六站，走完一条完整研发链路"
        }}</span>
      </div>
      <div ref="pipelineRef" class="pipeline" :class="{ 'pipeline--vertical': isNarrow }">
        <div class="track">
          <span class="track-line" aria-hidden="true" />
          <span
            class="track-fill"
            :style="isNarrow ? { height: fillPercent + '%' } : { width: fillPercent + '%' }"
            aria-hidden="true"
          />
          <div
            v-for="(agent, index) in agents"
            :key="agent.key"
            class="station-wrap"
            :class="{ 'station-current': focusedKey === agent.key }"
            :style="{ '--reveal-index': index }"
          >
            <button
              type="button"
              class="step-node"
              :class="{ active: focusedKey === agent.key, done: index < focusedIndex }"
              :aria-expanded="focusedKey === agent.key"
              :aria-label="`第 ${index + 1} 步 ${agent.name}`"
              @click="toggle(agent.key)"
            >
              <span class="station-mark">{{ index < focusedIndex ? "✓" : index + 1 }}</span>
            </button>
            <span class="station-name">{{ agent.name }}</span>
          </div>
        </div>
      </div>
      <transition name="detail-fade" mode="out-in">
        <div :key="activeAgent.key" class="pipeline-detail sc-glass">
          <div class="detail-grid">
            <div class="detail-main">
              <div class="detail-head">
                <span class="detail-step-badge">第 {{ activeIndex + 1 }} 步</span>
                <span class="detail-kicker">{{ activeAgent.key }}</span>
              </div>
              <h3>{{ activeAgent.name }}</h3>
              <p>{{ activeAgent.role }}</p>
              <p class="detail-extra">{{ activeAgent.detail }}</p>
              <div class="detail-kb-row" aria-label="关联知识库">
                <span v-for="kb in activeAgent.kb" :key="kb" class="detail-kb">{{ kb }}</span>
              </div>
            </div>
            <div class="detail-deliver" aria-label="阶段产出">
              <span class="deliver-kicker">Stage Output · 阶段产出</span>
              <ul>
                <li
                  v-for="(d, i) in activeAgent.deliverables"
                  :key="d"
                  class="deliver-item"
                  :style="{ animationDelay: `${120 + i * 120}ms` }"
                >
                  {{ d }}
                </li>
              </ul>
            </div>
          </div>
        </div>
      </transition>
      </div>
    </ShowcaseReveal3D>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";

import ShowcaseReveal3D from "./ShowcaseReveal3D.vue";
import ShowcaseSectionDecor from "./ShowcaseSectionDecor.vue";
import ShowcaseSectionHeader from "./ShowcaseSectionHeader.vue";
import { useMediaQuery } from "../../composables/useTilt";
import { useShowcaseMotionPreference } from "../../composables/useShowcaseMotionPreference";

const agents = [
  {
    key: "master_control",
    name: "主控 Agent",
    role: "需求拆解、模块调度、逻辑校验与方案整合。",
    detail: "识别研发目标，分配后续专家 Agent，并校验各步输出一致性。",
    kb: ["综合"],
    deliverables: ["研发需求拆解", "任务执行计划"],
  },
  {
    key: "formula_generation",
    name: "方剂生成专家",
    role: "组方设计、君臣佐使配伍、剂量建模与方解撰写。",
    detail: "基于图谱证据生成药食同源化组方草案，并做初步合规校验。",
    kb: ["KB1", "KB2", "KB5"],
    deliverables: ["药食同源组方草案", "君臣佐使配比"],
  },
  {
    key: "efficacy_prediction",
    name: "功效预测专家",
    role: "中医功效、现代药理与人群分层风险评估。",
    detail: "连接 KB2 功效-病症库，输出功效预测与适配人群说明。",
    kb: ["KB2"],
    deliverables: ["功效预测报告", "适用人群分层"],
  },
  {
    key: "flavor_prediction",
    name: "风味预测专家",
    role: "风味特征、协调性、缺陷识别与优化建议。",
    detail: "连接 KB3 风味评价库，评估苦味、涩感与接受度风险。",
    kb: ["KB3"],
    deliverables: ["风味轮廓评估", "苦涩风险与优化建议"],
  },
  {
    key: "replacement_mapping",
    name: "替代映射专家",
    role: "功效/风味/成本/合规/工艺/供应链替代方案。",
    detail: "连接 KB4 替代评分库，输出 CAN_REPLACE 映射与取舍说明。",
    kb: ["KB4", "KB7"],
    deliverables: ["替代映射方案", "合规与成本取舍"],
  },
  {
    key: "master_control_final",
    name: "最终主控汇总",
    role: "整合各模块输出，形成最终研发方案。",
    detail: "汇总证据、风险提示与后续建议，供研发决策使用。",
    kb: ["综合"],
    deliverables: ["最终研发方案", "证据与风险清单"],
  },
];

const { preferReducedMotion } = useShowcaseMotionPreference();
const isNarrow = useMediaQuery("(max-width: 767px)");

// —— 焦点与自动巡游 ——
const pipelineRef = ref(null);
const focusedIndex = ref(0);
const focusedKey = computed(() => agents[focusedIndex.value].key);
const activeAgent = computed(() => agents[focusedIndex.value]);
const activeIndex = computed(() => focusedIndex.value);
const fillPercent = computed(() => (focusedIndex.value / (agents.length - 1)) * 100);

const focusAgent = (index, { restartCarousel = false } = {}) => {
  const i = ((index % agents.length) + agents.length) % agents.length;
  focusedIndex.value = i;
  if (restartCarousel) startCarousel();
};

const toggle = (key) => {
  const index = agents.findIndex((agent) => agent.key === key);
  if (index >= 0) focusAgent(index, { restartCarousel: !hoveringPipeline.value && !missionActive.value });
};

let carouselTimer = null;
const hoveringPipeline = ref(false);

const startCarousel = () => {
  stopCarousel();
  if (preferReducedMotion.value) return;
  if (missionActive.value) return; // 任务演示期间不让位给自动巡游
  carouselTimer = window.setInterval(() => {
    if (document.hidden) return;
    focusAgent(focusedIndex.value + 1);
  }, 4000);
};

const pauseCarousel = () => {
  hoveringPipeline.value = true;
  stopCarousel();
};

const resumeCarousel = () => {
  hoveringPipeline.value = false;
  if (missionActive.value) return; // 演示进行中不受 hover 恢复影响
  startCarousel();
};

const stopCarousel = () => {
  if (carouselTimer != null) {
    window.clearInterval(carouselTimer);
    carouselTimer = null;
  }
};

// —— 任务演示：进度逐站推进，每站切换详情与交付物 ——
const missionActive = ref(false);
let missionTimer = null;
let missionIdx = 0;

const toggleMission = () => {
  if (missionActive.value) stopMission(false);
  else startMission();
};

const startMission = () => {
  missionActive.value = true;
  stopCarousel();
  missionIdx = 0;
  focusAgent(0);
  missionTimer = window.setInterval(() => {
    missionIdx += 1;
    if (missionIdx >= agents.length) {
      stopMission(true);
      return;
    }
    focusAgent(missionIdx);
  }, 1500);
};

const stopMission = (finished) => {
  missionActive.value = false;
  if (missionTimer != null) {
    window.clearInterval(missionTimer);
    missionTimer = null;
  }
  if (finished) {
    window.setTimeout(() => {
      if (!missionActive.value) startCarousel();
    }, 2000);
  } else {
    startCarousel();
  }
};

onMounted(() => {
  startCarousel();
});

onUnmounted(() => {
  stopCarousel();
  if (missionTimer != null) {
    window.clearInterval(missionTimer);
    missionTimer = null;
  }
});
</script>

<style scoped>
.agent-section {
  position: relative;
}

.section-inner {
  position: relative;
  z-index: 1;
}

/* —— 任务演示工具栏 —— */
.pipeline-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.9rem;
  margin-bottom: 1.1rem;
}

.mission-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.55rem 1.15rem;
  border-radius: 999px;
  border: 1px solid rgba(5, 150, 105, 0.32);
  background: linear-gradient(120deg, rgba(5, 150, 105, 0.1), rgba(217, 119, 6, 0.08));
  color: var(--sc-accent);
  font-weight: 700;
  font-size: 0.88rem;
  font-family: inherit;
  cursor: pointer;
  transition: transform 0.25s ease, box-shadow 0.25s ease, background 0.25s ease, color 0.25s ease;
}

.mission-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 22px rgba(5, 150, 105, 0.16);
}

.mission-btn.active {
  background: var(--sc-accent);
  border-color: var(--sc-accent);
  color: #ffffff;
}

.mission-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

.mission-btn.active .mission-dot {
  animation: missionPulse 1s ease-in-out infinite;
}

@keyframes missionPulse {
  0%, 100% { opacity: 0.5; transform: scale(0.85); }
  50% { opacity: 1; transform: scale(1.18); }
}

.mission-hint {
  font-size: 0.8rem;
  color: var(--sc-muted);
}

/* —— 极简进度轴 —— */
.pipeline {
  position: relative;
  padding: 2rem 1.8rem 1.5rem;
  border-radius: var(--sc-radius-lg);
  background:
    linear-gradient(90deg, rgba(5, 150, 105, 0.05), rgba(217, 119, 6, 0.04)),
    rgba(255, 255, 255, 0.58);
  border: 1px solid rgba(15, 23, 42, 0.06);
}

.track {
  position: relative;
  display: flex;
}

.track-line,
.track-fill {
  position: absolute;
  top: 23px;
  height: 2px;
  border-radius: 2px;
}

/* 轴线位于首末站点圆心之间（站点各占 1/6，圆心在 1/12 与 11/12 处） */
.track-line {
  left: calc(100% / 12);
  right: calc(100% / 12);
  background: rgba(15, 23, 42, 0.1);
}

.track-fill {
  left: calc(100% / 12);
  width: 0%;
  background: linear-gradient(90deg, #059669, #d97706);
  transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1);
}

.station-wrap {
  position: relative;
  z-index: 1;
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.55rem;
}

.step-node {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  border: 2px solid rgba(5, 150, 105, 0.25);
  background: #ffffff;
  color: var(--sc-accent);
  font-size: 1rem;
  font-weight: 750;
  font-family: inherit;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), background 0.3s ease, border-color 0.3s ease, color 0.3s ease, box-shadow 0.3s ease;
}

.step-node:hover {
  transform: scale(1.08);
  border-color: rgba(5, 150, 105, 0.5);
}

.step-node.done {
  background: rgba(5, 150, 105, 0.1);
  border-color: rgba(5, 150, 105, 0.4);
}

.step-node.active {
  width: 52px;
  height: 52px;
  background: var(--sc-accent);
  border-color: var(--sc-accent);
  color: #ffffff;
  box-shadow:
    0 0 0 6px rgba(5, 150, 105, 0.13),
    0 10px 26px rgba(5, 150, 105, 0.3);
  animation: stationGlow 3s ease-in-out infinite;
}

@keyframes stationGlow {
  0%, 100% { box-shadow: 0 0 0 6px rgba(5, 150, 105, 0.13), 0 10px 26px rgba(5, 150, 105, 0.3); }
  50% { box-shadow: 0 0 0 9px rgba(5, 150, 105, 0.09), 0 12px 32px rgba(5, 150, 105, 0.38); }
}

.station-name {
  font-size: 0.82rem;
  font-weight: 650;
  color: var(--sc-text-secondary);
  text-align: center;
  transition: color 0.3s ease;
}

.station-current .station-name {
  color: var(--sc-text);
  font-weight: 750;
}

/* —— 详情面板（双栏：阶段信息 / 阶段产出）—— */
.pipeline-detail {
  margin-top: 1.4rem;
  padding: 1.45rem 1.6rem;
  border-radius: var(--sc-radius-md);
  background:
    radial-gradient(circle at 8% 0%, rgba(5, 150, 105, 0.12), transparent 34%),
    var(--sc-bg-panel);
  border: 1px solid rgba(5, 150, 105, 0.12);
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr);
  gap: 1.4rem;
  align-items: start;
}

.detail-head {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.45rem;
}

.detail-step-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.22rem 0.62rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 750;
  background: rgba(5, 150, 105, 0.12);
  color: var(--sc-accent);
  border: 1px solid rgba(5, 150, 105, 0.24);
  white-space: nowrap;
}

.detail-kicker {
  color: var(--sc-accent);
  font-family: ui-monospace, monospace;
  font-size: 0.75rem;
  font-weight: 800;
}

.pipeline-detail h3 {
  margin: 0 0 0.55rem;
  color: var(--sc-text);
  font-size: 1.2rem;
}

.pipeline-detail p {
  margin: 0;
  font-size: 0.92rem;
  color: var(--sc-text);
  line-height: 1.65;
}

.detail-extra {
  margin-top: 0.45rem !important;
  color: var(--sc-muted) !important;
}

.detail-kb-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 1rem;
  padding-top: 0.9rem;
  border-top: 1px dashed rgba(0, 0, 0, 0.08);
}

.detail-kb {
  display: inline-flex;
  align-items: center;
  padding: 0.28rem 0.62rem;
  border-radius: 7px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  background: rgba(5, 150, 105, 0.07);
  color: #047857;
  border: 1px solid rgba(5, 150, 105, 0.18);
}

.detail-deliver {
  padding: 1rem 1.15rem 1.1rem;
  border-radius: 12px;
  background: rgba(5, 150, 105, 0.05);
  border: 1px dashed rgba(5, 150, 105, 0.3);
}

.deliver-kicker {
  display: block;
  margin-bottom: 0.62rem;
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--sc-accent);
}

.detail-deliver ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.deliver-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--sc-text);
  animation: deliverPop 0.45s cubic-bezier(0.16, 1, 0.3, 1) both;
}

.deliver-item::before {
  content: "✓";
  color: var(--sc-accent);
  font-weight: 800;
}

@keyframes deliverPop {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
}

.detail-fade-enter-active {
  transition: opacity 0.32s cubic-bezier(0.16, 1, 0.3, 1), transform 0.32s cubic-bezier(0.16, 1, 0.3, 1);
}

.detail-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.detail-fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.detail-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* —— 移动端：竖向进度轴 —— */
@media (max-width: 767px) {
  .pipeline {
    padding: 1.6rem 1.3rem 1.3rem;
  }

  .track {
    flex-direction: column;
    gap: 1.05rem;
  }

  .track-line,
  .track-fill {
    left: 23px;
    right: auto;
    width: 2px;
    height: auto;
  }

  .track-line {
    top: 23px;
    bottom: 23px;
  }

  .track-fill {
    top: 23px;
    transition: height 0.6s cubic-bezier(0.22, 1, 0.36, 1);
  }

  .station-wrap {
    flex-direction: row;
    align-items: center;
    gap: 0.9rem;
  }

  .station-name {
    text-align: left;
  }

  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
