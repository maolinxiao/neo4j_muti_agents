<template>
  <div class="app-container">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>{{ t("admin.templates.title") }}</span>
        </div>
      </template>
      <el-table :data="items" @row-click="selectRow" border stripe size="small" highlight-current-row>
        <el-table-column prop="key" label="Key" width="180" />
        <el-table-column prop="question_type" :label="t('admin.templates.questionType')" width="180" />
        <el-table-column prop="name" :label="t('admin.templates.name')" />
      </el-table>
      <el-form v-if="current" label-width="100px" class="editor" size="small">
        <el-form-item :label="t('admin.templates.name')"><el-input v-model="current.name" /></el-form-item>
        <el-form-item :label="t('admin.templates.questionType')"><el-input v-model="current.question_type" /></el-form-item>
        <el-form-item label="Cypher"><el-input v-model="current.cypher_query" type="textarea" :rows="12" /></el-form-item>
        <el-form-item :label="t('admin.templates.enabled')"><el-switch v-model="current.is_active" /></el-form-item>
        <el-form-item>
          <el-button type="primary" @click="save">{{ t("admin.templates.save") }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { api } from "../../api/client";
import { useI18n } from "../../composables/useI18n";

const { t } = useI18n();
const items = ref([]);
const current = ref(null);
const load = async () => {
  const { data } = await api.getTemplates();
  items.value = data;
  current.value = data[0] || null;
};
const selectRow = (row) => { current.value = { ...row }; };
const save = async () => {
  await api.updateTemplate(current.value.id, current.value);
  ElMessage.success(t("admin.templates.saved"));
  await load();
};
onMounted(load);
</script>

<style scoped>
.app-container {
  padding: 20px;
}
.card-header {
  font-weight: 500;
}
.editor {
  margin-top: 20px;
  background: var(--app-panel-2);
  padding: 20px;
  border: 1px solid var(--app-border);
  border-radius: 4px;
}
</style>
