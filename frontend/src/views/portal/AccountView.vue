<template>
  <div class="app-container account-page">
    <el-card shadow="never" class="account-card">
      <div class="account-header">
        <div class="account-user">
          <el-avatar :size="56" :src="avatarSrc" class="account-avatar">
            {{ (auth.user?.display_name || auth.user?.username || "U").slice(0, 1).toUpperCase() }}
          </el-avatar>
          <div>
            <div class="account-name">{{ auth.user?.display_name || auth.user?.username }}</div>
            <div class="account-sub">{{ auth.user?.username }} · {{ roleLabel }}</div>
          </div>
        </div>
      </div>

      <el-tabs v-model="activeTab" class="account-tabs">
        <!-- 基本资料 -->
        <el-tab-pane :label="t('account.profile')" name="profile">
          <div class="profile-grid">
            <div class="avatar-zone">
              <el-avatar :size="96" :src="avatarSrc" class="avatar-preview">
                {{ (auth.user?.display_name || auth.user?.username || "U").slice(0, 1).toUpperCase() }}
              </el-avatar>
              <el-upload
                :show-file-list="false"
                :before-upload="beforeAvatarUpload"
                :http-request="doUploadAvatar"
                accept="image/png,image/jpeg,image/webp"
              >
                <el-button size="small">{{ t("account.uploadAvatar") }}</el-button>
              </el-upload>
              <div class="avatar-hint">{{ t("account.avatarHint") }}</div>
            </div>
            <el-form label-position="top" class="profile-form">
              <el-form-item :label="t('account.username')">
                <el-input :model-value="auth.user?.username" disabled />
              </el-form-item>
              <el-form-item :label="t('account.nickname')">
                <el-input v-model="profileForm.display_name" maxlength="60" />
              </el-form-item>
              <el-form-item :label="t('account.email')">
                <el-input v-model="profileForm.email" placeholder="name@example.com" />
              </el-form-item>
              <el-form-item :label="t('account.role')">
                <el-tag>{{ roleLabel }}</el-tag>
              </el-form-item>
              <el-button type="primary" :loading="savingProfile" @click="saveProfile">
                {{ t("account.saveProfile") }}
              </el-button>
            </el-form>
          </div>
        </el-tab-pane>

        <!-- 账号安全 -->
        <el-tab-pane :label="t('account.security')" name="security">
          <el-card shadow="never" class="inner-card">
            <template #header>{{ t("account.changePassword") }}</template>
            <el-form label-position="top" class="security-form">
              <el-form-item :label="t('account.oldPassword')">
                <el-input v-model="passwordForm.old_password" type="password" show-password />
              </el-form-item>
              <el-form-item :label="t('account.newPassword')">
                <el-input v-model="passwordForm.new_password" type="password" show-password />
              </el-form-item>
              <el-form-item :label="t('account.confirmNewPassword')">
                <el-input v-model="passwordForm.confirm_password" type="password" show-password />
              </el-form-item>
              <el-form-item v-if="captchaEnabled" :label="t('account.captcha')">
                <div class="captcha-row">
                  <el-input
                    v-model="captchaText"
                    :placeholder="t('account.captchaPlaceholder')"
                    @keyup.enter="changePassword"
                  />
                  <img
                    v-if="captcha.image"
                    :src="`data:${captcha.mime};base64,${captcha.image}`"
                    class="captcha-img"
                    :class="{ 'is-loading': captchaLoading }"
                    :alt="t('account.captcha')"
                    :title="t('account.captchaHint')"
                    @click="loadCaptcha"
                  />
                </div>
              </el-form-item>
              <el-button type="primary" :loading="changingPassword" @click="changePassword">
                {{ t("account.changePassword") }}
              </el-button>
            </el-form>
          </el-card>

          <el-card shadow="never" class="inner-card session-card">
            <template #header>
              <div class="session-header">
                <span>{{ t("account.sessions") }}</span>
                <el-button size="small" text type="danger" :disabled="!sessions.some((s) => !s.is_current)" @click="revokeOthers">
                  {{ t("account.revokeOther") }}
                </el-button>
              </div>
            </template>
            <el-table v-if="sessions.length" :data="sessions" size="small" border>
              <el-table-column :label="t('account.device')" min-width="200" show-overflow-tooltip>
                <template #default="{ row }">
                  <el-tag v-if="row.is_current" size="small" type="success" class="mr-6">{{ t("account.currentDevice") }}</el-tag>
                  <span>{{ deviceLabel(row.user_agent) }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="ip" :label="t('account.ip')" width="140" />
              <el-table-column :label="t('account.loginTime')" width="170">
                <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
              </el-table-column>
              <el-table-column :label="t('account.expiresAt')" width="170">
                <template #default="{ row }">{{ formatTime(row.expires_at) }}</template>
              </el-table-column>
              <el-table-column :label="t('common.actions')" width="90" align="center">
                <template #default="{ row }">
                  <el-button v-if="!row.is_current" size="small" text type="danger" @click="revokeOne(row)">
                    {{ t("account.revoke") }}
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else :description="t('account.noSessions')" :image-size="48" />
          </el-card>
        </el-tab-pane>

        <!-- 使用统计 -->
        <el-tab-pane :label="t('account.stats')" name="stats">
          <div class="stats-grid">
            <div v-for="item in statItems" :key="item.key" class="stat-card">
              <div class="stat-value">{{ item.value }}</div>
              <div class="stat-label">{{ item.label }}</div>
            </div>
          </div>
        </el-tab-pane>

        <!-- 偏好设置 -->
        <el-tab-pane :label="t('account.preferences')" name="preferences">
          <div class="pref-section">
            <div class="pref-section-title">{{ t("account.theme") }}</div>
            <div class="pref-card-grid pref-theme-grid">
              <div
                v-for="item in themeOptions"
                :key="item.value"
                class="pref-card"
                :class="{ 'is-active': theme === item.value }"
                role="button"
                :tabindex="0"
                :aria-label="item.label"
                @click="setTheme(item.value)"
                @keyup.enter="setTheme(item.value)"
              >
                <div class="theme-preview" :class="`theme-preview-${item.value}`" aria-hidden="true">
                  <span class="tp-sidebar"></span>
                  <span class="tp-main">
                    <span class="tp-line tp-line-1"></span>
                    <span class="tp-line tp-line-2"></span>
                    <span class="tp-chip"></span>
                  </span>
                </div>
                <div class="pref-card-body">
                  <div class="pref-card-title">{{ item.label }}</div>
                  <div class="pref-card-desc">{{ item.desc }}</div>
                </div>
                <el-icon v-if="theme === item.value" class="pref-check"><CircleCheckFilled /></el-icon>
              </div>
            </div>
          </div>

          <div class="pref-section">
            <div class="pref-section-title">{{ t("account.language") }}</div>
            <div class="pref-card-grid pref-lang-grid">
              <div
                v-for="item in langOptions"
                :key="item.value"
                class="pref-card pref-lang-card"
                :class="{ 'is-active': locale === item.value }"
                role="button"
                :tabindex="0"
                :aria-label="item.label"
                @click="setLocale(item.value)"
                @keyup.enter="setLocale(item.value)"
              >
                <div class="lang-badge" aria-hidden="true">{{ item.badge }}</div>
                <div class="pref-card-body">
                  <div class="pref-card-title">{{ item.label }}</div>
                  <div class="pref-card-desc">{{ item.desc }}</div>
                </div>
                <el-icon v-if="locale === item.value" class="pref-check"><CircleCheckFilled /></el-icon>
              </div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { CircleCheckFilled } from "@element-plus/icons-vue";

import { api } from "../../api/client";
import { useI18n } from "../../composables/useI18n";
import { useTheme } from "../../composables/useTheme";
import { useAuthStore } from "../../stores/auth";

const { t, locale, setLocale } = useI18n();
const { theme, setTheme } = useTheme();
const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

const VALID_TABS = ["profile", "security", "stats", "preferences"];
const activeTab = ref("profile");
const savingProfile = ref(false);
const changingPassword = ref(false);
const sessions = ref([]);
const stats = ref({});

const profileForm = reactive({ display_name: "", email: "" });
const passwordForm = reactive({ old_password: "", new_password: "", confirm_password: "" });

const captcha = reactive({ id: "", image: "", mime: "image/png" });
const captchaEnabled = ref(false);
const captchaLoading = ref(false);
const captchaText = ref("");

const avatarSrc = computed(() => auth.user?.avatar_url || "");
const roleLabel = computed(() =>
  auth.user?.role === "admin" ? t("admin.users.roleAdmin") : t("admin.users.roleUser"),
);

const themeOptions = computed(() => [
  { value: "light", label: t("account.themeLight"), desc: t("account.themeLightDesc") },
  { value: "dark", label: t("account.themeDark"), desc: t("account.themeDarkDesc") },
  { value: "system", label: t("account.themeSystem"), desc: t("account.themeSystemDesc") },
]);

const langOptions = computed(() => [
  { value: "zh-CN", badge: "中", label: t("account.langZh"), desc: t("account.langZhDesc") },
  { value: "en-US", badge: "EN", label: t("account.langEn"), desc: t("account.langEnDesc") },
]);

const deviceLabel = (ua) => {
  if (!ua) return "-";
  const text = String(ua);
  if (text.includes("Edg/")) return `Edge · ${text.split("Edg/")[1]?.split(" ")[0] || ""}`;
  if (text.includes("Chrome/")) return `Chrome · ${text.split("Chrome/")[1]?.split(" ")[0] || ""}`;
  if (text.includes("Firefox/")) return `Firefox · ${text.split("Firefox/")[1]?.split(" ")[0] || ""}`;
  return text.slice(0, 60);
};

const formatTime = (value) => {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "-";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

const loadSessions = async () => {
  try {
    const { data } = await api.listMySessions();
    sessions.value = data;
  } catch {
    sessions.value = [];
  }
};

const loadStats = async () => {
  try {
    const { data } = await api.getMyStats();
    stats.value = data;
  } catch {
    stats.value = {};
  }
};

const statItems = computed(() => [
  { key: "chat_sessions", label: t("account.statChatSessions"), value: stats.value.chat_sessions ?? 0 },
  { key: "chat_messages", label: t("account.statMessages"), value: stats.value.chat_messages ?? 0 },
  { key: "workflow_sessions", label: t("account.statWorkflowSessions"), value: stats.value.workflow_sessions ?? 0 },
  { key: "workflow_runs", label: t("account.statWorkflowRuns"), value: stats.value.workflow_runs ?? 0 },
  { key: "constitution_assessments", label: t("account.statAssessments"), value: stats.value.constitution_assessments ?? 0 },
]);

const beforeAvatarUpload = (file) => {
  const okType = ["image/png", "image/jpeg", "image/webp"].includes(file.type);
  const okSize = file.size <= 2 * 1024 * 1024;
  if (!okType) ElMessage.error("png/jpg/webp only");
  if (!okSize) ElMessage.error("Max 2MB");
  return okType && okSize;
};

const doUploadAvatar = async ({ file }) => {
  const formData = new FormData();
  formData.append("file", file);
  try {
    const { data } = await api.uploadAvatar(formData);
    auth.user = data;
    localStorage.setItem("ys_auth_user", JSON.stringify(data));
    ElMessage.success(t("common.success"));
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || t("common.failed"));
  }
};

const saveProfile = async () => {
  savingProfile.value = true;
  try {
    const { data } = await api.updateProfile({
      display_name: profileForm.display_name,
      email: profileForm.email || null,
    });
    auth.user = data;
    localStorage.setItem("ys_auth_user", JSON.stringify(data));
    ElMessage.success(t("account.profileSaved"));
  } catch (error) {
    const detail = error?.response?.data?.detail;
    ElMessage.error(detail === "邮箱已被使用" || detail === "Email already in use" ? t("account.emailTaken") : t("common.failed"));
  } finally {
    savingProfile.value = false;
  }
};

const loadCaptcha = async () => {
  captchaLoading.value = true;
  try {
    const { data } = await api.getCaptcha();
    // 原子更新 captcha_id 与图片，并清空输入框（点击刷新 / 失败自动刷新共用）
    captcha.id = data.captcha_id || "";
    captcha.image = data.image_base64 || "";
    captcha.mime = data.mime || "image/png";
    captchaEnabled.value = true;
    captchaText.value = "";
  } catch {
    // 验证码功能未启用时，不展示验证码输入
    captchaEnabled.value = false;
    captcha.id = "";
    captcha.image = "";
  } finally {
    captchaLoading.value = false;
  }
};

const changePassword = async () => {
  if (!passwordForm.old_password || !passwordForm.new_password || !passwordForm.confirm_password) {
    ElMessage.error(t("account.passwordRequired"));
    return;
  }
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    ElMessage.error(t("account.passwordMismatch"));
    return;
  }
  if (captchaEnabled.value && (!captchaText.value.trim() || !captcha.id)) {
    ElMessage.error(t("account.captchaRequired"));
    return;
  }
  changingPassword.value = true;
  try {
    await api.changePassword({
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password,
      captcha_id: captcha.id || "n/a",
      captcha_text: captchaText.value.trim() || "n/a",
    });
    ElMessage.success(t("account.passwordChanged"));
    passwordForm.old_password = "";
    passwordForm.new_password = "";
    passwordForm.confirm_password = "";
    captchaText.value = "";
    // 改密成功：后端已撤销全部会话，本地登出并强制跳转登录页重新登录
    setTimeout(async () => {
      await auth.logout();
      await router.replace({ name: "login" });
    }, 800);
  } catch (error) {
    const detail = error?.response?.data?.detail;
    const detailText = typeof detail === "string" ? detail : "";
    const isCaptchaError = detailText.includes("验证码");
    ElMessage.error(
      isCaptchaError ? `${detailText}，${t("account.captchaAutoRefreshed")}` : detailText || t("common.failed"),
    );
    // 验证码类 400：提示原因后自动刷新验证码并清空输入，避免复用旧验证码
    if (isCaptchaError && captchaEnabled.value) {
      captchaText.value = "";
      await loadCaptcha();
    }
  } finally {
    changingPassword.value = false;
  }
};

