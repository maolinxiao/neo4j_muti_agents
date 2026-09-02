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
          <el-form label-position="top" class="pref-form">
            <el-form-item :label="t('account.theme')">
              <el-radio-group :model-value="theme.value" @update:model-value="(v) => setTheme(v)">
                <el-radio-button value="light">{{ t("account.themeLight") }}</el-radio-button>
                <el-radio-button value="dark">{{ t("account.themeDark") }}</el-radio-button>
                <el-radio-button value="system">{{ t("account.themeSystem") }}</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item :label="t('account.language')">
              <el-radio-group :model-value="locale.value" @update:model-value="(v) => setLocale(v)">
                <el-radio-button value="zh-CN">{{ t("account.langZh") }}</el-radio-button>
                <el-radio-button value="en-US">{{ t("account.langEn") }}</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { api } from "../../api/client";
import { useI18n } from "../../composables/useI18n";
import { useTheme } from "../../composables/useTheme";
import { useAuthStore } from "../../stores/auth";

const { t, locale, setLocale } = useI18n();
const { theme, setTheme } = useTheme();
const auth = useAuthStore();

const activeTab = ref("profile");
const savingProfile = ref(false);
const changingPassword = ref(false);
const sessions = ref([]);
const stats = ref({});

const profileForm = reactive({ display_name: "", email: "" });
const passwordForm = reactive({ old_password: "", new_password: "", confirm_password: "" });

const avatarSrc = computed(() => auth.user?.avatar_url || "");
const roleLabel = computed(() =>
  auth.user?.role === "admin" ? t("admin.users.roleAdmin") : t("admin.users.roleUser"),
);

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

const changePassword = async () => {
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    ElMessage.error(t("account.passwordMismatch"));
    return;
  }
  changingPassword.value = true;
  try {
    await api.changePassword({
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password,
    });
    ElMessage.success(t("account.passwordChanged"));
    passwordForm.old_password = "";
    passwordForm.new_password = "";
    passwordForm.confirm_password = "";
    setTimeout(() => auth.logout(), 800);
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || t("common.failed"));
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

onMounted(async () => {
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
.security-form,
.pref-form {
  max-width: 420px;
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
