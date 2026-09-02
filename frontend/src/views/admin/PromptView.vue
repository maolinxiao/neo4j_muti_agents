<template>
  <div class="app-container">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>{{ t("admin.prompts.title") }}</span>
        </div>
      </template>
      <el-space direction="vertical" fill style="width: 100%;">
        <el-segmented v-model="scenario" :options="scenarioOptions" />
        <el-table :data="filteredItems" @row-click="selectRow" border stripe size="small" highlight-current-row>
          <el-table-column prop="key" label="Key" width="220" />
          <el-table-column prop="agent_key" label="Agent" width="180" />
          <el-table-column prop="name" :label="t('admin.prompts.name')" min-width="180" />
          <el-table-column prop="updated_at" :label="t('admin.prompts.updatedAt')" width="180" />
        </el-table>

        <el-form v-if="current" label-width="110px" class="editor" size="small">
          <el-form-item :label="t('admin.prompts.scenario')"><el-input v-model="current.scenario" /></el-form-item>
          <el-form-item label="Agent"><el-input v-model="current.agent_key" /></el-form-item>
          <el-form-item :label="t('admin.prompts.name')"><el-input v-model="current.name" /></el-form-item>
          <el-form-item :label="t('admin.prompts.description')"><el-input v-model="current.description" /></el-form-item>
          <el-form-item label="System Prompt"><el-input v-model="current.system_prompt" type="textarea" :rows="12" /></el-form-item>
          <el-form-item :label="t('admin.prompts.outputSchema')"><el-input :model-value="formatJson(current.output_schema)" type="textarea" :rows="8" readonly /></el-form-item>
          <el-form-item :label="t('admin.prompts.enabled')"><el-switch v-model="current.is_active" /></el-form-item>
          <el-form-item>
            <el-button type="primary" @click="save">{{ t("admin.prompts.save") }}</el-button>
          </el-form-item>
        </el-form>
      </el-space>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { api } from "../../api/client";
import { useI18n } from "../../composables/useI18n";

const { t } = useI18n();
const items = ref([]);
const current = ref(null);
const scenario = ref("rnd_workflow");
const scenarioOptions = computed(() => [
  { label: t("admin.prompts.scenarioRnd"), value: "rnd_workflow" },
  { label: t("admin.prompts.scenarioQa"), value: "knowledge_qa" },
]);

const filteredItems = computed(() => items.value.filter((item) => item.scenario === scenario.value));

const load = async () => {
  const { data } = await api.getPrompts();
  items.value = data;
  current.value = filteredItems.value[0] ? { ...filteredItems.value[0] } : null;
};

const selectRow = (row) => {
  current.value = { ...row };
};

const save = async () => {
  await api.updatePrompt(current.value.id, current.value);
  ElMessage.success(t("admin.prompts.saved"));
  await load();
};

const formatJson = (value) => {
  try {
    return JSON.stringify(value || {}, null, 2);
  } catch {
    return String(value ?? "");
  }
};

onMounted(load);

watch(scenario, () => {
  current.value = filteredItems.value[0] ? { ...filteredItems.value[0] } : null;
});
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
