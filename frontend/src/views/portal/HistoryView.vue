<template>
  <div class="app-container">
    <el-card shadow="hover" class="box-card">
      <template #header>
        <div class="card-header">
          <span>历史记录</span>
        </div>
      </template>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="知识问答" name="chat">
          <el-table :data="pagedChatSessions" border stripe size="small">
            <el-table-column prop="title" label="标题" min-width="260" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="row.status === 'completed' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="updated_at" label="更新时间" width="180" />
            <el-table-column label="操作" width="140" align="center">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="goChat(row.id)">查看</el-button>
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
        <el-tab-pane label="研发协同" name="rnd">
          <el-table :data="pagedRndSessions" border stripe size="small">
            <el-table-column prop="title" label="标题" min-width="260" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="row.status === 'completed' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="updated_at" label="更新时间" width="180" />
            <el-table-column label="操作" width="140" align="center">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="goRnd(row.id)">进入</el-button>
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

import { useChatStore } from "../../stores/chat";
import { useRndStore } from "../../stores/rnd";

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
  background-color: #f5f7fa;
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
