<template>
  <div class="constitution-panel" :class="{ 'is-compact': compact }">
    <section class="panel-hero">
      <div class="hero-copy">
        <div class="hero-kicker">体质辨识</div>
        <h3>标准量表测评</h3>
        <p>可以直接选择已知体质，也可以按 1-5 分逐题作答，测评结果会保存为后续知识问答的默认体质档案。</p>
      </div>
      <div class="hero-stats">
        <div class="stat-item">
          <strong>{{ store.types.length }}</strong>
          <span>九种体质</span>
        </div>
        <div class="stat-item">
          <strong>{{ store.questions.length }}</strong>
          <span>量表题目</span>
        </div>
        <div class="stat-item">
          <strong>{{ store.answeredCount }}</strong>
          <span>已作答</span>
        </div>
      </div>
    </section>

    <section v-if="store.profile" class="profile-strip">
      <div class="profile-main">
        <span class="profile-label">当前体质档案</span>
        <strong>{{ store.profile.primary_constitution }}</strong>
        <el-tag size="small" :type="store.profile.source === 'assessment' ? 'success' : 'info'">
          {{ store.profile.source === "assessment" ? "量表测评" : "手动选择" }}
        </el-tag>
      </div>
      <div class="profile-detail">
        <span>兼夹：{{ profileSecondaryText }}</span>
        <span>更新：{{ formatTime(store.profile.updated_at) || "未知" }}</span>
      </div>
      <el-button size="small" type="primary" plain @click="startRetest">重新测评</el-button>
    </section>

    <div class="mode-row">
      <el-radio-group v-model="activeMode" size="small">
        <el-radio-button label="manual">手动选择体质</el-radio-button>
        <el-radio-button label="assessment">标准量表测评</el-radio-button>
        <el-radio-button v-if="store.assessments.length && !compact" label="history">历史记录</el-radio-button>
      </el-radio-group>
    </div>

    <section v-show="activeMode === 'manual'" class="mode-section">
      <div class="section-toolbar">
        <div>
          <h4>手动选择体质</h4>
          <p>如果用户已经知道自己的体质，可以直接保存；不确定时建议切换到标准量表测评。</p>
        </div>
        <div class="manual-actions">
          <el-select
            v-model="manualSelectedType"
            placeholder="选择体质"
            size="small"
            filterable
            class="type-select"
          >
            <el-option
              v-for="item in store.types"
              :key="item.constitution_type_name"
              :label="item.constitution_type_name"
              :value="item.constitution_type_name"
            />
          </el-select>
          <el-button
            size="small"
            type="primary"
            :disabled="!manualSelectedType"
            :loading="store.saving"
            @click="chooseSelectedType"
          >
            保存体质
          </el-button>
        </div>
      </div>

      <div class="type-grid">
        <button
          v-for="item in store.types"
          :key="item.constitution_type_name"
          type="button"
          class="type-card"
          :class="{ active: manualSelectedType === item.constitution_type_name }"
          @click="manualSelectedType = item.constitution_type_name"
        >
          <span class="type-name">{{ item.constitution_type_name }}</span>
          <span class="type-category">{{ item.constitution_category || "体质类型" }}</span>
          <span class="type-summary">{{ item.summary || "暂无简要说明" }}</span>
          <span class="type-diet">{{ item.diet_direction || item.food_homology_direction || "暂无食养方向" }}</span>
        </button>
      </div>
    </section>

    <section v-show="activeMode === 'assessment'" class="mode-section assessment-layout">
      <aside class="question-nav" v-if="store.questions.length">
        <div class="progress-title">
          <span>测评进度</span>
          <strong>{{ store.answeredCount }} / {{ store.questions.length }}</strong>
        </div>
        <el-progress :percentage="progressPercent" :stroke-width="8" :show-text="false" />
        <div class="question-dots">
          <button
            v-for="(question, index) in store.questions"
            :key="question.question_code"
            type="button"
            class="question-dot"
            :class="{
              active: index === store.currentQuestionIndex,
              answered: answeredCodes.has(question.question_code),
            }"
            :title="`${question.question_code} ${question.question_text}`"
            @click="goToQuestion(index)"
          >
            {{ index + 1 }}
          </button>
        </div>
      </aside>

      <div v-if="store.currentQuestion" class="question-card">
        <div class="question-meta">
          <el-tag size="small">{{ store.currentQuestion.constitution_type_name || "体质题" }}</el-tag>
          <el-tag v-if="store.currentQuestion.reverse_scored" size="small" type="warning">反向计分</el-tag>
          <span>第 {{ store.currentQuestionIndex + 1 }} / {{ store.questions.length }} 题</span>
        </div>
        <h4>{{ store.currentQuestion.question_code }} {{ store.currentQuestion.question_text }}</h4>

        <div class="score-grid">
          <button
            v-for="option in store.scoreOptions"
            :key="option.value"
            type="button"
            class="score-card"
            :class="{ selected: store.answers[store.currentQuestion.question_code] === Number(option.value) }"
            @click="store.setAnswer(store.currentQuestion.question_code, option.value)"
          >
            <strong>{{ option.value }}</strong>
            <span>{{ option.label }}</span>
            <small>{{ scoreDescription(option.value) }}</small>
          </button>
        </div>

        <div class="question-actions">
          <el-button @click="store.prevQuestion()" :disabled="store.currentQuestionIndex === 0">上一题</el-button>
          <el-button
            @click="store.nextQuestion()"
            :disabled="store.currentQuestionIndex >= store.questions.length - 1"
          >
            下一题
          </el-button>
          <el-button v-if="unansweredCount" plain type="primary" @click="goToFirstUnanswered">
            跳到未答题
          </el-button>
          <el-button
            type="success"
            :loading="store.saving"
            :disabled="!assessmentComplete"
            @click="submitAssessment"
          >
            保存测评结果
          </el-button>
        </div>
        <div class="completion-note" :class="{ done: assessmentComplete }">
          {{ assessmentComplete ? "已完成全部题目，可以保存测评结果。" : `还有 ${unansweredCount} 道题未作答，完成后即可生成体质结果。` }}
        </div>
      </div>

      <el-empty v-else description="当前没有可用的体质量表题目" />
    </section>

    <section v-if="activeMode === 'history' && !compact" class="mode-section">
      <div class="section-toolbar">
        <div>
          <h4>历史测评</h4>
          <p>保留最近的量表结果，便于查看体质档案的变化。</p>
        </div>
      </div>
      <el-table :data="store.assessments" size="small" border stripe max-height="280">
        <el-table-column prop="created_at" label="时间" min-width="160">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="primary_constitution" label="主体质" min-width="120" />
        <el-table-column label="兼夹体质" min-width="160">
          <template #default="{ row }">
            {{ row.secondary_constitutions?.join("、") || "无" }}
          </template>
        </el-table-column>
        <el-table-column prop="result_summary" label="结果摘要" min-width="280" show-overflow-tooltip />
      </el-table>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";

