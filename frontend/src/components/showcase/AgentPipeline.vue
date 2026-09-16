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
            ? "任务执行中——彗星依次停靠六站"
            : "彗星将依次停靠六站，走完一条完整研发链路"
        }}</span>
      </div>
      <div
        ref="pipelineRef"
        class="pipeline"
        :class="{ 'pipeline--no-scene': !useScene3d, 'pipeline--arc': isArc }"
        @mouseenter="pauseCarousel"
        @mouseleave="resumeCarousel(); tilt.onLeave()"
        @transitionend.capture="scheduleMeasure"
        @mousemove="tilt.onMove"
      >
        <AgentFlowScene
          v-if="useScene3d"
          ref="flowScene"
          class="pipeline-scene"
          color-a="#059669"
          color-b="#d97706"
          @resize="scheduleMeasure"
        />
        <template v-for="(agent, index) in agents" :key="agent.key">
          <div class="reveal-stagger-item pipeline-item" :style="itemStyle(index)">
            <button
              type="button"
              class="step-node sc-glass-subtle sc-card-hover sc-card-glow"
              :class="{ active: focusedKey === agent.key }"
              :aria-expanded="focusedKey === agent.key"
              :ref="(el) => { if (el) stepNodes[index] = el; }"
              @click="toggle(agent.key)"
            >
              <span class="step-index">{{ index + 1 }}</span>
              <span class="step-name">{{ agent.name }}</span>
              <span class="step-key">{{ agent.key }}</span>
            </button>
          </div>
          <!-- canvas 激活时由 3D 能量轨道承担连接表达；虚线连接线仅作无 canvas 回退 -->
          <div v-if="index < agents.length - 1 && !useScene3d" class="step-connector" aria-hidden="true">
            <span class="connector-line" />
          </div>
        </template>
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
import { computed, onMounted, onUnmounted, ref, nextTick } from "vue";

import AgentFlowScene from "./AgentFlowScene.vue";
import ShowcaseReveal3D from "./ShowcaseReveal3D.vue";
import ShowcaseSectionDecor from "./ShowcaseSectionDecor.vue";
import ShowcaseSectionHeader from "./ShowcaseSectionHeader.vue";
import { useMediaQuery, useTilt } from "../../composables/useTilt";
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
const useScene3d = computed(() => !preferReducedMotion.value && !isNarrow.value);
// 浅弧轨道：宽屏（≥1081px）+ canvas 激活时启用，节点沿上弧排布
const isWide = useMediaQuery("(min-width: 1081px)");
const isArc = computed(() => isWide.value && useScene3d.value);

const arcLift = (index) => 44 * Math.sin((Math.PI * index) / (agents.length - 1));

/** 弧形布局：节点中心沿浅弧定位（left/top 定位，不用 transform，避免与 reveal/tilt 冲突） */
const itemStyle = (index) => {
  const base = { "--reveal-index": index };
  if (!isArc.value) return base;
  return {
    ...base,
    left: `calc(${(((index + 0.5) * 100) / agents.length).toFixed(3)}% - 84px)`,
    top: `calc(56% - ${arcLift(index).toFixed(1)}px - 60px)`,
  };
};

// —— 任务演示：彗星依次停靠六站，每站切换详情与交付物 ——
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
  // 演示结束后稍作停留，再恢复自动巡游
  if (finished) {
    window.setTimeout(() => {
      if (!missionActive.value) startCarousel();
    }, 2000);
  } else {
    startCarousel();
  }
};

// —— AgentFlowScene 接入：六节点坐标测量 + 自动轮播 ——
const pipelineRef = ref(null);
const flowScene = ref(null);
const stepNodes = ref([]);

const focusedIndex = ref(0);
const focusedKey = computed(() => agents[focusedIndex.value].key);
const activeAgent = computed(() => agents[focusedIndex.value]);
const activeIndex = computed(() => focusedIndex.value);

const focusAgent = (index, { restartCarousel = false } = {}) => {
  const i = ((index % agents.length) + agents.length) % agents.length;
  focusedIndex.value = i;
  // 场景可用时联动 3D 脉冲（webglOk 已被暴露并解包为布尔；setActive 内部对未挂载场景安全返回）
  if (flowScene.value?.webglOk) {
    flowScene.value.setActive(i);
  }
  if (restartCarousel) startCarousel();
};

const toggle = (key) => {
  const index = agents.findIndex((agent) => agent.key === key);
  // 悬停中点击保持暂停；非悬停（如外部触发）点击后重启计时
  if (index >= 0) focusAgent(index, { restartCarousel: !hoveringPipeline.value });
};

