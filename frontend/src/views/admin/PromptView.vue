<template>
  <div class="app-container">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>Prompt 管理</span>
        </div>
      </template>
      <el-space direction="vertical" fill style="width: 100%;">
        <el-segmented v-model="scenario" :options="scenarioOptions" />
        <el-table :data="filteredItems" @row-click="selectRow" border stripe size="small" highlight-current-row>
          <el-table-column prop="key" label="Key" width="220" />
          <el-table-column prop="agent_key" label="Agent" width="180" />
          <el-table-column prop="name" label="名称" min-width="180" />
          <el-table-column prop="updated_at" label="更新时间" width="180" />
        </el-table>

        <el-form v-if="current" label-width="110px" class="editor" size="small">
          <el-form-item label="场景"><el-input v-model="current.scenario" /></el-form-item>
          <el-form-item label="Agent"><el-input v-model="current.agent_key" /></el-form-item>
          <el-form-item label="名称"><el-input v-model="current.name" /></el-form-item>
          <el-form-item label="描述"><el-input v-model="current.description" /></el-form-item>
          <el-form-item label="System Prompt"><el-input v-model="current.system_prompt" type="textarea" :rows="12" /></el-form-item>
          <el-form-item label="输出 Schema"><el-input :model-value="formatJson(current.output_schema)" type="textarea" :rows="8" readonly /></el-form-item>
          <el-form-item label="启用"><el-switch v-model="current.is_active" /></el-form-item>
          <el-form-item>
            <el-button type="primary" @click="save">保存修改</el-button>
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

const items = ref([]);
const current = ref(null);
const scenario = ref("rnd_workflow");
const scenarioOptions = [
  { label: "研发工作流", value: "rnd_workflow" },
  { label: "知识问答", value: "knowledge_qa" },
];

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
  ElMessage.success("保存成功");
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
  background: #fafafa;
  padding: 20px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}
</style>
