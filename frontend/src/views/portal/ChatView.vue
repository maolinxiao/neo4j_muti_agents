<template>
  <div class="chat-container">
    <!-- Header -->
    <div class="chat-header">
      <div class="header-left">
        <span class="header-title">知识问答</span>
      </div>
      <div class="header-right">
        <el-button type="primary" link @click="createNewSession">
          <el-icon><Plus /></el-icon>
          新建会话
        </el-button>
      </div>
    </div>

    <!-- Session list sidebar -->
    <div class="chat-body">
      <div class="session-sidebar">
        <div
          v-for="sess in store.sessions"
          :key="sess.id"
          :class="['session-item', { active: sess.id === store.currentSessionId }]"
          @click="switchSession(sess.id)"
        >
          <span class="session-title">{{ sess.title || '新会话' }}</span>
          <span class="session-time">{{ formatTime(sess.created_at) }}</span>
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
            <div class="empty-text">输入问题，开始基于知识图谱的问答</div>
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
            <div v-if="msg.role === 'assistant'" class="msg-row assistant-row">
              <div class="msg-avatar">
                <el-icon :size="24"><Cpu /></el-icon>
              </div>
              <div class="msg-body assistant-body">
                <!-- Think / Reasoning section (collapsible) -->
                <div
                  v-if="msg.extra_payload?.think_content"
                  class="msg-section think-section"
                >
                  <el-collapse v-model="thinkCollapseState[msg.id]">
                    <el-collapse-item name="think">
                      <template #title>
                        <span class="think-title">
                          <el-icon><Loading /></el-icon>
                          {{ store.streamingMessageId === msg.id ? "思考过程（流式生成中）" : "思考过程（已折叠，可展开）" }}
                          <span
                            v-if="store.streamingMessageId === msg.id"
                            class="think-streaming-badge"
                          >思考中...</span>
                        </span>
                      </template>
                      <div class="think-inner">{{ msg.extra_payload.think_content }}</div>
                    </el-collapse-item>
                  </el-collapse>
                </div>

                <div class="msg-content">
                  <!-- Streaming text -->
                  <div
                    v-if="parseAnswerSections(msg.content).length"
                    class="structured-answer"
                  >
                    <div
                      v-for="section in parseAnswerSections(msg.content)"
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
                  <span v-else class="answer-text">{{ msg.content }}</span>
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

                <!-- Evidence section -->
                <div
                  v-if="msg.extra_payload?.evidence_summary || msg.extra_payload?.related_entities?.length"
                  class="msg-section"
                >
                  <el-collapse>
                    <el-collapse-item title="图谱证据摘要" name="evidence">
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
                  v-if="msg.extra_payload?.follow_up_questions?.length && !msg.id.startsWith('pending')"
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
                    :type="msg.extra_payload.answer_mode === 'llm_grounded' ? 'success' : 'warning'"
                  >
                    {{ msg.extra_payload.answer_mode === 'llm_grounded' ? 'LLM整合回答' : '图谱本地总结' }}
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
            placeholder="输入你的问题，例如：黄芪的功效是什么？"
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
              发送
            </template>
            <template v-else>
              回答中...
            </template>
          </el-button>
        </div>
      </div>
    </div>

    <!-- All entities dialog -->
    <el-dialog v-model="allEntitiesVisible" title="参考来源 — 全部实体" width="560px">
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
import { ChatDotRound, Cpu, Loading, Plus, Promotion, UserFilled } from "@element-plus/icons-vue";

import { api } from "../../api/client";
import GraphCanvas from "../../components/GraphCanvas.vue";
import EntityDrawer from "../../components/EntityDrawer.vue";
import { useChatStore } from "../../stores/chat";
import {
  formatSectionBody,
  parseAnswerSections,
  sectionClass,
} from "../../utils/qaAnswerFormat";

