<template>
  <div class="app-container">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>用户管理</span>
          <el-button type="primary" :icon="Plus" @click="openCreateDialog">新增用户</el-button>
        </div>
      </template>

      <div class="toolbar">
        <el-input
          v-model="filters.query"
          placeholder="搜索用户名 / 显示名 / 邮箱"
          clearable
          style="width: 260px;"
          @keyup.enter="handleSearch"
        />
        <el-select v-model="filters.role" placeholder="角色" clearable style="width: 160px;">
          <el-option label="管理员" value="admin" />
          <el-option label="普通用户" value="user" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
        <el-button :icon="Refresh" @click="handleReset">重置</el-button>
      </div>

      <el-table :data="users" border stripe size="small" v-loading="loading">
        <el-table-column prop="username" label="用户名" min-width="140" show-overflow-tooltip />
        <el-table-column prop="display_name" label="显示名" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.display_name || "-" }}</template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.email || "-" }}</template>
        </el-table-column>
        <el-table-column label="角色" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
              {{ row.role === "admin" ? "管理员" : "用户" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.is_active"
              :disabled="row.id === auth.user?.id"
              inline-prompt
              active-text="启用"
              inactive-text="停用"
              @change="(value) => toggleActive(row, value)"
            />
          </template>
        </el-table-column>
        <el-table-column label="最后登录" width="180">
          <template #default="{ row }">{{ formatDateTime(row.last_login_at) }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEditDialog(row)">编辑</el-button>
            <el-button
              link
              type="warning"
              size="small"
              :disabled="row.id === auth.user?.id"
              @click="openResetPasswordDialog(row)"
            >重置密码</el-button>
            <el-button
              link
              type="warning"
              size="small"
              :disabled="row.id === auth.user?.id"
              @click="handleForceLogout(row)"
            >强制下线</el-button>
            <el-button
              link
              type="danger"
              size="small"
              :disabled="row.id === auth.user?.id"
              @click="handleDelete(row)"
            >删除</el-button>
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
    <el-dialog v-model="createVisible" title="新增用户" width="460px" :close-on-click-modal="false" @closed="resetCreateForm">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="90px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item label="初始密码" prop="password">
          <el-input
            v-model="createForm.password"
            type="password"
            show-password
            placeholder="留空则由系统随机生成"
          />
        </el-form-item>
        <el-form-item label="显示名" prop="displayName">
          <el-input v-model="createForm.displayName" placeholder="可不填" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="createForm.role" style="width: 100%;">
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="createSubmitting" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑用户 -->
    <el-dialog v-model="editVisible" title="编辑用户" width="460px" :close-on-click-modal="false" @closed="resetEditForm">
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="90px">
        <el-form-item label="用户名">
          <el-input :model-value="editingUsername" disabled />
        </el-form-item>
        <el-form-item label="显示名" prop="displayName">
          <el-input v-model="editForm.displayName" placeholder="可不填" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="editForm.email" placeholder="可不填" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="editForm.role" style="width: 100%;">
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="账号状态">
          <el-switch v-model="editForm.isActive" inline-prompt active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码 -->
    <el-dialog v-model="resetVisible" title="重置密码" width="440px" :close-on-click-modal="false" @closed="resetResetForm">
      <el-form ref="resetFormRef" :model="resetForm" :rules="resetRules" label-width="90px">
        <el-form-item label="用户">
          <el-input :model-value="resettingUsername" disabled />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="resetForm.newPassword"
            type="password"
            show-password
            placeholder="至少 8 位，须包含字母和数字"
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="resetForm.confirmPassword"
            type="password"
            show-password
            placeholder="请再次输入新密码"
            @keyup.enter="submitResetPassword"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :loading="resetSubmitting" @click="submitResetPassword">确认重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus, Search, Refresh } from "@element-plus/icons-vue";

import { api } from "../../api/client";
import { useAuthStore } from "../../stores/auth";

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
  return date.toLocaleString("zh-CN", { hour12: false });
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
    const detail = error?.response?.data?.detail || "加载用户列表失败。";
    ElMessage.error(typeof detail === "string" ? detail : "加载用户列表失败。");
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

const createRules = {
  username: [
    { required: true, message: "请输入用户名", trigger: "blur" },
    { min: 2, max: 64, message: "用户名长度需在 2-64 位之间", trigger: "blur" },
  ],
  password: [
    {
      validator: (_rule, value, callback) => {
        if (value && !PASSWORD_STRENGTH_RE.test(value)) {
          callback(new Error("密码至少 8 位，且须同时包含字母和数字"));
        } else {
          callback();
        }
      },
      trigger: "blur",
    },
  ],
  displayName: [{ max: 128, message: "显示名不能超过 128 个字符", trigger: "blur" }],
};

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
        `用户「${data.username}」创建成功。系统已生成初始密码：${data.generated_password}，请妥善转交给用户，密码仅显示一次。`,
        "初始密码",
        { confirmButtonText: "已记录" }
      );
    } else {
      ElMessage.success("用户创建成功");
    }
    await load();
  } catch (error) {
    const detail = error?.response?.data?.detail || "创建用户失败。";
    ElMessage.error(typeof detail === "string" ? detail : "创建用户失败。");
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

const editRules = {
  email: [
    {
      validator: (_rule, value, callback) => {
        if (value && !EMAIL_RE.test(value.trim())) {
          callback(new Error("邮箱格式不正确"));
        } else {
          callback();
        }
      },
      trigger: "blur",
    },
  ],
  displayName: [{ max: 128, message: "显示名不能超过 128 个字符", trigger: "blur" }],
};

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
    ElMessage.success("保存成功");
    editVisible.value = false;
    await load();
  } catch (error) {
    const detail = error?.response?.data?.detail || "保存失败。";
    ElMessage.error(typeof detail === "string" ? detail : "保存失败。");
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
    ElMessage.success(value ? "账号已启用" : "账号已停用");
    await load();
  } catch (error) {
    const detail = error?.response?.data?.detail || "更新状态失败。";
    ElMessage.error(typeof detail === "string" ? detail : "更新状态失败。");
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

const resetRules = {
  newPassword: [
    { required: true, message: "请输入新密码", trigger: "blur" },
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
    { required: true, message: "请再次输入新密码", trigger: "blur" },
    {
      validator: (_rule, value, callback) => {
        if (!value) {
          callback(new Error("请再次输入新密码"));
        } else if (value !== resetForm.newPassword) {
          callback(new Error("两次输入的密码不一致"));
        } else {
          callback();
        }
      },
      trigger: "blur",
    },
  ],
};

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
    ElMessage.success("密码已重置，该用户全部会话已失效");
    resetVisible.value = false;
    await load();
  } catch (error) {
    const detail = error?.response?.data?.detail || "重置密码失败。";
    ElMessage.error(typeof detail === "string" ? detail : "重置密码失败。");
  } finally {
    resetSubmitting.value = false;
  }
};

// ---------------------------------------------------------------------------
// 强制下线 / 删除
// ---------------------------------------------------------------------------
const handleForceLogout = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要让用户「${row.username}」强制下线吗？该用户所有会话将立即失效。`, "强制下线", {
      type: "warning",
      confirmButtonText: "强制下线",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  try {
    await api.forceLogoutUser(row.id);
    ElMessage.success("已强制下线");
    await load();
  } catch (error) {
    const detail = error?.response?.data?.detail || "强制下线失败。";
    ElMessage.error(typeof detail === "string" ? detail : "强制下线失败。");
  }
};

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要删除用户「${row.username}」吗？删除后不可恢复。`, "删除用户", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  try {
    await api.deleteUser(row.id);
    ElMessage.success("用户已删除");
    if (page.value > 1 && users.value.length === 1) {
      page.value -= 1;
    }
    await load();
  } catch (error) {
    const detail = error?.response?.data?.detail || "删除用户失败。";
    ElMessage.error(typeof detail === "string" ? detail : "删除用户失败。");
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
  background-color: #f5f7fa;
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