// —— 坐标测量：.step-node 中心相对 .pipeline ——
const measureNodes = () => {
  const scene = flowScene.value;
  const pipeline = pipelineRef.value;
  if (!scene || !pipeline) return;
  if (!scene.webglOk) return;
  const box = pipeline.getBoundingClientRect();
  const rects = stepNodes.value
    .filter(Boolean)
    .map((el) => {
      const r = el.getBoundingClientRect();
      return { x: r.left + r.width / 2 - box.left, y: r.top + r.height / 2 - box.top };
    })
    .filter((r) => Number.isFinite(r.x) && Number.isFinite(r.y));
  if (rects.length >= 2) scene.setNodes(rects);
};

let measureRaf = null;
const scheduleMeasure = () => {
  if (measureRaf != null) return;
  measureRaf = window.requestAnimationFrame(() => {
    measureRaf = null;
    measureNodes();
  });
};

let resizeObserver = null;
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

onMounted(async () => {
  await nextTick();
  measureNodes();
  requestAnimationFrame(measureNodes);
  // reveal 动画结束后坐标归位，再补一次
  window.setTimeout(measureNodes, 700);
  resizeObserver = new ResizeObserver(scheduleMeasure);
  if (pipelineRef.value) resizeObserver.observe(pipelineRef.value);
  startCarousel();
});

onUnmounted(() => {
  stopCarousel();
  if (missionTimer != null) {
    window.clearInterval(missionTimer);
    missionTimer = null;
  }
  resizeObserver?.disconnect();
  resizeObserver = null;
  if (measureRaf != null) window.cancelAnimationFrame(measureRaf);
});

// —— 节点 3D 倾斜（±3° 微动）——
const tilt = useTilt(pipelineRef, {
  selector: ".step-node",
  maxDeg: 3,
  perspective: 900,
  liftY: -3,
  hoverScale: 1,
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
  margin-bottom: 1rem;
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

/* —— 浅弧轨道布局（宽屏 + canvas 激活）：节点沿上弧排布，替代水平直线 —— */
.pipeline--arc {
  display: block;
  height: 336px;
}

.pipeline--arc .pipeline-item {
  position: absolute;
  width: 168px;
  max-width: none;
  flex: none;
}

.pipeline {
  position: relative;
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.85rem;
  border-radius: var(--sc-radius-lg);
  background:
    linear-gradient(90deg, rgba(5, 150, 105, 0.08), rgba(217, 119, 6, 0.06)),
    rgba(255, 255, 255, 0.58);
  border: 1px solid rgba(15, 23, 42, 0.06);
}

/* —— AgentFlowScene canvas 铺满 .pipeline（z-index:0），DOM 节点叠于其上 —— */
.pipeline .pipeline-scene {
  position: absolute;
  inset: 0;
  z-index: 0;
  width: 100%;
  height: 100%;
}

/* 无 canvas 回退模式下的水平基线（canvas 激活时由 3D 轨道承担） */
.pipeline--no-scene::before {
  content: "";
  position: absolute;
  left: 2rem;
  right: 2rem;
  top: 50%;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(5, 150, 105, 0.38), transparent);
}

.pipeline-item {
  position: relative;
  z-index: 1;
  flex: 1 1 140px;
  min-width: 120px;
  max-width: 180px;
}

.step-node {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 1.25rem 0.85rem;
  border-radius: 12px;
  color: var(--sc-text);
  cursor: pointer;
  /* 底色比 --sc-bg-panel 更实：能量轨道只从卡片间隙穿过，避免透过玻璃形成「删除线」 */
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.88));
  transition: border-color 0.25s ease, background 0.25s ease, transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.3s ease;
  will-change: transform;
}

.step-node:hover,
.step-node:focus,
.step-node.active {
  outline: none;
  border-color: rgba(5, 150, 105, 0.3);
  background: linear-gradient(180deg, rgba(233, 248, 240, 0.97), rgba(223, 244, 233, 0.93));
  transform: translateY(-3px);
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.06);
}

/* active 节点底色与编号强调 + 光晕呼吸 */
.step-node.active {
  background: linear-gradient(180deg, rgba(222, 245, 233, 0.98), rgba(208, 241, 224, 0.95));
  border-color: rgba(5, 150, 105, 0.42);
  animation: stepNodeGlow 3.2s ease-in-out infinite;
}

@keyframes stepNodeGlow {
  0%, 100% {
    box-shadow: 0 8px 28px rgba(5, 150, 105, 0.18), 0 0 0 rgba(5, 150, 105, 0);
  }
  50% {
    box-shadow: 0 10px 36px rgba(5, 150, 105, 0.34), 0 0 24px rgba(5, 150, 105, 0.2);
  }
}

