import axios from "axios";

const client = axios.create({
  baseURL: "/api",
  timeout: 180000,
  headers: {
    "Content-Type": "application/json; charset=utf-8",
  },
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("ys_auth_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem("ys_auth_token");
      localStorage.removeItem("ys_auth_user");
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export const api = {
  login: (payload) => client.post("/auth/login", payload),
  getCaptcha: () => client.get("/auth/captcha"),
  register: (payload) => client.post("/auth/register", payload),
  changePassword: (payload) => client.post("/auth/change-password", payload),
  getCurrentUser: () => client.get("/auth/me"),
  logout: () => client.post("/auth/logout"),
  getHealth: () => client.get("/health"),
  createSession: () => client.post("/chat/sessions"),
  getSession: (sessionId) => client.get(`/chat/sessions/${sessionId}`),
  listSessions: () => client.get("/chat/sessions"),
  sendQuestion: (sessionId, question) =>
    client.post(`/chat/sessions/${sessionId}/messages`, { question }),
  sendQuestionStream(sessionId, question, callbacks) {
    const { onToken, onThink, onAnswerReset, onEvidence, onGraph, onDone, onError } = callbacks;
    return fetch(`/api/chat/sessions/${sessionId}/messages/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(localStorage.getItem("ys_auth_token")
          ? { Authorization: `Bearer ${localStorage.getItem("ys_auth_token")}` }
          : {}),
      },
      body: JSON.stringify({ question }),
    })
      .then(async (response) => {
        if (!response.ok) {
          const text = await response.text().catch(() => "");
          throw new Error(text || `HTTP ${response.status}`);
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let currentEvent = null;
        let terminalEventReceived = false;

        const dispatch = (ev) => {
          try {
            const data = JSON.parse(ev.data || "{}");
            if (ev.event === "token") onToken(data);
            else if (ev.event === "think") onThink && onThink(data);
            else if (ev.event === "answer_reset") onAnswerReset && onAnswerReset(data);
            else if (ev.event === "evidence") onEvidence(data);
            else if (ev.event === "graph") onGraph(data);
            else if (ev.event === "done") {
              terminalEventReceived = true;
              onDone(data);
            } else if (ev.event === "error") {
              terminalEventReceived = true;
              onError(new Error(data.message || "Stream error"));
            }
          } catch (e) {
            // skip malformed events
          }
        };

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              if (currentEvent && currentEvent.event) {
                dispatch(currentEvent);
              }
              currentEvent = { event: line.slice(7).trim(), data: "" };
            } else if (line.startsWith("data: ")) {
              if (currentEvent) {
                currentEvent.data = line.slice(6);
              }
            } else if (line === "" && currentEvent) {
              dispatch(currentEvent);
              currentEvent = null;
            }
          }
        }
        if (currentEvent && currentEvent.event) {
          dispatch(currentEvent);
        }
        if (!terminalEventReceived && onDone) {
          onDone({ incomplete: true });
        }
      })
      .catch((err) => {
        if (onError) onError(err);
      });
  },
  listMessages: (sessionId) => client.get(`/chat/sessions/${sessionId}/messages`),
  getGraph: (sessionId) => client.get(`/chat/sessions/${sessionId}/graph`),
  getGraphSnapshot: (snapshotId) => client.get(`/chat/graph-snapshots/${snapshotId}`),
  getConstitutionTypes: () => client.get("/constitution/types"),
  getConstitutionQuestionnaire: () => client.get("/constitution/questionnaire"),
  getConstitutionProfile: () => client.get("/constitution/profile"),
  updateConstitutionProfile: (payload) => client.put("/constitution/profile", payload),
  createConstitutionAssessment: (payload) => client.post("/constitution/assessments", payload),
  listConstitutionAssessments: () => client.get("/constitution/assessments"),
  getConstitutionAssessment: (assessmentId) => client.get(`/constitution/assessments/${assessmentId}`),
  searchEntities: (q) => client.get("/entities/search", { params: { q } }),
  getEntity: (id) => client.get(`/entities/${id}`),
  getOverview: () => client.get("/admin/overview"),
  listUsers: (params) => client.get("/admin/users", { params }),
  createUser: (payload) => client.post("/admin/users", payload),
  updateUser: (id, payload) => client.put(`/admin/users/${id}`, payload),
  resetUserPassword: (id, payload) => client.put(`/admin/users/${id}/password`, payload),
  forceLogoutUser: (id) => client.post(`/admin/users/${id}/force-logout`),
  deleteUser: (id) => client.delete(`/admin/users/${id}`),
  getChatLogs: () => client.get("/admin/chat-logs"),
  getWorkflowLogs: () => client.get("/admin/workflow-logs"),
  getPrompts: () => client.get("/admin/prompts"),
  updatePrompt: (id, payload) => client.put(`/admin/prompts/${id}`, payload),
  getTemplates: () => client.get("/admin/cypher-templates"),
  updateTemplate: (id, payload) => client.put(`/admin/cypher-templates/${id}`, payload),
  createWorkflowSession: () => client.post("/rnd/sessions"),
  listWorkflowSessions: () => client.get("/rnd/sessions"),
  createWorkflowRun: (sessionId, payload) => client.post(`/rnd/sessions/${sessionId}/runs`, payload),
  getWorkflowRun: (runId) => client.get(`/rnd/runs/${runId}`),
  getWorkflowStepDetail: (runId, stepId) => client.get(`/rnd/runs/${runId}/steps/${stepId}`),
};
