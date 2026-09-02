<template>
  <div class="constitution-panel" :class="{ 'is-compact': compact }">
    <!-- 初次加载骨架屏 -->
    <div v-if="initialLoading" class="panel-skeleton">
      <el-skeleton animated :rows="2" />
      <el-skeleton animated :rows="6" class="skeleton-body" />
    </div>

    <template v-else>
      <!-- 顶部概览 -->
      <section class="panel-hero">
        <div class="hero-copy">
          <div class="hero-kicker">{{ t("constitution.kicker") }}</div>
          <h3>{{ t("constitution.assessmentTitle") }}</h3>
          <p>{{ t("constitution.assessmentDesc") }}</p>
        </div>
        <div class="hero-stats">
          <div class="stat-item">
            <strong>{{ store.types.length }}</strong>
            <span>{{ t("constitution.stats.types") }}</span>
          </div>
          <div class="stat-item">
            <strong>{{ store.questions.length }}</strong>
            <span>{{ t("constitution.stats.questions") }}</span>
          </div>
          <div class="stat-item">
            <strong>{{ store.answeredCount }}</strong>
            <span>{{ t("constitution.stats.answered") }}</span>
          </div>
        </div>
      </section>

      <!-- 结果区：体质结果大卡片 + 评分条 + 食养/慎用分区 -->
      <section v-if="store.profile" class="mode-section result-section">
        <div class="result-card">
          <div class="result-main">
            <span
              class="result-icon"
              :style="{ background: typeColor(store.profile.primary_constitution) }"
            >{{ typeIconChar(store.profile.primary_constitution) }}</span>
            <div class="result-info">
              <div class="result-kicker">{{ t("constitution.result.currentProfile") }}</div>
              <div class="result-primary">{{ store.profile.primary_constitution }}</div>
              <div class="result-tags">
                <el-tag
                  v-for="(sec, idx) in store.profile.secondary_constitutions || []"
                  :key="idx"
                  size="small"
                  effect="plain"
                >{{ sec }}</el-tag>
                <el-tag
                  size="small"
                  :type="store.profile.source === 'assessment' ? 'success' : 'info'"
                  effect="light"
                >
                  {{ store.profile.source === "assessment" ? t("constitution.result.sourceAssessment") : t("constitution.result.sourceManual") }}
                </el-tag>
              </div>
              <div class="result-meta">
                <span>{{ t("constitution.result.updatedAt") }}：{{ formatTime(store.profile.updated_at) || t("constitution.result.unknown") }}</span>
                <span v-if="store.profile.notes">{{ t("constitution.result.notes") }}：{{ store.profile.notes }}</span>
              </div>
            </div>
          </div>
          <div class="result-actions">
            <el-button size="small" type="primary" plain @click="startRetest">
              {{ t("constitution.result.retake") }}
            </el-button>
          </div>
        </div>

        <div v-if="scoreEntries.length" class="score-bars">
          <div class="subtitle-row">
            <span class="subtitle">{{ t("constitution.result.scoreBars") }}</span>
            <span class="subtitle-note">{{ t("constitution.result.scoreNote") }}</span>
          </div>
          <div v-for="entry in scoreEntries" :key="entry.name" class="score-bar-row">
            <span class="score-bar-name" :title="entry.name">{{ entry.name }}</span>
            <div class="score-bar-track">
              <div
                class="score-bar-fill"
                :style="{ width: `${entry.percent}%`, background: entry.color }"
              ></div>
            </div>
            <span class="score-bar-value">{{ entry.average.toFixed(2) }}</span>
          </div>
        </div>
        <div v-else class="result-summary">{{ t("constitution.result.noScoreData") }}</div>

        <div v-if="latestSummary" class="result-summary">
          <strong>{{ t("constitution.result.summary") }}：</strong>{{ latestSummary }}
        </div>

        <div class="diet-grid">
          <div class="diet-card">
            <div class="diet-title">
              <span class="diet-dot" style="background: #409eff"></span>
              {{ t("constitution.result.dietDirection") }}
            </div>
            <p class="diet-text">
              {{ currentType?.diet_direction || currentType?.food_homology_direction || t("constitution.result.noDiet") }}
            </p>
            <template v-if="currentType?.suitable_ingredient_examples">
              <div class="diet-sub">{{ t("constitution.result.suitableIngredients") }}</div>
              <p class="diet-text diet-text-sub">{{ currentType.suitable_ingredient_examples }}</p>
            </template>
            <template v-if="currentType?.recommended_herbs?.length">
              <div class="diet-sub">{{ t("constitution.result.recommendedHerbs") }}</div>
              <div class="herb-chips">
                <el-tag
                  v-for="(herb, idx) in currentType.recommended_herbs"
                  :key="`r${idx}`"
                  size="small"
                  type="success"
                  effect="light"
                >{{ herb }}</el-tag>
              </div>
            </template>
          </div>
          <div class="diet-card diet-card-caution">
            <div class="diet-title">
              <span class="diet-dot" style="background: #f56c6c"></span>
              {{ t("constitution.result.cautionHerbs") }}
            </div>
            <div v-if="currentType?.caution_herbs?.length" class="herb-chips">
              <el-tag
                v-for="(herb, idx) in currentType.caution_herbs"
                :key="`c${idx}`"
                size="small"
                type="danger"
                effect="light"
              >{{ herb }}</el-tag>
            </div>
            <p v-else class="diet-text">{{ t("constitution.result.noCaution") }}</p>
          </div>
        </div>
      </section>

      <!-- 模式切换 -->
      <div class="mode-row">
        <el-radio-group v-model="activeMode" size="small">
          <el-radio-button value="manual">{{ t("constitution.modes.manual") }}</el-radio-button>
          <el-radio-button value="assessment">{{ t("constitution.modes.assessment") }}</el-radio-button>
          <el-radio-button v-if="store.assessments.length && !compact" value="history">
            {{ t("constitution.modes.history") }}
          </el-radio-button>
        </el-radio-group>
      </div>

      <!-- 手动选择量表：九种体质卡片网格 -->
      <section v-show="activeMode === 'manual'" class="mode-section">
        <div class="section-toolbar">
          <div>
            <h4>{{ t("constitution.manual.title") }}</h4>
            <p>{{ t("constitution.manual.desc") }}</p>
          </div>
        </div>

        <div v-if="store.types.length" class="type-grid">
          <button
            v-for="item in store.types"
            :key="item.constitution_type_name"
            type="button"
            class="type-card"
            :class="{ active: manualSelectedType === item.constitution_type_name }"
            :aria-pressed="manualSelectedType === item.constitution_type_name"
            @click="manualSelectedType = item.constitution_type_name"
          >
            <div class="type-head">
              <span
                class="type-icon"
                :style="{ background: typeColor(item.constitution_type_name) }"
              >{{ typeIconChar(item.constitution_type_name) }}</span>
              <div class="type-head-text">
                <span class="type-name">{{ item.constitution_type_name }}</span>
                <span class="type-category">{{ item.constitution_category || t("constitution.manual.defaultCategory") }}</span>
              </div>
              <span
                v-if="manualSelectedType === item.constitution_type_name"
                class="type-check"
              >✓</span>
            </div>
            <span class="type-summary">{{ item.summary || t("constitution.manual.noSummary") }}</span>
            <span class="type-diet">{{ item.diet_direction || item.food_homology_direction || t("constitution.manual.noDiet") }}</span>
          </button>
        </div>
        <el-empty v-else :description="t('constitution.empty.noTypes')" :image-size="72" />

        <div class="manual-actions">
          <el-button
            type="primary"
            :disabled="!manualSelectedType"
            :loading="store.saving"
            @click="chooseSelectedType"
          >
            {{ t("constitution.manual.saveProfile") }}
          </el-button>
          <el-button plain :disabled="!manualSelectedType" @click="enterTypeAssessment">
            {{ t("constitution.manual.enterAssessment") }}
          </el-button>
        </div>
      </section>

      <!-- 标准量表测评 -->
      <section v-show="activeMode === 'assessment'" class="mode-section assessment-section">
        <template v-if="store.questions.length">
          <!-- 顶部进度条 -->
          <div class="assessment-progress">
            <div class="progress-head">
              <span class="progress-label">{{ t("constitution.assessment.progress") }}</span>
              <strong class="progress-count">{{ displayAnsweredCount }} / {{ displayQuestions.length }}</strong>
              <span class="progress-percent">{{ progressPercent }}%</span>
            </div>
            <el-progress
              :percentage="progressPercent"
              :stroke-width="10"
              striped
              striped-flow
              :show-text="false"
            />
            <div v-if="typeFilter" class="filter-chip">
              <span>{{ t("constitution.assessment.filtering", { type: typeFilter }) }}</span>
              <button type="button" class="filter-clear" @click="clearFilter">
                {{ t("constitution.assessment.clearFilter") }}
              </button>
            </div>
          </div>

          <template v-if="displayQuestions.length">
            <div class="assessment-layout">
              <!-- 题目导航 / 一键跳题缩略条 -->
              <aside class="question-nav">
                <div class="nav-head">
                  <span>{{ t("constitution.assessment.jumpTitle") }}</span>
                  <el-button
                    v-if="unansweredCount"
                    size="small"
                    text
                    type="primary"
                    @click="jumpToFirstUnanswered"
                  >
                    {{ t("constitution.assessment.jumpToUnanswered") }}
                  </el-button>
                </div>
                <div class="question-dots">
                  <button
                    v-for="(question, index) in displayQuestions"
                    :key="question.question_code"
                    type="button"
                    class="question-dot"
                    :class="{
                      active: index === currentIndex,
                      answered: answeredSet.has(question.question_code),
                    }"
                    :title="`${question.question_code} ${question.question_text}`"
                    @click="goToQuestion(index)"
                  >{{ index + 1 }}</button>
                </div>
              </aside>

              <!-- 题干卡片 -->
              <div v-if="currentQuestion" class="question-card">
                <div class="question-head">
                  <span
                    class="question-badge"
                    :style="{ background: typeColor(currentQuestion.constitution_type_name) }"
                  >{{ currentIndex + 1 }}</span>
                  <div class="question-meta">
                    <el-tag v-if="currentQuestion.constitution_type_name" size="small">
                      {{ currentQuestion.constitution_type_name }}
                    </el-tag>
                    <el-tag v-if="currentQuestion.reverse_scored" size="small" type="warning" effect="light">
                      {{ t("constitution.assessment.reverseScored") }}
                    </el-tag>
                    <span class="question-order">
                      {{ t("constitution.assessment.questionOfTotal", { current: currentIndex + 1, total: displayQuestions.length }) }}
                    </span>
                  </div>
                </div>
                <h4 class="question-text">
                  <span class="question-code">{{ currentQuestion.question_code }}</span>{{ currentQuestion.question_text }}
                </h4>

                <!-- 选项按钮组（radio 化） -->
                <div class="option-list" role="radiogroup" :aria-label="t('constitution.assessment.options')">
                  <button
                    v-for="option in store.scoreOptions"
                    :key="option.value"
                    type="button"
                    class="option-row"
                    role="radio"
                    :aria-checked="currentAnswer === Number(option.value)"
                    :class="{ selected: currentAnswer === Number(option.value) }"
                    @click="store.setAnswer(currentQuestion.question_code, option.value)"
                  >
                    <span class="option-radio"><i v-if="currentAnswer === Number(option.value)" /></span>
                    <span class="option-value">{{ option.value }}</span>
                    <span class="option-label">{{ scoreLabel(option) }}</span>
                    <span class="option-desc">{{ scoreDescription(option.value) }}</span>
                  </button>
                </div>

                <div class="question-actions">
                  <el-button :disabled="currentIndex === 0" @click="goPrev">
                    {{ t("constitution.assessment.prev") }}
                  </el-button>
                  <el-button :disabled="currentIndex >= displayQuestions.length - 1" @click="goNext">
                    {{ t("constitution.assessment.next") }}
                  </el-button>
                  <el-button v-if="unansweredCount" plain type="primary" @click="jumpToFirstUnanswered">
                    {{ t("constitution.assessment.jumpToUnanswered") }}
                  </el-button>
                  <el-button
                    type="success"
                    :loading="store.saving"
                    :disabled="!assessmentComplete"
                    @click="submitAssessment"
                  >
                    {{ t("constitution.assessment.submit") }}
                  </el-button>
                </div>

                <!-- 提交前未答提示 -->
                <div class="completion-note" :class="{ done: assessmentComplete }">
                  <template v-if="assessmentComplete">
                    {{ t("constitution.assessment.completeNote") }}
                  </template>
                  <template v-else>
                    <span>{{ t("constitution.assessment.incompleteNote", { count: unansweredCount }) }}</span>
                    <span class="unanswered-chips">
                      <button
                        v-for="item in unansweredQuestions"
                        :key="item.question_code"
                        type="button"
                        class="unanswered-chip"
                        :title="`${item.question_code} ${item.question_text}`"
                        @click="goToQuestion(item.index)"
                      >{{ item.index + 1 }}</button>
                    </span>
                  </template>
                </div>
              </div>
            </div>
          </template>
          <div v-else class="filter-empty">
            <el-empty :description="t('constitution.assessment.noMatchingQuestions')" :image-size="72">
              <el-button type="primary" plain size="small" @click="clearFilter">
                {{ t("constitution.assessment.allQuestions") }}
              </el-button>
            </el-empty>
          </div>
        </template>
        <el-empty v-else :description="t('constitution.empty.noQuestions')" :image-size="72" />
      </section>

      <!-- 历史测评时间线 -->
      <section v-if="activeMode === 'history' && !compact" class="mode-section">
        <div class="section-toolbar">
          <div>
            <h4>{{ t("constitution.history.title") }}</h4>
            <p>{{ t("constitution.history.desc") }}</p>
          </div>
        </div>
        <el-timeline v-if="store.assessments.length" class="history-timeline">
          <el-timeline-item
            v-for="item in store.assessments"
            :key="item.id"
            :timestamp="formatTime(item.created_at)"
            placement="top"
            :color="typeColor(item.primary_constitution)"
          >
            <div
              class="history-card"
              :class="{ expanded: expandedHistoryId === item.id }"
              @click="toggleHistory(item.id)"
            >
              <div class="history-head">
                <strong class="history-primary">{{ item.primary_constitution }}</strong>
                <span
                  v-for="(sec, idx) in item.secondary_constitutions || []"
                  :key="idx"
                  class="history-sec"
                >{{ sec }}</span>
                <span class="history-count">
                  {{ historyQuestionCount(item) }} {{ t("constitution.history.questionsAnswered") }}
                </span>
              </div>
              <div v-if="item.result_summary" class="history-summary">{{ item.result_summary }}</div>
              <div v-if="expandedHistoryId === item.id && historyEntries(item).length" class="history-scores">
                <div v-for="entry in historyEntries(item)" :key="entry.name" class="score-bar-row">
                  <span class="score-bar-name" :title="entry.name">{{ entry.name }}</span>
                  <div class="score-bar-track">
                    <div
                      class="score-bar-fill"
                      :style="{ width: `${entry.percent}%`, background: entry.color }"
                    ></div>
                  </div>
                  <span class="score-bar-value">{{ entry.average.toFixed(2) }}</span>
                </div>
              </div>
              <div v-if="historyEntries(item).length" class="history-toggle">
                {{ expandedHistoryId === item.id ? t("constitution.history.collapse") : t("constitution.history.viewScores") }}
              </div>
            </div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else :description="t('constitution.empty.noAssessments')" :image-size="72" />
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";

