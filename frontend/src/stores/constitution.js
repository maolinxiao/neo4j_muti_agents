import { ElMessage } from "element-plus";
import { defineStore } from "pinia";

import { api } from "../api/client";
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();

const clonePayload = (payload) => ({
  mode: payload?.mode || "need_user_choice",
  types: payload?.types || [],
  questions: payload?.questions || [],
  score_options: payload?.score_options || [
    { value: 1, label: "从不" },
    { value: 2, label: "很少" },
    { value: 3, label: "有时" },
    { value: 4, label: "经常" },
    { value: 5, label: "总是" },
  ],
  existing_profile: payload?.existing_profile || null,
});

export const useConstitutionStore = defineStore("constitution", {
  state: () => ({
    questionnaire: clonePayload(null),
    profile: null,
    assessments: [],
    answers: {},
    currentQuestionIndex: 0,
    loading: false,
    saving: false,
  }),
  getters: {
    types: (state) => state.questionnaire.types || [],
    questions: (state) => state.questionnaire.questions || [],
    scoreOptions: (state) => state.questionnaire.score_options || [],
    currentQuestion(state) {
      return state.questionnaire.questions?.[state.currentQuestionIndex] || null;
    },
    answeredCount: (state) => Object.keys(state.answers || {}).length,
  },
  actions: {
    applyQuestionnaire(payload) {
      this.questionnaire = clonePayload(payload);
      if (payload?.existing_profile) {
        this.profile = payload.existing_profile;
      }
      if (this.currentQuestionIndex >= this.questions.length) {
        this.currentQuestionIndex = 0;
      }
    },
    async refreshAll() {
      this.loading = true;
      try {
        const [questionnaireRes, profileRes, assessmentsRes] = await Promise.all([
          api.getConstitutionQuestionnaire(),
          api.getConstitutionProfile(),
          api.listConstitutionAssessments(),
        ]);
        this.applyQuestionnaire(questionnaireRes.data);
        this.profile = profileRes.data || questionnaireRes.data?.existing_profile || null;
        this.assessments = assessmentsRes.data || [];
      } finally {
        this.loading = false;
      }
    },
    setAnswer(questionCode, value) {
      this.answers = {
        ...this.answers,
        [questionCode]: Number(value),
      };
    },
    nextQuestion() {
      if (this.currentQuestionIndex < this.questions.length - 1) {
        this.currentQuestionIndex += 1;
      }
    },
    prevQuestion() {
      if (this.currentQuestionIndex > 0) {
        this.currentQuestionIndex -= 1;
      }
    },
    resetAssessment() {
      this.answers = {};
      this.currentQuestionIndex = 0;
    },
    async saveManualProfile(typeName) {
      this.saving = true;
      try {
        const { data } = await api.updateConstitutionProfile({
          primary_constitution: typeName,
          secondary_constitutions: [],
          source: "manual",
          scores: {},
          notes: "",
          last_assessment_id: null,
        });
        this.profile = data;
        this.applyQuestionnaire({
          ...this.questionnaire,
          mode: "existing_profile",
          existing_profile: data,
        });
        ElMessage.success(t("constitution.messages.profileSaved"));
      } finally {
        this.saving = false;
      }
    },
    async submitAssessment(notes = "") {
      if (!Object.keys(this.answers).length) {
        ElMessage.warning(t("constitution.messages.answerAtLeastOne"));
        return null;
      }
      this.saving = true;
      try {
        const { data } = await api.createConstitutionAssessment({
          answers: this.answers,
          notes,
        });
        this.profile = data.profile;
        this.assessments = [data.assessment, ...this.assessments.filter((item) => item.id !== data.assessment.id)];
        this.applyQuestionnaire({
          ...this.questionnaire,
          mode: "existing_profile",
          existing_profile: data.profile,
        });
        ElMessage.success(t("constitution.messages.assessmentSaved"));
        return data;
      } finally {
        this.saving = false;
      }
    },
  },
});
