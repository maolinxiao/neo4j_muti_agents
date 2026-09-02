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

          <div class="brief-option-row">
            <el-checkbox v-model="showBrief" size="small">显示当前 brief（研发需求解析结果）</el-checkbox>
          </div>
          <el-divider v-if="showBrief" />
          <div v-if="showBrief" class="brief-preview">
            <div class="brief-heading">当前 brief</div>
            <el-descriptions v-if="store.currentRun.brief" :column="1" border size="small">
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
            <el-empty
              v-else
              class="brief-empty"
              description="尚未生成 brief：启动研发工作流后，系统会把研发需求解析为结构化 brief 并展示在这里。"
              :image-size="48"
            />
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
        <el-tabs v-if="stepPanelTabs.length" v-model="activeTab">
          <el-tab-pane
            v-for="tab in stepPanelTabs"
            :key="tab.key"
            :label="tab.label"
            :name="tab.key"
          >
            <!-- 任务计划：主控 Agent -->
            <div v-if="tab.key === 'plan'" class="tab-content">
              <el-empty v-if="!planSections.length" description="无结构化计划" :image-size="60" />
              <div v-for="section in planSections" :key="section.label" class="report-section">
                <strong>{{ section.label }}</strong>
                <ul class="section-list">
                  <li v-for="item in section.items" :key="item">{{ item }}</li>
                </ul>
              </div>
            </div>

            <!-- 配方组成：方剂生成 Agent -->
            <div v-else-if="tab.key === 'formula'" class="tab-content">
              <el-empty v-if="!formulaCards.length" description="方剂生成结果暂无结构化配方" :image-size="60" />
              <template v-else>
                <div v-for="(card, cardIndex) in formulaCards" :key="cardIndex" class="report-section formula-card-block">
                  <div class="formula-card-head">
                    <strong>{{ card.name }}</strong>
                    <el-tag v-if="formulaCards.length > 1" size="small" type="info">候选 {{ cardIndex + 1 }} / {{ formulaCards.length }}</el-tag>
                  </div>
                  <el-table :data="card.ingredients" size="small" border class="mt-10">
                    <el-table-column prop="name" label="药材" min-width="90" />
                    <el-table-column prop="role" label="角色" width="80" />
                    <el-table-column prop="dose" label="剂量" min-width="110" show-overflow-tooltip />
                    <el-table-column prop="rationale" label="作用依据" min-width="170" show-overflow-tooltip />
                  </el-table>
                  <p v-if="card.fangJie" class="report-copy mt-10">{{ card.fangJie }}</p>
                </div>

                <div v-if="roleGroups.length" class="report-section">
                  <strong>君臣佐使分组</strong>
                  <div class="role-grid">
                    <div v-for="group in roleGroups" :key="group.role" class="role-card">
                      <div class="role-title">{{ group.role }}</div>
                      <div class="role-herbs">{{ group.herbs }}</div>
                      <div class="role-duty">{{ group.duty }}</div>
                      <div v-if="group.notes.length" class="role-notes">
                        <div v-for="note in group.notes" :key="note">{{ note }}</div>
                      </div>
                    </div>
                  </div>
                </div>

                <div v-if="originalFormula" class="report-section">
                  <strong>原方依据</strong>
                  <p class="report-copy mt-8">{{ originalFormula }}</p>
                </div>

                <div v-if="selectionRationale" class="report-section">
                  <strong>选方说明</strong>
                  <p class="report-copy mt-8">{{ selectionRationale }}</p>
                </div>

                <div v-if="complianceNotes.length || risks.length" class="report-section">
                  <div v-if="complianceNotes.length" class="mb-10">
                    <strong>合规说明</strong>
                    <ul class="section-list">
                      <li v-for="item in complianceNotes" :key="item">{{ item }}</li>
                    </ul>
                  </div>
                  <div v-if="risks.length">
                    <strong>风险提示</strong>
                    <ul class="section-list">
                      <li v-for="item in risks" :key="item">{{ item }}</li>
                    </ul>
                  </div>
                </div>
              </template>
            </div>

            <!-- 功效评估：功效预测 Agent -->
            <div v-else-if="tab.key === 'efficacy'" class="tab-content">
              <el-empty v-if="!efficacySections.length" description="该步骤暂无结构化功效结果" :image-size="60" />
              <div v-for="section in efficacySections" :key="section.label" class="report-section">
                <strong>{{ section.label }}</strong>
                <ul class="section-list">
                  <li v-for="item in section.items" :key="item">{{ item }}</li>
                </ul>
              </div>
            </div>

            <!-- 风味评估：风味预测 Agent -->
            <div v-else-if="tab.key === 'flavor'" class="tab-content">
              <el-empty v-if="!flavorSections.length" description="该步骤暂无结构化风味结果" :image-size="60" />
              <div v-for="section in flavorSections" :key="section.label" class="report-section">
                <strong>{{ section.label }}</strong>
                <ul class="section-list">
                  <li v-for="item in section.items" :key="item">{{ item }}</li>
                </ul>
              </div>
            </div>

            <!-- 替代对比：替代映射 Agent -->
            <div v-else-if="tab.key === 'replacement'" class="tab-content">
              <el-empty v-if="!replacementRows.length" description="替代映射阶段完成后，这里会展示 GNN 正式替代和 Baseline 对比。" :image-size="60" />
              <template v-else>
                <div class="report-section">
                  <strong>替代对比</strong>
                  <el-table :data="replacementRows" size="small" border class="mt-10">
                    <el-table-column prop="source_herb" label="原药材" min-width="90" />
                    <el-table-column prop="recommended_herb" label="推荐替代" min-width="90" />
                    <el-table-column prop="score" label="GNN分数" width="80" />
                    <el-table-column prop="flavor_acceptance" label="风味接受度" width="100" />
                    <el-table-column prop="flavor_similarity" label="风味相似度" width="100" />
                    <el-table-column prop="safety_score" label="安全分" width="80" />
                    <el-table-column prop="population_fit" label="人群适配" min-width="180" show-overflow-tooltip />
                    <el-table-column prop="reason" label="说明" min-width="140" show-overflow-tooltip />
                  </el-table>
                </div>

                <div v-if="baselineRows.length" class="report-section">
                  <strong>Baseline 对比</strong>
                  <el-table :data="baselineRows" size="small" border class="mt-10">
                    <el-table-column prop="source_herb" label="原药材" min-width="80" />
                    <el-table-column prop="candidate_herb" label="候选替代" min-width="80" />
                    <el-table-column label="功效分" width="80">
                      <template #default="{ row }">{{ formatCell(row.efficacy_score) }}</template>
                    </el-table-column>
                    <el-table-column label="风味替换前" min-width="150" show-overflow-tooltip>
                      <template #default="{ row }">{{ shortText(row.flavor_before, 60) }}</template>
                    </el-table-column>
                    <el-table-column label="风味替换后" min-width="150" show-overflow-tooltip>
                      <template #default="{ row }">{{ shortText(row.flavor_after, 60) }}</template>
                    </el-table-column>
                    <el-table-column prop="flavor_acceptance" label="接受度" width="80" />
                    <el-table-column prop="flavor_similarity" label="相似度" width="80" />
                    <el-table-column prop="safety_score" label="安全分" width="80" />
                    <el-table-column prop="decision" label="决策" width="90" />
                  </el-table>
                </div>

                <div v-if="impactSummary" class="report-section">
                  <strong>影响评估</strong>
                  <p class="report-copy mt-8">{{ impactSummary }}</p>
                </div>

                <div v-if="replacementComplianceNotes.length || replacementScenarios.length" class="report-section">
                  <div v-if="replacementComplianceNotes.length" class="mb-10">
                    <strong>合规说明</strong>
                    <ul class="section-list">
                      <li v-for="item in replacementComplianceNotes" :key="item">{{ item }}</li>
                    </ul>
                  </div>
                  <div v-if="replacementScenarios.length">
                    <strong>适用场景</strong>
                    <ul class="section-list">
                      <li v-for="item in replacementScenarios" :key="item">{{ item }}</li>
                    </ul>
                  </div>
                </div>
              </template>
            </div>

            <!-- 最终方案：主控汇总 Agent -->
            <div v-else-if="tab.key === 'report'" class="tab-content">
              <el-empty v-if="!reportHasContent" :description="workflowBusy ? '工作流正在运行，完成的主控汇总结果会自动刷新到这里。' : '完成工作流后会在这里展示最终研发方案。'" :image-size="60" />
              <div v-else class="report-block">
                <h3>{{ reportTitle }}</h3>
                <p v-if="reportIntro" class="report-copy">{{ reportIntro }}</p>
                <div v-if="reportBriefTags.length" class="report-section">
                  <strong>需求要点</strong>
                  <div class="tag-list mt-8">
                    <el-tag v-for="tag in reportBriefTags" :key="tag" size="small" type="info">{{ tag }}</el-tag>
                  </div>
                </div>

                <div v-if="reportComposition.length" class="report-section">
                  <strong>最终配方</strong>
                  <el-table :data="reportComposition" size="small" border class="mt-10">
                    <el-table-column prop="name" label="药材" min-width="90" />
                    <el-table-column prop="role" label="角色" width="80" />
                    <el-table-column prop="dose" label="建议剂量" min-width="110" show-overflow-tooltip />
                    <el-table-column prop="rationale" label="作用与剂量依据" min-width="170" show-overflow-tooltip />
                    <el-table-column prop="basis" label="方解" min-width="140" show-overflow-tooltip />
                    <el-table-column prop="source" label="依据来源" min-width="130" show-overflow-tooltip />
                  </el-table>
                </div>

                <div v-if="reportMonarchSummary.length" class="report-section">
                  <strong>君臣佐使一览</strong>
                  <div class="role-grid">
                    <div v-for="group in reportMonarchSummary" :key="group.role" class="role-card">
                      <div class="role-title">{{ group.role }}</div>
                      <div class="role-herbs">{{ (group.herbs || []).join("、") }}</div>
                      <div class="role-duty">{{ group.duty }}</div>
                    </div>
                  </div>
                </div>

                <div v-if="reportOriginalName" class="report-section">
                  <strong>原方依据</strong>
                  <p class="report-copy mt-8">{{ reportOriginalName }}<span v-if="reportOriginalSource">（来源：{{ reportOriginalSource }}）</span></p>
                  <div v-if="reportOriginalRetained.length" class="mt-10">
                    <div class="change-label">保留</div>
                    <div class="tag-list mt-8">
                      <el-tag v-for="item in reportOriginalRetained" :key="item" size="small" type="success">{{ item }}</el-tag>
                    </div>
                  </div>
                  <div v-if="reportOriginalReplacedRows.length" class="mt-10">
                    <div class="change-label">替换</div>
                    <el-table :data="reportOriginalReplacedRows" size="small" border class="mt-8">
                      <el-table-column prop="from" label="原药材" min-width="90" />
                      <el-table-column prop="to" label="替代药材" min-width="90" />
                      <el-table-column label="KB4 评分" width="100">
                        <template #default="{ row }">{{ formatCell(row.score) }}</template>
                      </el-table-column>
                      <el-table-column prop="confidence" label="综合可信度" min-width="110" show-overflow-tooltip />
                    </el-table>
                  </div>
                  <div v-if="reportOriginalAdded.length" class="mt-10">
                    <div class="change-label">新增</div>
                    <div class="tag-list mt-8">
                      <el-tag v-for="item in reportOriginalAdded" :key="item" size="small" type="warning">{{ item }}</el-tag>
                    </div>
                  </div>
                  <div v-if="reportOriginalRemoved.length" class="mt-10">
                    <div class="change-label">删除</div>
                    <div class="tag-list mt-8">
                      <el-tag v-for="item in reportOriginalRemoved" :key="item" size="small" type="danger" effect="plain">{{ item }}</el-tag>
                    </div>
                  </div>
                </div>

                <div v-if="reportEfficacyEffects.length || reportEfficacyMechanisms.length" class="report-section">
                  <strong>功效与机制</strong>
                  <ul v-if="reportEfficacyEffects.length" class="section-list">
                    <li v-for="item in reportEfficacyEffects" :key="item">功效：{{ item }}</li>
                  </ul>
                  <ul v-if="reportEfficacyMechanisms.length" class="section-list">
                    <li v-for="item in reportEfficacyMechanisms" :key="item">机制：{{ item }}</li>
                  </ul>
                </div>

                <div v-if="reportFlavorNotes.length || reportFlavorAcceptance" class="report-section">
                  <strong>风味与适配</strong>
                  <ul v-if="reportFlavorNotes.length" class="section-list">
                    <li v-for="item in reportFlavorNotes" :key="item">{{ item }}</li>
                  </ul>
                  <p v-if="reportFlavorAcceptance" class="report-copy mt-8">{{ reportFlavorAcceptance }}</p>
                </div>

                <div v-if="reportReplacementPoints.length" class="report-section">
                  <strong>替代对比要点</strong>
                  <ul class="section-list">
                    <li v-for="item in reportReplacementPoints" :key="item">{{ item }}</li>
                  </ul>
                  <p class="text-secondary small-note">完整替代比对请切换至「替代映射 Agent」的阶段面板。</p>
                </div>

                <div v-if="reportComplianceRisks.length" class="report-section">
                  <strong>合规与风险</strong>
                  <ul class="section-list">
                    <li v-for="item in reportComplianceRisks" :key="item">{{ item }}</li>
                  </ul>
                </div>

                <div v-if="reportEvidenceGaps.length" class="report-section">
                  <strong>证据缺口</strong>
                  <ul class="section-list">
                    <li v-for="item in reportEvidenceGaps" :key="item">{{ item }}</li>
                  </ul>
                </div>

                <div v-if="reportConsistencyChecks.length" class="report-section">
                  <strong>一致性检查</strong>
                  <ul class="section-list">
                    <li v-for="item in reportConsistencyChecks" :key="item">{{ item }}</li>
                  </ul>
                </div>

                <div v-if="reportNextActions.length" class="report-section">
                  <strong>下一步建议</strong>
                  <ul class="section-list">
                    <li v-for="item in reportNextActions" :key="item">{{ item }}</li>
                  </ul>
                </div>

                <!-- 旧版 final_report 兼容：仅当新结构化键缺失时展示分阶段汇总 -->
                <div v-if="!reportHasStructured && legacyModuleSummaries.length" class="report-section">
                  <strong>分阶段汇总</strong>
                  <div class="module-grid">
                    <div v-for="moduleItem in legacyModuleSummaries" :key="moduleItem.key" class="module-card">
                      <div class="module-title">{{ moduleItem.title }}</div>
                      <div class="module-copy">{{ moduleItem.summary }}</div>
                    </div>
                  </div>
                </div>

                <div v-if="reportDataSources.length" class="report-section">
                  <strong>数据来源</strong>
                  <div class="tag-list mt-8">
                    <el-tag v-for="item in reportDataSources" :key="item" size="small" type="info" effect="plain">{{ item }}</el-tag>
                  </div>
                </div>
              </div>
            </div>

            <!-- 证据图谱 -->
            <div v-else-if="tab.key === 'graph'" class="tab-content">
              <GraphCanvas
                :nodes="graphNodes"
                :edges="graphEdges"
                :focus-paths="graphFocusPaths"
                :loading="store.loading"
              />
            </div>

            <!-- 兜底：结构化原文 -->
            <div v-else class="tab-content">
              <pre class="raw-pre">{{ formatJson(selectedStepPayload) }}</pre>
            </div>
          </el-tab-pane>
        </el-tabs>
        <el-empty
          v-else
          :description="store.currentRun.steps?.length
            ? '请选择左侧阶段卡片，查看对应 Agent 的证据与结果。'
            : (workflowBusy ? '工作流正在运行，完成的阶段结果会自动刷新到这里。' : '运行一次研发工作流后，这里会展示各 Agent 的阶段结果。')"
        />
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
const showBrief = ref(true);
const activeTab = ref("plan");

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

