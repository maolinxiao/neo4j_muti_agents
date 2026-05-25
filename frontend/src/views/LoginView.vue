<template>
  <div class="login-page">
    <video
      class="bg-video"
      autoplay
      muted
      loop
      playsinline
      poster="/login-bg-poster.svg"
    >
      <source src="/login-bg.mp4" type="video/mp4" />
    </video>
    <div class="bg-fallback"></div>

    <div class="login-overlay" aria-hidden="true">
      <div class="grid-scan"></div>
      <svg class="graph-svg" viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid slice">
        <defs>
          <linearGradient id="edgeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#78d8b7" stop-opacity="0.15" />
            <stop offset="50%" stop-color="#69b7ff" stop-opacity="0.55" />
            <stop offset="100%" stop-color="#78d8b7" stop-opacity="0.15" />
          </linearGradient>
        </defs>
        <g class="graph-edges">
          <line x1="180" y1="220" x2="420" y2="160" />
          <line x1="420" y1="160" x2="680" y2="280" />
          <line x1="680" y1="280" x2="920" y2="200" />
          <line x1="680" y1="280" x2="540" y2="480" />
          <line x1="540" y1="480" x2="280" y2="520" />
          <line x1="280" y1="520" x2="180" y2="220" />
          <line x1="920" y1="200" x2="1020" y2="420" />
          <line x1="1020" y1="420" x2="540" y2="480" />
        </g>
        <g class="graph-nodes">
          <circle cx="180" cy="220" r="6" />
          <circle cx="420" cy="160" r="6" />
          <circle cx="680" cy="280" r="7" />
          <circle cx="920" cy="200" r="6" />
          <circle cx="1020" cy="420" r="5" />
          <circle cx="540" cy="480" r="6" />
          <circle cx="280" cy="520" r="5" />
        </g>
      </svg>
      <div class="sweep-light"></div>
    </div>

    <section class="brand-panel">
      <div class="brand-mark">药食同源 · 知识图谱</div>
      <h1>多智能体研发协同平台</h1>
      <p>
        基于 Neo4j 图谱证据链，串联知识问答与研发协同 Agent，让方剂、功效、风味与替代映射在同一工作台内可追溯、可验证。
      </p>
      <div class="feature-tags">
        <span>知识问答</span>
        <span>研发协同</span>
        <span>图谱证据</span>
        <span>多智能体</span>
      </div>
      <div class="signal-grid">
        <div>
          <span>Neo4j</span>
          <strong>图谱检索</strong>
        </div>
        <div>
          <span>MiniMax</span>
          <strong>结构化生成</strong>
        </div>
        <div>
          <span>Agent</span>
          <strong>方剂协同</strong>
        </div>
      </div>
    </section>

    <section class="login-card">
      <div class="card-glow"></div>
      <div class="card-header">
        <div>
          <span class="eyebrow">安全登录</span>
          <h2>登录系统</h2>
        </div>
        <el-icon class="header-icon"><Lock /></el-icon>
      </div>

      <el-form :model="form" label-position="top" @submit.prevent>
        <el-form-item label="账号">
          <el-input
            v-model="form.username"
            size="large"
            placeholder="请输入账号"
            :prefix-icon="User"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            size="large"
            placeholder="请输入密码"
            type="password"
            show-password
            :prefix-icon="Key"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          class="login-button"
          :loading="auth.loading"
          :disabled="!form.username.trim() || !form.password"
          @click="submit"
        >
          <el-icon><ArrowRight /></el-icon>
          进入工作台
        </el-button>
      </el-form>

      <div class="login-footnote">
        默认本地管理员由后端 <span>.env</span> 配置。
      </div>
    </section>
  </div>
</template>

<script setup>
import { reactive } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { ArrowRight, Key, Lock, User } from "@element-plus/icons-vue";

import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

const form = reactive({
  username: "admin",
  password: "",
});

const submit = async () => {
  if (!form.username.trim() || !form.password) return;
  try {
    await auth.login(form.username.trim(), form.password);
    ElMessage.success("登录成功");
    await router.replace(route.query.redirect || { name: "home" });
  } catch (error) {
    const detail =
      error?.response?.data?.detail || "登录失败，请检查账号和密码。";
    ElMessage.error(detail);
  }
};
</script>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  width: 100vw;
  overflow: hidden;
  display: grid;
  grid-template-columns: minmax(420px, 1fr) 420px;
  align-items: center;
  gap: 56px;
  padding: 48px clamp(28px, 7vw, 96px);
  box-sizing: border-box;
  color: #f8fafc;
  background: #122033;
}

