<template>
  <div class="app-container rnd-page">
    <el-card shadow="never" class="mb-20 rnd-intro-card">
      <div class="rnd-intro">
        <div>
          <h2>{{ t("rnd.title") }}</h2>
          <p class="text-secondary">{{ t("rnd.intro") }}</p>
        </div>
        <el-space wrap>
          <el-tag type="success" effect="light">{{ t("rnd.tagGnn") }}</el-tag>
          <el-tag type="warning" effect="light">{{ t("rnd.tagHomology") }}</el-tag>
        </el-space>
      </div>
    </el-card>

    <div class="rnd-grid-scroll">
      <div class="rnd-grid">
        <el-card shadow="hover" class="box-card panel-card">
        <template #header>
          <div class="card-header">
            <span>{{ t("rnd.requirement") }}</span>
            <el-button type="primary" link @click="createNewSession">{{ t("rnd.newSession") }}</el-button>
          </div>
        </template>
        <el-space direction="vertical" fill class="panel-body">
          <el-input v-model="question" type="textarea" :rows="8" :placeholder="t('rnd.requirementPlaceholder')" />
          <el-checkbox v-model="reuseLastBrief">{{ t("rnd.reuseBrief") }}</el-checkbox>
          <el-button type="primary" :loading="store.submitting" :disabled="workflowBusy" @click="runWorkflow" style="width: 100%;">{{ t("rnd.run") }}</el-button>
          <el-alert
            v-if="workflowBusy"
            :title="t('rnd.runningTip')"
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
            <el-checkbox v-model="showBrief" size="small">{{ t("rnd.briefToggle") }}</el-checkbox>
          </div>
          <el-divider v-if="showBrief" />
          <div v-if="showBrief" class="brief-preview">
            <div class="brief-heading">{{ t("rnd.briefHeading") }}</div>
            <el-descriptions v-if="store.currentRun.brief" :column="1" border size="small">
              <el-descriptions-item :label="t('rnd.goal')">{{ store.currentRun.brief.goal }}</el-descriptions-item>
              <el-descriptions-item :label="t('rnd.dosageForm')">{{ store.currentRun.brief.dosage_form || t("rnd.unspecified") }}</el-descriptions-item>
              <el-descriptions-item :label="t('rnd.population')">{{ store.currentRun.brief.target_population || t("rnd.unspecified") }}</el-descriptions-item>
              <el-descriptions-item :label="t('rnd.timeline')">{{ store.currentRun.brief.timeline || t("rnd.unspecified") }}</el-descriptions-item>
              <el-descriptions-item :label="t('rnd.budget')">{{ store.currentRun.brief.budget || t("rnd.unspecified") }}</el-descriptions-item>
              <el-descriptions-item :label="t('rnd.constraints')">
                <div class="constraint-list">
                  <el-tag v-for="item in store.currentRun.brief.constraints || []" :key="item" size="small" type="info">{{ item }}</el-tag>
                </div>
              </el-descriptions-item>
            </el-descriptions>
            <el-empty
              v-else
              class="brief-empty"
              :description="t('rnd.briefEmpty')"
              :image-size="48"
            />
          </div>
        </el-space>
      </el-card>

        <el-card shadow="hover" class="box-card panel-card">
        <template #header>
          <div class="card-header">
            <span>{{ t("rnd.stageFlow") }}</span>
            <el-tag v-if="store.currentRun.status" :type="statusTagType(store.currentRun.status)" size="small">
              {{ store.currentRun.status }}
            </el-tag>
          </div>
        </template>
        <div v-if="workflowBusy" class="streaming-tip">
          {{ t("rnd.executingStep", { step: runningStepLabel }) }}
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
              <span>{{ t("rnd.latency", { ms: step.latency_ms }) }}</span>
              <span>{{ t("rnd.evidenceCount", { count: step.graph_snapshot_id ? 1 : 0 }) }}</span>
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
              <summary>{{ t("rnd.viewRaw") }}</summary>
              <pre>{{ formatJson(step.output_payload) }}</pre>
            </details>
          </el-card>
        </div>
        <el-empty v-else :description="t('rnd.stepsEmpty')" />
      </el-card>

        <el-card shadow="hover" class="box-card panel-card">
        <template #header>
          <div class="card-header">
            <span>{{ t("rnd.evidenceResults") }}</span>
            <el-tag v-if="store.currentStepDetail" size="small" type="primary">{{ agentLabels[store.currentStepDetail.agent_key] || store.currentStepDetail.agent_key }}</el-tag>
          </div>
        </template>
        <div class="result-overview" v-if="store.currentRun.steps?.length">
          <div class="overview-item">
            <div class="overview-label">{{ t("rnd.totalSteps") }}</div>
            <div class="overview-value">{{ store.currentRun.steps.length }}</div>
          </div>
          <div class="overview-item">
            <div class="overview-label">{{ t("rnd.completed") }}</div>
            <div class="overview-value">{{ completedStepCount }}</div>
          </div>
          <div class="overview-item">
            <div class="overview-label">{{ t("rnd.evidenceSnapshots") }}</div>
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
              <el-empty v-if="!planSections.length" :description="t('rnd.noPlan')" :image-size="60" />
              <div v-for="section in planSections" :key="section.label" class="report-section">
                <strong>{{ section.label }}</strong>
                <ul class="section-list">
                  <li v-for="item in section.items" :key="item">{{ item }}</li>
                </ul>
              </div>
            </div>

            <!-- 配方组成：方剂生成 Agent -->
            <div v-else-if="tab.key === 'formula'" class="tab-content">
              <el-empty v-if="!formulaCards.length" :description="t('rnd.noFormula')" :image-size="60" />
              <template v-else>
                <div v-for="(card, cardIndex) in formulaCards" :key="cardIndex" class="report-section formula-card-block">
                  <div class="formula-card-head">
                    <strong>{{ card.name }}</strong>
                    <el-tag v-if="formulaCards.length > 1" size="small" type="info">{{ t("rnd.candidate", { index: cardIndex + 1, total: formulaCards.length }) }}</el-tag>
                  </div>
                  <el-table :data="card.ingredients" size="small" border class="mt-10">
                    <el-table-column prop="name" :label="t('rnd.herb')" min-width="90" />
                    <el-table-column prop="role" :label="t('rnd.role')" width="80" />
                    <el-table-column prop="dose" :label="t('rnd.dose')" min-width="110" show-overflow-tooltip />
                    <el-table-column prop="rationale" :label="t('rnd.rationale')" min-width="170" show-overflow-tooltip />
                  </el-table>
                  <p v-if="card.fangJie" class="report-copy mt-10">{{ card.fangJie }}</p>
                </div>

                <div v-if="roleGroups.length" class="report-section">
                  <strong>{{ t("rnd.roleGroupsTitle") }}</strong>
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
                  <strong>{{ t("rnd.sourceBasis") }}</strong>
                  <p class="report-copy mt-8">{{ originalFormula }}</p>
                </div>

                <div v-if="selectionRationale" class="report-section">
                  <strong>{{ t("rnd.selectionRationale") }}</strong>
                  <p class="report-copy mt-8">{{ selectionRationale }}</p>
                </div>

                <div v-if="complianceNotes.length || risks.length" class="report-section">
                  <div v-if="complianceNotes.length" class="mb-10">
                    <strong>{{ t("rnd.complianceNotes") }}</strong>
                    <ul class="section-list">
                      <li v-for="item in complianceNotes" :key="item">{{ item }}</li>
                    </ul>
                  </div>
                  <div v-if="risks.length">
                    <strong>{{ t("rnd.risks") }}</strong>
                    <ul class="section-list">
                      <li v-for="item in risks" :key="item">{{ item }}</li>
                    </ul>
                  </div>
                </div>
              </template>
            </div>

            <!-- 功效评估：功效预测 Agent -->
            <div v-else-if="tab.key === 'efficacy'" class="tab-content">
              <el-empty v-if="!efficacySections.length" :description="t('rnd.noEfficacy')" :image-size="60" />
              <div v-for="section in efficacySections" :key="section.label" class="report-section">
                <strong>{{ section.label }}</strong>
                <ul class="section-list">
                  <li v-for="item in section.items" :key="item">{{ item }}</li>
                </ul>
              </div>
            </div>

            <!-- 风味评估：风味预测 Agent -->
            <div v-else-if="tab.key === 'flavor'" class="tab-content">
              <el-empty v-if="!flavorSections.length" :description="t('rnd.noFlavor')" :image-size="60" />
              <div v-for="section in flavorSections" :key="section.label" class="report-section">
                <strong>{{ section.label }}</strong>
                <ul class="section-list">
                  <li v-for="item in section.items" :key="item">{{ item }}</li>
                </ul>
              </div>
            </div>

            <!-- 替代对比：替代映射 Agent -->
            <div v-else-if="tab.key === 'replacement'" class="tab-content">
              <el-empty v-if="!replacementRows.length" :description="t('rnd.replacementEmpty')" :image-size="60" />
              <template v-else>
                <div class="report-section">
                  <strong>{{ t("rnd.replacementCompare") }}</strong>
                  <el-table :data="replacementRows" size="small" border class="mt-10">
                    <el-table-column prop="source_herb" :label="t('rnd.sourceHerb')" min-width="90" />
                    <el-table-column prop="recommended_herb" :label="t('rnd.recommendedHerb')" min-width="90" />
                    <el-table-column prop="score" :label="t('rnd.gnnScore')" width="80" />
                    <el-table-column prop="flavor_acceptance" :label="t('rnd.flavorAcceptance')" width="100" />
                    <el-table-column prop="flavor_similarity" :label="t('rnd.flavorSimilarity')" width="100" />
                    <el-table-column prop="safety_score" :label="t('rnd.safetyScore')" width="80" />
                    <el-table-column prop="population_fit" :label="t('rnd.populationFit')" min-width="180" show-overflow-tooltip />
                    <el-table-column prop="reason" :label="t('rnd.reason')" min-width="140" show-overflow-tooltip />
                  </el-table>
                </div>

                <div v-if="baselineRows.length" class="report-section">
                  <strong>{{ t("rnd.baselineCompare") }}</strong>
                  <el-table :data="baselineRows" size="small" border class="mt-10">
                    <el-table-column prop="source_herb" :label="t('rnd.sourceHerb')" min-width="80" />
                    <el-table-column prop="candidate_herb" :label="t('rnd.candidateHerb')" min-width="80" />
                    <el-table-column :label="t('rnd.efficacyScore')" width="80">
                      <template #default="{ row }">{{ formatCell(row.efficacy_score) }}</template>
                    </el-table-column>
                    <el-table-column :label="t('rnd.flavorBefore')" min-width="150" show-overflow-tooltip>
                      <template #default="{ row }">{{ shortText(row.flavor_before, 60) }}</template>
                    </el-table-column>
                    <el-table-column :label="t('rnd.flavorAfter')" min-width="150" show-overflow-tooltip>
                      <template #default="{ row }">{{ shortText(row.flavor_after, 60) }}</template>
                    </el-table-column>
                    <el-table-column prop="flavor_acceptance" :label="t('rnd.acceptance')" width="80" />
                    <el-table-column prop="flavor_similarity" :label="t('rnd.similarity')" width="80" />
                    <el-table-column prop="safety_score" :label="t('rnd.safetyScore')" width="80" />
                    <el-table-column prop="decision" :label="t('rnd.decision')" width="90" />
                  </el-table>
                </div>

                <div v-if="impactSummary" class="report-section">
                  <strong>{{ t("rnd.impactSummary") }}</strong>
                  <p class="report-copy mt-8">{{ impactSummary }}</p>
                </div>

                <div v-if="replacementComplianceNotes.length || replacementScenarios.length" class="report-section">
                  <div v-if="replacementComplianceNotes.length" class="mb-10">
                    <strong>{{ t("rnd.complianceNotes") }}</strong>
                    <ul class="section-list">
                      <li v-for="item in replacementComplianceNotes" :key="item">{{ item }}</li>
                    </ul>
                  </div>
                  <div v-if="replacementScenarios.length">
                    <strong>{{ t("rnd.scenarios") }}</strong>
                    <ul class="section-list">
                      <li v-for="item in replacementScenarios" :key="item">{{ item }}</li>
                    </ul>
                  </div>
                </div>
              </template>
            </div>

            <!-- 最终方案：主控汇总 Agent -->
            <div v-else-if="tab.key === 'report'" class="tab-content">
              <el-empty v-if="!reportHasContent" :description="workflowBusy ? t('rnd.reportBusy') : t('rnd.reportEmpty')" :image-size="60" />
              <div v-else class="report-block">
                <h3>{{ reportTitle }}</h3>
                <p v-if="reportIntro" class="report-copy">{{ reportIntro }}</p>
                <div v-if="reportBriefTags.length" class="report-section">
                  <strong>{{ t("rnd.requirementPoints") }}</strong>
                  <div class="tag-list mt-8">
                    <el-tag v-for="tag in reportBriefTags" :key="tag" size="small" type="info">{{ tag }}</el-tag>
                  </div>
                </div>

                <div v-if="reportComposition.length" class="report-section">
                  <strong>{{ t("rnd.finalFormula") }}</strong>
                  <el-table :data="reportComposition" size="small" border class="mt-10">
                    <el-table-column prop="name" :label="t('rnd.herb')" min-width="90" />
                    <el-table-column prop="role" :label="t('rnd.role')" width="80" />
                    <el-table-column prop="dose" :label="t('rnd.suggestedDose')" min-width="110" show-overflow-tooltip />
                    <el-table-column prop="rationale" :label="t('rnd.doseRationale')" min-width="170" show-overflow-tooltip />
                    <el-table-column prop="basis" :label="t('rnd.fangJie')" min-width="140" show-overflow-tooltip />
                    <el-table-column prop="source" :label="t('rnd.basisSource')" min-width="130" show-overflow-tooltip />
                  </el-table>
                </div>

                <div v-if="reportMonarchSummary.length" class="report-section">
                  <strong>{{ t("rnd.monarchSummary") }}</strong>
                  <div class="role-grid">
                    <div v-for="group in reportMonarchSummary" :key="group.role" class="role-card">
                      <div class="role-title">{{ group.role }}</div>
                      <div class="role-herbs">{{ (group.herbs || []).join("、") }}</div>
                      <div class="role-duty">{{ group.duty }}</div>
                    </div>
                  </div>
                </div>

                <div v-if="reportOriginalName" class="report-section">
                  <strong>{{ t("rnd.sourceBasis") }}</strong>
                  <p class="report-copy mt-8">{{ reportOriginalName }}<span v-if="reportOriginalSource">{{ t("rnd.sourceWith", { sources: reportOriginalSource }) }}</span></p>
                  <div v-if="reportOriginalRetained.length" class="mt-10">
                    <div class="change-label">{{ t("rnd.retained") }}</div>
                    <div class="tag-list mt-8">
                      <el-tag v-for="item in reportOriginalRetained" :key="item" size="small" type="success">{{ item }}</el-tag>
                    </div>
                  </div>
                  <div v-if="reportOriginalReplacedRows.length" class="mt-10">
                    <div class="change-label">{{ t("rnd.replaced") }}</div>
                    <el-table :data="reportOriginalReplacedRows" size="small" border class="mt-8">
                      <el-table-column prop="from" :label="t('rnd.sourceHerb')" min-width="90" />
                      <el-table-column prop="to" :label="t('rnd.replacementHerb')" min-width="90" />
                      <el-table-column :label="t('rnd.kb4Score')" width="100">
                        <template #default="{ row }">{{ formatCell(row.score) }}</template>
                      </el-table-column>
                      <el-table-column prop="confidence" :label="t('rnd.confidence')" min-width="110" show-overflow-tooltip />
                    </el-table>
                  </div>
                  <div v-if="reportOriginalAdded.length" class="mt-10">
                    <div class="change-label">{{ t("rnd.added") }}</div>
                    <div class="tag-list mt-8">
                      <el-tag v-for="item in reportOriginalAdded" :key="item" size="small" type="warning">{{ item }}</el-tag>
                    </div>
                  </div>
                  <div v-if="reportOriginalRemoved.length" class="mt-10">
                    <div class="change-label">{{ t("rnd.removed") }}</div>
                    <div class="tag-list mt-8">
                      <el-tag v-for="item in reportOriginalRemoved" :key="item" size="small" type="danger" effect="plain">{{ item }}</el-tag>
                    </div>
                  </div>
                </div>

                <div v-if="reportEfficacyEffects.length || reportEfficacyMechanisms.length" class="report-section">
                  <strong>{{ t("rnd.efficacyMechanism") }}</strong>
                  <ul v-if="reportEfficacyEffects.length" class="section-list">
                    <li v-for="item in reportEfficacyEffects" :key="item">{{ t("rnd.effectItem", { item }) }}</li>
                  </ul>
                  <ul v-if="reportEfficacyMechanisms.length" class="section-list">
                    <li v-for="item in reportEfficacyMechanisms" :key="item">{{ t("rnd.mechanismItem", { item }) }}</li>
                  </ul>
                </div>

                <div v-if="reportFlavorNotes.length || reportFlavorAcceptance" class="report-section">
                  <strong>{{ t("rnd.flavorFit") }}</strong>
                  <ul v-if="reportFlavorNotes.length" class="section-list">
                    <li v-for="item in reportFlavorNotes" :key="item">{{ item }}</li>
                  </ul>
                  <p v-if="reportFlavorAcceptance" class="report-copy mt-8">{{ reportFlavorAcceptance }}</p>
                </div>

                <div v-if="reportReplacementPoints.length" class="report-section">
                  <strong>{{ t("rnd.replacementPoints") }}</strong>
                  <ul class="section-list">
                    <li v-for="item in reportReplacementPoints" :key="item">{{ item }}</li>
                  </ul>
                  <p class="text-secondary small-note">{{ t("rnd.replacementNote") }}</p>
                </div>

                <div v-if="reportComplianceRisks.length" class="report-section">
                  <strong>{{ t("rnd.complianceRisks") }}</strong>
                  <ul class="section-list">
                    <li v-for="item in reportComplianceRisks" :key="item">{{ item }}</li>
                  </ul>
                </div>

                <div v-if="reportEvidenceGaps.length" class="report-section">
                  <strong>{{ t("rnd.evidenceGaps") }}</strong>
                  <ul class="section-list">
                    <li v-for="item in reportEvidenceGaps" :key="item">{{ item }}</li>
                  </ul>
                </div>

                <div v-if="reportConsistencyChecks.length" class="report-section">
                  <strong>{{ t("rnd.consistencyChecks") }}</strong>
                  <ul class="section-list">
                    <li v-for="item in reportConsistencyChecks" :key="item">{{ item }}</li>
                  </ul>
                </div>

                <div v-if="reportNextActions.length" class="report-section">
                  <strong>{{ t("rnd.nextSteps") }}</strong>
                  <ul class="section-list">
                    <li v-for="item in reportNextActions" :key="item">{{ item }}</li>
                  </ul>
                </div>

                <!-- 旧版 final_report 兼容：仅当新结构化键缺失时展示分阶段汇总 -->
                <div v-if="!reportHasStructured && legacyModuleSummaries.length" class="report-section">
                  <strong>{{ t("rnd.moduleSummary") }}</strong>
                  <div class="module-grid">
                    <div v-for="moduleItem in legacyModuleSummaries" :key="moduleItem.key" class="module-card">
                      <div class="module-title">{{ moduleItem.title }}</div>
                      <div class="module-copy">{{ moduleItem.summary }}</div>
                    </div>
                  </div>
                </div>

                <div v-if="reportDataSources.length" class="report-section">
                  <strong>{{ t("rnd.dataSources") }}</strong>
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
            ? t('rnd.selectStepHint')
            : (workflowBusy ? t('rnd.resultsBusy') : t('rnd.stepsEmpty'))"
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
import { useI18n } from "../../composables/useI18n";
import { useRndStore } from "../../stores/rnd";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const store = useRndStore();
const question = ref("");
const reuseLastBrief = ref(false);
const showBrief = ref(true);
const activeTab = ref("plan");