const revokeOne = async (row) => {
  try {
    await api.revokeSession(row.id);
    ElMessage.success(t("account.sessionRevoked"));
    await loadSessions();
  } catch {
    ElMessage.error(t("common.failed"));
  }
};

const revokeOthers = async () => {
  try {
    await ElMessageBox.confirm(t("account.revokeOtherConfirm"), t("common.confirm"), { type: "warning" });
  } catch {
    return;
  }
  try {
    await api.revokeOtherSessions();
    ElMessage.success(t("account.sessionRevoked"));
    await loadSessions();
  } catch {
    ElMessage.error(t("common.failed"));
  }
};

// 支持路由 query.tab 指定初始页签（如 /app/account?tab=security）
const applyTabFromQuery = () => {
  const tab = route.query.tab;
  if (typeof tab === "string" && VALID_TABS.includes(tab)) {
    activeTab.value = tab;
  }
};

watch(
  () => route.query.tab,
  () => applyTabFromQuery(),
);

// 进入「账号安全」页签时拉取/刷新图形验证码
watch(activeTab, (value) => {
  if (value === "security") loadCaptcha();
});

onMounted(async () => {
  applyTabFromQuery();
  profileForm.display_name = auth.user?.display_name || "";
  profileForm.email = auth.user?.email || "";
  await Promise.all([loadSessions(), loadStats()]);
});
</script>