import { useI18n } from "../composables/useI18n";
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

const { t } = useI18n();
const store = useConstitutionStore();

const activeMode = ref("assessment");
const manualSelectedType = ref("");
const typeFilter = ref("");
const currentIndex = ref(0);
const expandedHistoryId = ref(null);

// ---- 体质配色与图标（九种体质 + 兜底散列色） ----
const TYPE_COLORS = {
  平和质: "#67c23a",
  气虚质: "#409eff",
  阳虚质: "#d68910",
  阴虚质: "#f56c6c",
  痰湿质: "#8d6e63",
  湿热质: "#f0932b",
  血瘀质: "#9c27b0",
  气郁质: "#1abc9c",
  特禀质: "#e91e63",
};
const FALLBACK_COLORS = [
  "#409eff",
  "#67c23a",
  "#e6a23c",
  "#f56c6c",
  "#9c27b0",
  "#1abc9c",
  "#e91e63",
  "#f0932b",
  "#8d6e63",
];
const typeColor = (name) => {
  if (name && TYPE_COLORS[name]) return TYPE_COLORS[name];
  let hash = 0;
  const source = String(name || "体质");
  for (let i = 0; i < source.length; i += 1) {
    hash = (hash * 31 + source.charCodeAt(i)) >>> 0;
  }
  return FALLBACK_COLORS[hash % FALLBACK_COLORS.length];
};
const typeIconChar = (name) => (String(name || "体").trim().charAt(0) || "体");

