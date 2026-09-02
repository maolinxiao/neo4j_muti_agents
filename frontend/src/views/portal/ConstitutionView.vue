<template>
  <div class="constitution-view">
    <div class="page-header">
      <div>
        <div class="page-title">{{ t("constitution.title") }}</div>
        <div class="page-desc">{{ t("constitution.pageDesc") }}</div>
      </div>
      <el-button type="primary" :loading="store.loading" @click="store.refreshAll()">
        {{ t("common.refresh") }}
      </el-button>
    </div>

    <ConstitutionAssessmentPanel />
  </div>
</template>

<script setup>
import { onMounted } from "vue";

import ConstitutionAssessmentPanel from "../../components/ConstitutionAssessmentPanel.vue";
import { useI18n } from "../../composables/useI18n";
import { useConstitutionStore } from "../../stores/constitution";

const { t } = useI18n();
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
  background: var(--app-panel);
  border: 1px solid var(--app-border);
  border-radius: 10px;
  padding: 16px 20px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--app-text);
  margin-bottom: 8px;
}

.page-desc {
  font-size: 14px;
  line-height: 1.7;
  color: var(--app-text-2);
  max-width: 860px;
  margin: 0;
}

@media (max-width: 640px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