/* ---------- 数据源 ---------- */

const selectedStepPayload = computed(() => store.currentStepDetail?.output_payload || {});

const reportPayload = computed(() => store.currentRun.final_report || selectedStepPayload.value);

const graphNodes = computed(() => store.selectedSnapshot?.graph_data?.nodes || []);
const graphEdges = computed(() => store.selectedSnapshot?.graph_data?.edges || []);
const graphFocusPaths = computed(() => store.selectedSnapshot?.graph_data?.focus_paths || []);

/* ---------- 按 Agent 生成面板 tabs ---------- */

const stepPanelTabs = computed(() => {
  const step = store.currentStepDetail;
  if (!step) return [];
  const tabs = [];
  const key = step.agent_key;
  if (key === "master_control") {
    tabs.push({ key: "plan", label: "任务计划" });
  } else if (key === "formula_generation") {
    tabs.push({ key: "formula", label: "配方组成" });
  } else if (key === "efficacy_prediction") {
    tabs.push({ key: "efficacy", label: "功效评估" });
  } else if (key === "flavor_prediction") {
    tabs.push({ key: "flavor", label: "风味评估" });
  } else if (key === "replacement_mapping") {
    tabs.push({ key: "replacement", label: "替代对比" });
  } else if (key === "master_control_final") {
    tabs.push({ key: "report", label: "最终方案" });
  } else {
    tabs.push({ key: "raw", label: "结构化结果" });
  }
  if (step.graph_snapshot_id || step.graph_snapshot) {
    tabs.push({ key: "graph", label: "证据图谱" });
  }
  return tabs;
});