// ---- 问卷状态 ----
const answeredSet = computed(() => new Set(Object.keys(store.answers || {})));
const displayQuestions = computed(() => {
  const all = store.questions || [];
  if (!typeFilter.value) return all;
  return all.filter((item) => item.constitution_type_name === typeFilter.value);
});
const currentQuestion = computed(() => displayQuestions.value[currentIndex.value] || null);
const currentAnswer = computed(() => {
  const code = currentQuestion.value?.question_code;
  if (!code || store.answers?.[code] == null) return null;
  return Number(store.answers[code]);
});
const displayAnsweredCount = computed(() =>
  displayQuestions.value.filter((item) => answeredSet.value.has(item.question_code)).length,
);
const progressPercent = computed(() => {
  if (!displayQuestions.value.length) return 0;
  return Math.round((displayAnsweredCount.value / displayQuestions.value.length) * 100);
});
const unansweredCount = computed(() =>
  Math.max(displayQuestions.value.length - displayAnsweredCount.value, 0),
);
const assessmentComplete = computed(
  () => displayQuestions.value.length > 0 && unansweredCount.value === 0,
);
const unansweredQuestions = computed(() =>
  displayQuestions.value
    .map((item, index) => ({ ...item, index }))
    .filter((item) => !answeredSet.value.has(item.question_code)),
);
const initialLoading = computed(
  () => store.loading && !store.types.length && !store.questions.length && !store.profile,
);

