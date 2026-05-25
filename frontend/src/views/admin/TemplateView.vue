<template>
  <div class="app-container">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>Cypher 模板管理</span>
        </div>
      </template>
      <el-table :data="items" @row-click="selectRow" border stripe size="small" highlight-current-row>
        <el-table-column prop="key" label="Key" width="180" />
        <el-table-column prop="question_type" label="问题类型" width="180" />
        <el-table-column prop="name" label="名称" />
      </el-table>
      <el-form v-if="current" label-width="100px" class="editor" size="small">
        <el-form-item label="名称"><el-input v-model="current.name" /></el-form-item>
        <el-form-item label="问题类型"><el-input v-model="current.question_type" /></el-form-item>
        <el-form-item label="Cypher"><el-input v-model="current.cypher_query" type="textarea" :rows="12" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="current.is_active" /></el-form-item>
        <el-form-item>
          <el-button type="primary" @click="save">保存修改</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { api } from "../../api/client";

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
  ElMessage.success("保存成功");
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
  background: #fafafa;
  padding: 20px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}
</style>
