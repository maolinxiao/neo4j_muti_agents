<template>
  <div class="chat-container">
    <!-- Header -->
    <div class="chat-header">
      <div class="header-left">
        <span class="header-title">{{ t("menu.chat") }}</span>
      </div>
      <div class="header-right">
        <el-button type="primary" link @click="createNewSession">
          <el-icon><Plus /></el-icon>
          {{ t("chat.newSession") }}
        </el-button>
      </div>
    </div>

    <!-- Session list sidebar -->
    <div class="chat-body">
      <div class="session-sidebar">
        <div
          v-for="sess in store.sessions"
          :key="sess.id"
          :class="['session-item', { active: sess.id === store.currentSessionId, pinned: sess.pinned }]"
          @click="switchSession(sess.id)"
        >
          <span class="session-title">
            <el-icon v-if="sess.pinned" class="pin-icon" :size="12"><Top /></el-icon>
            {{ sess.title || '新会话' }}
          </span>
          <span class="session-time">{{ formatTime(sess.created_at) }}</span>
          <el-dropdown
            class="session-actions"
            trigger="click"
            @command="(cmd) => handleSessionCommand(cmd, sess)"
            @click.stop
          >
            <el-icon class="more-btn" :size="14"><MoreFilled /></el-icon>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="pin">{{ sess.pinned ? t("common.unpin") : t("common.pin") }}</el-dropdown-item>
                <el-dropdown-item command="rename">{{ t("common.rename") }}</el-dropdown-item>
                <el-dropdown-item command="copy">{{ t("common.copyLink") }}</el-dropdown-item>
                <el-dropdown-item command="delete" divided>
                  <span class="danger-text">{{ t("common.delete") }}</span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>

      <!-- Main chat area -->
      <div class="chat-main">
        <!-- Messages -->
        <div class="message-list" ref="messageListRef">
          <div v-if="store.messages.length === 0" class="empty-state">
            <div class="empty-icon">
              <el-icon :size="48"><ChatDotRound /></el-icon>
            </div>
            <div class="empty-text">{{ t("chat.emptyTitle") }}</div>
            <div class="empty-hints">
              <el-tag
                v-for="hint in exampleQuestions"
                :key="hint"
                class="hint-tag"
                @click="useHint(hint)"
              >
                {{ hint }}
              </el-tag>
            </div>
          </div>

          <template v-for="msg in store.messages" :key="msg.id">
            <!-- AI message -->
            <div
              v-if="msg.role === 'assistant'"
              class="msg-row assistant-row"
              :class="{ 'assistant-row-wide': msg.extra_payload?.constitution_assessment }"
            >
              <div class="msg-avatar">
                <el-icon :size="24"><Cpu /></el-icon>
              </div>
              <div class="msg-body assistant-body">
                <!-- Think / Reasoning section (collapsible) -->
                <div
                  v-if="msg.extra_payload?.process_summary || msg.extra_payload?.think_content"
                  class="msg-section think-section"
                >
                  <el-collapse v-model="thinkCollapseState[msg.id]">
                    <el-collapse-item name="think">
                      <template #title>
                        <span class="think-title">
                          <el-icon><Loading /></el-icon>
                          {{ store.streamingMessageId === msg.id ? "图谱检索与证据整理摘要（生成中）" : "图谱检索与证据整理摘要" }}
                          <span
                            v-if="store.streamingMessageId === msg.id"
                            class="think-streaming-badge"
                          >生成中...</span>
                        </span>
                      </template>
                      <div class="think-inner">{{ displayProcessSummary(msg) }}</div>
                      <div
                        v-if="msg.extra_payload?.missing_slots?.length"
                        class="missing-slot-list"
                      >
                        <span class="missing-slot-label">待补充信息</span>
                        <el-tag
                          v-for="(slot, slotIdx) in msg.extra_payload.missing_slots.slice(0, 4)"
                          :key="slotIdx"
                          class="missing-slot-tag"
                          size="small"
                        >
                          {{ slot }}
                        </el-tag>
                      </div>
                    </el-collapse-item>
                  </el-collapse>
                </div>

                <div class="msg-content">
                  <!-- Streaming text -->
                  <div
                    v-if="parseAnswerSections(msg.content, msg.extra_payload?.qa_route?.task_key).length"
                    class="structured-answer answer-panel"
                  >
                    <div
                      v-for="section in parseAnswerSections(msg.content, msg.extra_payload?.qa_route?.task_key)"
                      :key="section.title"
                      :class="['answer-section', sectionClass(section.title)]"
                    >
                      <div class="answer-section-title">{{ section.title }}</div>
                      <div class="answer-section-body">
                        <template
                          v-for="(block, blockIdx) in formatSectionBody(section.body)"
                          :key="`${section.title}-${blockIdx}`"
                        >
                          <p v-if="block.type === 'paragraph'" class="answer-paragraph">
                            {{ block.text }}
                          </p>
                          <div v-else-if="block.type === 'definition'" class="answer-definition">
                            <span class="answer-definition-term">{{ block.term }}</span>
                            <span v-if="block.text" class="answer-definition-text">{{ block.text }}</span>
                          </div>
                          <div v-else-if="block.type === 'formula-group'" class="answer-formula-group">
                            <span class="answer-formula-group-title">{{ block.title }}</span>
                            <span class="answer-formula-group-meta">{{ block.meta }}</span>
                          </div>
                          <div v-else-if="block.type === 'ingredient'" class="answer-ingredient">
                            <span class="answer-ingredient-name">{{ block.name }}</span>
                            <span :class="['answer-role', `is-${block.roleTone}`]">{{ block.role }}</span>
                            <span class="answer-ingredient-text">{{ block.text }}</span>
                          </div>
                          <p v-else-if="block.type === 'note'" class="answer-note">
                            {{ block.text }}
                          </p>
                          <ul
                            v-else-if="block.type === 'list' && !block.ordered"
                            class="answer-list"
                          >
                            <li v-for="(item, itemIdx) in block.items" :key="itemIdx">{{ item }}</li>
                          </ul>
                          <ol
                            v-else-if="block.type === 'list' && block.ordered"
                            class="answer-list answer-list-ordered"
                          >
                            <li v-for="(item, itemIdx) in block.items" :key="itemIdx">{{ item }}</li>
                          </ol>
                        </template>
                      </div>
                    </div>
                  </div>
                  <span v-else class="answer-text">{{ cleanAnswerText(msg.content) }}</span>
                  <span
                    v-if="store.streamingMessageId === msg.id"
                    class="streaming-cursor"
                  >|</span>
                  <!-- Loading placeholder -->
                  <span
                    v-if="!msg.content && store.streamingMessageId === msg.id"
                    class="thinking-text"
                  >正在生成回答...</span>
                </div>

                <div
                  v-if="msg.extra_payload?.constitution_assessment && isLatestAssistantMessage(msg.id)"
                  class="msg-section constitution-section"
                >
                  <ConstitutionAssessmentPanel
                    :payload="msg.extra_payload.constitution_assessment"
                    compact
                  />
                </div>

                <!-- Evidence section -->
                <div
                  v-if="msg.extra_payload?.evidence_summary || msg.extra_payload?.related_entities?.length"
                  class="msg-section"
                >
                  <el-collapse>
                    <el-collapse-item title="证据来源与实体" name="evidence">
                      <div class="evidence-inner">
                        <div
                          v-if="msg.extra_payload?.evidence_summary"
                          class="evidence-summary"
                        >{{ msg.extra_payload.evidence_summary }}</div>
                        <div
                          v-if="msg.extra_payload?.related_entities?.length"
                          class="entity-chips"
                        >
                          <el-tag
                            v-for="entity in msg.extra_payload.related_entities.slice(0, 8)"
                            :key="entity.id || entity.name"
                            size="small"
                            effect="plain"
                            type="info"
                          >
                            {{ entity.name }}
                            <template v-if="entity.entity_type"> · {{ entity.entity_type }}</template>
                          </el-tag>
                          <el-button
                            v-if="msg.extra_payload.related_entities.length > 8"
                            text
                            type="primary"
                            size="small"
                            @click="showAllEntities(msg)"
                          >查看全部 ({{ msg.extra_payload.related_entities.length }})</el-button>
                        </div>
                      </div>
                    </el-collapse-item>
                  </el-collapse>
                </div>

                <!-- Graph section -->
                <div v-if="msg.graph?.nodes?.length" class="msg-section">
                  <el-collapse>
                    <el-collapse-item title="证据子图" name="graph">
                      <div class="graph-inner">
                        <GraphCanvas
                          :nodes="msg.graph.nodes"
                          :edges="msg.graph.edges"
                          :focus-paths="msg.graph.focus_paths"
                          :loading="false"
                          @node-click="(id) => openNode(id, msg)"
                        />
                        <div class="graph-metrics">
                          <span>{{ msg.graph.metrics?.nodeCount || msg.graph.nodes.length }} 节点</span>
                          <span class="metrics-sep">|</span>
                          <span>{{ msg.graph.metrics?.edgeCount || msg.graph.edges.length }} 边</span>
                          <span class="metrics-sep">|</span>
                          <span>{{ msg.graph.focus_paths?.length || 0 }} 主路径</span>
                        </div>
                      </div>
                    </el-collapse-item>
                  </el-collapse>
                </div>

                <!-- Cautions section -->
                <div v-if="msg.extra_payload?.cautions" class="msg-section">
                  <el-collapse>
                    <el-collapse-item title="注意事项" name="cautions">
                      <div class="cautions-inner">{{ msg.extra_payload.cautions }}</div>
                    </el-collapse-item>
                  </el-collapse>
                </div>

                <!-- Follow-up questions -->
                <div
                  v-if="msg.extra_payload?.follow_up_questions?.length"
                  class="follow-up-row"
                >
                  <el-tag
                    v-for="(fq, idx) in msg.extra_payload.follow_up_questions.slice(0, 4)"
                    :key="idx"
                    class="follow-up-tag"
                    effect="plain"
                    @click="useHint(fq)"
                  >
                    {{ fq }}
                  </el-tag>
                </div>

                <!-- Meta -->
                <div class="msg-meta-row">
                  <el-tag
                    v-if="msg.extra_payload?.answer_mode && msg.extra_payload.answer_mode !== 'pending'"
                    size="small"
                    :type="answerModeType(msg.extra_payload.answer_mode)"
                  >
                    {{ answerModeLabel(msg.extra_payload.answer_mode) }}
                  </el-tag>
                  <el-tag
                    v-if="msg.extra_payload?.qa_route?.label"
                    size="small"
                    type="info"
                    effect="plain"
                  >
                    {{ msg.extra_payload.qa_route.label }}
                  </el-tag>
                  <span class="msg-time">{{ formatTime(msg.created_at) }}</span>
                </div>
              </div>
            </div>

            <!-- User message -->
            <div v-else class="msg-row user-row">
              <div class="msg-body user-body">
                <div class="msg-content">{{ msg.content }}</div>
              </div>
              <div class="msg-avatar user-avatar">
                <el-icon :size="24"><UserFilled /></el-icon>
              </div>
            </div>
          </template>

          <!-- Loading indicator for new question -->
          <div v-if="store.loading && !store.streamingMessageId" class="loading-row">
            <span>正在处理...</span>
          </div>
        </div>

        <!-- Input area -->
        <div class="input-area">
          <el-input
            v-model="question"
            type="textarea"
            :rows="3"
            :placeholder="t('chat.placeholder')"
            :disabled="store.loading"
            resize="none"
            @keydown.enter.exact.prevent="submit"
          />
          <el-button
            type="primary"
            :disabled="!question.trim() || store.loading"
            :loading="store.loading"
            @click="submit"
            class="send-btn"
          >
            <template v-if="!store.loading">
              <el-icon><Promotion /></el-icon>
              {{ t("chat.send") }}
            </template>
            <template v-else>
              回答中...
            </template>
          </el-button>
        </div>
      </div>
    </div>

    <!-- Rename session dialog -->
    <el-dialog v-model="renameVisible" :title="t('chat.renameTitle')" width="420px" append-to-body>
      <el-input
        v-model="renameTitle"
        maxlength="60"
        show-word-limit
        :placeholder="t('chat.renamePlaceholder')"
        @keyup.enter="submitRename"
      />
      <template #footer>
        <el-button @click="renameVisible = false">{{ t("common.cancel") }}</el-button>
        <el-button type="primary" :disabled="!renameTitle.trim()" @click="submitRename">{{ t("common.save") }}</el-button>
      </template>
    </el-dialog>

    <!-- All entities dialog -->
    <el-dialog v-model="allEntitiesVisible" :title="t('chat.referenceSources')" width="560px">
      <el-table :data="allEntitiesData" size="small" border stripe max-height="400">
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="entity_type" label="类型" width="120" />
        <el-table-column prop="id" label="ID" min-width="180" show-overflow-tooltip />
      </el-table>
    </el-dialog>

    <!-- Entity drawer -->
    <EntityDrawer v-model:visible="drawerVisible" :entity="selectedEntity" />
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ChatDotRound, Cpu, Loading, MoreFilled, Plus, Promotion, Top, UserFilled } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { api } from "../../api/client";
import ConstitutionAssessmentPanel from "../../components/ConstitutionAssessmentPanel.vue";
import GraphCanvas from "../../components/GraphCanvas.vue";
import EntityDrawer from "../../components/EntityDrawer.vue";
import { normalizeThinkContent, useChatStore } from "../../stores/chat";
import { useI18n } from "../../composables/useI18n";
const { t } = useI18n();
import {
  cleanAnswerText,
  formatSectionBody,
  parseAnswerSections,
  sectionClass,
} from "../../utils/qaAnswerFormat";