// ---- 结果区 ----
const normalizeScoreEntries = (scores) => {
  const byConstitution = scores?.by_constitution || {};
  return Object.entries(byConstitution)
    .map(([name, value]) => ({
      name,
      average: Number(value?.average_score ?? 0),
      count: Number(value?.question_count ?? 0),
    }))
    .filter((entry) => entry.count > 0)
    .sort((a, b) => b.average - a.average || a.name.localeCompare(b.name))
    .map((entry) => ({
      ...entry,
      percent: Math.max(0, Math.min(100, Math.round((entry.average / 5) * 100))),
      color: typeColor(entry.name),
    }));
};
const scoreEntries = computed(() => normalizeScoreEntries(store.profile?.scores));
const historyEntries = (item) => normalizeScoreEntries(item?.scores);
const historyQuestionCount = (item) => Object.keys(item?.answers || {}).length;
const currentType = computed(() => {
  const name = store.profile?.primary_constitution;
  if (!name) return null;
  return store.types.find((item) => item.constitution_type_name === name) || null;
});
const latestSummary = computed(() => {
  if (store.profile?.source !== "assessment" || !store.assessments?.length) return "";
  const latest =
    store.assessments.find((item) => item.id === store.profile?.last_assessment_id) ||
    store.assessments[0];
  return latest?.result_summary || "";
});

