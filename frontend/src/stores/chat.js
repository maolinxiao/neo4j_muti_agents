import { ElMessage } from "element-plus";
import { defineStore } from "pinia";

import { api } from "../api/client";

const mergeText = (...parts) => {
  const merged = [];
  parts.forEach((part) => {
    const cleaned = (part || "").trim();
    if (cleaned && !merged.includes(cleaned)) {
      merged.push(cleaned);
    }
  });
  return merged.join("\n\n");
};

const preserveThinkLine = (line) =>
  /^([-*]|\d+[.)]|[A-Za-z]+[.)])\s+/.test(line) ||
  /^【.+】$/.test(line) ||
  /^▌\s*阶段\s*\d+\/\d+/.test(line) ||
  /^·\s*/.test(line);

const sentenceEnded = (text) => /[。！？.!?；;]$/.test(text || "");

const joinerForThinkLine = (left, right) => {
  if (/[\u4e00-\u9fff]$/.test(left || "") || /^[\u4e00-\u9fff，。！？；：、]/.test(right || "")) {
    return "";
  }
  return " ";
};

export const normalizeThinkContent = (text) => {
  const source = (text || "")
    .replace(/\r\n/g, "\n")
    .replace(/<\/?think\b[^>]*>/gi, "")
    .trim();
  if (!source) return "";

  const output = [];
  let paragraph = "";
  source.split("\n").forEach((rawLine) => {
    const line = rawLine.trim();
    if (!line) {
      if (paragraph) {
        output.push(paragraph);
        paragraph = "";
      }
      return;
    }

    if (preserveThinkLine(line)) {
      if (paragraph) {
        output.push(paragraph);
        paragraph = "";
      }
      output.push(line);
      return;
    }

    if (!paragraph) {
      paragraph = line;
      return;
    }

    if (sentenceEnded(paragraph)) {
      output.push(paragraph);
      paragraph = line;
      return;
    }

    paragraph = `${paragraph}${joinerForThinkLine(paragraph, line)}${line}`;
  });

  if (paragraph) output.push(paragraph);
  return output
    .join("\n\n")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
};

const splitReasoningAndAnswer = (text) => {
  const source = text || "";
  const thinkBlocks = [];
  const visible = source
    .replace(/<think\b[^>]*>([\s\S]*?)<\/think>/gi, (_, think) => {
      const cleaned = (think || "").trim();
      if (cleaned) thinkBlocks.push(cleaned);
      return "";
    })
    .replace(/<\/?think\b[^>]*>/gi, "")
    .trim();

  return {
    visible,
    think: thinkBlocks.filter(Boolean).join("\n\n"),
  };
};

const splitStoredThinkPayload = (text) => {
  const source = (text || "").replace(/<\/?think\b[^>]*>/gi, "").trim();
  if (!source) {
    return { visible: "", think: "" };
  }

  return {
    visible: "",
    think: source,
  };
};

const splitAnswerFromThink = (text) => {
  const source = (text || "").trim();
  if (!source) {
    return { think: "", answer: "" };
  }
  const markers = ["【核心结论】", "【判断依据】", "【推荐理由】", "【原方依据】", "【替代依据】", "【知识依据】", "【任务路由】"];
  const positions = markers
    .map((marker) => source.indexOf(marker))
    .filter((index) => index >= 0);
  if (!positions.length) {
    return { think: source, answer: "" };
  }
  const answerStart = Math.min(...positions);
  const beforeAnswer = source.slice(0, answerStart).trim();
  const preambleMarkers = ["您好，", "您好", "您的问题是", "系统已经检测"];
  const preamblePositions = preambleMarkers
    .map((marker) => beforeAnswer.lastIndexOf(marker))
    .filter((index) => index >= 0);
  const preambleStart = preamblePositions.length ? Math.min(...preamblePositions) : -1;
  return {
    think: (preambleStart >= 0 ? beforeAnswer.slice(0, preambleStart) : beforeAnswer).trim(),
    answer: source.slice(answerStart).trim(),
  };
};

const buildFallbackAnswer = (extraPayload = {}) => {
  const evidence = (extraPayload.evidence_summary || "").trim();
  const cautions = (extraPayload.cautions || "").trim();
  const entityNames = (extraPayload.related_entities || [])
    .map((entity) => entity?.name || entity?.id)
    .filter(Boolean)
    .slice(0, 8)
    .join("、");

  if (!evidence && !cautions && !entityNames) return "";

  return [
    "【核心结论】\n当前回答正文没有完整返回，先展示系统已经检索到的知识图谱依据，避免页面空白。",
    `【知识依据】\n${evidence || (entityNames ? `相关实体：${entityNames}` : "暂无可展示的图谱摘要。")}`,
    `【注意事项】\n${cautions || "以下内容仅供知识问答参考，具体用药和剂量请咨询医生或药师。"}`,
    "【总结建议】\n建议补充年龄、体质、既往病史、正在使用的药物和禁忌情况后，再获取更完整的方剂建议。",
  ].join("\n\n");
};