const route = useRoute();
const router = useRouter();
const store = useChatStore();
const question = ref(route.query.q || store.pendingQuestion || "");
if (store.pendingQuestion) {
  store.pendingQuestion = "";
}
const messageListRef = ref(null);
const drawerVisible = ref(false);
const selectedEntity = ref(null);
const entityCache = new Map();
const allEntitiesVisible = ref(false);
const allEntitiesData = ref([]);
const thinkCollapseState = ref({});

const exampleQuestions = [
  "把四君子汤改造成药食同源代餐粉",
  "麻黄可以用什么药食同源原料替代？",
  "孕妇能不能吃黄芪？",
];

const answerModeType = (mode) => {
  if (mode === "llm_grounded") return "success";
  if (mode === "graph_grounded") return "primary";
  return "warning";
};

const answerModeLabel = (mode) => {
  if (mode === "llm_grounded") return "LLM整合回答";
  if (mode === "graph_grounded") return "图谱证据回答";
  return "图谱本地总结";
};

const useHint = (text) => {
  question.value = text;
  submit();
};

const isLatestAssistantMessage = (messageId) => {
  const latestAssistant = [...store.messages].reverse().find((msg) => msg.role === "assistant");
  return latestAssistant?.id === messageId;
};

const displayProcessSummary = (msg) => normalizeThinkContent(
  msg.extra_payload?.process_summary || msg.extra_payload?.think_content || ""
);

