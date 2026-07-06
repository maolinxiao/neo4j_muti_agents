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
      <div class="pipeline">
        <template v-for="(agent, index) in agents" :key="agent.key">
          <div class="reveal-stagger-item pipeline-item" :style="{ '--reveal-index': index }">
            <button
              type="button"
              class="step-node sc-glass-subtle sc-card-hover sc-card-glow"
              :class="{ active: focusedKey === agent.key }"
              :aria-expanded="focusedKey === agent.key"
              @click="toggle(agent.key)"
            >
              <span class="step-index">{{ index + 1 }}</span>
              <span class="step-name">{{ agent.name }}</span>
              <span class="step-key">{{ agent.key }}</span>
            </button>
          </div>
          <div v-if="index < agents.length - 1" class="step-connector" aria-hidden="true">
            <span class="connector-line" />
          </div>
        </template>
      </div>
      <transition name="detail-fade" mode="out-in">
        <div :key="activeAgent.key" class="pipeline-detail sc-glass">
          <span class="detail-kicker">{{ activeAgent.key }}</span>
          <h3>{{ activeAgent.name }}</h3>
          <p>{{ activeAgent.role }}</p>
          <p class="detail-extra">{{ activeAgent.detail }}</p>
        </div>
      </transition>
      </div>
    </ShowcaseReveal3D>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";

import ShowcaseReveal3D from "./ShowcaseReveal3D.vue";
import ShowcaseSectionDecor from "./ShowcaseSectionDecor.vue";
import ShowcaseSectionHeader from "./ShowcaseSectionHeader.vue";

const agents = [
  {
    key: "master_control",
    name: "主控 Agent",
    role: "需求拆解、模块调度、逻辑校验与方案整合。",
    detail: "识别研发目标，分配后续专家 Agent，并校验各步输出一致性。",
  },
  {
    key: "formula_generation",
    name: "方剂生成专家",
    role: "组方设计、君臣佐使配伍、剂量建模与方解撰写。",
    detail: "基于图谱证据生成药食同源化组方草案，并做初步合规校验。",
  },
  {
    key: "efficacy_prediction",
    name: "功效预测专家",
    role: "中医功效、现代药理与人群分层风险评估。",
    detail: "连接 KB2 功效-病症库，输出功效预测与适配人群说明。",
  },
  {
    key: "flavor_prediction",
    name: "风味预测专家",
    role: "风味特征、协调性、缺陷识别与优化建议。",
    detail: "连接 KB3 风味评价库，评估苦味、涩感与接受度风险。",
  },
  {
    key: "replacement_mapping",
    name: "替代映射专家",
    role: "功效/风味/成本/合规/工艺/供应链替代方案。",
    detail: "连接 KB4 替代评分库，输出 CAN_REPLACE 映射与取舍说明。",
  },
  {
    key: "master_control_final",
    name: "最终主控汇总",
    role: "整合各模块输出，形成最终研发方案。",
    detail: "汇总证据、风险提示与后续建议，供研发决策使用。",
  },
];

const focusedKey = ref(agents[0].key);
const activeAgent = computed(() => agents.find((agent) => agent.key === focusedKey.value) || agents[0]);

const toggle = (key) => {
  focusedKey.value = key;
};
</script>

<style scoped>
.agent-section {
  position: relative;
}

.section-inner {
  position: relative;
  z-index: 1;
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

.pipeline::before {
  content: "";
  position: absolute;
  left: 2rem;
  right: 2rem;
  top: 50%;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(5, 150, 105, 0.38), transparent);
}

.pipeline-item {
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
  background: var(--sc-bg-panel);
  transition: border-color 0.25s ease, background 0.25s ease, transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.3s ease;
}

.step-node:hover,
.step-node:focus,
.step-node.active {
  outline: none;
  border-color: rgba(5, 150, 105, 0.3);
  background: rgba(5, 150, 105, 0.05);
  transform: translateY(-3px);
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.06);
}

/* active 节点底色与编号强调 */
.step-node.active {
  background: rgba(5, 150, 105, 0.08);
  border-color: rgba(5, 150, 105, 0.42);
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

/* 渐变细线 + 流动光点 */
.connector-line {
  position: relative;
  display: block;
  width: 26px;
  height: 2px;
  border-radius: 2px;
  background: linear-gradient(90deg, rgba(5, 150, 105, 0.08), rgba(5, 150, 105, 0.4), rgba(5, 150, 105, 0.08));
  overflow: hidden;
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

.detail-kicker {
  display: block;
  margin-bottom: 0.45rem;
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

  .pipeline::before {
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
    background: linear-gradient(180deg, rgba(5, 150, 105, 0.08), rgba(5, 150, 105, 0.4), rgba(5, 150, 105, 0.08));
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
