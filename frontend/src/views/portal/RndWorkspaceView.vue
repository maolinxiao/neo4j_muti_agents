<template>
  <div class="app-container rnd-page">
    <el-card shadow="never" class="mb-20 rnd-intro-card">
      <div class="rnd-intro">
        <div>
          <h2>研发协同工作台</h2>
          <p class="text-secondary">把产品目标、约束条件和研发偏好整理成 brief，系统会按顺序完成主控拆解、组方、功效、风味和替代映射。</p>
        </div>
        <el-space wrap>
          <el-tag type="success" effect="light">正式替代以 GNN 为主</el-tag>
          <el-tag type="warning" effect="light">配方推荐仅保留药食同源目录药材</el-tag>
        </el-space>
      </div>
    </el-card>

    <div class="rnd-grid-scroll">
      <div class="rnd-grid">
        <el-card shadow="hover" class="box-card panel-card">
        <template #header>
          <div class="card-header">
            <span>研发需求</span>
            <el-button type="primary" link @click="createNewSession">新建会话</el-button>
          </div>
        </template>
        <el-space direction="vertical" fill class="panel-body">
          <el-input v-model="question" type="textarea" :rows="8" placeholder="例如：开发一款增强免疫力的固体饮料，成分只使用药食同源目录，预算有限，3个月内完成配方。" />
          <el-checkbox v-model="reuseLastBrief">复用上次 brief 里的约束信息</el-checkbox>
          <el-button type="primary" :loading="store.submitting" :disabled="workflowBusy" @click="runWorkflow" style="width: 100%;">启动研发工作流</el-button>
          <el-alert
            v-if="workflowBusy"
            title="工作流正在持续生成中，页面会自动刷新阶段结果。"
            type="info"
            :closable="false"
            show-icon
          />
          <div class="suggestion-list mt-10">
            <el-tag
              v-for="item in suggestions"
              :key="item"
              class="suggestion-tag"
              type="info"
              @click="question = item"
            >
              {{ item }}
            </el-tag>
          </div>

          <el-divider v-if="store.currentRun.brief" />
          <div v-if="store.currentRun.brief" class="brief-preview">
            <div class="brief-heading">当前 brief</div>
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="目标">{{ store.currentRun.brief.goal }}</el-descriptions-item>
              <el-descriptions-item label="剂型">{{ store.currentRun.brief.dosage_form || "未指定" }}</el-descriptions-item>
              <el-descriptions-item label="适用人群">{{ store.currentRun.brief.target_population || "未指定" }}</el-descriptions-item>
              <el-descriptions-item label="周期">{{ store.currentRun.brief.timeline || "未指定" }}</el-descriptions-item>
              <el-descriptions-item label="预算">{{ store.currentRun.brief.budget || "未指定" }}</el-descriptions-item>
              <el-descriptions-item label="约束">
                <div class="constraint-list">
                  <el-tag v-for="item in store.currentRun.brief.constraints || []" :key="item" size="small" type="info">{{ item }}</el-tag>
                </div>
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </el-space>
      </el-card>

        <el-card shadow="hover" class="box-card panel-card">
        <template #header>
          <div class="card-header">
            <span>阶段卡片流</span>
            <el-tag v-if="store.currentRun.status" :type="statusTagType(store.currentRun.status)" size="small">
              {{ store.currentRun.status }}
            </el-tag>
          </div>
        </template>
        <div v-if="workflowBusy" class="streaming-tip">
          正在执行 {{ runningStepLabel }}，结果会随着步骤完成逐步刷新。
        </div>
        <div v-if="store.currentRun.steps?.length" class="step-list">
          <el-card
            v-for="step in store.currentRun.steps"
            :key="step.id"
            class="step-card"
            shadow="hover"
            :class="{ active: store.currentStepDetail?.id === step.id }"
            @click="selectStep(step.id)"
          >
            <div class="step-top">
              <div>
                <div class="step-seq">Step {{ step.sequence }}</div>
                <div class="step-agent">{{ agentLabels[step.agent_key] || step.agent_key }}</div>
              </div>
              <el-tag size="small" :type="statusTagType(step.status)">{{ step.status }}</el-tag>
            </div>
            <div class="step-metrics">
              <span>耗时 {{ step.latency_ms }} ms</span>
              <span>证据 {{ step.graph_snapshot_id ? 1 : 0 }}</span>
            </div>
            <div class="step-summary">{{ summarizeStep(step.output_payload) }}</div>
            <div v-if="getStepHighlights(step.output_payload).length" class="step-highlight-list">
              <div
                v-for="(point, index) in getStepHighlights(step.output_payload)"
                :key="`${step.id}-${index}`"
                class="step-highlight-item"
              >
                {{ point }}
              </div>
            </div>
            <details class="step-detail">
              <summary>查看结构化原文</summary>
              <pre>{{ formatJson(step.output_payload) }}</pre>
            </details>
          </el-card>
        </div>
        <el-empty v-else description="运行一次研发工作流后，这里会展示各 Agent 的阶段结果。" />
      </el-card>

        <el-card shadow="hover" class="box-card panel-card">
        <template #header>
          <div class="card-header">
            <span>证据与结果</span>
            <el-tag v-if="store.currentStepDetail" size="small" type="primary">{{ agentLabels[store.currentStepDetail.agent_key] || store.currentStepDetail.agent_key }}</el-tag>
          </div>
        </template>
        <div class="result-overview" v-if="store.currentRun.steps?.length">
          <div class="overview-item">
            <div class="overview-label">总步骤</div>
            <div class="overview-value">{{ store.currentRun.steps.length }}</div>
          </div>
          <div class="overview-item">
            <div class="overview-label">已完成</div>
            <div class="overview-value">{{ completedStepCount }}</div>
          </div>
          <div class="overview-item">
            <div class="overview-label">证据快照</div>
            <div class="overview-value">{{ evidenceSnapshotCount }}</div>
          </div>
        </div>
        <el-tabs v-model="activeTab">
          <el-tab-pane label="最终方案" name="report">
            <div v-if="store.currentRun.final_report" class="report-block">
              <h3>{{ store.currentRun.final_report.brief_summary || briefTitle }}</h3>
              <p class="report-copy">{{ store.currentRun.final_report.final_recommendation }}</p>

              <div v-if="resultChecklist.length" class="report-section">
                <strong>方案要点</strong>
                <ul>
                  <li v-for="item in resultChecklist" :key="item">{{ item }}</li>
                </ul>
              </div>

              <div v-if="formulaRoleSummary.length" class="report-section">
                <strong>方剂配伍摘要</strong>
                <div class="role-grid">
                  <div v-for="item in formulaRoleSummary" :key="item.role" class="role-card">
                    <div class="role-title">{{ item.role }}</div>
                    <div class="role-herbs">{{ item.herbs }}</div>
                    <div v-if="item.notes.length" class="role-notes">
                      <div v-for="note in item.notes" :key="note">{{ note }}</div>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="moduleSummaries.length" class="report-section">
                <strong>分阶段汇总</strong>
                <div class="module-grid">
                  <div v-for="moduleItem in moduleSummaries" :key="moduleItem.key" class="module-card">
                    <div class="module-title">{{ moduleItem.title }}</div>
                    <div class="module-copy">{{ moduleItem.summary }}</div>
                  </div>
                </div>
              </div>

              <div class="report-section">
                <strong>一致性检查</strong>
                <ul>
                  <li v-for="item in store.currentRun.final_report.consistency_checks || []" :key="item">{{ item }}</li>
                </ul>
              </div>
              <div class="report-section">
                <strong>下一步建议</strong>
                <ul>
                  <li v-for="item in store.currentRun.final_report.next_actions || []" :key="item">{{ item }}</li>
                </ul>
              </div>
            </div>
            <el-empty v-else :description="workflowBusy ? '工作流正在运行，完成的阶段结果会自动刷新到这里。' : '完成工作流后会在这里展示最终研发方案。'" />
          </el-tab-pane>
          <el-tab-pane label="证据图谱" name="graph">
            <GraphCanvas
              :nodes="store.selectedSnapshot?.graph_data?.nodes || []"
              :edges="store.selectedSnapshot?.graph_data?.edges || []"
              :focus-paths="store.selectedSnapshot?.graph_data?.focus_paths || []"
              :loading="store.loading"
            />
          </el-tab-pane>
          <el-tab-pane label="替代对比" name="replacement">
            <div v-if="replacementRows.length">
              <el-table :data="replacementRows" size="small" border>
                <el-table-column prop="source_herb" label="原药材" min-width="90" />
                <el-table-column prop="recommended_herb" label="推荐替代" min-width="90" />
                <el-table-column prop="score" label="GNN分数" width="80" />
                <el-table-column prop="flavor_acceptance" label="风味接受度" width="100" />
                <el-table-column prop="flavor_similarity" label="风味相似度" width="100" />
                <el-table-column prop="safety_score" label="安全分" width="80" />
                <el-table-column prop="population_fit" label="人群适配" min-width="180" show-overflow-tooltip />
                <el-table-column prop="reason" label="说明" min-width="140" show-overflow-tooltip />
              </el-table>
              <div class="compare-block mt-10">
                <strong>Baseline 对比</strong>
                <pre>{{ formatJson(store.currentRun.final_report?.modules?.replacement_mapping?.baseline_comparison || []) }}</pre>
              </div>
            </div>
            <el-empty v-else description="替代映射阶段完成后，这里会展示 GNN 正式替代和 Baseline 对比。" />
          </el-tab-pane>
        </el-tabs>
      </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import GraphCanvas from "../../components/GraphCanvas.vue";