const scrollToBottom = () => {
  nextTick(() => {
    const el = messageListRef.value;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  });
};

// Auto-scroll when messages change or content streams
watch(
  () => store.messages.map((m) => m.content),
  () => scrollToBottom(),
  { deep: false }
);

watch(
  () => store.messages.map((m) => `${m.id}:${m.extra_payload?.think_content?.length || 0}`),
  () => {
    const streamingId = store.streamingMessageId;
    const streamingMsg = store.messages.find((msg) => msg.id === streamingId);
    if (streamingMsg?.extra_payload?.think_content && thinkCollapseState.value[streamingId]?.length) {
      scrollToBottom();
    }
  },
  { deep: false }
);

watch(
  () => store.streamingMessageId,
  (newId, oldId) => {
    if (newId) {
      thinkCollapseState.value[newId] = [];
      return;
    }
    if (oldId) {
      thinkCollapseState.value[oldId] = [];
    }
  }
);

const load = async () => {
  if (route.params.sessionId) {
    if (store.loading && route.params.sessionId === store.currentSessionId) {
      return;
    }
    await store.loadSession(route.params.sessionId);
  }
};

const submit = () => {
  if (!question.value.trim() || store.loading) return;
  store.ask(question.value.trim());
  question.value = "";
};

const switchSession = async (sessionId) => {
  if (store.loading) return;
  await store.loadSession(sessionId);
  await router.push({ name: "chat", params: { sessionId } });
};

