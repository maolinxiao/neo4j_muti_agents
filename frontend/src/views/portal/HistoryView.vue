<template>
  <div class="app-container">
    <el-card shadow="hover" class="box-card">
      <template #header>
        <div class="card-header">
          <span>{{ t("history.title") }}</span>
          <span class="header-stats">
            <el-tag size="small" type="info" effect="plain">{{ t("menu.chat") }} · {{ chatStore.sessions.length }} {{ t("history.sessionsUnit") }}</el-tag>
            <el-tag size="small" type="info" effect="plain">{{ t("menu.rnd") }} · {{ rndStore.sessions.length }} {{ t("history.sessionsUnit") }}</el-tag>
          </span>
        </div>
      </template>
      <el-tabs v-model="activeTab">
        <el-tab-pane :label="t('menu.chat')" name="chat">
          <el-table :data="pagedChatSessions" border stripe size="small">
            <template #empty>
              <el-empty :description="t('history.empty')" :image-size="88">
                <el-button type="primary" plain size="small" @click="goNewChat">{{ t("history.emptyAction") }}</el-button>
              </el-empty>
            </template>
            <el-table-column prop="title" :label="t('history.sessionTitle')" min-width="260" show-overflow-tooltip />
            <el-table-column prop="status" :label="t('history.status')" width="120">
              <template #default="{ row }">
                <el-tag :type="row.status === 'completed' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="updated_at" :label="t('history.updatedAt')" width="150">
              <template #default="{ row }">
                <el-tooltip :content="formatDateTime(row.updated_at)" placement="top">
                  <span>{{ formatRelativeTime(row.updated_at, locale) }}</span>
                </el-tooltip>
              </template>
            </el-table-column>
            <el-table-column :label="t('common.actions')" width="140" align="center">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="goChat(row.id)">{{ t("history.view") }}</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="pagination-container">
            <el-pagination
              v-model:current-page="chatCurrentPage"
              v-model:page-size="chatPageSize"
              :page-sizes="[10, 20, 50, 100]"
              background
              layout="total, sizes, prev, pager, next, jumper"
              :total="chatStore.sessions.length"
            />
          </div>
        </el-tab-pane>
        <el-tab-pane :label="t('menu.rnd')" name="rnd">
          <el-table :data="pagedRndSessions" border stripe size="small">
            <template #empty>
              <el-empty :description="t('history.empty')" :image-size="88">
                <el-button type="primary" plain size="small" @click="goNewRnd">{{ t("menu.rnd") }}</el-button>
              </el-empty>
            </template>
            <el-table-column prop="title" :label="t('history.sessionTitle')" min-width="260" show-overflow-tooltip />
            <el-table-column prop="status" :label="t('history.status')" width="120">
              <template #default="{ row }">
                <el-tag :type="row.status === 'completed' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="updated_at" :label="t('history.updatedAt')" width="150">
              <template #default="{ row }">
                <el-tooltip :content="formatDateTime(row.updated_at)" placement="top">
                  <span>{{ formatRelativeTime(row.updated_at, locale) }}</span>
                </el-tooltip>
              </template>
            </el-table-column>
            <el-table-column :label="t('common.actions')" width="140" align="center">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="goRnd(row.id)">{{ t("history.enter") }}</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="pagination-container">
            <el-pagination
              v-model:current-page="rndCurrentPage"
              v-model:page-size="rndPageSize"
              :page-sizes="[10, 20, 50, 100]"
              background
              layout="total, sizes, prev, pager, next, jumper"
              :total="rndStore.sessions.length"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from "vue";
import { useRouter } from "vue-router";

import { useI18n } from "../../composables/useI18n";
import { useChatStore } from "../../stores/chat";
import { useRndStore } from "../../stores/rnd";
import { formatDateTime, formatRelativeTime } from "../../utils/timeFormat";

const { t, locale } = useI18n();
const activeTab = ref("chat");
const chatStore = useChatStore();
const rndStore = useRndStore();
const router = useRouter();

const chatCurrentPage = ref(1);
const chatPageSize = ref(10);
const rndCurrentPage = ref(1);
const rndPageSize = ref(10);

const pagedChatSessions = computed(() => {
  const start = (chatCurrentPage.value - 1) * chatPageSize.value;
  return chatStore.sessions.slice(start, start + chatPageSize.value);
});

const pagedRndSessions = computed(() => {
  const start = (rndCurrentPage.value - 1) * rndPageSize.value;
  return rndStore.sessions.slice(start, start + rndPageSize.value);
});

const goChat = (id) => router.push({ name: "chat", params: { sessionId: id } });
const goRnd = (id) => router.push({ name: "rnd", params: { sessionId: id } });
const goNewChat = () => router.push({ name: "chat" });
const goNewRnd = () => router.push({ name: "rnd" });

onMounted(async () => {
  await Promise.all([chatStore.refreshSessions(), rndStore.refreshSessions()]);
});
</script>

<style scoped>
.app-container {
  padding: 20px;
}
.box-card {
  border-radius: 4px;
}
.card-header {
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.header-stats {
  display: flex;
  gap: 8px;
  font-weight: 400;
}
:deep(.el-table) {
  font-size: 14px;
}
:deep(.el-table td.el-table__cell) {
  padding: 10px 8px;
}
:deep(.el-table th.el-table__cell) {
  font-size: 14px;
  font-weight: 600;
  background-color: var(--el-table-header-bg-color);
}
:deep(.el-pagination) {
  font-size: 14px;
  padding: 16px 0;
}
:deep(.el-pagination .el-pagination__total) {
  font-size: 14px;
  margin-right: 16px;
}
.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}
</style>