import { useRndStore } from "../../stores/rnd";

const route = useRoute();
const router = useRouter();
const store = useRndStore();
const question = ref("");
const reuseLastBrief = ref(false);
const activeTab = ref("report");

const agentLabels = {
  master_control: "主控 Agent",
  master_control_final: "主控汇总 Agent",
  formula_generation: "方剂生成 Agent",
  efficacy_prediction: "功效预测 Agent",
  flavor_prediction: "风味预测 Agent",
  replacement_mapping: "替代映射 Agent",
};

const suggestions = [
  "开发一款增强免疫力的固体饮料，成分只使用药食同源目录，预算有限，3个月内完成配方。",
  "设计一款健脾养胃的代用茶，适合白领人群，强调温和口感和合规性。",
  "做一款主打抗氧化的咀嚼片，要求药食同源目录内成分，便于做替代优化。",
];

const replacementRows = computed(
  () => store.currentRun.final_report?.modules?.replacement_mapping?.recommended_replacements || [],
);

const completedStepCount = computed(
  () => store.currentRun.steps?.filter((item) => item.status === "completed").length || 0,
);

const evidenceSnapshotCount = computed(
  () => store.currentRun.steps?.filter((item) => item.graph_snapshot_id).length || 0,
);

const workflowBusy = computed(
  () => store.submitting || ["queued", "running"].includes(store.currentRun.status),
);