const renameVisible = ref(false);
const renameId = ref("");
const renameTitle = ref("");

const handleSessionCommand = async (command, sess) => {
  if (command === "pin") {
    try {
      await store.togglePin(sess.id);
      ElMessage.success(sess.pinned ? t("chat.unpinned") : t("chat.pinned"));
    } catch {
      ElMessage.error(t("common.failed"));
    }
  } else if (command === "rename") {
    renameId.value = sess.id;
    renameTitle.value = sess.title || "";
    renameVisible.value = true;
  } else if (command === "copy") {
    const url = `${window.location.origin}/app/chat/${sess.id}`;
    try {
      await navigator.clipboard.writeText(url);
      ElMessage.success(t("chat.linkCopied"));
    } catch {
      ElMessage.warning(`${t("chat.linkCopyFailed")}${url}`);
    }
  } else if (command === "delete") {
    try {
      await ElMessageBox.confirm(
        t("chat.deleteConfirm", { title: sess.title || t("chat.newSessionTitle") }),
        t("chat.deleteConfirmTitle"),
        { type: "warning", confirmButtonText: t("common.delete"), cancelButtonText: t("common.cancel") },
      );
    } catch {
      return;
    }
    try {
      await store.deleteSession(sess.id);
      ElMessage.success(t("chat.deleted"));
    } catch {
      ElMessage.error(t("common.failed"));
    }
  }
};

