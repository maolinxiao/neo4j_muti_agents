<template>
  <div class="register-page">
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
          {{ t("common.appName") }}
        </div>
        <h1>{{ t("register.title") }}</h1>
        <p class="subtitle">
          {{ t("login.subtitle") }}
        </p>
        <div class="feature-list">
          <div class="feature-item">
            <el-icon><Monitor /></el-icon>
            <span>{{ t("login.feature1") }}</span>
          </div>
          <div class="feature-item">
            <el-icon><Connection /></el-icon>
            <span>{{ t("login.feature2") }}</span>
          </div>
          <div class="feature-item">
            <el-icon><Cpu /></el-icon>
            <span>{{ t("login.feature3") }}</span>
          </div>
        </div>
      </section>

      <section class="register-panel">
        <div class="register-card">
          <div class="card-header">
            <h2>{{ t("register.title") }}</h2>
            <p>{{ t("login.loginCardSub") }}</p>
          </div>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-position="top"
            class="register-form"
            @submit.prevent
          >
            <el-form-item :label="t('register.username')" prop="username">
              <el-input
                v-model="form.username"
                size="large"
                :placeholder="t('register.usernamePlaceholder')"
                :prefix-icon="User"
              />
            </el-form-item>
            <el-form-item :label="t('register.password')" prop="password">
              <el-input
                v-model="form.password"
                size="large"
                :placeholder="t('register.passwordPlaceholder')"
                type="password"
                show-password
                :prefix-icon="Key"
              />
            </el-form-item>
            <el-form-item :label="t('register.confirmPassword')" prop="confirmPassword">
              <el-input
                v-model="form.confirmPassword"
                size="large"
                :placeholder="t('register.confirmPlaceholder')"
                type="password"
                show-password
                :prefix-icon="Key"
              />
            </el-form-item>
            <el-form-item :label="t('register.email')" prop="email">
              <el-input
                v-model="form.email"
                size="large"
                :placeholder="t('register.emailPlaceholder')"
                :prefix-icon="Message"
              />
            </el-form-item>
            <el-form-item v-if="captchaEnabled" :label="t('register.captcha')" prop="captchaText">
              <div class="captcha-row">
                <el-input
                  v-model="form.captchaText"
                  size="large"
                  :placeholder="t('login.captchaPlaceholder')"
                  @keyup.enter="submit"
                />
                <img
                  v-if="captcha.image"
                  :src="`data:${captcha.mime};base64,${captcha.image}`"
                  class="captcha-img"
                  alt="captcha"
                  :title="t('login.captcha')"
                  @click="loadCaptcha"
                />
              </div>
            </el-form-item>
            <el-button
              type="primary"
              size="large"
              class="register-button"
              :loading="submitting"
              :disabled="!form.username.trim() || !form.password || !form.confirmPassword || (captchaEnabled && !form.captchaText.trim())"
              @click="submit"
            >
              {{ t("register.submit") }}
              <el-icon class="btn-icon"><ArrowRight /></el-icon>
            </el-button>
          </el-form>

          <div class="register-footnote">
            <el-icon><InfoFilled /></el-icon>
            <span>{{ t("register.success") }}</span>
          </div>

          <div class="register-login-link">
            <span>{{ t("login.noAccount") }}</span>
            <router-link to="/login" class="login-link">{{ t("register.backToLogin") }}</router-link>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { ArrowRight, Key, User, Message, Monitor, Connection, Cpu, InfoFilled } from "@element-plus/icons-vue";

import { api } from "../api/client";
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();
const router = useRouter();

const PASSWORD_STRENGTH_RE = /^(?=.*[A-Za-z])(?=.*\d).{8,}$/;
const EMAIL_RE = /^[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}$/;

const formRef = ref(null);
const submitting = ref(false);

const form = reactive({
  username: "",
  password: "",
  confirmPassword: "",
  email: "",
  captchaText: "",
});