import { useConstitutionStore } from "../stores/constitution";

const props = defineProps({
  payload: {
    type: Object,
    default: null,
  },
  compact: {
    type: Boolean,
    default: false,
  },
});

const store = useConstitutionStore();
const activeMode = ref("assessment");
const manualSelectedType = ref("");

const answeredCodes = computed(() => new Set(Object.keys(store.answers || {})));
const progressPercent = computed(() => {
  if (!store.questions.length) return 0;
  return Math.round((store.answeredCount / store.questions.length) * 100);
});
const unansweredCount = computed(() => Math.max(store.questions.length - store.answeredCount, 0));
const assessmentComplete = computed(() => store.questions.length > 0 && unansweredCount.value === 0);
const profileSecondaryText = computed(() => {
  const values = store.profile?.secondary_constitutions || [];
  return values.length ? values.join("、") : "无";
});

const formatTime = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (value) => String(value).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

const scoreDescription = (value) => {
  const question = store.currentQuestion;
  if (!question) return "";
  return question[`score_${value}`] || store.scoreOptions.find((item) => item.value === value)?.label || "";
};

const chooseSelectedType = async () => {
  if (!manualSelectedType.value) {
    ElMessage.warning("请先选择体质。");
    return;
  }
  await store.saveManualProfile(manualSelectedType.value);
};

const startRetest = () => {
  activeMode.value = "assessment";
  store.resetAssessment();
};

const goToQuestion = (index) => {
  if (index >= 0 && index < store.questions.length) {
    store.currentQuestionIndex = index;
  }
};

const goToFirstUnanswered = () => {
  const index = store.questions.findIndex((item) => !answeredCodes.value.has(item.question_code));
  if (index >= 0) {
    goToQuestion(index);
  }
};

const submitAssessment = async () => {
  if (!assessmentComplete.value) {
    ElMessage.warning(`请先完成全部 ${store.questions.length} 道量表题。`);
    goToFirstUnanswered();
    return;
  }
  await store.submitAssessment("");
};

watch(
  () => props.payload,
  (payload) => {
    if (payload) {
      store.applyQuestionnaire(payload);
      activeMode.value = "assessment";
      manualSelectedType.value = payload.existing_profile?.primary_constitution || "";
    }
  },
  { immediate: true, deep: true }
);

watch(
  () => store.profile?.primary_constitution,
  (value) => {
    if (value) {
      manualSelectedType.value = value;
    }
  },
  { immediate: true }
);

onMounted(async () => {
  if (!props.payload?.questions?.length && !store.questions.length) {
    await store.refreshAll();
  }
});
</script>

<style scoped>
.constitution-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  color: #303133;
}

.panel-hero,
.profile-strip,
.mode-section {
  border: 1px solid #e4e7ed;
  background: #fff;
  border-radius: 8px;
}