<style scoped>
.account-page {
  padding: 20px;
}
.account-card {
  max-width: 860px;
  margin: 0 auto;
}
.account-header {
  margin-bottom: 8px;
}
.account-user {
  display: flex;
  align-items: center;
  gap: 14px;
}
.account-name {
  font-size: 18px;
  font-weight: 600;
  color: var(--app-text);
}
.account-sub {
  font-size: 13px;
  color: var(--app-text-3);
}
.profile-grid {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 28px;
}
.avatar-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}
.avatar-hint {
  font-size: 12px;
  color: var(--app-text-3);
  text-align: center;
  line-height: 1.5;
}
.inner-card {
  margin-bottom: 16px;
  background: var(--app-panel-2);
}
.security-form {
  max-width: 420px;
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
  border: 1px solid var(--app-border);
  background: var(--app-panel-2);
  cursor: pointer;
  object-fit: cover;
  flex-shrink: 0;
  transition: transform 0.25s ease, opacity 0.2s ease, filter 0.2s ease, border-color 0.2s ease;
}

.captcha-img:hover {
  opacity: 0.85;
  border-color: var(--app-active-border);
  transform: scale(1.03);
}

.captcha-img:active {
  transform: scale(0.97);
}

.captcha-img.is-loading {
  opacity: 0.55;
  cursor: wait;
  pointer-events: none;
  animation: captcha-pulse 1s ease-in-out infinite;
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

.pref-section + .pref-section {
  margin-top: 26px;
}

.pref-section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--app-text);
  margin-bottom: 12px;
}