/* ---------- 通用文本抽取 ---------- */

const itemText = (value) => {
  if (value == null) return "";
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (typeof value === "object") {
    for (const key of ["name", "task", "description", "title", "reason", "detail", "value"]) {
      if (value[key] != null && String(value[key]).trim()) return String(value[key]).trim();
    }
    try {
      return JSON.stringify(value);
    } catch {
      return "";
    }
  }
  return String(value);
};

const toTextList = (value) => {
  if (value == null) return [];
  if (Array.isArray(value)) return value.map(itemText).filter(Boolean);
  const text = itemText(value);
  return text ? [text] : [];
};

const formatCell = (value) => {
  if (value == null || value === "") return "—";
  return String(value);
};

/* ---------- 主控 Agent：任务计划 ---------- */

const planSections = computed(() => {
  const payload = selectedStepPayload.value;
  if (!payload || typeof payload !== "object") return [];
  const defs = [
    ["brief_summary", "需求摘要"],
    ["task_plan", "任务计划"],
    ["plan", "需求拆解"],
    ["tasks", "任务清单"],
    ["checkpoints", "检查点"],
    ["target_population", "目标人群"],
    ["deliverables", "交付物"],
    ["consistency_checks", "一致性检查"],
    ["next_actions", "下一步行动"],
    ["data_sources", "数据来源"],
  ];
  const sections = [];
  const seenLabels = new Set();
  for (const [key, label] of defs) {
    if (seenLabels.has(label)) continue;
    const items = toTextList(payload[key]);
    if (items.length) {
      sections.push({ label, items });
      seenLabels.add(label);
    }
  }
  return sections;
});