const runningStepLabel = computed(() => {
  const runningStep = store.currentRun.steps?.find((item) => item.status === "running");
  if (runningStep) {
    return agentLabels[runningStep.agent_key] || runningStep.agent_key;
  }
  if (store.currentRun.status === "queued") {
    return "主控 Agent";
  }
  return "当前工作流";
});

const briefTitle = computed(() => {
  if (store.currentRun.brief?.goal) return `面向“${store.currentRun.brief.goal}”的研发建议`;
  return "最终研发建议";
});

const moduleLabelMap = {
  master_control: "主控拆解",
  formula_generation: "方剂生成",
  efficacy_prediction: "功效预测",
  flavor_prediction: "风味预测",
  replacement_mapping: "替代映射",
};

const shortText = (value, maxLength = 120) => {
  const text = String(value || "").trim();
  if (!text) return "";
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength)}...`;
};

const pickFirstMeaningfulText = (payload) => {
  if (!payload || typeof payload !== "object") return "";
  const preferredKeys = [
    "final_recommendation",
    "selection_rationale",
    "coordination_summary",
    "impact_summary",
    "summary",
    "reason",
    "notes",
  ];
  for (const key of preferredKeys) {
    const value = payload[key];
    if (typeof value === "string" && value.trim()) {
      return shortText(value, 140);
    }
  }
  for (const value of Object.values(payload)) {
    if (typeof value === "string" && value.trim()) {
      return shortText(value, 140);
    }
  }
  return "已生成结构化结果";
};

const summarizeFormulaGeneration = (payload) => {
  const ingredients = payload?.formulas?.[0]?.ingredients || [];
  if (!ingredients.length) {
    return pickFirstMeaningfulText(payload);
  }
  return ingredients
    .map((item) => `${item.role || "配伍"}：${item.name || "未命名药材"}`)
    .join("；");
};

const moduleSummaries = computed(() => {
  const modules = store.currentRun.final_report?.modules || {};
  return Object.entries(modules).map(([key, payload]) => ({
    key,
    title: moduleLabelMap[key] || key,
    summary: key === "formula_generation" ? summarizeFormulaGeneration(payload) : pickFirstMeaningfulText(payload),
  }));
});

const firstFormula = computed(
  () => store.currentRun.final_report?.modules?.formula_generation?.formulas?.[0] || null,
);

const formulaRoleSummary = computed(() => {
  const ingredients = firstFormula.value?.ingredients || [];
  const orderedRoles = ["君药", "臣药", "佐药", "使药", "配伍药"];
  return orderedRoles
    .map((role) => {
      const matched = ingredients.filter((item) => item.role === role);
      if (!matched.length) return null;
      return {
        role,
        herbs: matched.map((item) => item.name).filter(Boolean).join("、"),
        notes: matched
          .map((item) => {
            const rationale = shortText(item.rationale || "", 42);
            const doseRange = item.dose_range ? `，剂量：${item.dose_range}` : "";
            return rationale ? `${item.name}：${rationale}${doseRange}` : "";
          })
          .filter(Boolean),
      };
    })
    .filter(Boolean);
});

const resultChecklist = computed(() => {
  const result = [];
  if (store.currentRun.brief?.goal) result.push(`目标：${store.currentRun.brief.goal}`);
  if (store.currentRun.brief?.constraints?.length) {
    result.push(`约束：${store.currentRun.brief.constraints.join("；")}`);
  }
  const recommendation = store.currentRun.final_report?.final_recommendation;
  if (recommendation) result.push(`结论：${recommendation}`);
  return result;
});

const runWorkflow = async () => {
  if (!question.value) return;
  await store.runWorkflow(question.value, reuseLastBrief.value);
  await router.push({
    name: "rnd",
    params: { sessionId: store.currentSessionId },
    query: { runId: store.currentRun.run_id || store.currentRun.id || "" },
  });
};

const statusTagType = (status) => {
  if (status === "completed") return "success";
  if (status === "failed") return "danger";
  if (status === "running") return "warning";
  return "info";
};

const selectStep = async (stepId) => {
  await store.selectStep(stepId);
  activeTab.value = store.selectedSnapshot ? "graph" : "report";
};

const createNewSession = async () => {
  store.reset();
  question.value = "";
  await router.push({ name: "rnd" });
};

const summarizeStep = (payload) => {
  if (!payload) return "等待结果";
  if (payload.final_recommendation) return shortText(payload.final_recommendation, 140);
  if (payload.selection_rationale) return shortText(payload.selection_rationale, 140);
  if (payload.coordination_summary) return shortText(payload.coordination_summary, 140);
  if (payload.impact_summary) return shortText(payload.impact_summary, 140);
  if (payload.core_tcm_efficacy?.length) return payload.core_tcm_efficacy.join("；");
  return "已生成结构化结果";
};

const getStepHighlights = (payload) => {
  if (!payload || typeof payload !== "object") return [];
  const points = [];
  for (const [key, value] of Object.entries(payload)) {
    if (points.length >= 4) break;
    if (typeof value === "string" && value.trim()) {
      points.push(`${key}：${shortText(value, 48)}`);
      continue;
    }
    if (Array.isArray(value) && value.length) {
      const first = value[0];
      if (typeof first === "string") {
        points.push(`${key}：${shortText(value.slice(0, 3).join("；"), 48)}`);
      }
    }
  }
  return points;
};

const formatJson = (value) => {
  try {
    return JSON.stringify(value || {}, null, 2);
  } catch {
    return String(value ?? "");
  }
};

const hydrate = async () => {
  await store.refreshSessions();
  if (route.params.sessionId) {
    store.currentSessionId = route.params.sessionId;
  }
  if (route.query.runId) {
    await store.loadRun(route.query.runId);
  } else if (route.params.sessionId) {
    await store.loadLatestRunForSession(route.params.sessionId);
  }
};

watch(() => route.query.runId, hydrate);
onMounted(hydrate);
onUnmounted(() => store.stopPolling());
</script>

<style scoped>
.app-container {
  padding: 20px;
}

.mb-20 {
  margin-bottom: 20px;
}

.mt-10 {
  margin-top: 10px;
}

.text-secondary {
  color: #909399;
}

.rnd-page {
  display: flex;
  flex-direction: column;
}

.rnd-intro-card {
  border: none;
  background-color: #f8f8f9;
}

.rnd-intro {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.rnd-intro h2 {
  margin: 0 0 8px;
  color: #303133;
  font-size: 18px;
  font-weight: 600;
}

.rnd-intro p {
  line-height: 1.6;
  max-width: 800px;
  font-size: 14px;
  margin: 0;
}

.rnd-grid {
  display: grid;
  grid-template-columns: 340px minmax(0, 1fr) 460px;
  gap: 20px;
  align-items: start;
  min-width: 1320px;
}

.rnd-grid-scroll {
  overflow-x: auto;
  padding-bottom: 2px;
}

.box-card {
  border-radius: 4px;
}

.panel-card {
  height: calc(100vh - 210px);
  display: flex;
  flex-direction: column;
}

.panel-card :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.panel-body {
  width: 100%;
}

.streaming-tip {
  margin-bottom: 12px;
  color: #909399;
  font-size: 13px;
}

.role-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.role-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px;
  background: #fafafa;
}

.role-title {
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.role-herbs {
  color: #409eff;
  font-weight: 500;
  margin-bottom: 8px;
  line-height: 1.6;
}

.role-notes {
  color: #606266;
  font-size: 13px;
  line-height: 1.6;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 500;
}

.suggestion-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.suggestion-tag {
  cursor: pointer;
  white-space: normal;
  height: auto;
  padding: 4px 8px;
  line-height: 1.4;
}

.suggestion-tag:hover {
  opacity: 0.8;
}

.brief-heading {
  margin-bottom: 10px;
  color: #303133;
  font-weight: 600;
  font-size: 14px;
}

.constraint-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.step-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.step-card {
  cursor: pointer;
  border-radius: 4px;
  border: 1px solid #ebeef5;
  transition: all 0.3s;
}

.step-card:hover {
  border-color: #c0c4cc;
}

.step-card.active {
  border-color: #409EFF;
  box-shadow: 0 2px 12px 0 rgba(64, 158, 255, 0.2);
}

.step-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.step-seq {
  color: #909399;
  font-size: 12px;
  text-transform: uppercase;
}

.step-agent {
  margin-top: 4px;
  color: #303133;
  font-weight: 600;
  font-size: 14px;
}

.step-metrics {
  margin-top: 10px;
  display: flex;
  gap: 12px;
  color: #909399;
  font-size: 12px;
}

.step-summary {
  margin-top: 12px;
  line-height: 1.6;
  font-size: 13px;
  color: #303133;
  font-weight: 500;
}

.step-highlight-list {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-highlight-item {
  padding: 8px 10px;
  border-radius: 4px;
  background: #f5f7fa;
  color: #606266;
  font-size: 12px;
  line-height: 1.5;
}

.step-detail {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed #ebeef5;
}

.step-detail summary {
  color: #409EFF;
  cursor: pointer;
  font-size: 13px;
  user-select: none;
}

.step-detail pre,
.compare-block pre {
  margin: 10px 0 0;
  padding: 12px;
  border-radius: 4px;
  background: #f5f7fa;
  color: #606266;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  border: 1px solid #ebeef5;
}

.report-block h3 {
  margin: 0 0 12px;
  color: #303133;
  font-size: 16px;
}

.report-copy {
  color: #606266;
  line-height: 1.6;
  font-size: 14px;
}

.report-section {
  margin-top: 20px;
}

.report-section strong {
  color: #303133;
  font-size: 14px;
}

.report-section ul {
  margin: 8px 0 0;
  padding-left: 20px;
  color: #606266;
  line-height: 1.6;
  font-size: 14px;
}

.compare-block {
  margin-top: 16px;
}

.result-overview {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}

.overview-item {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  background: #f8fafc;
  padding: 10px;
}

.overview-label {
  font-size: 12px;
  color: #909399;
}

.overview-value {
  margin-top: 4px;
  font-size: 18px;
  color: #303133;
  font-weight: 600;
}

.module-grid {
  margin-top: 10px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.module-card {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 10px;
  background: #fff;
}

.module-title {
  color: #303133;
  font-weight: 600;
  font-size: 13px;
}

.module-copy {
  margin-top: 6px;
  color: #606266;
  line-height: 1.5;
  font-size: 12px;
}
</style>
