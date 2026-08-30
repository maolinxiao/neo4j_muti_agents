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
                  :class="{ 'is-loading': captchaLoading }"
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
// 仅用于验证码刷新过程中的视觉加载态，不改动任何交互逻辑
const captchaLoading = ref(false);

const loadCaptcha = async () => {
  captchaLoading.value = true;
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
  } finally {
    captchaLoading.value = false;
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
  animation: fade-in-up 0.7s cubic-bezier(0.16, 1, 0.3, 1) 0.05s both;
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 7px 16px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.45);
  border: 1px solid rgba(56, 189, 248, 0.35);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.08) inset,
    0 0 24px -6px rgba(56, 189, 248, 0.4);
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: #e0f2fe;
  margin-bottom: 28px;
}

.mark-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: radial-gradient(circle at 30% 30%, #a7f3d0, #34d399 55%, #38bdf8);
  animation: dot-pulse 2.4s ease-in-out infinite;
}

.brand-panel h1 {
  font-size: 48px;
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.02em;
  margin: 0 0 24px;
  background: linear-gradient(90deg, #34d399 0%, #38bdf8 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}

.subtitle {
  font-size: 18px;
  line-height: 1.6;
  color: #cbd5e1;
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
  gap: 14px;
  font-size: 16px;
  color: #cbd5e1;
}

.feature-item .el-icon {
  font-size: 20px;
  color: #67e8f9;
  background: linear-gradient(135deg, rgba(52, 211, 153, 0.16), rgba(56, 189, 248, 0.16));
  border: 1px solid rgba(56, 189, 248, 0.25);
  padding: 9px;
  border-radius: 10px;
  box-shadow: 0 4px 12px -4px rgba(56, 189, 248, 0.3);
}

.login-panel {
  display: flex;
  justify-content: flex-end;
  animation: fade-in-up 0.7s cubic-bezier(0.16, 1, 0.3, 1) 0.22s both;
}

.login-card {
  position: relative;
  width: 100%;
  max-width: 440px;
  background: rgba(15, 23, 42, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 20px;
  padding: 48px 40px;
  box-shadow:
    0 1px 0 0 rgba(255, 255, 255, 0.12) inset,
    0 25px 50px -12px rgba(0, 0, 0, 0.55),
    0 12px 32px -8px rgba(2, 6, 23, 0.6);
  color: #e2e8f0;
}

/* 支持 backdrop-filter 时使用玻璃拟态；不支持则回退到上方更不透明的深色面板 */
@supports ((backdrop-filter: blur(18px) saturate(140%)) or (-webkit-backdrop-filter: blur(18px) saturate(140%))) {
  .login-card {
    background: rgba(15, 23, 42, 0.55);
    -webkit-backdrop-filter: blur(18px) saturate(140%);
    backdrop-filter: blur(18px) saturate(140%);
  }
}

/* 顶部高光渐变边 */
.login-card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 12%;
  right: 12%;
  height: 1px;
  pointer-events: none;
  background: linear-gradient(90deg, transparent, rgba(103, 232, 249, 0.7), rgba(52, 211, 153, 0.7), transparent);
}

.card-header {
  margin-bottom: 32px;
}

.card-header h2 {
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 8px;
  color: #f8fafc;
  letter-spacing: -0.01em;
}

.card-header p {
  margin: 0;
  font-size: 15px;
  color: #cbd5e1;
}

.login-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: #cbd5e1;
  padding-bottom: 6px;
}

.login-form :deep(.el-input__wrapper) {
  background-color: rgba(255, 255, 255, 0.06);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.12) inset;
  border-radius: 10px;
  transition: box-shadow 0.25s ease, background-color 0.25s ease;
}

.login-form :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.22) inset;
}

.login-form :deep(.el-input__wrapper.is-focus) {
  background-color: rgba(255, 255, 255, 0.09);
  box-shadow:
    0 0 0 1px rgba(56, 189, 248, 0.55) inset,
    0 0 0 4px rgba(56, 189, 248, 0.14),
    0 0 24px -6px rgba(56, 189, 248, 0.35);
}

.login-form :deep(.el-input__inner) {
  color: #e2e8f0;
}

.login-form :deep(.el-input__inner::placeholder) {
  color: #64748b;
}

.login-form :deep(.el-input__prefix),
.login-form :deep(.el-input__suffix) {
  color: #7dd3fc;
}

/* 避免浏览器自动填充在深色玻璃输入框中刷成浅色 */
.login-form :deep(.el-input__inner:-webkit-autofill) {
  -webkit-text-fill-color: #e2e8f0;
  -webkit-box-shadow: 0 0 0 1000px rgba(30, 41, 59, 0.9) inset;
  caret-color: #e2e8f0;
  transition: background-color 9999s ease-in-out 0s;
}