const route = useRoute();
const router = useRouter();
const store = useChatStore();
const question = ref(route.query.q || "");
const messageListRef = ref(null);
const drawerVisible = ref(false);
const selectedEntity = ref(null);
const entityCache = new Map();
const allEntitiesVisible = ref(false);
const allEntitiesData = ref([]);
const thinkCollapseState = ref({});

const exampleQuestions = [
  "黄芪的功效是什么？",
  "四君子汤包含哪些药材？",
  "治疗失眠的药食同源药材有哪些？",
];

const useHint = (text) => {
  question.value = text;
  submit();
};

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
    if (streamingMsg?.extra_payload?.think_content) {
      thinkCollapseState.value[streamingId] = ["think"];
      scrollToBottom();
    }
  },
  { deep: false }
);

watch(
  () => store.streamingMessageId,
  (newId, oldId) => {
    if (newId) {
      thinkCollapseState.value[newId] = ["think"];
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
  background: #f5f5f5;
}

/* Header */
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  flex-shrink: 0;
}
.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
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
  background: #fff;
  border-right: 1px solid #e4e7ed;
  overflow-y: auto;
  flex-shrink: 0;
  padding: 8px 0;
}
.session-item {
  padding: 12px 16px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-left: 3px solid transparent;
  transition: all 0.15s;
}
.session-item:hover {
  background: #f5f7fa;
}
.session-item.active {
  background: #ecf5ff;
  border-left-color: #409eff;
}
.session-title {
  font-size: 13px;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.session-time {
  font-size: 11px;
  color: #c0c4cc;
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
  background: #dcdfe6;
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
  color: #909399;
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
  background: #ecf5ff;
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
  background: #fff;
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
  color: #303133;
}
.structured-answer {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.answer-section {
  padding: 10px 12px 12px;
  border-radius: 6px;
  border-left: 3px solid #dcdfe6;
  background: #fafbfc;
  margin-bottom: 4px;
}
.answer-section.is-primary {
  border-left-color: #409eff;
  background: #f0f7ff;
}
.answer-section.is-info {
  border-left-color: #79bbff;
  background: #f5faff;
}
.answer-section.is-warning {
  border-left-color: #e6a23c;
  background: #fdf6ec;
}
.answer-section.is-plan {
  border-left-color: #67c23a;
  background: #f6ffed;
}
.answer-section.is-summary {
  border-left-color: #909399;
  background: #f4f4f5;
}
.answer-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}
.answer-section-body {
  font-size: 14px;
  line-height: 1.7;
  color: #303133;
  word-break: break-word;
}
.answer-paragraph {
  margin: 0 0 8px;
  white-space: pre-wrap;
}
.answer-paragraph:last-child {
  margin-bottom: 0;
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
  color: #909399;
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
  color: #909399;
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
  color: #909399;
  line-height: 1.7;
  white-space: pre-wrap;
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 10px 12px;
  max-height: 300px;
  overflow-y: auto;
}

/* Sections in AI bubble */
.msg-section {
  margin-top: 8px;
}
.msg-section :deep(.el-collapse) {
  border: none;
}
.msg-section :deep(.el-collapse-item__header) {
  font-size: 13px;
  color: #606266;
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
  background: #fafafa;
  border-radius: 6px;
  border: 1px solid #ebeef5;
}
.evidence-summary {
  font-size: 13px;
  color: #606266;
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
  color: #909399;
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
}
.follow-up-tag:hover {
  background: #ecf5ff;
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
  color: #909399;
  font-size: 13px;
  padding: 16px;
}

/* Input area */
.input-area {
  padding: 16px 24px;
  background: #fff;
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
  background: #f5f7fa;
  border-color: #e4e7ed;
}
.input-area :deep(.el-textarea__inner:focus) {
  background: #fff;
  border-color: #409eff;
}
.send-btn {
  height: 40px;
  border-radius: 8px;
  flex-shrink: 0;
  min-width: 88px;
}
</style>