.pref-card-grid {
  display: grid;
  gap: 14px;
}

.pref-theme-grid {
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
}

.pref-lang-grid {
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  max-width: 500px;
}

.pref-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border: 1.5px solid var(--app-border);
  border-radius: 12px;
  background: var(--app-panel-2);
  cursor: pointer;
  user-select: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease, background-color 0.2s ease;
}

.pref-card:hover {
  border-color: var(--app-active-border);
  box-shadow: 0 6px 16px -8px rgba(64, 158, 255, 0.45);
  transform: translateY(-2px);
}

.pref-card:focus-visible {
  outline: 2px solid var(--app-active-border);
  outline-offset: 2px;
}

.pref-card.is-active {
  border-color: var(--app-active-border);
  background: var(--app-active);
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.18), 0 6px 16px -8px rgba(64, 158, 255, 0.4);
}

.pref-card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--app-text);
}

.pref-card-desc {
  font-size: 12px;
  color: var(--app-text-3);
  line-height: 1.5;
}

.pref-check {
  position: absolute;
  top: 10px;
  right: 10px;
  font-size: 18px;
  color: var(--app-active-border);
}

/* 主题卡片迷你预览 */
.theme-preview {
  height: 62px;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.theme-preview .tp-sidebar {
  width: 26%;
}

.theme-preview .tp-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 9px;
}