// ---- 工具函数 ----
const formatTime = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (value) => String(value).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

const scoreLabel = (option) => {
  const key = `constitution.scoreScale.${option.value}`;
  const text = t(key);
  return text === key ? option.label : text;
};

const scoreDescription = (value) => {
  const question = currentQuestion.value;
  if (!question) return "";
  return (
    question[`score_${value}`] ||
    store.scoreOptions.find((item) => item.value === value)?.label ||
    ""
  );
};

// ---- 交互动作 ----
const chooseSelectedType = async () => {
  if (!manualSelectedType.value) {
    ElMessage.warning(t("constitution.messages.selectTypeFirst"));
    return;
  }
  await store.saveManualProfile(manualSelectedType.value);
};

const enterTypeAssessment = () => {
  if (!manualSelectedType.value) return;
  typeFilter.value = manualSelectedType.value;
  currentIndex.value = 0;
  activeMode.value = "assessment";
};

const clearFilter = () => {
  typeFilter.value = "";
  currentIndex.value = 0;
};

const startRetest = () => {
  typeFilter.value = "";
  currentIndex.value = 0;
  activeMode.value = "assessment";
  store.resetAssessment();
};

const goPrev = () => {
  if (currentIndex.value > 0) currentIndex.value -= 1;
};

const goNext = () => {
  if (currentIndex.value < displayQuestions.value.length - 1) currentIndex.value += 1;
};

