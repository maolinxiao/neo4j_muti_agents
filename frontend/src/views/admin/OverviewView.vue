<template>
  <div class="app-container">
    <el-space direction="vertical" fill size="large" style="width: 100%;">
      <el-row :gutter="20">
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <el-statistic title="PostgreSQL" :value="overview.postgres_ok ? 1 : 0"><template #suffix>{{ overview.postgres_ok ? "正常" : "异常" }}</template></el-statistic>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <el-statistic title="Neo4j" :value="overview.neo4j_ok ? 1 : 0"><template #suffix>{{ overview.neo4j_ok ? "正常" : "异常" }}</template></el-statistic>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <el-statistic title="研发会话" :value="overview.workflow_session_count || 0" />
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <el-statistic title="研发运行数" :value="overview.workflow_run_count || 0" />
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="4">
          <el-card shadow="hover" class="stat-card">
            <el-statistic title="实体档案" :value="overview.entity_profile_count || 0" />
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="hover" class="stat-card">
            <el-statistic title="Prompt 模板" :value="overview.prompt_template_count || 0" />
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="hover" class="stat-card">
            <el-statistic title="Cypher 模板" :value="overview.cypher_template_count || 0" />
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="hover" class="stat-card">
            <el-statistic title="药材数" :value="overview.graph_metrics?.herb_count || 0" />
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="hover" class="stat-card">
            <el-statistic title="药食同源数" :value="overview.graph_metrics?.food_homology_count || 0" />
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="hover" class="stat-card">
            <el-statistic title="正式替代边" :value="overview.graph_metrics?.replacement_edge_count || 0" />
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="hover">
        <template #header>
          <div class="card-header">
            <span>图谱标签分布</span>
          </div>
        </template>
        <el-table :data="overview.graph_label_counts || []" border stripe>
          <el-table-column prop="label" label="标签" />
          <el-table-column prop="total" label="数量" />
        </el-table>
      </el-card>
    </el-space>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { api } from "../../api/client";

const overview = ref({});
onMounted(async () => {
  const { data } = await api.getOverview();
  overview.value = data;
});
</script>

<style scoped>
.app-container {
  padding: 20px;
}
.stat-card {
  text-align: center;
  padding: 10px 0;
}
.card-header {
  font-weight: 500;
}
</style>