const submitRename = async () => {
  const title = renameTitle.value.trim();
  if (!title || !renameId.value) return;
  try {
    await store.renameSession(renameId.value, title);
    renameVisible.value = false;
    ElMessage.success(t("chat.renamed"));
  } catch {
    ElMessage.error(t("common.failed"));
  }
};

const openNode = async (id, msg) => {
  drawerVisible.value = true;
  const graphNodes = msg.graph?.nodes || [];
  const graphNode = graphNodes.find((node) => node.id === id);
  if (graphNode) {
    selectedEntity.value = {
      id: graphNode.id,
      name: graphNode.label || graphNode.name || graphNode.id,
      entity_type: graphNode.type || "Entity",
      aliases: graphNode.props?.aliases || [],
      props: graphNode.props || {},
    };
  }
  if (graphNode && ["Question", "Attribute", "EvidenceNote"].includes(graphNode.type)) {
    return;
  }
  if (entityCache.has(id)) {
    selectedEntity.value = entityCache.get(id);
    return;
  }
  try {
    const { data } = await api.getEntity(id);
    entityCache.set(id, data);
    if (drawerVisible.value && selectedEntity.value?.id === id) {
      selectedEntity.value = data;
    }
  } catch {
    // Keep the graph snapshot version if detail lookup fails.
  }
};

const showAllEntities = (msg) => {
  allEntitiesData.value = (msg.extra_payload?.related_entities || []).map((e) => ({
    name: e.name || e.id || "—",
    entity_type: e.entity_type || "Entity",
    id: e.id || "—",
  }));
  allEntitiesVisible.value = true;
};

const createNewSession = async () => {
  store.resetCurrentSession();
  question.value = "";
  await router.push({ name: "chat" });
};

