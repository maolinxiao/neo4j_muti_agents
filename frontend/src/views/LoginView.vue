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
    <div class="bg-overlay"></div>

    <div class="content-wrapper">
      <section class="brand-panel">
        <div class="brand-mark">
          <div class="mark-dot"></div>
          药食同源图谱
        </div>
        <h1>多智能体研发协同平台</h1>
        <p class="subtitle">
          基于 Neo4j 图谱证据链，串联知识问答与研发协同 Agent，让方剂、功效、风味与替代映射在同一工作台内可追溯、可验证。
        </p>

        <div class="feature-list">
          <div class="feature-item">
            <el-icon><Monitor /></el-icon>
            <span>工作台级图谱问答与交互</span>
          </div>
          <div class="feature-item">
            <el-icon><Connection /></el-icon>
            <span>多 Agent 组方与风味推演</span>
          </div>
          <div class="feature-item">
            <el-icon><Cpu /></el-icon>
            <span>循证驱动的替代映射引擎</span>
          </div>
        </div>
      </section>

      <section class="login-panel">
        <div class="login-card">
          <div class="card-header">
            <h2>登录工作台</h2>
            <p>请输入您的系统账号</p>
          </div>

          <el-form :model="form" label-position="top" class="login-form" @submit.prevent>
            <el-form-item label="账号">
              <el-input
                v-model="form.username"
                size="large"
                placeholder="admin"
                :prefix-icon="User"
              />
            </el-form-item>
            <el-form-item label="密码">
              <el-input
                v-model="form.password"
                size="large"
                placeholder="••••••••"
                type="password"
                show-password
                :prefix-icon="Key"
                @keyup.enter="submit"
              />
            </el-form-item>
            <el-form-item v-if="captchaEnabled" label="验证码">
              <div class="captcha-row">
                <el-input
                  v-model="form.captchaText"
                  size="large"
                  placeholder="请输入验证码"
                  @keyup.enter="submit"
                />
                <img
                  v-if="captcha.image"
                  :src="`data:${captcha.mime};base64,${captcha.image}`"
                  class="captcha-img"
                  alt="验证码"
                  title="点击刷新验证码"
                  @click="loadCaptcha"
                />
              </div>
            </el-form-item>
            <el-button
              type="primary"
              size="large"
              class="login-button"
              :loading="auth.loading"
              :disabled="!form.username.trim() || !form.password || (captchaEnabled && !form.captchaText.trim())"
              @click="submit"
            >
              进入工作台
              <el-icon class="btn-icon"><ArrowRight /></el-icon>
            </el-button>
          </el-form>

          <div class="login-footnote">
            <el-icon><InfoFilled /></el-icon>
            <span>默认本地管理员账号由后端配置指定。</span>
          </div>

          <div class="login-register-link">
            <span>还没有账号？</span>
            <router-link to="/register" class="register-link">注册账号</router-link>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { ArrowRight, Key, User, Monitor, Connection, Cpu, InfoFilled } from "@element-plus/icons-vue";

import { api } from "../api/client";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

const form = reactive({
  username: "admin",
  password: "",
  captchaText: "",
});

const captcha = reactive({ id: "", image: "", mime: "image/png" });
const captchaEnabled = ref(false);

const loadCaptcha = async () => {
  try {
    const { data } = await api.getCaptcha();
    // 同时原子更新 captcha_id 与图片，并清空输入框（点击刷新 / 失败自动刷新共用）
    captcha.id = data.captcha_id || "";
    captcha.image = data.image_base64 || "";
    captcha.mime = data.mime || "image/png";
    captchaEnabled.value = true;
    form.captchaText = "";
  } catch {
    // 验证码功能未启用时，不展示验证码输入
    captchaEnabled.value = false;
    captcha.id = "";
    captcha.image = "";
  }
};

const submit = async () => {
  if (!form.username.trim() || !form.password) return;
  if (captchaEnabled.value && (!form.captchaText.trim() || !captcha.id)) return;
  try {
    await auth.login(form.username.trim(), form.password, {
      captcha_id: captcha.id || "n/a",
      captcha_text: form.captchaText.trim() || "n/a",
    });
    ElMessage.success("登录成功");
    await router.replace(route.query.redirect || { name: "app-home" });
  } catch (error) {
    const status = error?.response?.status;
    const detail = error?.response?.data?.detail || "";
    if (detail && detail.includes("未启用")) {
      ElMessage.error("账号未启用，请等待管理员审核");
    } else if (detail) {
      // 验证码类 400：后端已返回可区分原因（过期/已使用/次数过多/输入错误等），提示并自动刷新验证码
      ElMessage.error(detail.includes("验证码") ? `${detail}，验证码已自动刷新` : detail);
    } else {
      ElMessage.error(status === 401 ? "用户名或密码错误。" : "登录失败，请检查账号和密码。");
    }
    // 登录失败后刷新验证码，避免复用旧验证码
    if (captchaEnabled.value) {
      form.captchaText = "";
      await loadCaptcha();
    }
  }
};

