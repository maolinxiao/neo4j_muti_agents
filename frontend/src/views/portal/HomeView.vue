<template>
  <div class="app-container home">
    <!-- 欢迎横幅 -->
    <section class="hero-banner">
      <div class="hero-text">
        <div class="hero-greeting">{{ t("home.greeting", { name: auth.displayName }) }}</div>
        <h1 class="hero-title">{{ t("home.welcomeTitle") }}</h1>
        <p class="hero-desc">{{ t("home.welcomeDesc") }}</p>
        <div class="hero-actions">
          <el-button type="primary" size="large" @click="goKnowledge">
            <el-icon class="mr-6"><ChatDotRound /></el-icon>{{ t("home.enterQa") }}
          </el-button>
          <el-button size="large" plain class="hero-btn-light" @click="goRnd">
            <el-icon class="mr-6"><Cpu /></el-icon>{{ t("home.enterRnd") }}
          </el-button>
          <el-button size="large" plain class="hero-btn-light" @click="goConstitution">
            <el-icon class="mr-6"><List /></el-icon>{{ t("home.enterConstitution") }}
          </el-button>
        </div>
      </div>
      <div class="hero-orbit" aria-hidden="true">
        <span class="orbit-dot dot-a" />
        <span class="orbit-dot dot-b" />
        <span class="orbit-dot dot-c" />
        <span class="orbit-ring ring-a" />
        <span class="orbit-ring ring-b" />
      </div>
    </section>

    <!-- 我的统计（真实数据） -->
    <section class="stats-row">
      <div v-for="item in statItems" :key="item.key" class="stat-card" :class="`stat-${item.tone}`">
        <div class="stat-icon">
          <el-icon :size="22"><component :is="item.icon" /></el-icon>
        </div>
        <div class="stat-meta">
          <div class="stat-value">{{ item.value }}</div>
          <div class="stat-label">{{ item.label }}</div>
        </div>
      </div>
    </section>

    <!-- 三大入口 -->
    <section class="entries-row">
      <article
        v-for="entry in entries"
        :key="entry.key"
        class="entry-card"
        :class="`entry-${entry.key}`"
        @click="entry.go"
      >
        <div class="entry-icon">
          <el-icon :size="26"><component :is="entry.icon" /></el-icon>
        </div>
        <h3 class="entry-title">{{ entry.title }}</h3>
        <p class="entry-desc">{{ entry.desc }}</p>
        <div class="entry-tags">
          <el-tag v-for="tag in entry.tags" :key="tag" size="small" effect="plain" round>{{ tag }}</el-tag>
        </div>
        <div class="entry-cta">
          {{ t("home.enter") }} {{ entry.title }}
          <el-icon><ArrowRight /></el-icon>
        </div>
      </article>
    </section>

    <!-- 底部两栏：最近会话 + 快捷提问 -->
    <section class="bottom-row">
      <el-card shadow="never" class="panel-card">
        <template #header>
          <div class="panel-header">
            <span class="panel-title">{{ t("home.recentChats") }}</span>
            <el-button link type="primary" @click="goKnowledge">{{ t("home.viewAll") }}</el-button>
          </div>
        </template>
        <template v-if="recentSessions.length">
          <div
            v-for="sess in recentSessions"
            :key="sess.id"
            class="recent-item"
            @click="openSession(sess.id)"
          >
            <div class="recent-icon">
              <el-icon><ChatDotRound /></el-icon>
            </div>
            <div class="recent-body">
              <div class="recent-title">{{ sess.title || t("chat.newSessionTitle") }}</div>
              <div class="recent-time">{{ formatTime(sess.updated_at || sess.created_at) }}</div>
            </div>
            <el-icon class="recent-arrow"><ArrowRight /></el-icon>
          </div>
        </template>
        <el-empty v-else :description="t('home.emptyRecent')" :image-size="56" />
      </el-card>

      <el-card shadow="never" class="panel-card">
        <template #header>
          <div class="panel-header">
            <span class="panel-title">{{ t("home.quickAsk") }}</span>
          </div>
        </template>
        <div class="quick-list">
          <div v-for="q in quickQuestions" :key="q" class="quick-item" @click="askQuestion(q)">
            <span class="quick-text">{{ q }}</span>
            <el-icon class="quick-arrow"><ArrowRight /></el-icon>
          </div>
        </div>
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  ArrowRight,
  ChatDotRound,
  ChatLineRound,
  Cpu,
  List,
  Share,
} from "@element-plus/icons-vue";

