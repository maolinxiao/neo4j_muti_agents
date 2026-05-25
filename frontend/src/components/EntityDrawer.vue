<template>
  <el-drawer v-model="visible" title="实体详情" size="32%">
    <template v-if="entity">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="名称">{{ entity.name }}</el-descriptions-item>
        <el-descriptions-item label="类型">{{ entity.entity_type }}</el-descriptions-item>
        <el-descriptions-item label="别名">{{ (entity.aliases || []).join(" / ") || "-" }}</el-descriptions-item>
      </el-descriptions>
      <pre class="props">{{ entity.props }}</pre>
    </template>
  </el-drawer>
</template>

<script setup>
const visible = defineModel("visible", { type: Boolean, default: false });
defineProps({ entity: { type: Object, default: null } });
</script>

<style scoped>
.props { margin-top: 16px; padding: 12px; background: #0f172a; color: #e2e8f0; border-radius: 8px; white-space: pre-wrap; }
</style>