.login-button {
  width: 100%;
  margin-top: 16px;
  height: 48px;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.25s ease;
  border: none;
  color: #082f49;
  background: linear-gradient(90deg, #34d399 0%, #22d3ee 50%, #38bdf8 100%);
  background-size: 160% 100%;
  background-position: 0% 50%;
  box-shadow:
    0 8px 24px -8px rgba(52, 211, 153, 0.35),
    0 4px 12px -4px rgba(56, 189, 248, 0.3);
}

.login-button:not(:disabled):not(.is-loading):hover {
  background-position: 100% 50%;
  transform: translateY(-2px);
  box-shadow:
    0 16px 32px -8px rgba(56, 189, 248, 0.45),
    0 8px 20px -6px rgba(52, 211, 153, 0.4);
}

.login-button:not(:disabled):not(.is-loading):active {
  transform: translateY(0);
}

.login-button.is-disabled,
.login-button:disabled {
  background: rgba(148, 163, 184, 0.22);
  color: rgba(226, 232, 240, 0.55);
  box-shadow: none;
  cursor: not-allowed;
}

.login-button:focus-visible {
  outline: 2px solid rgba(56, 189, 248, 0.8);
  outline-offset: 3px;
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
  color: #94a3b8;
  line-height: 1.5;
  background: rgba(255, 255, 255, 0.05);
  padding: 12px 16px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.login-footnote .el-icon {
  font-size: 16px;
  color: #7dd3fc;
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
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.06);
  cursor: pointer;
  object-fit: cover;
  flex-shrink: 0;
  transition: transform 0.3s ease, opacity 0.2s ease, filter 0.2s ease, border-color 0.2s ease;
}

.captcha-img:hover {
  opacity: 0.85;
  filter: brightness(1.12);
  border-color: rgba(56, 189, 248, 0.5);
  transform: rotate(-2deg) scale(1.04);
}

.captcha-img:active {
  transform: rotate(-6deg) scale(0.97);
  filter: brightness(0.8);
}

.captcha-img.is-loading {
  opacity: 0.55;
  filter: brightness(0.7);
  cursor: wait;
  pointer-events: none;
  animation: captcha-pulse 1s ease-in-out infinite;
}

.captcha-img:focus-visible {
  outline: 2px solid rgba(56, 189, 248, 0.75);
  outline-offset: 2px;
}

.login-register-link {
  margin-top: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 14px;
  color: #94a3b8;
}

.register-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 18px;
  border-radius: 999px;
  border: 1px solid rgba(56, 189, 248, 0.45);
  background: rgba(56, 189, 248, 0.08);
  color: #7dd3fc;
  font-weight: 500;
  text-decoration: none;
  transition: all 0.25s ease;
}

.register-link:hover {
  color: #082f49;
  background: linear-gradient(90deg, #34d399, #38bdf8);
  border-color: transparent;
  box-shadow: 0 8px 20px -6px rgba(56, 189, 248, 0.5);
  transform: translateY(-1px);
}

.register-link:focus-visible {
  outline: 2px solid rgba(56, 189, 248, 0.75);
  outline-offset: 2px;
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

@keyframes dot-pulse {
  0%,
  100% {
    box-shadow: 0 0 10px 2px rgba(52, 211, 153, 0.7), 0 0 20px 4px rgba(56, 189, 248, 0.35);
  }
  50% {
    box-shadow: 0 0 14px 4px rgba(52, 211, 153, 0.95), 0 0 28px 8px rgba(56, 189, 248, 0.55);
  }
}

@keyframes captcha-pulse {
  0%,
  100% {
    opacity: 0.35;
  }
  50% {
    opacity: 0.65;
  }
}

@media (prefers-reduced-motion: reduce) {
  .brand-panel,
  .login-panel,
  .mark-dot,
  .captcha-img.is-loading {
    animation: none;
  }
}

@media (max-width: 1024px) {
  .login-page {
    align-items: flex-start;
    overflow-y: auto;
    padding: 48px 0;
  }

  .bg-video,
  .bg-overlay {
    position: fixed;
  }

  .content-wrapper {
    grid-template-columns: 1fr;
    gap: 40px;
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
    font-size: 32px;
  }

  .subtitle {
    font-size: 16px;
  }

  .content-wrapper {
    gap: 32px;
  }

  .login-card {
    padding: 32px 22px;
    border-radius: 16px;
  }
}
</style>
