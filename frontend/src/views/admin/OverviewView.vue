<template>
  <div class="app-container">
    <el-space direction="vertical" fill size="large" style="width: 100%;">
      <el-row :gutter="20">
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <el-statistic title="PostgreSQL" :value="overview.postgres_ok ? 1 : 0"><template #suffix>{{ overview.postgres_ok ? t("admin.overview.ok") : t("admin.overview.error") }}</template></el-statistic>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <el-statistic title="Neo4j" :value="overview.neo4j_ok ? 1 : 0"><template #suffix>{{ overview.neo4j_ok ? t("admin.overview.ok") : t("admin.overview.error") }}</template></el-statistic>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <el-statistic :title="t('admin.overview.workflowSessions')" :value="overview.workflow_session_count || 0" />
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <el-statistic :title="t('admin.overview.workflowRuns')" :value="overview.workflow_run_count || 0" />
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="4">
          <el-card shadow="hover" class="stat-card">
            <el-statistic :title="t('admin.overview.entityProfiles')" :value="overview.entity_profile_count || 0" />
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="hover" class="stat-card">
            <el-statistic :title="t('admin.overview.promptTemplates')" :value="overview.prompt_template_count || 0" />
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="hover" class="stat-card">
            <el-statistic :title="t('admin.overview.cypherTemplates')" :value="overview.cypher_template_count || 0" />
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="hover" class="stat-card">
            <el-statistic :title="t('admin.overview.herbCount')" :value="overview.graph_metrics?.herb_count || 0" />
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="hover" class="stat-card">
            <el-statistic :title="t('admin.overview.foodHomologyCount')" :value="overview.graph_metrics?.food_homology_count || 0" />
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="hover" class="stat-card">
            <el-statistic :title="t('admin.overview.replacementEdges')" :value="overview.graph_metrics?.replacement_edge_count || 0" />
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="hover">
        <template #header>
          <div class="card-header">
            <span>{{ t("admin.overview.graphLabels") }}</span>
          </div>
        </template>
        <el-table :data="overview.graph_label_counts || []" border stripe>
          <el-table-column prop="label" :label="t('admin.overview.label')" />
          <el-table-column prop="total" :label="t('admin.overview.count')" />
        </el-table>
      </el-card>
    </el-space>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { api } from "../../api/client";
import { useI18n } from "../../composables/useI18n";

const { t } = useI18n();
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