const goToQuestion = (index) => {
  if (index >= 0 && index < displayQuestions.value.length) {
    currentIndex.value = index;
  }
};

const jumpToFirstUnanswered = () => {
  const item = unansweredQuestions.value[0];
  if (item) {
    goToQuestion(item.index);
  }
};

const toggleHistory = (id) => {
  expandedHistoryId.value = expandedHistoryId.value === id ? null : id;
};

const submitAssessment = async () => {
  if (!assessmentComplete.value) {
    ElMessage.warning(
      t("constitution.messages.completeAll", { count: displayQuestions.value.length }),
    );
    jumpToFirstUnanswered();
    return;
  }
  await store.submitAssessment("");
};

// ---- 响应式同步 ----
watch(
  () => props.payload,
  (payload) => {
    if (payload) {
      store.applyQuestionnaire(payload);
      activeMode.value = "assessment";
      typeFilter.value = "";
      currentIndex.value = 0;
      manualSelectedType.value = payload.existing_profile?.primary_constitution || "";
    }
  },
  { immediate: true, deep: true },
);

watch(
  () => store.profile?.primary_constitution,
  (value) => {
    if (value) {
      manualSelectedType.value = value;
    }
  },
  { immediate: true },
);

watch(
  () => displayQuestions.value.length,
  (length) => {
    if (currentIndex.value >= length) {
      currentIndex.value = Math.max(length - 1, 0);
    }
  },
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
  color: var(--app-text);
}

/* ---- 骨架屏 ---- */
.panel-skeleton {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 18px;
  border: 1px solid var(--app-border);
  border-radius: 10px;
  background: var(--app-panel);
}

/* ---- 通用卡片 ---- */
.panel-hero,
.mode-section {
  border: 1px solid var(--app-border);
  background: var(--app-panel);
  border-radius: 10px;
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
  color: var(--app-active-border);
  font-size: 12px;
  font-weight: 600;
}

.hero-copy h3,
.section-toolbar h4 {
  margin: 0;
  letter-spacing: 0;
}

.hero-copy h3 {
  font-size: 18px;
  line-height: 1.4;
  color: var(--app-text);
}

.hero-copy p,
.section-toolbar p {
  margin: 6px 0 0;
  color: var(--app-text-2);
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
  border: 1px solid var(--app-border);
  border-radius: 8px;
  text-align: center;
  background: var(--app-panel-2);
}

.stat-item strong {
  font-size: 20px;
  line-height: 1.2;
  color: var(--app-text);
}

.stat-item span {
  margin-top: 4px;
  color: var(--app-text-2);
  font-size: 12px;
}

/* ---- 结果区 ---- */
.mode-section {
  padding: 14px;
}

.result-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.result-main {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  min-width: 0;
}

.result-icon {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 14px;
  color: #fff;
  font-size: 24px;
  font-weight: 600;
}

.result-info {
  min-width: 0;
}

.result-kicker {
  color: var(--app-text-3);
  font-size: 12px;
  margin-bottom: 2px;
}

.result-primary {
  font-size: 20px;
  font-weight: 600;
  color: var(--app-text);
  line-height: 1.3;
}

.result-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  margin-top: 8px;
  color: var(--app-text-3);
  font-size: 12px;
}

.result-actions {
  flex: none;
}

.score-bars {
  margin-top: 16px;
}

.subtitle-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.subtitle {
  font-size: 14px;
  font-weight: 600;
  color: var(--app-text);
}

.subtitle-note {
  color: var(--app-text-3);
  font-size: 12px;
}

.score-bar-row {
  display: grid;
  grid-template-columns: 92px 1fr 52px;
  gap: 10px;
  align-items: center;
  margin-bottom: 8px;
}