const normalizeAssistantMessage = (msg) => {
  if (!msg || msg.role !== "assistant") return msg;
  const extraPayload = msg.extra_payload || {};
  const contentParts = splitReasoningAndAnswer(msg.content);
  const thinkPayloadParts = splitStoredThinkPayload(extraPayload.think_content);
  const rescuedThink = splitAnswerFromThink(mergeText(contentParts.think, thinkPayloadParts.think));
  const normalizedContent = mergeText(contentParts.visible, thinkPayloadParts.visible, rescuedThink.answer);

  msg.content = normalizedContent || buildFallbackAnswer(extraPayload);
  msg.extra_payload = {
    ...extraPayload,
    think_content: normalizeThinkContent(rescuedThink.think),
  };
  return msg;
};

const drainThinkStreamBuffer = (buffer, inThink, force = false) => {
  const openTag = "<think>";
  const closeTag = "</think>";
  const events = [];
  let remaining = buffer || "";
  let thinking = inThink;

  while (remaining) {
    const lower = remaining.toLowerCase();

    if (thinking) {
      const closeIndex = lower.indexOf(closeTag);
      if (closeIndex !== -1) {
        if (closeIndex > 0) {
          events.push({ event: "think", text: remaining.slice(0, closeIndex) });
        }
        remaining = remaining.slice(closeIndex + closeTag.length);
        thinking = false;
        continue;
      }

      if (force) {
        events.push({ event: "think", text: remaining });
        remaining = "";
        break;
      }

      const keepLength = Math.max(closeTag.length - 1, 80);
      const safeLength = Math.max(0, remaining.length - keepLength);
      if (safeLength === 0) break;
      events.push({ event: "think", text: remaining.slice(0, safeLength) });
      remaining = remaining.slice(safeLength);
      break;
    }

    const openIndex = lower.indexOf(openTag);
    const strayCloseIndex = lower.indexOf(closeTag);
    if (strayCloseIndex !== -1 && (openIndex === -1 || strayCloseIndex < openIndex)) {
      if (strayCloseIndex > 0) {
        events.push({ event: "token", text: remaining.slice(0, strayCloseIndex) });
      }
      remaining = remaining.slice(strayCloseIndex + closeTag.length);
      continue;
    }

    if (openIndex !== -1) {
      if (openIndex > 0) {
        events.push({ event: "token", text: remaining.slice(0, openIndex) });
      }
      remaining = remaining.slice(openIndex + openTag.length);
      thinking = true;
      continue;
    }

    if (force) {
      events.push({ event: "token", text: remaining });
      remaining = "";
      break;
    }

    let keepLength = 0;
    const maxCandidateLength = Math.min(openTag.length - 1, remaining.length);
    for (let candidateLength = 1; candidateLength <= maxCandidateLength; candidateLength += 1) {
      if (openTag.startsWith(lower.slice(-candidateLength))) {
        keepLength = candidateLength;
      }
    }
    const safeLength = remaining.length - keepLength;
    if (safeLength > 0) {
      events.push({ event: "token", text: remaining.slice(0, safeLength) });
      remaining = remaining.slice(safeLength);
    }
    break;
  }

  return { events, buffer: remaining, inThink: thinking };
};

const appendThinkContent = (msg, text) => {
  if (!msg || !text) return;
  const extraPayload = msg.extra_payload || {};
  const nextThink = normalizeThinkContent(`${extraPayload.think_content || ""}${text}`);
  msg.extra_payload = {
    ...extraPayload,
    think_content: nextThink,
  };
};

const appendStreamText = (msg, text, force = false) => {
  if (!msg || (!text && !force)) return;
  const state = msg.stream_state || { buffer: "", inThink: false };
  const result = drainThinkStreamBuffer(`${state.buffer}${text || ""}`, state.inThink, force);
  result.events.forEach((event) => {
    if (event.event === "think") {
      appendThinkContent(msg, event.text || "");
    } else {
      msg.content += event.text || "";
    }
  });
  msg.stream_state = {
    buffer: result.buffer,
    inThink: result.inThink,
  };
};