/* ---------- 方剂生成 Agent：配方组成 ---------- */

const formulaCards = computed(() => {
  const payload = selectedStepPayload.value;
  const formulas = Array.isArray(payload?.formulas) ? payload.formulas : [];
  if (!formulas.length) return [];
  return formulas.map((formula) => ({
    name: formula.name || "候选方",
    ingredients: (formula.ingredients || []).map((item) => ({
      name: item.name || item.herb_key || "未命名药材",
      role: item.role || "配伍药",
      dose: item.dose_range || item.dose || "待校验",
      rationale: item.rationale || item.fang_jie_role || item.dose_rationale || "与目标功效相关",
    })),
    fangJie: formula.fang_jie || "",
  }));
});

const ROLE_DUTY = {
  君药: "针对目标需求与核心功效起主导作用",
  臣药: "辅助君药增强功效或针对兼证",
  佐药: "佐助主药或制约偏性，平衡药性与口感",
  使药: "调和诸药、改善整体协调性",
  配伍药: "协同配方整体目标，起辅助配伍作用",
};

const roleGroups = computed(() => {
  const first = formulaCards.value[0];
  if (!first || !first.ingredients.length) return [];
  const orderedRoles = ["君药", "臣药", "佐药", "使药", "配伍药"];
  return orderedRoles
    .map((role) => {
      const matched = first.ingredients.filter((item) => item.role === role);
      if (!matched.length) return null;
      return {
        role,
        herbs: matched.map((item) => item.name).join("、"),
        duty: ROLE_DUTY[role] || "协同配方整体目标，起辅助配伍作用",
        notes: matched.map((item) => [item.name, item.rationale].filter(Boolean).join("：")),
      };
    })
    .filter(Boolean);
});