import { api } from "../../api/client";
import { useI18n } from "../../composables/useI18n";
import { useAuthStore } from "../../stores/auth";
import { useChatStore } from "../../stores/chat";

const { t } = useI18n();
const router = useRouter();
const auth = useAuthStore();
const chatStore = useChatStore();

const stats = ref({});
const recentSessions = ref([]);

const goConstitution = () => router.push({ name: "constitution" });
const goKnowledge = () => router.push({ name: "chat" });
const goRnd = () => router.push({ name: "rnd" });
const openSession = (id) => router.push({ name: "chat", params: { sessionId: id } });
const askQuestion = (q) => {
  chatStore.pendingQuestion = q;
  router.push({ name: "chat" });
};

const statItems = computed(() => [
  { key: "sessions", tone: "blue", icon: ChatLineRound, label: t("account.statChatSessions"), value: stats.value.chat_sessions ?? 0 },
  { key: "messages", tone: "green", icon: ChatDotRound, label: t("account.statMessages"), value: stats.value.chat_messages ?? 0 },
  { key: "runs", tone: "orange", icon: Cpu, label: t("account.statWorkflowRuns"), value: stats.value.workflow_runs ?? 0 },
  { key: "assessments", tone: "pink", icon: List, label: t("account.statAssessments"), value: stats.value.constitution_assessments ?? 0 },
]);

const entries = computed(() => [
  {
    key: "qa",
    icon: ChatDotRound,
    title: t("home.qaTitle"),
    desc: t("home.qaDesc"),
    tags: ["KB1-KB7", "Graph"],
    go: goKnowledge,
  },
  {
    key: "constitution",
    icon: List,
    title: t("home.constitutionTitle"),
    desc: t("home.constitutionDesc"),
    tags: ["KB8", "9 Types"],
    go: goConstitution,
  },
  {
    key: "rnd",
    icon: Cpu,
    title: t("home.rndTitle"),
    desc: t("home.rndDesc"),
    tags: ["6 Agents", "KB3-KB5"],
    go: goRnd,
  },
]);

const quickQuestions = [
  "黄芪的功效与适用人群是什么？",
  "把四君子汤改造成药食同源代餐粉",
  "我是什么体质？",
  "孕妇食用人参有什么风险？",
];

const formatTime = (value) => {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getMonth() + 1}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

onMounted(async () => {
  try {
    const { data } = await api.getMyStats();
    stats.value = data;
  } catch {
    stats.value = {};
  }
  try {
    const { data } = await api.listSessions();
    recentSessions.value = (data || []).slice(0, 6);
  } catch {
    recentSessions.value = [];
  }
});
</script>

<style scoped>
.app-container {
  padding: 20px;
}
.mr-6 {
  margin-right: 6px;
}

/* 欢迎横幅 */
.hero-banner {
  position: relative;
  overflow: hidden;
  border-radius: 16px;
  padding: 34px 36px;
  color: #fff;
  background:
    radial-gradient(circle at 85% 20%, rgba(255, 255, 255, 0.16), transparent 42%),
    linear-gradient(120deg, #409eff 0%, #2f7cd6 55%, #1f4d8f 100%);
  box-shadow: 0 10px 28px rgba(30, 90, 160, 0.25);
}
.hero-greeting {
  font-size: 14px;
  opacity: 0.85;
  margin-bottom: 8px;
}
.hero-title {
  margin: 0 0 10px;
  font-size: 26px;
  font-weight: 700;
}
.hero-desc {
  margin: 0 0 22px;
  max-width: 720px;
  font-size: 14px;
  line-height: 1.7;
  opacity: 0.92;
}
.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.hero-actions .el-button--primary {
  background: #fff;
  color: #2f7cd6;
  border: none;
}
.hero-btn-light {
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.35);
  color: #fff;
}
.hero-btn-light:hover {
  background: rgba(255, 255, 255, 0.24);
  color: #fff;
}
.hero-orbit {
  position: absolute;
  right: 40px;
  top: 50%;
  width: 180px;
  height: 180px;
  transform: translateY(-50%);
  opacity: 0.9;
}
.orbit-ring {
  position: absolute;
  border: 1px solid rgba(255, 255, 255, 0.28);
  border-radius: 50%;
}
.ring-a {
  inset: 10px;
  animation: orbitSpin 14s linear infinite;
}
.ring-b {
  inset: 38px;
  animation: orbitSpin 9s linear infinite reverse;
}
.orbit-dot {
  position: absolute;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #a7f3d0;
  box-shadow: 0 0 12px rgba(167, 243, 208, 0.9);
}
.dot-a {
  top: 6px;
  left: 50%;
}
.dot-b {
  right: 18px;
  bottom: 34px;
  width: 9px;
  height: 9px;
  background: #c4b5fd;
}
.dot-c {
  left: 22px;
  bottom: 40px;
  width: 8px;
  height: 8px;
  background: #fde68a;
}
@keyframes orbitSpin {
  to {
    transform: rotate(360deg);
  }
}