const agentLabels = computed(() => ({
  master_control: t("rnd.agents.master_control"),
  master_control_final: t("rnd.agents.master_control_final"),
  formula_generation: t("rnd.agents.formula_generation"),
  efficacy_prediction: t("rnd.agents.efficacy_prediction"),
  flavor_prediction: t("rnd.agents.flavor_prediction"),
  replacement_mapping: t("rnd.agents.replacement_mapping"),
}));

const suggestions = computed(() => [
  t("rnd.suggestion1"),
  t("rnd.suggestion2"),
  t("rnd.suggestion3"),
]);

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
    return agentLabels.value[runningStep.agent_key] || runningStep.agent_key;
  }
  if (store.currentRun.status === "queued") {
    return t("rnd.agents.master_control");
  }
  return t("rnd.currentWorkflow");
});

const briefTitle = computed(() => {
  if (store.currentRun.brief?.goal) return t("rnd.briefTitleWithGoal", { goal: store.currentRun.brief.goal });
  return t("rnd.finalRecommendation");
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
    tabs.push({ key: "plan", label: t("rnd.taskPlan") });
  } else if (key === "formula_generation") {
    tabs.push({ key: "formula", label: t("rnd.formulaComposition") });
  } else if (key === "efficacy_prediction") {
    tabs.push({ key: "efficacy", label: t("rnd.efficacyEval") });
  } else if (key === "flavor_prediction") {
    tabs.push({ key: "flavor", label: t("rnd.flavorEval") });
  } else if (key === "replacement_mapping") {
    tabs.push({ key: "replacement", label: t("rnd.replacementCompare") });
  } else if (key === "master_control_final") {
    tabs.push({ key: "report", label: t("rnd.finalPlan") });
  } else {
    tabs.push({ key: "raw", label: t("rnd.rawResult") });
  }
  if (step.graph_snapshot_id || step.graph_snapshot) {
    tabs.push({ key: "graph", label: t("rnd.evidenceGraph") });
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
    ["brief_summary", t("rnd.sections.briefSummary")],
    ["task_plan", t("rnd.sections.taskPlan")],
    ["plan", t("rnd.sections.planBreakdown")],
    ["tasks", t("rnd.sections.tasks")],
    ["checkpoints", t("rnd.sections.checkpoints")],
    ["target_population", t("rnd.sections.targetPopulation")],
    ["deliverables", t("rnd.sections.deliverables")],
    ["consistency_checks", t("rnd.sections.consistencyChecks")],
    ["next_actions", t("rnd.sections.nextActions")],
    ["data_sources", t("rnd.sections.dataSources")],
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
    name: formula.name || t("rnd.candidateFormula"),
    ingredients: (formula.ingredients || []).map((item) => ({
      name: item.name || item.herb_key || t("rnd.unnamedHerb"),
      role: item.role || t("rnd.compatHerb"),
      dose: item.dose_range || item.dose || t("rnd.pendingVerify"),
      rationale: item.rationale || item.fang_jie_role || item.dose_rationale || t("rnd.efficacyRelated"),
    })),
    fangJie: formula.fang_jie || "",
  }));
});