const formatTime = (iso) => {
  if (!iso) return "";
  let normalized = iso;
  if (!iso.endsWith("Z") && !/[+-]\d{2}:\d{2}$/.test(iso) && !/\+\d{4}$/.test(iso)) {
    normalized = iso + "Z";
  }
  const d = new Date(normalized);
  if (isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

watch(() => route.params.sessionId, load);
watch(() => store.currentSessionId, (newId) => {
  if (newId && route.params.sessionId !== newId) {
    router.replace({ name: "chat", params: { sessionId: newId }, query: route.query });
  }
});
onMounted(async () => {
  await store.refreshSessions();
  if (route.params.sessionId) {
    await store.loadSession(route.params.sessionId);
  } else if (store.sessions.length > 0) {
    await switchSession(store.sessions[0].id);
  }
  if (route.query.q) {
    await submit();
  }
});
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 84px);
  background: var(--app-bg);
}

/* Header */
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: var(--app-panel);
  border-bottom: 1px solid #e4e7ed;
  flex-shrink: 0;
}
.header-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--app-text);
}
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Body */
.chat-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* Session sidebar */
.session-sidebar {
  width: 240px;
  background: var(--app-panel);
  border-right: 1px solid #e4e7ed;
  overflow-y: auto;
  flex-shrink: 0;
  padding: 8px 0;
}
.session-item {
  position: relative;
  padding: 12px 32px 12px 16px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-left: 3px solid transparent;
  transition: all 0.15s;
}
.session-item:hover {
  background: var(--app-hover);
}
.session-item.active {
  background: var(--app-active);
  border-left-color: var(--app-active-border);
}
.session-item.pinned {
  border-left-color: #409eff;
  background: rgba(64, 158, 255, 0.05);
}
.session-item.pinned:hover {
  background: rgba(64, 158, 255, 0.1);
}
.session-title {
  font-size: 13px;
  color: var(--app-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: flex;
  align-items: center;
  gap: 4px;
}
.pin-icon {
  color: #409eff;
  flex-shrink: 0;
}
.session-time {
  font-size: 11px;
  color: var(--app-text-3);
}
.session-actions {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  opacity: 0;
  transition: opacity 0.15s;
}
.session-item:hover .session-actions,
.session-item.active .session-actions {
  opacity: 1;
}
.more-btn {
  color: var(--app-text-3);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
}
.more-btn:hover {
  color: #409eff;
  background: rgba(64, 158, 255, 0.1);
}
.danger-text {
  color: #f56c6c;
}

/* Chat main */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* Messages */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.message-list::-webkit-scrollbar {
  width: 6px;
}
.message-list::-webkit-scrollbar-thumb {
  background: var(--app-border);
  border-radius: 3px;
}

/* Empty state */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 16px;
  padding-top: 120px;
}
.empty-icon {
  color: #c0c4cc;
}
.empty-text {
  font-size: 15px;
  color: var(--app-text-3);
}
.empty-hints {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  max-width: 500px;
}
.hint-tag {
  cursor: pointer;
}
.hint-tag:hover {
  background: var(--app-active);
}

/* Message row */
.msg-row {
  display: flex;
  gap: 12px;
  max-width: 85%;
}
.assistant-row {
  align-self: flex-start;
}
.assistant-row-wide {
  width: 100%;
  max-width: min(1120px, 100%);
}
.assistant-row-wide .assistant-body {
  flex: 1;
}
.user-row {
  align-self: flex-end;
}

/* Avatar */
.msg-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: #e6f7ff;
  color: #409eff;
}
.user-avatar {
  background: #f0f9eb;
  color: #67c23a;
}

/* Message body */
.msg-body {
  padding: 12px 16px;
  border-radius: 8px;
  min-width: 0;
}
.assistant-body {
  background: var(--app-panel);
  border: 1px solid #e4e7ed;
  border-radius: 4px 12px 12px 12px;
}
.user-body {
  background: #409eff;
  color: #fff;
  border-radius: 12px 4px 12px 12px;
}