.bg-video,
.bg-fallback {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.bg-video {
  z-index: 0;
  opacity: 0.72;
}

.bg-fallback {
  z-index: 1;
  background:
    linear-gradient(90deg, rgba(13, 30, 48, 0.94), rgba(17, 45, 58, 0.72) 48%, rgba(12, 20, 35, 0.92)),
    radial-gradient(circle at 20% 20%, rgba(64, 158, 255, 0.18), transparent 34%),
    radial-gradient(circle at 76% 64%, rgba(103, 194, 58, 0.14), transparent 32%);
}

.login-overlay {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  overflow: hidden;
}

.grid-scan {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(105, 183, 255, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(105, 183, 255, 0.06) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: linear-gradient(90deg, rgba(0, 0, 0, 0.9), transparent 70%);
}

.graph-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0.55;
}

.graph-edges line {
  stroke: url(#edgeGrad);
  stroke-width: 1.5;
  stroke-dasharray: 8 10;
  animation: edge-flow 4s linear infinite;
}

.graph-nodes circle {
  fill: #78d8b7;
  filter: drop-shadow(0 0 6px rgba(120, 216, 183, 0.6));
  animation: node-pulse 3s ease-in-out infinite;
}

.graph-nodes circle:nth-child(3) {
  fill: #69b7ff;
  animation-delay: 0.6s;
}

.graph-nodes circle:nth-child(5) {
  animation-delay: 1.2s;
}

.sweep-light {
  position: absolute;
  top: 0;
  left: -30%;
  width: 40%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(105, 183, 255, 0.08),
    transparent
  );
  animation: sweep 8s ease-in-out infinite;
}

.brand-panel,
.login-card {
  position: relative;
  z-index: 2;
}

.brand-panel {
  max-width: 680px;
  animation: fade-up 0.7s ease-out both;
}

.login-card {
  animation: fade-up 0.7s ease-out 0.15s both;
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  height: 32px;
  padding: 0 14px;
  border: 1px solid rgba(120, 216, 183, 0.45);
  border-radius: 4px;
  background: rgba(120, 216, 183, 0.1);
  font-size: 13px;
  font-weight: 600;
  color: #c9f7df;
  margin-bottom: 22px;
  letter-spacing: 0.02em;
}

.brand-panel h1 {
  font-size: clamp(32px, 4vw, 46px);
  line-height: 1.12;
  margin: 0 0 18px;
  font-weight: 700;
}

.brand-panel p {
  max-width: 560px;
  margin: 0;
  color: rgba(241, 245, 249, 0.78);
  font-size: 17px;
  line-height: 1.8;
}

.feature-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 22px;
}

.feature-tags span {
  padding: 6px 12px;
  font-size: 12px;
  border-radius: 4px;
  border: 1px solid rgba(64, 158, 255, 0.35);
  background: rgba(64, 158, 255, 0.12);
  color: #d4e8ff;
}

.signal-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 32px;
  max-width: 620px;
}

.signal-grid div {
  border-left: 2px solid rgba(64, 158, 255, 0.78);
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(12px);
  border-radius: 0 4px 4px 0;
  transition: background 0.25s ease, transform 0.25s ease;
}

.signal-grid div:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: translateY(-2px);
}

.signal-grid span {
  display: block;
  color: rgba(203, 213, 225, 0.78);
  font-size: 12px;
  margin-bottom: 6px;
}

.signal-grid strong {
  display: block;
  font-size: 15px;
  color: #ffffff;
}

.login-card {
  width: 420px;
  padding: 32px 30px 28px;
  box-sizing: border-box;
  background: rgba(255, 255, 255, 0.88);
  color: #303133;
  border: 1px solid rgba(255, 255, 255, 0.65);
  border-radius: 10px;
  box-shadow:
    0 24px 60px rgba(0, 0, 0, 0.28),
    inset 0 1px 0 rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(20px);
  overflow: hidden;
}

.card-glow {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #67c23a, #409eff, #78d8b7);
  opacity: 0.9;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 24px;
}

.eyebrow {
  font-size: 12px;
  color: #409eff;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.card-header h2 {
  font-size: 24px;
  margin: 6px 0 0;
  color: #1f2937;
}

.header-icon {
  font-size: 26px;
  color: #67c23a;
  margin-top: 4px;
}

.login-card :deep(.el-input__wrapper) {
  transition: box-shadow 0.2s ease;
}

.login-card :deep(.el-input__wrapper:hover),
.login-card :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.35) inset;
}

.login-button {
  width: 100%;
  margin-top: 8px;
  border-radius: 6px;
  font-weight: 600;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.login-button:not(:disabled):hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 20px rgba(64, 158, 255, 0.35);
}

.login-footnote {
  margin-top: 18px;
  font-size: 12px;
  color: #909399;
  text-align: center;
}

.login-footnote span {
  color: #606266;
  font-weight: 600;
}

@keyframes fade-up {
  from {
    opacity: 0;
    transform: translateY(18px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes edge-flow {
  to {
    stroke-dashoffset: -36;
  }
}

@keyframes node-pulse {
  0%,
  100% {
    opacity: 0.65;
    r: 5;
  }
  50% {
    opacity: 1;
    r: 7;
  }
}

@keyframes sweep {
  0%,
  100% {
    transform: translateX(0);
    opacity: 0.4;
  }
  50% {
    transform: translateX(220%);
    opacity: 0.85;
  }
}

@media (max-width: 900px) {
  .login-page {
    grid-template-columns: 1fr;
    justify-items: center;
    gap: 28px;
    padding: 28px 20px;
  }

  .brand-panel {
    width: 100%;
    max-width: 520px;
  }

  .brand-panel h1 {
    font-size: 32px;
  }

  .brand-panel p {
    font-size: 15px;
  }

  .signal-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .login-card {
    width: 100%;
    max-width: 420px;
  }

  .bg-video {
    opacity: 0.45;
  }
}

@media (prefers-reduced-motion: reduce) {
  .brand-panel,
  .login-card,
  .graph-edges line,
  .graph-nodes circle,
  .sweep-light {
    animation: none;
  }

  .signal-grid div:hover {
    transform: none;
  }

  .login-button:not(:disabled):hover {
    transform: none;
  }
}
</style>