.panel-hero {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding: 16px;
}

.hero-copy {
  min-width: 0;
}

.hero-kicker {
  margin-bottom: 4px;
  color: #337ecc;
  font-size: 12px;
  font-weight: 600;
}

.hero-copy h3,
.section-toolbar h4,
.question-card h4 {
  margin: 0;
  letter-spacing: 0;
}

.hero-copy h3 {
  font-size: 18px;
  line-height: 1.4;
}

.hero-copy p,
.section-toolbar p {
  margin: 6px 0 0;
  color: #606266;
  font-size: 13px;
  line-height: 1.7;
}

.hero-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(72px, 1fr));
  gap: 8px;
  min-width: 250px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 64px;
  padding: 8px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  text-align: center;
  background: #f7f9fc;
}

.stat-item strong {
  font-size: 20px;
  line-height: 1.2;
  color: #1f2d3d;
}

.stat-item span {
  margin-top: 4px;
  color: #606266;
  font-size: 12px;
}

.profile-strip {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
}

.profile-main,
.profile-detail {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.profile-main {
  flex-wrap: wrap;
}

.profile-main strong {
  font-size: 15px;
}

.profile-label,
.profile-detail {
  color: #606266;
  font-size: 13px;
}

.profile-detail {
  flex: 1;
  flex-wrap: wrap;
}

.mode-row {
  display: flex;
  justify-content: flex-start;
}

.mode-section {
  padding: 14px;
}

.section-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.manual-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.type-select {
  width: 180px;
}

.type-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
}

.type-card,
.score-card,
.question-dot {
  appearance: none;
  border: 1px solid #dcdfe6;
  background: #fff;
  color: inherit;
  cursor: pointer;
  font: inherit;
}

.type-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 148px;
  padding: 12px;
  border-radius: 8px;
  text-align: left;
}

.type-card:hover,
.type-card.active {
  border-color: #409eff;
  background: #ecf5ff;
}

.type-name {
  font-size: 15px;
  font-weight: 600;
}

.type-category {
  color: #337ecc;
  font-size: 12px;
}

.type-summary,
.type-diet {
  color: #606266;
  font-size: 12px;
  line-height: 1.6;
}

.type-summary {
  display: -webkit-box;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.type-diet {
  padding-top: 6px;
  border-top: 1px dashed #dcdfe6;
}

.assessment-layout {
  display: grid;
  grid-template-columns: minmax(180px, 240px) minmax(0, 1fr);
  gap: 16px;
}

.question-nav {
  border-right: 1px solid #ebeef5;
  padding-right: 16px;
}

.progress-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  color: #606266;
  font-size: 13px;
}

.progress-title strong {
  color: #303133;
}

.question-dots {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(30px, 1fr));
  gap: 8px;
  margin-top: 14px;
}

.question-dot {
  width: 30px;
  height: 30px;
  border-radius: 6px;
  color: #606266;
  font-size: 12px;
}

.question-dot.answered {
  border-color: #95d475;
  background: #f0f9eb;
  color: #529b2e;
}

.question-dot.active {
  border-color: #409eff;
  background: #409eff;
  color: #fff;
  font-weight: 600;
}

.question-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.question-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  color: #909399;
  font-size: 13px;
}

.question-card h4 {
  font-size: 16px;
  line-height: 1.7;
}

.score-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(92px, 1fr));
  gap: 8px;
}

.score-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 92px;
  padding: 10px 8px;
  border-radius: 8px;
  text-align: center;
}

.score-card:hover,
.score-card.selected {
  border-color: #409eff;
  background: #ecf5ff;
}

.score-card strong {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #f2f3f5;
  color: #303133;
}

.score-card.selected strong {
  background: #409eff;
  color: #fff;
}

.score-card span {
  font-weight: 600;
}

.score-card small {
  color: #909399;
  line-height: 1.4;
}

.question-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.completion-note {
  padding: 8px 10px;
  border-radius: 6px;
  background: #fdf6ec;
  color: #b88230;
  font-size: 13px;
}

.completion-note.done {
  background: #f0f9eb;
  color: #529b2e;
}

.is-compact .panel-hero,
.is-compact .profile-strip,
.is-compact .mode-section {
  border-color: #d9ecff;
}

.is-compact .panel-hero {
  padding: 14px;
}

.is-compact .type-grid {
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
}

@media (max-width: 900px) {
  .panel-hero,
  .profile-strip,
  .section-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .hero-stats {
    min-width: 0;
  }

  .manual-actions {
    justify-content: flex-start;
  }

  .assessment-layout {
    grid-template-columns: 1fr;
  }

  .question-nav {
    border-right: 0;
    border-bottom: 1px solid #ebeef5;
    padding-right: 0;
    padding-bottom: 14px;
  }

  .score-grid {
    grid-template-columns: repeat(auto-fit, minmax(104px, 1fr));
  }
}
</style>
