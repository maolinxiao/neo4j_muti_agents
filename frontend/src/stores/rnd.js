import { ElMessage } from "element-plus";
import { defineStore } from "pinia";

import { api } from "../api/client";

const RUN_POLL_INTERVAL_MS = 1500;

const emptyRun = () => ({
  id: null,
  question: "",
  brief: null,
  final_report: null,
  steps: [],
  summary_metrics: {},
  related_graph_snapshots: [],
  status: "idle",
});

const normalizeRun = (data = {}) => ({
  ...emptyRun(),
  ...data,
  id: data.id || data.run_id || null,
});

const isActiveRunStatus = (status) => ["queued", "running"].includes(status);

export const useRndStore = defineStore("rnd", {
  state: () => ({
    sessions: [],
    currentSessionId: null,
    currentRun: emptyRun(),
    currentStepDetail: null,
    selectedSnapshot: null,
    loading: false,
    submitting: false,
    polling: false,
    pollTimer: null,
  }),
  actions: {
    reset() {
      this.stopPolling();
      this.currentSessionId = null;
      this.currentRun = emptyRun();
      this.currentStepDetail = null;
      this.selectedSnapshot = null;
    },
    stopPolling() {
      if (this.pollTimer) {
        window.clearTimeout(this.pollTimer);
        this.pollTimer = null;
      }
      this.polling = false;
    },
    startPolling(runId) {
      if (!runId) return;
      this.stopPolling();
      this.polling = true;
      this.pollTimer = window.setTimeout(async () => {
        try {
          await this.loadRun(runId, { silent: true, preserveSelection: true });
        } catch {
          this.stopPolling();
          return;
        }
        if (isActiveRunStatus(this.currentRun.status)) {
          this.startPolling(runId);
          return;
        }
        this.stopPolling();
      }, RUN_POLL_INTERVAL_MS);
    },
    async ensureSession() {
      if (this.currentSessionId) return this.currentSessionId;
      const { data } = await api.createWorkflowSession();
      this.currentSessionId = data.id || data.session_id;
      await this.refreshSessions();
      return this.currentSessionId;
    },
    async refreshSessions() {
      const { data } = await api.listWorkflowSessions();
      this.sessions = data;
    },
    async runWorkflow(question, reuseLastBrief = false) {
      this.submitting = true;
      try {
        const sessionId = await this.ensureSession();
        const { data } = await api.createWorkflowRun(sessionId, { question, reuse_last_brief: reuseLastBrief });
        this.currentRun = normalizeRun(data);
        this.currentStepDetail = null;
        this.selectedSnapshot = null;
        await this.refreshSessions();
        this.startPolling(this.currentRun.id);
      } catch (error) {
        ElMessage.error("研发工作流执行失败，请稍后重试。");
        throw error;
      } finally {
        this.submitting = false;
      }
    },
    async loadRun(runId, options = {}) {
      if (!runId) {
        this.stopPolling();
        this.currentRun = emptyRun();
        return;
      }
      const { silent = false, preserveSelection = false } = options;
      if (!silent) {
        this.loading = true;
      }
      try {
        const { data } = await api.getWorkflowRun(runId);
        this.currentRun = normalizeRun(data);
        this.currentSessionId = data.session_id;
        await this.syncCurrentStepDetail(preserveSelection ? this.currentStepDetail?.id : null);
        if (isActiveRunStatus(this.currentRun.status)) {
          this.startPolling(this.currentRun.id);
        } else {
          this.stopPolling();
        }
      } finally {
        if (!silent) {
          this.loading = false;
        }
      }
    },
    async loadLatestRunForSession(sessionId) {
      const { data } = await api.getWorkflowLogs();
      const latest = data.find((item) => item.session_id === sessionId);
      if (latest?.id) {
        await this.loadRun(latest.id);
      }
    },
    async syncCurrentStepDetail(preferredStepId = null) {
      const steps = this.currentRun?.steps || [];
      if (!steps.length) {
        this.currentStepDetail = null;
        this.selectedSnapshot = null;
        return;
      }
      const availableStepIds = new Set(steps.map((item) => item.id));
      const fallbackStep =
        steps.find((item) => item.status === "running") ||
        [...steps].reverse().find((item) => item.status === "completed") ||
        steps[0];
      const targetId =
        (preferredStepId && availableStepIds.has(preferredStepId) && preferredStepId) ||
        (this.currentStepDetail?.id && availableStepIds.has(this.currentStepDetail.id) && this.currentStepDetail.id) ||
        fallbackStep?.id;
      if (targetId) {
        await this.selectStep(targetId, { silent: true });
      }
    },
    async selectStep(stepId, options = {}) {
      const runId = this.currentRun?.id || this.currentRun?.run_id;
      if (!runId || !stepId) return;
      const { silent = false } = options;
      if (!silent) {
        this.loading = true;
      }
      try {
        const { data } = await api.getWorkflowStepDetail(runId, stepId);
        this.currentStepDetail = data;
        let snapshot = data.graph_snapshot || null;
        if (!snapshot && data.graph_snapshot_id) {
          try {
            const { data: snap } = await api.getGraphSnapshot(data.graph_snapshot_id);
            snapshot = snap;
          } catch {
            snapshot = null;
          }
        }
        this.selectedSnapshot = snapshot;
      } finally {
        if (!silent) {
          this.loading = false;
        }
      }
    },
  },
});