export const useChatStore = defineStore("chat", {
  state: () => ({
    sessions: [],
    currentSessionId: null,
    messages: [],
    loading: false,
    streamingMessageId: null,
  }),
  actions: {
    resetCurrentSession() {
      this.currentSessionId = null;
      this.messages = [];
      this.streamingMessageId = null;
    },
    async ensureSession() {
      if (this.currentSessionId) return this.currentSessionId;
      const { data } = await api.createSession();
      this.currentSessionId = data.session_id;
      await this.refreshSessions();
      return this.currentSessionId;
    },
    async refreshSessions() {
      const { data } = await api.listSessions();
      this.sessions = data;
    },
    async updateSession(sessionId, payload) {
      const { data } = await api.updateChatSession(sessionId, payload);
      const idx = this.sessions.findIndex((item) => item.id === sessionId);
      if (idx >= 0) {
        this.sessions[idx] = { ...this.sessions[idx], ...data };
      }
      return data;
    },
    async renameSession(sessionId, title) {
      return this.updateSession(sessionId, { title });
    },
    async togglePin(sessionId) {
      const target = this.sessions.find((item) => item.id === sessionId);
      if (!target) return null;
      const updated = await this.updateSession(sessionId, { pinned: !target.pinned });
      // 服务端以「置顶优先 + 更新时间」排序，刷新列表顺序
      await this.refreshSessions();
      return updated;
    },
    async deleteSession(sessionId) {
      await api.deleteChatSession(sessionId);
      this.sessions = this.sessions.filter((item) => item.id !== sessionId);
      if (this.currentSessionId === sessionId) {
        this.resetCurrentSession();
        const next = this.sessions[0];
        if (next) {
          await this.loadSession(next.id);
        } else {
          await this.ensureSession();
        }
      }
    },
    async loadSession(sessionId) {
      this.currentSessionId = sessionId;
      const { data: messages } = await api.listMessages(sessionId);
      this.messages = messages
        .map((msg) => ({
          ...msg,
          graph: null,
        }))
        .map(normalizeAssistantMessage);
      this.streamingMessageId = null;

      for (const msg of this.messages) {
        const snapshotId = msg.extra_payload?.graph_snapshot_id;
        if (!snapshotId) continue;
        try {
          const { data } = await api.getGraphSnapshot(snapshotId);
          msg.graph = {
            nodes: data.graph_data?.nodes || [],
            edges: data.graph_data?.edges || [],
            focus_paths: data.graph_data?.focus_paths || [],
            legend: data.graph_data?.legend || {},
            metrics: data.graph_data?.metrics || {},
          };
        } catch {
          // skip if snapshot fetch fails
        }
      }
    },
    ask(question) {
      const self = this;
      self.loading = true;

      const pendingId = `pending-${Date.now()}`;
      const userMsg = {
        id: `${pendingId}-user`,
        role: "user",
        content: question,
        created_at: new Date().toISOString(),
        extra_payload: null,
        graph: null,
      };
      const assistantMsg = {
        id: `${pendingId}-assistant`,
        role: "assistant",
        content: "",
        created_at: new Date().toISOString(),
        extra_payload: {
          answer_mode: "pending",
          evidence_summary: "",
          related_entities: [],
          cautions: "",
          follow_up_questions: [],
          qa_route: null,
          process_summary: "",
          missing_slots: [],
          think_content: "",
          constitution_assessment: null,
        },
        stream_state: { buffer: "", inThink: false },
        graph: null,
      };
      self.messages = [...self.messages, userMsg, assistantMsg];
      self.streamingMessageId = assistantMsg.id;

      self.ensureSession()
        .then((sessionId) => {
          api.sendQuestionStream(sessionId, question, {
            onToken(data) {
              const msg = self.messages.find((m) => m.id === assistantMsg.id);
              if (msg) {
                appendStreamText(msg, data.text || "");
              }
            },
            onThink(data) {
              const msg = self.messages.find((m) => m.id === assistantMsg.id);
              if (!msg || !data || !data.text) return;
              appendThinkContent(msg, data.text);
            },
            onAnswerReset() {
              const msg = self.messages.find((m) => m.id === assistantMsg.id);
              if (!msg) return;
              msg.content = "";
              msg.stream_state = { buffer: "", inThink: false };
            },
            onEvidence(data) {
              const msg = self.messages.find((m) => m.id === assistantMsg.id);
              if (msg) {
                msg.extra_payload = {
                  ...msg.extra_payload,
                  evidence_summary: data.evidence_summary || "",
                  related_entities: data.related_entities || [],
                  cautions: data.cautions || "",
                  follow_up_questions: data.follow_up_questions || [],
                  answer_mode: data.answer_mode || "llm_grounded",
                  qa_route: data.qa_route || msg.extra_payload?.qa_route || null,
                  process_summary: data.process_summary || msg.extra_payload?.process_summary || "",
                  missing_slots: data.missing_slots || msg.extra_payload?.missing_slots || [],
                  constitution_assessment: data.constitution_assessment || null,
                };
              }
            },
            onGraph(data) {
              const msg = self.messages.find((m) => m.id === assistantMsg.id);
              if (msg) {
                msg.graph = {
                  nodes: data.nodes || [],
                  edges: data.edges || [],
                  focus_paths: data.focus_paths || [],
                  legend: data.legend || {},
                  metrics: data.metrics || {},
                };
              }
            },
            onDone() {
              const msg = self.messages.find((m) => m.id === assistantMsg.id);
              if (msg) {
                appendStreamText(msg, "", true);
                delete msg.stream_state;
                normalizeAssistantMessage(msg);
              }
              self.loading = false;
              self.streamingMessageId = null;
              self.refreshSessions();
            },
            onError() {
              self.messages = self.messages.filter((m) => !m.id.startsWith(`${pendingId}-`));
              self.loading = false;
              self.streamingMessageId = null;
              ElMessage.error("回答加载失败，请稍后重试。");
            },
          });
        })
        .catch(() => {
          self.messages = self.messages.filter((m) => !m.id.startsWith(`${pendingId}-`));
          self.loading = false;
          self.streamingMessageId = null;
          ElMessage.error("会话创建失败，请稍后重试。");
        });
    },
  },
});