.tp-line {
  height: 5px;
  border-radius: 3px;
}

.tp-line-1 {
  width: 72%;
}

.tp-line-2 {
  width: 45%;
}

.tp-chip {
  width: 36%;
  height: 13px;
  border-radius: 4px;
  margin-top: auto;
}

.theme-preview-light {
  background: #eef1f6;
}

.theme-preview-light .tp-sidebar {
  background: #ffffff;
  border-right: 1px solid #e4e7ed;
}

.theme-preview-light .tp-line {
  background: #d3d8e0;
}

.theme-preview-light .tp-chip {
  background: #409eff;
}

.theme-preview-dark {
  background: #0f1419;
}

.theme-preview-dark .tp-sidebar {
  background: #1a2129;
  border-right: 1px solid #333a45;
}

.theme-preview-dark .tp-line {
  background: #3a4657;
}

.theme-preview-dark .tp-chip {
  background: #409eff;
}

.theme-preview-system {
  background: linear-gradient(90deg, #eef1f6 50%, #0f1419 50%);
}

.theme-preview-system .tp-sidebar {
  background: linear-gradient(90deg, #ffffff 50%, #1a2129 50%);
  border-right: 1px solid rgba(0, 0, 0, 0.1);
}

.theme-preview-system .tp-line {
  background: linear-gradient(90deg, #d3d8e0 50%, #3a4657 50%);
}

.theme-preview-system .tp-chip {
  background: #409eff;
}

/* 语言卡片徽标 */
.lang-badge {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #409eff 0%, #79bbff 100%);
  letter-spacing: 0.02em;
  flex-shrink: 0;
}

.pref-lang-card {
  flex-direction: row;
  align-items: center;
}

.pref-lang-card .pref-card-body {
  flex: 1;
  min-width: 0;
}
.session-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 14px;
}
.stat-card {
  border: 1px solid var(--app-border);
  border-radius: 10px;
  padding: 18px;
  background: var(--app-panel-2);
}
.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--app-active-border);
}
.stat-label {
  margin-top: 6px;
  font-size: 13px;
  color: var(--app-text-2);
}
.mr-6 {
  margin-right: 6px;
}
@media (max-width: 640px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }
}
</style>
