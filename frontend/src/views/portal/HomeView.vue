<template>
  <div class="app-container home">
    <el-row :gutter="20">
      <el-col :sm="24" :lg="24">
        <el-card shadow="never" class="welcome-card">
          <div class="welcome-content">
            <h1 class="welcome-title">{{ t("home.welcomeTitle") }}</h1>
            <p class="welcome-desc">
              {{ t("home.welcomeDesc") }}
            </p>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="mt-20">
      <el-col :xs="24" :sm="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon stat-icon-primary">
            <el-icon><Monitor /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">3</div>
            <div class="stat-label">{{ t("home.statWorkbenches") }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon stat-icon-success">
            <el-icon><Cpu /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">5</div>
            <div class="stat-label">{{ t("home.statAgents") }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon stat-icon-warning">
            <el-icon><Share /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">Neo4j</div>
            <div class="stat-label">{{ t("home.statEvidenceBase") }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="mt-20">
      <el-col :xs="24" :md="8">
        <el-card shadow="hover" class="feature-card">
          <template #header>
            <div class="card-header">
              <span class="card-title">{{ t("home.constitutionTitle") }}</span>
            </div>
          </template>
          <div class="feature-body">
            <p class="feature-desc">{{ t("home.constitutionDesc") }}</p>
            <ul class="feature-list">
              <li>{{ t("home.constitutionItem1") }}</li>
              <li>{{ t("home.constitutionItem2") }}</li>
              <li>{{ t("home.constitutionItem3") }}</li>
            </ul>
            <el-button type="warning" @click="goConstitution">{{ t("home.enterConstitution") }}</el-button>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="hover" class="feature-card">
          <template #header>
            <div class="card-header">
              <span class="card-title">{{ t("home.qaTitle") }}</span>
            </div>
          </template>
          <div class="feature-body">
            <p class="feature-desc">{{ t("home.qaDesc") }}</p>
            <ul class="feature-list">
              <li>{{ t("home.qaItem1") }}</li>
              <li>{{ t("home.qaItem2") }}</li>
              <li>{{ t("home.qaItem3") }}</li>
            </ul>
            <el-button type="primary" @click="goKnowledge">{{ t("home.enterQa") }}</el-button>
          </div>
        </el-card>
      </el-col>
      
      <el-col :xs="24" :md="8">
        <el-card shadow="hover" class="feature-card">
          <template #header>
            <div class="card-header">
              <span class="card-title">{{ t("home.rndTitle") }}</span>
            </div>
          </template>
          <div class="feature-body">
            <p class="feature-desc">{{ t("home.rndDesc") }}</p>
            <ul class="feature-list">
              <li>{{ t("home.rndItem1") }}</li>
              <li>{{ t("home.rndItem2") }}</li>
              <li>{{ t("home.rndItem3") }}</li>
            </ul>
            <el-button type="success" @click="goRnd">{{ t("home.enterRnd") }}</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { useRouter } from "vue-router";
import { Monitor, Cpu, Share } from "@element-plus/icons-vue";

import { useI18n } from "../../composables/useI18n";

const { t } = useI18n();
const router = useRouter();

const goConstitution = () => router.push({ name: "constitution" });
const goKnowledge = () => router.push({ name: "chat" });
const goRnd = () => router.push({ name: "rnd" });
</script>

<style scoped>
.app-container {
  padding: 20px;
}

.mt-20 {
  margin-top: 20px;
}

.welcome-card {
  background: linear-gradient(135deg, #409EFF, #66b1ff);
  color: #fff;
  border: none;
}

.welcome-content {
  padding: 20px;
}

.welcome-title {
  font-size: 24px;
  font-weight: 500;
  margin: 0 0 16px 0;
}

.welcome-desc {
  font-size: 15px;
  line-height: 1.8;
  opacity: 0.9;
  margin: 0;
  max-width: 800px;
}

.stat-card {
  :deep(.el-card__body) {
    display: flex;
    align-items: center;
    padding: 20px;
  }
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 30px;
  margin-right: 20px;
}

.stat-icon-primary {
  background: rgba(64, 158, 255, 0.1);
  color: #409EFF;
}

.stat-icon-success {
  background: rgba(103, 194, 58, 0.1);
  color: #67C23A;
}

.stat-icon-warning {
  background: rgba(230, 162, 60, 0.1);
  color: #E6A23C;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: var(--app-text);
  margin-bottom: 8px;
}

.stat-label {
  font-size: 14px;
  color: var(--app-text-3);
}

.feature-card {
  height: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--app-text);
}

.feature-body {
  padding: 10px 0;
}

.feature-desc {
  color: var(--app-text-2);
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 16px;
}

.feature-list {
  padding-left: 20px;
  margin-bottom: 24px;
  color: var(--app-text-2);
  font-size: 14px;
  line-height: 2;
}

.feature-list li {
  list-style-type: disc;
}
</style>
