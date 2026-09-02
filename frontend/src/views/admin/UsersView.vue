<template>
  <div class="app-container">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>{{ t("admin.users.title") }}</span>
          <el-button type="primary" :icon="Plus" @click="openCreateDialog">{{ t("admin.users.addUser") }}</el-button>
        </div>
      </template>

      <div class="toolbar">
        <el-input
          v-model="filters.query"
          :placeholder="t('admin.users.searchPlaceholder')"
          clearable
          style="width: 260px;"
          @keyup.enter="handleSearch"
        />
        <el-select v-model="filters.role" :placeholder="t('admin.users.rolePlaceholder')" clearable style="width: 160px;">
          <el-option :label="t('admin.users.roleAdmin')" value="admin" />
          <el-option :label="t('admin.users.roleUser')" value="user" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="handleSearch">{{ t("admin.users.searchBtn") }}</el-button>
        <el-button :icon="Refresh" @click="handleReset">{{ t("admin.users.resetBtn") }}</el-button>
      </div>

      <el-table :data="users" border stripe size="small" v-loading="loading">
        <el-table-column prop="username" :label="t('admin.users.username')" min-width="140" show-overflow-tooltip />
        <el-table-column prop="display_name" :label="t('admin.users.showName')" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.display_name || "-" }}</template>
        </el-table-column>
        <el-table-column prop="email" :label="t('admin.users.email')" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.email || "-" }}</template>
        </el-table-column>
        <el-table-column :label="t('admin.users.role')" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
              {{ row.role === "admin" ? t("admin.users.roleAdmin") : t("admin.users.tagUser") }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('admin.users.status')" width="100" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.is_active"
              :disabled="row.id === auth.user?.id"
              inline-prompt
              :active-text="t('admin.users.active')"
              :inactive-text="t('admin.users.disabled')"
              @change="(value) => toggleActive(row, value)"
            />
          </template>
        </el-table-column>
        <el-table-column :label="t('admin.users.lastLogin')" width="180">
          <template #default="{ row }">{{ formatDateTime(row.last_login_at) }}</template>
        </el-table-column>
        <el-table-column :label="t('admin.users.createdAt')" width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column :label="t('common.actions')" width="300" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEditDialog(row)">{{ t("common.edit") }}</el-button>
            <el-button
              link
              type="warning"
              size="small"
              :disabled="row.id === auth.user?.id"
              @click="openResetPasswordDialog(row)"
            >{{ t("admin.users.resetPassword") }}</el-button>
            <el-button
              link
              type="warning"
              size="small"
              :disabled="row.id === auth.user?.id"
              @click="handleForceLogout(row)"
            >{{ t("admin.users.forceLogout") }}</el-button>
            <el-button
              link
              type="danger"
              size="small"
              :disabled="row.id === auth.user?.id"
              @click="handleDelete(row)"
            >{{ t("common.delete") }}</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          background
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @current-change="load"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>

    <!-- 新增用户 -->
    <el-dialog v-model="createVisible" :title="t('admin.users.addUser')" width="460px" :close-on-click-modal="false" @closed="resetCreateForm">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="90px">
        <el-form-item :label="t('admin.users.username')" prop="username">
          <el-input v-model="createForm.username" :placeholder="t('admin.users.loginUsername')" />
        </el-form-item>
        <el-form-item :label="t('admin.users.initialPassword')" prop="password">
          <el-input
            v-model="createForm.password"
            type="password"
            show-password
            :placeholder="t('admin.users.initialPasswordHint')"
          />
        </el-form-item>
        <el-form-item :label="t('admin.users.showName')" prop="displayName">
          <el-input v-model="createForm.displayName" :placeholder="t('admin.users.optional')" />
        </el-form-item>
        <el-form-item :label="t('admin.users.role')" prop="role">
          <el-select v-model="createForm.role" style="width: 100%;">
            <el-option :label="t('admin.users.roleUser')" value="user" />
            <el-option :label="t('admin.users.roleAdmin')" value="admin" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">{{ t("common.cancel") }}</el-button>
        <el-button type="primary" :loading="createSubmitting" @click="submitCreate">{{ t("admin.users.create") }}</el-button>
      </template>
    </el-dialog>

    <!-- 编辑用户 -->
    <el-dialog v-model="editVisible" :title="t('admin.users.editUser')" width="460px" :close-on-click-modal="false" @closed="resetEditForm">
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="90px">
        <el-form-item :label="t('admin.users.username')">
          <el-input :model-value="editingUsername" disabled />
        </el-form-item>
        <el-form-item :label="t('admin.users.showName')" prop="displayName">
          <el-input v-model="editForm.displayName" :placeholder="t('admin.users.optional')" />
        </el-form-item>
        <el-form-item :label="t('admin.users.email')" prop="email">
          <el-input v-model="editForm.email" :placeholder="t('admin.users.optional')" />
        </el-form-item>
        <el-form-item :label="t('admin.users.role')" prop="role">
          <el-select v-model="editForm.role" style="width: 100%;">
            <el-option :label="t('admin.users.roleUser')" value="user" />
            <el-option :label="t('admin.users.roleAdmin')" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('admin.users.accountStatus')">
          <el-switch v-model="editForm.isActive" inline-prompt :active-text="t('admin.users.active')" :inactive-text="t('admin.users.disabled')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">{{ t("common.cancel") }}</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="submitEdit">{{ t("common.save") }}</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码 -->
    <el-dialog v-model="resetVisible" :title="t('admin.users.resetPassword')" width="440px" :close-on-click-modal="false" @closed="resetResetForm">
      <el-form ref="resetFormRef" :model="resetForm" :rules="resetRules" label-width="90px">
        <el-form-item :label="t('admin.users.userLabel')">
          <el-input :model-value="resettingUsername" disabled />
        </el-form-item>
        <el-form-item :label="t('admin.users.newPassword')" prop="newPassword">
          <el-input
            v-model="resetForm.newPassword"
            type="password"
            show-password
            :placeholder="t('admin.users.passwordRule')"
          />
        </el-form-item>
        <el-form-item :label="t('admin.users.confirmPassword')" prop="confirmPassword">
          <el-input
            v-model="resetForm.confirmPassword"
            type="password"
            show-password
            :placeholder="t('admin.users.confirmPasswordPlaceholder')"
            @keyup.enter="submitResetPassword"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetVisible = false">{{ t("common.cancel") }}</el-button>
        <el-button type="primary" :loading="resetSubmitting" @click="submitResetPassword">{{ t("admin.users.confirmReset") }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus, Search, Refresh } from "@element-plus/icons-vue";

import { api } from "../../api/client";
import { useAuthStore } from "../../stores/auth";
import { useI18n } from "../../composables/useI18n";

const { t, locale } = useI18n();
const auth = useAuthStore();

const PASSWORD_STRENGTH_RE = /^(?=.*[A-Za-z])(?=.*\d).{8,}$/;
const EMAIL_RE = /^[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}$/;

const users = ref([]);
const loading = ref(false);
const total = ref(0);
const page = ref(1);
const pageSize = ref(10);
const filters = reactive({ query: "", role: "" });

const formatDateTime = (value) => {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const dateLocale = locale.value === "en-US" ? "en-US" : "zh-CN";
  return date.toLocaleString(dateLocale, { hour12: false });
};

const load = async () => {
  loading.value = true;
  try {
    const { data } = await api.listUsers({
      query: filters.query.trim() || undefined,
      role: filters.role || undefined,
      page: page.value,
      page_size: pageSize.value,
    });
    users.value = data.items || [];
    total.value = data.total || 0;
  } catch (error) {
    const detail = error?.response?.data?.detail || t("admin.users.loadFailed");
    ElMessage.error(typeof detail === "string" ? detail : t("admin.users.loadFailed"));
  } finally {
    loading.value = false;
  }
};

const handleSearch = () => {
  page.value = 1;
  load();
};

const handleReset = () => {
  filters.query = "";
  filters.role = "";
  page.value = 1;
  load();
};

const handleSizeChange = () => {
  page.value = 1;
  load();
};

// ---------------------------------------------------------------------------
// 新增用户
// ---------------------------------------------------------------------------
const createVisible = ref(false);
const createSubmitting = ref(false);
const createFormRef = ref(null);
const createForm = reactive({ username: "", password: "", displayName: "", role: "user" });

const createRules = computed(() => ({
  username: [
    { required: true, message: t("admin.users.usernameRequired"), trigger: "blur" },
    { min: 2, max: 64, message: t("admin.users.usernameLength"), trigger: "blur" },
  ],
  password: [
    {
      validator: (_rule, value, callback) => {
        if (value && !PASSWORD_STRENGTH_RE.test(value)) {
          callback(new Error(t("admin.users.passwordStrength")));
        } else {
          callback();
        }
      },
      trigger: "blur",
    },
  ],
  displayName: [{ max: 128, message: t("admin.users.displayNameMax"), trigger: "blur" }],
}));

const openCreateDialog = () => {
  resetCreateForm();
  createVisible.value = true;
};

const resetCreateForm = () => {
  createForm.username = "";
  createForm.password = "";
  createForm.displayName = "";
  createForm.role = "user";
  createFormRef.value?.clearValidate();
};

const submitCreate = async () => {
  try {
    await createFormRef.value.validate();
  } catch {
    return;
  }
  createSubmitting.value = true;
  try {
    const { data } = await api.createUser({
      username: createForm.username.trim(),
      password: createForm.password || null,
      display_name: createForm.displayName.trim() || null,
      role: createForm.role,
    });
    createVisible.value = false;
    if (data.generated_password) {
      ElMessageBox.alert(
        t("admin.users.createSuccessWithPassword", { name: data.username, password: data.generated_password }),
        t("admin.users.initialPassword"),
        { confirmButtonText: t("admin.users.recorded") }
      );
    } else {
      ElMessage.success(t("admin.users.createSuccess"));
    }
    await load();
  } catch (error) {
    const detail = error?.response?.data?.detail || t("admin.users.createFailed");
    ElMessage.error(typeof detail === "string" ? detail : t("admin.users.createFailed"));
  } finally {
    createSubmitting.value = false;
  }
};

// ---------------------------------------------------------------------------
// 编辑用户
// ---------------------------------------------------------------------------
const editVisible = ref(false);
const editSubmitting = ref(false);
const editFormRef = ref(null);
const editingId = ref("");
const editingUsername = ref("");
const editForm = reactive({ displayName: "", email: "", role: "user", isActive: true });

const editRules = computed(() => ({
  email: [
    {
      validator: (_rule, value, callback) => {
        if (value && !EMAIL_RE.test(value.trim())) {
          callback(new Error(t("admin.users.emailInvalid")));
        } else {
          callback();
        }
      },
      trigger: "blur",
    },
  ],
  displayName: [{ max: 128, message: t("admin.users.displayNameMax"), trigger: "blur" }],
}));

const openEditDialog = (row) => {
  editingId.value = row.id;
  editingUsername.value = row.username;
  editForm.displayName = row.display_name || "";
  editForm.email = row.email || "";
  editForm.role = row.role;
  editForm.isActive = row.is_active;
  editVisible.value = true;
};

const resetEditForm = () => {
  editFormRef.value?.clearValidate();
};

const submitEdit = async () => {
  try {
    await editFormRef.value.validate();
  } catch {
    return;
  }
  editSubmitting.value = true;
  try {
    await api.updateUser(editingId.value, {
      display_name: editForm.displayName.trim() || null,
      email: editForm.email.trim() || null,
      role: editForm.role,
      is_active: editForm.isActive,
    });
    ElMessage.success(t("admin.users.saved"));
    editVisible.value = false;
    await load();
  } catch (error) {
    const detail = error?.response?.data?.detail || t("admin.users.saveFailed");
    ElMessage.error(typeof detail === "string" ? detail : t("admin.users.saveFailed"));
  } finally {
    editSubmitting.value = false;
  }
};

// ---------------------------------------------------------------------------
// 状态开关
// ---------------------------------------------------------------------------
const toggleActive = async (row, value) => {
  try {
    await api.updateUser(row.id, { is_active: value });
    ElMessage.success(value ? t("admin.users.accountEnabled") : t("admin.users.accountDisabled"));
    await load();
  } catch (error) {
    const detail = error?.response?.data?.detail || t("admin.users.statusUpdateFailed");
    ElMessage.error(typeof detail === "string" ? detail : t("admin.users.statusUpdateFailed"));
    load();
  }
};

// ---------------------------------------------------------------------------
// 重置密码
// ---------------------------------------------------------------------------
const resetVisible = ref(false);
const resetSubmitting = ref(false);
const resetFormRef = ref(null);
const resettingId = ref("");
const resettingUsername = ref("");
const resetForm = reactive({ newPassword: "", confirmPassword: "" });

const resetRules = computed(() => ({
  newPassword: [
    { required: true, message: t("admin.users.newPasswordRequired"), trigger: "blur" },
    {
      validator: (_rule, value, callback) => {
        if (!PASSWORD_STRENGTH_RE.test(value || "")) {
          callback(new Error(t("admin.users.passwordStrength")));
        } else {
          callback();
        }
      },
      trigger: "blur",
    },
  ],
  confirmPassword: [
    { required: true, message: t("admin.users.confirmRequired"), trigger: "blur" },
    {
      validator: (_rule, value, callback) => {
        if (!value) {
          callback(new Error(t("admin.users.confirmRequired")));
        } else if (value !== resetForm.newPassword) {
          callback(new Error(t("admin.users.passwordMismatch")));
        } else {
          callback();
        }
      },
      trigger: "blur",
    },
  ],
}));

const openResetPasswordDialog = (row) => {
  resettingId.value = row.id;
  resettingUsername.value = row.username;
  resetForm.newPassword = "";
  resetForm.confirmPassword = "";
  resetVisible.value = true;
};

const resetResetForm = () => {
  resetFormRef.value?.clearValidate();
};

const submitResetPassword = async () => {
  try {
    await resetFormRef.value.validate();
  } catch {
    return;
  }
  resetSubmitting.value = true;
  try {
    await api.resetUserPassword(resettingId.value, { new_password: resetForm.newPassword });
    ElMessage.success(t("admin.users.passwordReset"));
    resetVisible.value = false;
    await load();
  } catch (error) {
    const detail = error?.response?.data?.detail || t("admin.users.resetFailed");
    ElMessage.error(typeof detail === "string" ? detail : t("admin.users.resetFailed"));
  } finally {
    resetSubmitting.value = false;
  }
};

// ---------------------------------------------------------------------------
// 强制下线 / 删除
// ---------------------------------------------------------------------------
const handleForceLogout = async (row) => {
  try {
    await ElMessageBox.confirm(
      t("admin.users.forceLogoutConfirm", { name: row.username }),
      t("admin.users.forceLogoutTitle"),
      {
        type: "warning",
        confirmButtonText: t("admin.users.forceLogout"),
        cancelButtonText: t("common.cancel"),
      }
    );
  } catch {
    return;
  }
  try {
    await api.forceLogoutUser(row.id);
    ElMessage.success(t("admin.users.forceLoggedOut"));
    await load();
  } catch (error) {
    const detail = error?.response?.data?.detail || t("admin.users.forceLogoutFailed");
    ElMessage.error(typeof detail === "string" ? detail : t("admin.users.forceLogoutFailed"));
  }
};

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      t("admin.users.deleteUserConfirm", { name: row.username }),
      t("admin.users.deleteUserTitle"),
      {
        type: "warning",
        confirmButtonText: t("common.delete"),
        cancelButtonText: t("common.cancel"),
      }
    );
  } catch {
    return;
  }
  try {
    await api.deleteUser(row.id);
    ElMessage.success(t("admin.users.userDeleted"));
    if (page.value > 1 && users.value.length === 1) {
      page.value -= 1;
    }
    await load();
  } catch (error) {
    const detail = error?.response?.data?.detail || t("admin.users.deleteFailed");
    ElMessage.error(typeof detail === "string" ? detail : t("admin.users.deleteFailed"));
  }
};

onMounted(load);
</script>

<style scoped>
.app-container {
  padding: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 16px;
  font-weight: 600;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

:deep(.el-table) {
  font-size: 14px;
}

:deep(.el-table td.el-table__cell) {
  padding: 10px 8px;
}

:deep(.el-table th.el-table__cell) {
  font-size: 14px;
  font-weight: 600;
  background-color: var(--el-table-header-bg-color);
}

:deep(.el-pagination) {
  font-size: 14px;
  padding: 16px 0;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}
</style>