onMounted(loadCaptcha);
</script>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  width: 100vw;
  overflow: hidden;
  background: #0f172a;
  color: #f8fafc;
  display: flex;
  align-items: center;
  justify-content: center;
}

.bg-video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  z-index: 0;
  opacity: 0.4;
  mix-blend-mode: luminosity;
}

.bg-overlay {
  position: absolute;
  inset: 0;
  z-index: 1;
  background: radial-gradient(circle at 0% 0%, rgba(15, 23, 42, 0.4) 0%, rgba(15, 23, 42, 0.95) 100%);
}

.content-wrapper {
  position: relative;
  z-index: 2;
  width: 100%;
  max-width: 1200px;
  padding: 0 40px;
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 80px;
  align-items: center;
}

.brand-panel {
  animation: fade-in-up 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 14px;
  font-weight: 500;
  color: #e2e8f0;
  margin-bottom: 24px;
}

.mark-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #3b82f6;
  box-shadow: 0 0 8px #3b82f6;
}

.brand-panel h1 {
  font-size: 48px;
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.02em;
  margin: 0 0 24px;
  color: #ffffff;
}

.subtitle {
  font-size: 18px;
  line-height: 1.6;
  color: #94a3b8;
  max-width: 520px;
  margin: 0 0 40px;
}

.feature-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 16px;
  color: #cbd5e1;
}

.feature-item .el-icon {
  font-size: 20px;
  color: #3b82f6;
  background: rgba(59, 130, 246, 0.15);
  padding: 8px;
  border-radius: 8px;
}

.login-panel {
  display: flex;
  justify-content: flex-end;
  animation: fade-in-up 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.15s forwards;
}

.login-card {
  width: 100%;
  max-width: 440px;
  background: #ffffff;
  border-radius: 16px;
  padding: 48px 40px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.4);
  color: #0f172a;
}

.card-header {
  margin-bottom: 32px;
}

.card-header h2 {
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 8px;
  color: #0f172a;
  letter-spacing: -0.01em;
}

.card-header p {
  margin: 0;
  font-size: 15px;
  color: #64748b;
}

.login-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: #334155;
  padding-bottom: 6px;
}

.login-form :deep(.el-input__wrapper) {
  background-color: #f8fafc;
  box-shadow: 0 0 0 1px #e2e8f0 inset;
  border-radius: 8px;
  transition: all 0.2s;
}

.login-form :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #cbd5e1 inset;
}

.login-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 2px #3b82f6 inset;
  background-color: #ffffff;
}

.login-button {
  width: 100%;
  margin-top: 16px;
  height: 48px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s ease;
  background-color: #3b82f6;
  border: none;
}

.login-button:not(:disabled):hover {
  background-color: #2563eb;
  transform: translateY(-1px);
  box-shadow: 0 8px 16px -4px rgba(59, 130, 246, 0.4);
}

.btn-icon {
  font-size: 16px;
  transition: transform 0.2s;
}

.login-button:not(:disabled):hover .btn-icon {
  transform: translateX(4px);
}

.login-footnote {
  margin-top: 24px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
  background: #f8fafc;
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.login-footnote .el-icon {
  font-size: 16px;
  color: #94a3b8;
  margin-top: 1px;
}

.captcha-row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.captcha-row .el-input {
  flex: 1;
}

.captcha-img {
  width: 120px;
  height: 40px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  cursor: pointer;
  object-fit: cover;
  flex-shrink: 0;
  transition: opacity 0.2s;
}

.captcha-img:hover {
  opacity: 0.8;
}

.login-register-link {
  margin-top: 16px;
  text-align: center;
  font-size: 14px;
  color: #64748b;
}

.register-link {
  color: #3b82f6;
  font-weight: 500;
  text-decoration: none;
}

.register-link:hover {
  color: #2563eb;
  text-decoration: underline;
}

@keyframes fade-in-up {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 1024px) {
  .content-wrapper {
    grid-template-columns: 1fr;
    gap: 48px;
    padding: 0 24px;
  }

  .brand-panel {
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .subtitle {
    margin: 0 auto 32px;
  }

  .feature-list {
    align-items: flex-start;
    text-align: left;
    display: inline-flex;
  }

  .login-panel {
    justify-content: center;
  }
}

@media (max-width: 640px) {
  .brand-panel h1 {
    font-size: 36px;
  }

  .login-card {
    padding: 32px 24px;
  }
}
</style>
