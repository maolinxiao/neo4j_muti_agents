<template>
  <div class="app-container">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>{{ t("admin.logs.title") }}</span>
        </div>
      </template>
      <el-tabs v-model="activeTab">
        <el-tab-pane :label="t('admin.logs.qaTab')" name="qa">
          <el-table :data="pagedChatLogs" border stripe size="small">
            <el-table-column prop="question" :label="t('admin.logs.question')" min-width="260" show-overflow-tooltip />
            <el-table-column prop="question_type" :label="t('admin.logs.type')" width="150" />
            <el-table-column prop="trace_summary" :label="t('admin.logs.summary')" min-width="260" show-overflow-tooltip />
            <el-table-column prop="retrieval_ms" :label="t('admin.logs.retrievalMs')" width="130" align="center" />
            <el-table-column prop="llm_ms" :label="t('admin.logs.llmMs')" width="130" align="center" />
            <el-table-column prop="created_at" :label="t('admin.logs.time')" width="180" />
          </el-table>
          <div class="pagination-container">
            <el-pagination
              v-model:current-page="qaCurrentPage"
              v-model:page-size="qaPageSize"
              :page-sizes="[10, 20, 50, 100]"
              background
              layout="total, sizes, prev, pager, next, jumper"
              :total="chatLogs.length"
            />
          </div>
        </el-tab-pane>
        <el-tab-pane :label="t('admin.logs.rndTab')" name="rnd">
          <el-table :data="pagedWorkflowLogs" border stripe size="small">
            <el-table-column prop="question" :label="t('admin.logs.requirement')" min-width="300" show-overflow-tooltip />
            <el-table-column prop="status" :label="t('admin.logs.status')" width="120">
              <template #default="{ row }">
                <el-tag :type="row.status === 'completed' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('admin.logs.stepCount')" width="120" align="center">
              <template #default="{ row }">{{ row.summary_metrics?.stepCount || 0 }}</template>
            </el-table-column>
            <el-table-column :label="t('admin.logs.snapshotCount')" width="140" align="center">
              <template #default="{ row }">{{ row.summary_metrics?.graphSnapshotCount || 0 }}</template>
            </el-table-column>
            <el-table-column prop="created_at" :label="t('admin.logs.startTime')" width="180" />
          </el-table>
          <div class="pagination-container">
            <el-pagination
              v-model:current-page="rndCurrentPage"
              v-model:page-size="rndPageSize"
              :page-sizes="[10, 20, 50, 100]"
              background
              layout="total, sizes, prev, pager, next, jumper"
              :total="workflowLogs.length"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from "vue";
import { api } from "../../api/client";
import { useI18n } from "../../composables/useI18n";

const { t } = useI18n();
const activeTab = ref("qa");
const chatLogs = ref([]);
const workflowLogs = ref([]);

const qaCurrentPage = ref(1);
const qaPageSize = ref(10);
const rndCurrentPage = ref(1);
const rndPageSize = ref(10);

const pagedChatLogs = computed(() => {
  const start = (qaCurrentPage.value - 1) * qaPageSize.value;
  return chatLogs.value.slice(start, start + qaPageSize.value);
});

const pagedWorkflowLogs = computed(() => {
  const start = (rndCurrentPage.value - 1) * rndPageSize.value;
  return workflowLogs.value.slice(start, start + rndPageSize.value);
});

onMounted(async () => {
  const [{ data: qa }, { data: workflow }] = await Promise.all([
    api.getChatLogs(),
    api.getWorkflowLogs(),
  ]);
  chatLogs.value = qa;
  workflowLogs.value = workflow;
});
</script>

<style scoped>
.app-container {
  padding: 20px;
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
