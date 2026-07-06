<template>
  <div class="constitution-view">
    <div class="page-header">
      <div>
        <div class="page-title">体质辨识</div>
        <div class="page-desc">支持手动选择九种体质、逐题完成标准量表测评，并把结果保存为后续知识问答的默认体质档案。</div>
      </div>
      <el-button type="primary" :loading="store.loading" @click="store.refreshAll()">刷新数据</el-button>
    </div>

    <ConstitutionAssessmentPanel />
  </div>
</template>

<script setup>
import { onMounted } from "vue";

import ConstitutionAssessmentPanel from "../../components/ConstitutionAssessmentPanel.vue";
import { useConstitutionStore } from "../../stores/constitution";

const store = useConstitutionStore();

onMounted(async () => {
  await store.refreshAll();
});
</script>

<style scoped>
.constitution-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  padding: 16px 20px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.page-desc {
  font-size: 14px;
  line-height: 1.7;
  color: #606266;
  max-width: 860px;
}
</style>