const originalFormula = computed(() => {
  const payload = selectedStepPayload.value;
  const context = Array.isArray(payload?.kb5_formula_context) ? payload.kb5_formula_context[0] : null;
  if (context?.formula_name) {
    const sources = Array.isArray(context.sources)
      ? context.sources.filter(Boolean).join("、")
      : context.sources || "";
    const herbs = (context.ingredients || [])
      .map((item) => item.name)
      .filter(Boolean)
      .join("、");
    return `KB5 原方「${context.formula_name}」${sources ? `（来源：${sources}）` : ""}${herbs ? `，组成：${herbs}` : ""}`;
  }
  return payload?.formulas?.[0]?.classic_reference || "";
});

const selectionRationale = computed(() => {
  const payload = selectedStepPayload.value;
  const rationale = payload?.selection_rationale || "";
  return typeof rationale === "string" ? rationale : itemText(rationale);
});

const complianceNotes = computed(() => toTextList(selectedStepPayload.value?.compliance_notes));

const risks = computed(() => toTextList(selectedStepPayload.value?.risks));

/* ---------- 功效预测 Agent ---------- */

const efficacySections = computed(() => {
  const payload = selectedStepPayload.value;
  if (!payload || typeof payload !== "object") return [];
  const defs = [
    ["core_tcm_efficacy", "中医功效"],
    ["core_modern_efficacy", "现代药理功效"],
    ["mechanisms", "作用机制"],
    ["target_population", "适用人群"],
    ["avoid_population", "不适宜人群"],
    ["contraindicated_population", "禁忌人群"],
    ["risks", "风险提示"],
    ["literature_basis", "文献依据"],
  ];
  const sections = [];
  for (const [key, label] of defs) {
    const items = toTextList(payload[key]);
    if (items.length) sections.push({ label, items });
  }
  return sections;
});