/* 统计卡 */
.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 16px;
  margin-top: 20px;
}
.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px;
  border-radius: 12px;
  border: 1px solid var(--app-border);
  background: var(--app-panel);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
}
.stat-icon {
  width: 46px;
  height: 46px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-blue .stat-icon {
  background: rgba(64, 158, 255, 0.12);
  color: #409eff;
}
.stat-green .stat-icon {
  background: rgba(103, 194, 58, 0.12);
  color: #67c23a;
}
.stat-orange .stat-icon {
  background: rgba(230, 162, 60, 0.14);
  color: #e6a23c;
}
.stat-pink .stat-icon {
  background: rgba(236, 72, 153, 0.12);
  color: #ec4899;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--app-text);
  line-height: 1.1;
}
.stat-label {
  font-size: 13px;
  color: var(--app-text-3);
  margin-top: 4px;
}

/* 入口卡 */
.entries-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
  margin-top: 20px;
}
.entry-card {
  position: relative;
  border-radius: 14px;
  padding: 22px;
  background: var(--app-panel);
  border: 1px solid var(--app-border);
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}
.entry-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 26px rgba(0, 0, 0, 0.1);
  border-color: var(--app-active-border);
}
.entry-icon {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 14px;
}
.entry-qa .entry-icon {
  background: rgba(64, 158, 255, 0.12);
  color: #409eff;
}
.entry-constitution .entry-icon {
  background: rgba(236, 72, 153, 0.12);
  color: #ec4899;
}
.entry-rnd .entry-icon {
  background: rgba(230, 162, 60, 0.14);
  color: #e6a23c;
}
.entry-title {
  margin: 0 0 8px;
  font-size: 17px;
  font-weight: 600;
  color: var(--app-text);
}
.entry-desc {
  margin: 0 0 14px;
  font-size: 13px;
  line-height: 1.65;
  color: var(--app-text-2);
  min-height: 42px;
}
.entry-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 16px;
}
.entry-cta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 600;
  color: var(--app-active-border);
}
.entry-card:hover .entry-cta .el-icon {
  transform: translateX(3px);
}
.entry-cta .el-icon {
  transition: transform 0.18s ease;
}

/* 底部两栏 */
.bottom-row {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 16px;
  margin-top: 20px;
}
.panel-card {
  border-radius: 12px;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--app-text);
}
.recent-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s ease;
}
.recent-item:hover {
  background: var(--app-hover);
}
.recent-icon {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  background: rgba(64, 158, 255, 0.1);
  color: #409eff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.recent-body {
  flex: 1;
  min-width: 0;
}
.recent-title {
  font-size: 13px;
  color: var(--app-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.recent-time {
  font-size: 12px;
  color: var(--app-text-3);
  margin-top: 2px;
}
.recent-arrow {
  color: var(--app-text-3);
}
.quick-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.quick-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--app-panel-2);
  border: 1px solid var(--app-border);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.quick-item:hover {
  border-color: var(--app-active-border);
  background: var(--app-active);
}
.quick-text {
  font-size: 13px;
  color: var(--app-text-2);
}
.quick-arrow {
  color: var(--app-text-3);
  flex-shrink: 0;
}

@media (max-width: 900px) {
  .bottom-row {
    grid-template-columns: 1fr;
  }
  .hero-orbit {
    display: none;
  }
}
</style>