const ROLE_DUTY_KEYS = {
  君药: "rnd.roleDuty.monarch",
  臣药: "rnd.roleDuty.minister",
  佐药: "rnd.roleDuty.assistant",
  使药: "rnd.roleDuty.guide",
  配伍药: "rnd.roleDuty.compat",
};

const roleDutyText = (role) => t(ROLE_DUTY_KEYS[role] || "rnd.roleDuty.compat");

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
        duty: roleDutyText(role),
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
    return `${t("rnd.kb5Source", { name: context.formula_name })}${sources ? t("rnd.sourceWith", { sources }) : ""}${herbs ? t("rnd.compositionWith", { herbs }) : ""}`;
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
    ["core_tcm_efficacy", t("rnd.sections.tcmEfficacy")],
    ["core_modern_efficacy", t("rnd.sections.modernEfficacy")],
    ["mechanisms", t("rnd.sections.mechanisms")],
    ["target_population", t("rnd.sections.suitablePopulation")],
    ["avoid_population", t("rnd.sections.avoidPopulation")],
    ["contraindicated_population", t("rnd.sections.contraindicatedPopulation")],
    ["risks", t("rnd.sections.riskNotes")],
    ["literature_basis", t("rnd.sections.literatureBasis")],
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
    ["taste", t("rnd.sections.taste")],
    ["aroma", t("rnd.sections.aroma")],
    ["mouthfeel", t("rnd.sections.mouthfeel")],
  ];
  const sections = [];
  for (const [key, label] of defs) {
    const items = toTextList(profile[key] || payload[key]);
    if (items.length) sections.push({ label, items });
  }
  const extraDefs = [
    ["coordination_summary", t("rnd.sections.coordination")],
    ["defects", t("rnd.sections.flavorDefects")],
    ["optimization_suggestions", t("rnd.sections.optimization")],
    ["consumer_acceptance", t("rnd.sections.consumerAcceptance")],
    ["data_sources", t("rnd.sections.dataSources")],
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
  if (brief?.goal) tags.push(t("rnd.briefGoal", { value: brief.goal }));
  if (brief?.target_population) tags.push(t("rnd.briefPopulation", { value: brief.target_population }));
  if (brief?.dosage_form) tags.push(t("rnd.briefForm", { value: brief.dosage_form }));
  if (Array.isArray(brief?.constraints)) {
    tags.push(...brief.constraints.filter(Boolean).map((item) => t("rnd.briefConstraint", { value: item })));
  }
  return tags;
});