/* ---------- 风味预测 Agent ---------- */

const flavorSections = computed(() => {
  const payload = selectedStepPayload.value;
  if (!payload || typeof payload !== "object") return [];
  const profile = payload.flavor_profile || {};
  const defs = [
    ["taste", "味觉"],
    ["aroma", "香气"],
    ["mouthfeel", "口感"],
  ];
  const sections = [];
  for (const [key, label] of defs) {
    const items = toTextList(profile[key] || payload[key]);
    if (items.length) sections.push({ label, items });
  }
  const extraDefs = [
    ["coordination_summary", "协调性"],
    ["defects", "风味缺陷"],
    ["optimization_suggestions", "优化建议"],
    ["consumer_acceptance", "消费者接受度"],
    ["data_sources", "数据来源"],
  ];
  for (const [key, label] of extraDefs) {
    const items = toTextList(payload[key]);
    if (items.length) sections.push({ label, items });
  }
  return sections;
});

/* ---------- 替代映射 Agent ---------- */

const replacementRows = computed(() => {
  const payload = selectedStepPayload.value;
  const rows =
    (Array.isArray(payload?.recommended_replacements) && payload.recommended_replacements) ||
    store.currentRun.final_report?.modules?.replacement_mapping?.recommended_replacements ||
    [];
  return rows;
});

const baselineRows = computed(() => {
  const payload = selectedStepPayload.value;
  const rows =
    (Array.isArray(payload?.baseline_comparison) && payload.baseline_comparison) ||
    store.currentRun.final_report?.modules?.replacement_mapping?.baseline_comparison ||
    [];
  return rows;
});

const impactSummary = computed(() => {
  const value = selectedStepPayload.value?.impact_summary;
  return typeof value === "string" ? value : itemText(value);
});