.score-bar-name {
  font-size: 13px;
  color: var(--app-text-2);
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.score-bar-track {
  height: 10px;
  border-radius: 5px;
  background: var(--app-hover);
  overflow: hidden;
}

.score-bar-fill {
  height: 100%;
  min-width: 2px;
  border-radius: 5px;
  transition: width 0.4s ease;
}

.score-bar-value {
  font-size: 12px;
  color: var(--app-text-3);
  font-variant-numeric: tabular-nums;
}

.result-summary {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--app-panel-2);
  border: 1px dashed var(--app-border);
  color: var(--app-text-2);
  font-size: 13px;
  line-height: 1.7;
}

.diet-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.diet-card {
  border: 1px solid var(--app-border);
  border-radius: 8px;
  padding: 12px;
  background: var(--app-panel-2);
}

.diet-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--app-text);
  margin-bottom: 8px;
}

.diet-dot {
  flex: none;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.diet-text {
  margin: 0;
  color: var(--app-text-2);
  font-size: 13px;
  line-height: 1.7;
}

.diet-text-sub {
  margin-top: 4px;
}

.diet-sub {
  margin-top: 10px;
  color: var(--app-text-3);
  font-size: 12px;
  font-weight: 600;
}

.herb-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}

/* ---- 模式切换 ---- */
.mode-row {
  display: flex;
  justify-content: flex-start;
}

.section-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

/* ---- 手动选择量表卡片 ---- */
.type-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.type-card {
  appearance: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 150px;
  padding: 12px;
  border: 1px solid var(--app-border);
  border-radius: 10px;
  background: var(--app-panel);
  color: inherit;
  cursor: pointer;
  font: inherit;
  text-align: left;
  transition: border-color 0.2s ease, background-color 0.2s ease, transform 0.15s ease, box-shadow 0.2s ease;
}

.type-card:hover {
  border-color: var(--app-active-border);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.type-card.active {
  border-color: var(--app-active-border);
  background: var(--app-active);
}

.type-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.type-icon {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
}

.type-head-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.type-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--app-text);
}

.type-category {
  color: var(--app-text-3);
  font-size: 12px;
}

.type-check {
  margin-left: auto;
  color: var(--app-active-border);
  font-size: 16px;
  font-weight: 700;
}

.type-summary,
.type-diet {
  color: var(--app-text-2);
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
  border-top: 1px dashed var(--app-border);
}

.manual-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 14px;
}

/* ---- 标准量表测评 ---- */
.assessment-progress {
  margin-bottom: 14px;
}

.progress-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 6px;
}

.progress-label {
  color: var(--app-text-2);
  font-size: 13px;
}

.progress-count {
  color: var(--app-text);
  font-size: 15px;
}

.progress-percent {
  margin-left: auto;
  color: var(--app-active-border);
  font-size: 14px;
  font-weight: 600;
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding: 4px 10px;
  border: 1px solid var(--app-active-border);
  border-radius: 999px;
  background: var(--app-active);
  color: var(--app-active-border);
  font-size: 12px;
}

.filter-clear {
  appearance: none;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
  padding: 0;
  text-decoration: underline;
}

.filter-empty {
  padding: 8px 0;
}

.assessment-layout {
  display: grid;
  grid-template-columns: minmax(180px, 240px) minmax(0, 1fr);
  gap: 16px;
}

.question-nav {
  border-right: 1px solid var(--app-border);
  padding-right: 16px;
}

.nav-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
  color: var(--app-text-2);
  font-size: 13px;
}

.question-dots {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(30px, 1fr));
  gap: 8px;
}

.question-dot {
  appearance: none;
  width: 30px;
  height: 30px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-panel);
  color: var(--app-text-2);
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.question-dot:hover {
  border-color: var(--app-active-border);
  color: var(--app-active-border);
}

.question-dot.answered {
  border-color: rgba(103, 194, 58, 0.55);
  background: rgba(103, 194, 58, 0.12);
  color: #67c23a;
}

.question-dot.active {
  border-color: var(--app-active-border);
  background: var(--app-active-border);
  color: #fff;
  font-weight: 600;
}

.question-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.question-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.question-badge {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}

.question-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--app-text-3);
  font-size: 13px;
}

.question-order {
  color: var(--app-text-3);
}

.question-text {
  margin: 0;
  font-size: 16px;
  line-height: 1.7;
  color: var(--app-text);
}