/* Content */
.msg-content {
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
}
.answer-text {
  color: var(--app-text);
}
.structured-answer {
  display: block;
}
.answer-panel {
  background: transparent;
  border: none;
  border-top: 1px solid #e4e7ed;
  overflow: visible;
}
.answer-section {
  padding: 14px 2px 16px;
  border-bottom: 1px solid #ebeef5;
  background: transparent;
}
.answer-section.is-primary {
  background: transparent;
}
.answer-section.is-info {
  background: transparent;
}
.answer-section.is-warning {
  background: transparent;
}
.answer-section.is-plan {
  background: transparent;
}
.answer-section.is-summary {
  background: transparent;
}
.answer-section:last-child {
  border-bottom: none;
}
.answer-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--app-text);
  margin-bottom: 8px;
}
.answer-section-title::before {
  content: "";
  width: 3px;
  height: 16px;
  border-radius: 1px;
  background: #909399;
  flex: 0 0 auto;
}
.answer-section.is-primary .answer-section-title::before {
  background: #409eff;
}
.answer-section.is-warning .answer-section-title::before {
  background: #e6a23c;
}
.answer-section.is-plan .answer-section-title::before {
  background: #67c23a;
}
.answer-section.is-info .answer-section-title::before {
  background: #79bbff;
}
.answer-section-body {
  font-size: 14px;
  line-height: 1.7;
  color: var(--app-text);
  word-break: break-word;
}
.answer-paragraph {
  margin: 0 0 8px;
  white-space: pre-wrap;
}
.answer-paragraph:last-child {
  margin-bottom: 0;
}
.answer-definition {
  display: grid;
  grid-template-columns: minmax(104px, 144px) minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  margin: 0;
  padding: 7px 0;
  border-bottom: 1px dashed #ebeef5;
}
.answer-definition:last-child {
  border-bottom: none;
}
.answer-definition-term {
  font-weight: 500;
  color: #4e5969;
  overflow-wrap: anywhere;
}
.answer-definition-text {
  min-width: 0;
  color: var(--app-text-2);
  overflow-wrap: anywhere;
}
.answer-formula-group {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px 12px;
  margin: 14px 0 4px;
  padding: 10px 0 7px;
  border-top: 1px solid #ebeef5;
}
.answer-formula-group:first-child {
  margin-top: 2px;
  padding-top: 0;
  border-top: none;
}
.answer-formula-group-title {
  font-weight: 600;
  color: var(--app-text);
}
.answer-formula-group-meta {
  color: #7a8494;
  font-size: 13px;
}
.answer-ingredient {
  display: grid;
  grid-template-columns: minmax(72px, 112px) 24px minmax(0, 1fr);
  gap: 8px;
  align-items: start;
  padding: 7px 0;
  border-bottom: 1px dashed #ebeef5;
}
.answer-ingredient-name {
  color: var(--app-text);
  font-weight: 500;
  overflow-wrap: anywhere;
}
.answer-role {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1;
  color: var(--app-text-2);
  background: var(--app-hover);
}
.answer-role.is-primary {
  color: #337ecc;
  border-color: #a0cfff;
  background: var(--app-active);
}
.answer-role.is-success {
  color: #529b2e;
  border-color: #b3e19d;
  background: #f0f9eb;
}
.answer-role.is-warning {
  color: #b88230;
  border-color: #f3d19e;
  background: #fdf6ec;
}
.answer-ingredient-text {
  min-width: 0;
  color: var(--app-text-2);
  overflow-wrap: anywhere;
}
.answer-note {
  margin: 6px 0 2px;
  padding: 6px 10px;
  border-left: 2px solid #dcdfe6;
  color: #7a8494;
  font-size: 13px;
  background: var(--app-panel-2);
}
.answer-list {
  margin: 0 0 8px;
  padding-left: 20px;
}
.answer-list:last-child {
  margin-bottom: 0;
}
.answer-list li {
  margin-bottom: 4px;
}
.answer-list-ordered {
  list-style-type: decimal;
}
@media (max-width: 640px) {
  .answer-definition {
    grid-template-columns: minmax(0, 1fr);
    gap: 2px;
  }
  .answer-ingredient {
    grid-template-columns: minmax(64px, 92px) 24px minmax(0, 1fr);
    gap: 6px;
  }
}
.streaming-cursor {
  display: inline;
  animation: blink 1s infinite;
  color: #409eff;
  font-weight: bold;
}
@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
.thinking-text {
  color: var(--app-text-3);
  font-style: italic;
}