const replacementComplianceNotes = computed(() =>
  toTextList(selectedStepPayload.value?.compliance_notes),
);

const replacementScenarios = computed(() =>
  toTextList(selectedStepPayload.value?.applicable_scenarios),
);

/* ---------- 主控汇总 Agent：最终方案 ---------- */

const reportTitle = computed(() => {
  const report = reportPayload.value;
  return report?.final_formula?.name || report?.brief_summary || briefTitle.value;
});

const reportIntro = computed(() => {
  const value = reportPayload.value?.final_recommendation;
  return typeof value === "string" ? value : "";
});

const reportBriefTags = computed(() => {
  const tags = [];
  const brief = store.currentRun.brief;
  if (brief?.goal) tags.push(`目标：${brief.goal}`);
  if (brief?.target_population) tags.push(`人群：${brief.target_population}`);
  if (brief?.dosage_form) tags.push(`剂型：${brief.dosage_form}`);
  if (Array.isArray(brief?.constraints)) {
    tags.push(...brief.constraints.filter(Boolean).map((item) => `约束：${item}`));
  }
  return tags;
});

const reportComposition = computed(() => {
  const report = reportPayload.value;
  const composition = report?.final_formula?.composition;
  if (!Array.isArray(composition)) return [];
  return composition.map((item) => ({
    name: item.name || "未命名药材",
    role: item.role || "配伍药",
    dose: item.dose || "待校验",
    rationale: item.rationale || item.dose_rationale || "",
    basis: item.basis || "",
    source: item.source || "",
  }));
});

const reportMonarchSummary = computed(() => {
  const items = reportPayload.value?.monarch_minister_summary;
  if (!Array.isArray(items)) return [];
  return items
    .map((item) => ({
      role: item.role || "配伍药",
      herbs: Array.isArray(item.herbs) ? item.herbs : [],
      duty: item.duty || ROLE_DUTY[item.role] || "协同配方整体目标，起辅助配伍作用",
    }))
    .filter((item) => item.role && item.herbs.length);
});

const reportOriginalName = computed(() => reportPayload.value?.original_formula?.name || "");
const reportOriginalSource = computed(() => reportPayload.value?.original_formula?.source || "");

const reportOriginalRetained = computed(() => {
  const changes = reportPayload.value?.original_formula?.changes;
  return Array.isArray(changes?.retained) ? changes.retained.map(itemText).filter(Boolean) : [];
});

const reportOriginalReplacedRows = computed(() => {
  const changes = reportPayload.value?.original_formula?.changes;
  if (!Array.isArray(changes?.replaced)) return [];
  return changes.replaced.map((item) => ({
    from: item.from || "",
    to: item.to || "",
    score: item.score,
    confidence: item.confidence || "",
  }));
});

const reportOriginalAdded = computed(() => {
  const changes = reportPayload.value?.original_formula?.changes;
  return Array.isArray(changes?.added) ? changes.added.map(itemText).filter(Boolean) : [];
});

const reportOriginalRemoved = computed(() => {
  const changes = reportPayload.value?.original_formula?.changes;
  return Array.isArray(changes?.removed) ? changes.removed.map(itemText).filter(Boolean) : [];
});

const reportEfficacyEffects = computed(() => {
  const effects = reportPayload.value?.efficacy_summary?.effects;
  return Array.isArray(effects) ? effects.map(itemText).filter(Boolean) : [];
});

const reportEfficacyMechanisms = computed(() => {
  const mechanisms = reportPayload.value?.efficacy_summary?.mechanisms;
  return Array.isArray(mechanisms) ? mechanisms.map(itemText).filter(Boolean) : [];
});

const reportFlavorNotes = computed(() => {
  const notes = reportPayload.value?.flavor_summary?.notes;
  return Array.isArray(notes) ? notes.map(itemText).filter(Boolean) : [];
});

const reportFlavorAcceptance = computed(() => {
  const value = reportPayload.value?.flavor_summary?.acceptance;
  return typeof value === "string" ? value : "";
});

