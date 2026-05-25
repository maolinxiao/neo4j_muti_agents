<template>
  <div class="app-container home">
    <el-row :gutter="20">
      <el-col :sm="24" :lg="24">
        <el-card shadow="never" class="welcome-card">
          <div class="welcome-content">
            <h1 class="welcome-title">欢迎使用 药食同源研发协同平台</h1>
            <p class="welcome-desc">
              本系统基于知识图谱与多智能体技术，提供药食同源产品研发的智能化辅助决策。
              核心功能包括：图谱检索、组方建议、功效预测、风味分析和替代映射。
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
            <div class="stat-value">2</div>
            <div class="stat-label">核心工作台</div>
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
            <div class="stat-label">研发 Agent</div>
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
            <div class="stat-label">证据底座</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="mt-20">
      <el-col :xs="24" :md="12">
        <el-card shadow="hover" class="feature-card">
          <template #header>
            <div class="card-header">
              <span class="card-title">知识问答工作台</span>
            </div>
          </template>
          <div class="feature-body">
            <p class="feature-desc">适合快速检索药材、成分、功效标签和替代关系，查看证据图谱并追溯节点详情。</p>
            <ul class="feature-list">
              <li>药材 / 成分 / 功效标签检索</li>
              <li>证据子图与参考来源</li>
              <li>历史知识问答回看</li>
            </ul>
            <el-button type="primary" @click="goKnowledge">进入知识问答</el-button>
          </div>
        </el-card>
      </el-col>
      
      <el-col :xs="24" :md="12">
        <el-card shadow="hover" class="feature-card">
          <template #header>
            <div class="card-header">
              <span class="card-title">研发协同工作台</span>
            </div>
          </template>
          <div class="feature-body">
            <p class="feature-desc">适合围绕产品目标发起研发工作流，查看方剂生成、功效预测、风味分析与替代映射结果。</p>
            <ul class="feature-list">
              <li>结构化研发需求解析</li>
              <li>多阶段 Agent 自动化执行</li>
              <li>替代对比与最终方案输出</li>
            </ul>
            <el-button type="success" @click="goRnd">进入研发协同</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { useRouter } from "vue-router";
import { Monitor, Cpu, Share } from "@element-plus/icons-vue";

const router = useRouter();

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
  color: #303133;
  margin-bottom: 8px;
}

.stat-label {
  font-size: 14px;
  color: #909399;
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
  color: #303133;
}

.feature-body {
  padding: 10px 0;
}

.feature-desc {
  color: #606266;
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 16px;
}

.feature-list {
  padding-left: 20px;
  margin-bottom: 24px;
  color: #606266;
  font-size: 14px;
  line-height: 2;
}

.feature-list li {
  list-style-type: disc;
}
</style>