/* Think / Reasoning section */
.think-section {
  margin-bottom: 8px;
}

.think-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--app-text-3);
}

.think-streaming-badge {
  font-size: 11px;
  color: #409eff;
  margin-left: 4px;
  animation: think-pulse 1.5s ease-in-out infinite;
}

@keyframes think-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.think-inner {
  font-size: 13px;
  color: var(--app-text-3);
  line-height: 1.7;
  white-space: pre-wrap;
  background: var(--app-panel-2);
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 10px 12px;
  max-height: 220px;
  overflow-y: auto;
}

.missing-slot-list {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
}

.missing-slot-label {
  font-size: 12px;
  color: var(--app-text-3);
}

.missing-slot-tag {
  max-width: 100%;
  white-space: normal;
  height: auto;
  line-height: 1.45;
  padding: 4px 8px;
}

/* Sections in AI bubble */
.msg-section {
  margin-top: 8px;
}
.constitution-section {
  margin-top: 12px;
}
.msg-section :deep(.el-collapse) {
  border: none;
}
.msg-section :deep(.el-collapse-item__header) {
  font-size: 13px;
  color: var(--app-text-2);
  height: 32px;
  line-height: 32px;
  border: none;
  background: transparent;
}
.msg-section :deep(.el-collapse-item__wrap) {
  border: none;
  background: transparent;
}
.msg-section :deep(.el-collapse-item__content) {
  padding: 4px 0 8px 0;
}
.evidence-inner {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 12px;
  background: var(--app-panel-2);
  border-radius: 6px;
  border: 1px solid #ebeef5;
}
.evidence-summary {
  font-size: 13px;
  color: var(--app-text-2);
  line-height: 1.5;
  white-space: pre-wrap;
}
.entity-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.graph-inner {
  padding: 8px 0;
}
.graph-metrics {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--app-text-3);
}
.metrics-sep {
  color: #dcdfe6;
}
.cautions-inner {
  font-size: 13px;
  color: #e6a23c;
  line-height: 1.5;
  padding: 8px 12px;
  background: #fdf6ec;
  border-radius: 6px;
  white-space: pre-wrap;
}

/* Follow-ups */
.follow-up-row {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.follow-up-tag {
  cursor: pointer;
  font-size: 12px;
  max-width: 100%;
  height: auto;
  white-space: normal;
  line-height: 1.5;
  align-items: flex-start;
}
.follow-up-tag :deep(.el-tag__content) {
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
}
.follow-up-tag:hover {
  background: var(--app-active);
  color: #409eff;
  border-color: #409eff;
}

/* Meta */
.msg-meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}
.msg-time {
  font-size: 11px;
  color: #c0c4cc;
}

/* Loading */
.loading-row {
  text-align: center;
  color: var(--app-text-3);
  font-size: 13px;
  padding: 16px;
}

/* Input area */
.input-area {
  padding: 16px 24px;
  background: var(--app-panel);
  border-top: 1px solid #e4e7ed;
  display: flex;
  gap: 12px;
  align-items: flex-end;
  flex-shrink: 0;
}
.input-area :deep(.el-textarea__inner) {
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.6;
  background: var(--app-hover);
  border-color: #e4e7ed;
}
.input-area :deep(.el-textarea__inner:focus) {
  background: var(--app-panel);
  border-color: #409eff;
}
.send-btn {
  height: 40px;
  border-radius: 8px;
  flex-shrink: 0;
  min-width: 88px;
}
</style>