.step-index {
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  font-weight: 700;
  background: rgba(5, 150, 105, 0.1);
  color: var(--sc-accent);
  transition: background 0.25s ease, color 0.25s ease, box-shadow 0.25s ease;
}

.step-node.active .step-index {
  background: var(--sc-accent);
  color: #ffffff;
  box-shadow: 0 4px 14px rgba(5, 150, 105, 0.35);
}

.step-name {
  font-size: 0.95rem;
  font-weight: 700;
  text-align: center;
}

.step-key {
  font-size: 0.7rem;
  color: var(--sc-muted);
  font-family: ui-monospace, monospace;
  word-break: break-all;
  text-align: center;
}

.step-connector {
  align-self: center;
  display: flex;
  align-items: center;
  padding-top: 1.5rem;
}

/* —— 渐变流动线（repeating 渐变 + background-position 循环；保留光点明灭）—— */
.connector-line {
  position: relative;
  display: block;
  width: 26px;
  height: 2px;
  border-radius: 2px;
  background: repeating-linear-gradient(
    90deg,
    rgba(5, 150, 105, 0.08) 0 12px,
    rgba(5, 150, 105, 0.55) 26px,
    rgba(5, 150, 105, 0.08) 40px
  );
  animation: connectorGradientFlow 1.6s linear infinite;
  overflow: hidden;
}

@keyframes connectorGradientFlow {
  0% { background-position: 0 0; }
  100% { background-position: 40px 0; }
}

.connector-line::after {
  content: "";
  position: absolute;
  top: 50%;
  left: -4px;
  width: 8px;
  height: 2px;
  border-radius: 2px;
  background: var(--sc-accent);
  box-shadow: 0 0 6px rgba(5, 150, 105, 0.7);
  transform: translateY(-50%);
  animation: connectorFlow 1.8s ease-in-out infinite;
}

@keyframes connectorFlow {
  0% { left: -8px; opacity: 0; }
  25% { opacity: 1; }
  75% { opacity: 1; }
  100% { left: 26px; opacity: 0; }
}

.step-detail {
  display: none;
}

.pipeline-detail {
  margin-top: 1.25rem;
  padding: 1.45rem 1.6rem;
  border-radius: var(--sc-radius-md);
  background:
    radial-gradient(circle at 8% 0%, rgba(5, 150, 105, 0.12), transparent 34%),
    var(--sc-bg-panel);
  border: 1px solid rgba(5, 150, 105, 0.12);
}

/* 详情双栏：左阶段信息 / 右阶段产出 */
.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr);
  gap: 1.4rem;
  align-items: start;
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

.detail-head {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.45rem;
}

/* —— 第 {n} 步 徽章 —— */
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
  display: block;
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

/* —— KB 标签 chips —— */
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

.detail-fade-enter-active {
  transition: opacity 0.32s cubic-bezier(0.16, 1, 0.3, 1), transform 0.32s cubic-bezier(0.16, 1, 0.3, 1), max-height 0.32s ease;
}

.detail-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.detail-fade-enter-from {
  opacity: 0;
  transform: translateY(10px) scale(0.99);
  max-height: 0;
}

.detail-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (max-width: 900px) {
  .pipeline {
    flex-direction: column;
    align-items: stretch;
  }

  .pipeline--arc {
    height: auto;
  }

  .pipeline--arc .pipeline-item {
    position: static;
    width: auto;
  }

  .detail-grid {
    grid-template-columns: 1fr;
  }

  .pipeline--no-scene::before {
    top: 1.75rem;
    bottom: 1.75rem;
    left: 50%;
    right: auto;
    width: 1px;
    height: auto;
  }

  .pipeline-item {
    max-width: none;
  }

  .step-connector {
    align-self: center;
    padding: 0;
  }

  .connector-line {
    width: 2px;
    height: 22px;
    background: repeating-linear-gradient(
      180deg,
      rgba(5, 150, 105, 0.08) 0 10px,
      rgba(5, 150, 105, 0.55) 22px,
      rgba(5, 150, 105, 0.08) 34px
    );
    animation: connectorGradientFlowV 1.6s linear infinite;
  }

  @keyframes connectorGradientFlowV {
    0% { background-position: 0 0; }
    100% { background-position: 0 34px; }
  }

  .connector-line::after {
    top: -8px;
    left: 50%;
    width: 2px;
    height: 8px;
    transform: translateX(-50%);
    animation: connectorFlowDown 1.8s ease-in-out infinite;
  }

  @keyframes connectorFlowDown {
    0% { top: -8px; opacity: 0; }
    25% { opacity: 1; }
    75% { opacity: 1; }
    100% { top: 22px; opacity: 0; }
  }
}
</style>