const rules = {
  username: [
    { required: true, message: "请输入用户名", trigger: "blur" },
    { min: 2, max: 64, message: "用户名长度需在 2-64 位之间", trigger: "blur" },
  ],
  password: [
    { required: true, message: "请输入密码", trigger: "blur" },
    {
      validator: (_rule, value, callback) => {
        if (!PASSWORD_STRENGTH_RE.test(value || "")) {
          callback(new Error("密码至少 8 位，且须同时包含字母和数字"));
        } else {
          callback();
        }
      },
      trigger: "blur",
    },
  ],
  confirmPassword: [
    { required: true, message: "请再次输入密码", trigger: "blur" },
    {
      validator: (_rule, value, callback) => {
        if (!value) {
          callback(new Error("请再次输入密码"));
        } else if (value !== form.password) {
          callback(new Error("两次输入的密码不一致"));
        } else {
          callback();
        }
      },
      trigger: "blur",
    },
  ],
  email: [
    {
      validator: (_rule, value, callback) => {
        if (!value) {
          callback();
        } else if (!EMAIL_RE.test(value.trim())) {
          callback(new Error("邮箱格式不正确"));
        } else {
          callback();
        }
      },
      trigger: "blur",
    },
  ],
  captchaText: [
    {
      validator: (_rule, value, callback) => {
        if (captchaEnabled.value && !value.trim()) {
          callback(new Error("请输入验证码"));
        } else {
          callback();
        }
      },
      trigger: "blur",
    },
  ],
};

const captcha = reactive({ id: "", image: "", mime: "image/png" });
const captchaEnabled = ref(false);

const loadCaptcha = async () => {
  try {
    const { data } = await api.getCaptcha();
    captcha.id = data.captcha_id || "";
    captcha.image = data.image_base64 || "";
    captcha.mime = data.mime || "image/png";
    captchaEnabled.value = true;
  } catch {
    captchaEnabled.value = false;
    captcha.id = "";
    captcha.image = "";
  }
};

const submit = async () => {
  if (!form.username.trim() || !form.password || !form.confirmPassword) return;
  if (captchaEnabled.value && (!form.captchaText.trim() || !captcha.id)) return;
  try {
    await formRef.value.validate();
  } catch {
    return;
  }
  submitting.value = true;
  try {
    await api.register({
      username: form.username.trim(),
      password: form.password,
      email: form.email.trim() || null,
      captcha_id: captcha.id || "n/a",
      captcha_text: form.captchaText.trim() || "n/a",
    });
    ElMessage.success("注册成功，请等待管理员审核");
    await router.replace({ name: "login" });
  } catch (error) {
    const detail = error?.response?.data?.detail || "注册失败，请稍后重试。";
    ElMessage.error(typeof detail === "string" ? detail : "注册失败，请稍后重试。");
    if (captchaEnabled.value) {
      form.captchaText = "";
      await loadCaptcha();
    }
  } finally {
    submitting.value = false;
  }
};

onMounted(loadCaptcha);
</script>

<style scoped>
.register-page {
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
  padding: 40px;
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

.register-panel {
  display: flex;
  justify-content: flex-end;
  animation: fade-in-up 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.15s forwards;
}

.register-card {
  width: 100%;
  max-width: 440px;
  background: #ffffff;
  border-radius: 16px;
  padding: 40px 40px 32px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.4);
  color: #0f172a;
  max-height: calc(100vh - 60px);
  overflow-y: auto;
}

.card-header {
  margin-bottom: 24px;
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

.register-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: #334155;
  padding-bottom: 6px;
}

.register-form :deep(.el-input__wrapper) {
  background-color: #f8fafc;
  box-shadow: 0 0 0 1px #e2e8f0 inset;
  border-radius: 8px;
  transition: all 0.2s;
}

.register-form :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #cbd5e1 inset;
}

.register-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 2px #3b82f6 inset;
  background-color: #ffffff;
}

.register-button {
  width: 100%;
  margin-top: 12px;
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

.register-button:not(:disabled):hover {
  background-color: #2563eb;
  transform: translateY(-1px);
  box-shadow: 0 8px 16px -4px rgba(59, 130, 246, 0.4);
}

.btn-icon {
  font-size: 16px;
  transition: transform 0.2s;
}

.register-button:not(:disabled):hover .btn-icon {
  transform: translateX(4px);
}

.register-footnote {
  margin-top: 20px;
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

.register-footnote .el-icon {
  font-size: 16px;
  color: #94a3b8;
  margin-top: 1px;
}

.register-login-link {
  margin-top: 16px;
  text-align: center;
  font-size: 14px;
  color: #64748b;
}

.login-link {
  color: #3b82f6;
  font-weight: 500;
  text-decoration: none;
}

.login-link:hover {
  color: #2563eb;
  text-decoration: underline;
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
    gap: 32px;
    padding: 24px;
  }

  .brand-panel {
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .subtitle {
    margin: 0 auto 24px;
  }

  .feature-list {
    align-items: flex-start;
    text-align: left;
    display: inline-flex;
  }

  .register-panel {
    justify-content: center;
  }
}

@media (max-width: 640px) {
  .brand-panel h1 {
    font-size: 32px;
  }

  .register-card {
    padding: 28px 20px;
  }
}
</style>