const reportReplacementPoints = computed(() => {
  const rows = reportPayload.value?.modules?.replacement_mapping?.recommended_replacements || [];
  return rows.slice(0, 6).map((row) => {
    const parts = [
      `${row.source_herb || "?"} → ${row.recommended_herb || "?"}`,
      `评分 ${formatCell(row.score)}`,
    ];
    if (row.recommendation_status) parts.push(row.recommendation_status);
    return parts.join(" · ");
  });
});

const reportComplianceRisks = computed(() =>
  toTextList(reportPayload.value?.compliance_risks),
);

const reportEvidenceGaps = computed(() => toTextList(reportPayload.value?.evidence_gaps));

const reportConsistencyChecks = computed(() =>
  toTextList(reportPayload.value?.consistency_checks),
);

const reportNextActions = computed(() => toTextList(reportPayload.value?.next_actions));

const reportDataSources = computed(() => toTextList(reportPayload.value?.data_sources));

const reportHasStructured = computed(
  () =>
    reportComposition.value.length > 0 ||
    reportMonarchSummary.value.length > 0 ||
    Boolean(reportOriginalName.value) ||
    reportOriginalRetained.value.length > 0 ||
    reportOriginalReplacedRows.value.length > 0 ||
    reportOriginalAdded.value.length > 0 ||
    reportOriginalRemoved.value.length > 0 ||
    reportEfficacyEffects.value.length > 0 ||
    reportEfficacyMechanisms.value.length > 0 ||
    reportFlavorNotes.value.length > 0 ||
    Boolean(reportFlavorAcceptance.value) ||
    reportComplianceRisks.value.length > 0 ||
    reportEvidenceGaps.value.length > 0,
);

const reportHasContent = computed(
  () =>
    reportHasStructured.value ||
    Boolean(reportIntro.value) ||
    reportConsistencyChecks.value.length > 0 ||
    reportNextActions.value.length > 0 ||
    reportDataSources.value.length > 0 ||
    legacyModuleSummaries.value.length > 0,
);

/* ---------- 旧版 final_report 兼容 ---------- */

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

const legacyModuleLabelMap = {
  master_control: "主控拆解",
  formula_generation: "方剂生成",
  efficacy_prediction: "功效预测",
  flavor_prediction: "风味预测",
  replacement_mapping: "替代映射",
};

const legacyModuleSummaries = computed(() => {
  const modules =
    store.currentRun.final_report?.modules ||
    (selectedStepPayload.value?.modules || {});
  return Object.entries(modules).map(([key, payload]) => ({
    key,
    title: legacyModuleLabelMap[key] || key,
    summary: key === "formula_generation" ? summarizeFormulaGeneration(payload) : pickFirstMeaningfulText(payload),
  }));
});

/* ---------- 交互 ---------- */

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
  activeTab.value = stepPanelTabs.value[0]?.key || "";
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
  // 回填研发需求输入框：重载历史会话时展示用户原始问题
  question.value = store.currentRun?.question || "";
};

watch(() => store.currentStepDetail?.id, () => {
  activeTab.value = stepPanelTabs.value[0]?.key || "";
  if (!activeTab.value && store.selectedSnapshot) {
    activeTab.value = "graph";
  }
});

watch(() => route.query.runId, hydrate);
watch(() => route.params.sessionId, hydrate);
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

.mt-8 {
  margin-top: 8px;
}

.mb-10 {
  margin-bottom: 10px;
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

.role-duty {
  color: #909399;
  font-size: 12px;
  line-height: 1.6;
  margin-bottom: 6px;
}

.role-notes {
  color: #606266;
  font-size: 12px;
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

.brief-option-row {
  margin-top: 14px;
}

.brief-empty {
  padding: 8px 0;
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
.raw-pre {
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

.section-list {
  margin: 8px 0 0;
  padding-left: 20px;
  color: #606266;
  line-height: 1.6;
  font-size: 13px;
}

.tab-content {
  padding-top: 4px;
}

.formula-card-block {
  padding: 12px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fafafa;
}

.formula-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.change-label {
  color: #606266;
  font-size: 13px;
  font-weight: 500;
}

.small-note {
  margin-top: 8px;
  font-size: 12px;
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