.question-code {
  display: inline-block;
  margin-right: 8px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--app-hover);
  color: var(--app-text-3);
  font-size: 12px;
  font-weight: 500;
  vertical-align: 1px;
}

.option-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.option-row {
  appearance: none;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border: 1px solid var(--app-border);
  border-radius: 10px;
  background: var(--app-panel);
  color: inherit;
  cursor: pointer;
  font: inherit;
  text-align: left;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.option-row:hover {
  border-color: var(--app-active-border);
}

.option-row.selected {
  border-color: var(--app-active-border);
  background: var(--app-active);
}

.option-radio {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: 2px solid var(--app-text-3);
  border-radius: 50%;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.option-row.selected .option-radio {
  border-color: var(--app-active-border);
  background: var(--app-active-border);
}

.option-radio i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #fff;
}

.option-value {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 8px;
  background: var(--app-hover);
  color: var(--app-text);
  font-size: 13px;
  font-weight: 600;
}

.option-row.selected .option-value {
  background: var(--app-active-border);
  color: #fff;
}

.option-label {
  flex: none;
  min-width: 44px;
  font-size: 14px;
  font-weight: 600;
}

.option-desc {
  color: var(--app-text-3);
  font-size: 12px;
  line-height: 1.5;
}

.question-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.completion-note {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(230, 162, 60, 0.12);
  color: #b88230;
  font-size: 13px;
  line-height: 1.6;
}

.completion-note.done {
  background: rgba(103, 194, 58, 0.12);
  color: #529b2e;
}

.unanswered-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.unanswered-chip {
  appearance: none;
  width: 24px;
  height: 24px;
  border: 1px solid rgba(230, 162, 60, 0.55);
  border-radius: 6px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  transition: background-color 0.15s ease;
}

.unanswered-chip:hover {
  background: rgba(230, 162, 60, 0.25);
}

/* ---- 历史测评时间线 ---- */
.history-timeline {
  padding: 4px 2px;
}

.history-card {
  border: 1px solid var(--app-border);
  border-radius: 10px;
  padding: 12px 14px;
  background: var(--app-panel-2);
  cursor: pointer;
  transition: border-color 0.15s ease;
}

.history-card:hover,
.history-card.expanded {
  border-color: var(--app-active-border);
}

.history-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.history-primary {
  font-size: 15px;
  color: var(--app-text);
}

.history-sec {
  padding: 1px 8px;
  border-radius: 999px;
  background: var(--app-hover);
  color: var(--app-text-2);
  font-size: 12px;
}

.history-count {
  margin-left: auto;
  color: var(--app-text-3);
  font-size: 12px;
}

.history-summary {
  margin-top: 8px;
  color: var(--app-text-2);
  font-size: 13px;
  line-height: 1.7;
}

.history-scores {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--app-border);
}

.history-toggle {
  margin-top: 8px;
  color: var(--app-active-border);
  font-size: 12px;
}

/* ---- 紧凑模式（问答内嵌面板） ---- */
.is-compact .panel-hero,
.is-compact .mode-section {
  border-color: var(--app-border);
}

.is-compact .panel-hero {
  padding: 14px;
}

.is-compact .hero-stats {
  min-width: 0;
}

.is-compact .type-grid {
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
}

/* ---- 响应式 ---- */
@media (max-width: 900px) {
  .panel-hero,
  .section-toolbar,
  .result-card {
    flex-direction: column;
    align-items: stretch;
  }

  .hero-stats {
    min-width: 0;
  }

  .assessment-layout {
    grid-template-columns: 1fr;
  }

  .question-nav {
    border-right: 0;
    border-bottom: 1px solid var(--app-border);
    padding-right: 0;
    padding-bottom: 14px;
  }

  .score-bar-row {
    grid-template-columns: 76px 1fr 44px;
  }
}

@media (max-width: 640px) {
  .type-grid {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  }

  .option-row {
    flex-wrap: wrap;
    gap: 8px 12px;
  }

  .option-desc {
    flex-basis: 100%;
    padding-left: 30px;
  }

  .result-main {
    gap: 10px;
  }

  .result-icon {
    width: 44px;
    height: 44px;
    font-size: 20px;
    border-radius: 12px;
  }

  .result-primary {
    font-size: 17px;
  }
}
</style>