const reportComposition = computed(() => {
  const report = reportPayload.value;
  const composition = report?.final_formula?.composition;
  if (!Array.isArray(composition)) return [];
  return composition.map((item) => ({
    name: item.name || t("rnd.unnamedHerb"),
    role: item.role || t("rnd.compatHerb"),
    dose: item.dose || t("rnd.pendingVerify"),
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
      role: item.role || t("rnd.compatHerb"),
      herbs: Array.isArray(item.herbs) ? item.herbs : [],
      duty: item.duty || roleDutyText(item.role),
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
      t("rnd.scoreOf", { score: formatCell(row.score) }),
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
  return t("rnd.generatedResult");
};

const summarizeFormulaGeneration = (payload) => {
  const ingredients = payload?.formulas?.[0]?.ingredients || [];
  if (!ingredients.length) {
    return pickFirstMeaningfulText(payload);
  }
  return ingredients
    .map((item) => `${item.role || t("rnd.compatRoleShort")}：${item.name || t("rnd.unnamedHerb")}`)
    .join("；");
};

const legacyModuleLabelMap = computed(() => ({
  master_control: t("rnd.moduleLabels.master_control"),
  formula_generation: t("rnd.moduleLabels.formula_generation"),
  efficacy_prediction: t("rnd.moduleLabels.efficacy_prediction"),
  flavor_prediction: t("rnd.moduleLabels.flavor_prediction"),
  replacement_mapping: t("rnd.moduleLabels.replacement_mapping"),
}));

const legacyModuleSummaries = computed(() => {
  const modules =
    store.currentRun.final_report?.modules ||
    (selectedStepPayload.value?.modules || {});
  return Object.entries(modules).map(([key, payload]) => ({
    key,
    title: legacyModuleLabelMap.value[key] || key,
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
  if (!payload) return t("rnd.waitingResult");
  if (payload.final_recommendation) return shortText(payload.final_recommendation, 140);
  if (payload.selection_rationale) return shortText(payload.selection_rationale, 140);
  if (payload.coordination_summary) return shortText(payload.coordination_summary, 140);
  if (payload.impact_summary) return shortText(payload.impact_summary, 140);
  if (payload.core_tcm_efficacy?.length) return payload.core_tcm_efficacy.join("；");
  return t("rnd.generatedResult");
};

const getStepHighlights = (payload) => {
  if (!payload || typeof payload !== "object") return [];
  const points = [];
  for (const [key, value] of Object.entries(payload)) {
    if (points.length >= 4) break;
    if (typeof value === "string" && value.trim()) {
      points.push(t("rnd.kv", { key, value: shortText(value, 48) }));
      continue;
    }
    if (Array.isArray(value) && value.length) {
      const first = value[0];
      if (typeof first === "string") {
        points.push(t("rnd.kv", { key, value: shortText(value.slice(0, 3).join("；"), 48) }));
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
  color: var(--app-text-3);
}

.rnd-page {
  display: flex;
  flex-direction: column;
}

.rnd-intro-card {
  border: none;
  background-color: var(--app-panel-2);
}

.rnd-intro {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.rnd-intro h2 {
  margin: 0 0 8px;
  color: var(--app-text);
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
  color: var(--app-text-3);
  font-size: 13px;
}

.role-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.role-card {
  border: 1px solid var(--app-border);
  border-radius: 8px;
  padding: 12px;
  background: var(--app-panel-2);
}

.role-title {
  font-weight: 600;
  color: var(--app-text);
  margin-bottom: 8px;
}

.role-herbs {
  color: #409eff;
  font-weight: 500;
  margin-bottom: 8px;
  line-height: 1.6;
}

.role-duty {
  color: var(--app-text-3);
  font-size: 12px;
  line-height: 1.6;
  margin-bottom: 6px;
}

.role-notes {
  color: var(--app-text-2);
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
  color: var(--app-text);
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
  border: 1px solid var(--app-border);
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
  color: var(--app-text-3);
  font-size: 12px;
  text-transform: uppercase;
}

.step-agent {
  margin-top: 4px;
  color: var(--app-text);
  font-weight: 600;
  font-size: 14px;
}

.step-metrics {
  margin-top: 10px;
  display: flex;
  gap: 12px;
  color: var(--app-text-3);
  font-size: 12px;
}

.step-summary {
  margin-top: 12px;
  line-height: 1.6;
  font-size: 13px;
  color: var(--app-text);
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
  background: var(--app-hover);
  color: var(--app-text-2);
  font-size: 12px;
  line-height: 1.5;
}

.step-detail {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--app-border);
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
  background: var(--app-hover);
  color: var(--app-text-2);
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  border: 1px solid var(--app-border);
}

.report-block h3 {
  margin: 0 0 12px;
  color: var(--app-text);
  font-size: 16px;
}

.report-copy {
  color: var(--app-text-2);
  line-height: 1.6;
  font-size: 14px;
}

.report-section {
  margin-top: 20px;
}

.report-section strong {
  color: var(--app-text);
  font-size: 14px;
}

.report-section ul {
  margin: 8px 0 0;
  padding-left: 20px;
  color: var(--app-text-2);
  line-height: 1.6;
  font-size: 14px;
}

.section-list {
  margin: 8px 0 0;
  padding-left: 20px;
  color: var(--app-text-2);
  line-height: 1.6;
  font-size: 13px;
}

.tab-content {
  padding-top: 4px;
}

.formula-card-block {
  padding: 12px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-panel-2);
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
  color: var(--app-text-2);
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
  border: 1px solid var(--app-border);
  border-radius: 4px;
  background: var(--app-panel-2);
  padding: 10px;
}

.overview-label {
  font-size: 12px;
  color: var(--app-text-3);
}

.overview-value {
  margin-top: 4px;
  font-size: 18px;
  color: var(--app-text);
  font-weight: 600;
}

.module-grid {
  margin-top: 10px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.module-card {
  border: 1px solid var(--app-border);
  border-radius: 4px;
  padding: 10px;
  background: var(--app-panel);
}

.module-title {
  color: var(--app-text);
  font-weight: 600;
  font-size: 13px;
}

.module-copy {
  margin-top: 6px;
  color: var(--app-text-2);
  line-height: 1.5;
  font-size: 12px;
}
</style>
