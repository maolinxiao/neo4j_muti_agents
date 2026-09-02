<template>
  <el-container class="app-shell">
    <el-aside width="200px" class="sidebar">
      <div class="brand-block">
        <img src="https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png" class="brand-logo" alt="logo" />
        <span class="brand-title">药食同源平台</span>
      </div>
      <el-scrollbar>
        <el-menu
          :default-active="activePath"
          router
          class="nav-menu"
          background-color="#304156"
          text-color="#bfcbd9"
          active-text-color="#409EFF"
          :unique-opened="false"
          :collapse-transition="false"
        >
          <el-menu-item index="/app">
            <el-icon><House /></el-icon>
            <template #title>{{ t("menu.home") }}</template>
          </el-menu-item>
          <el-menu-item index="/app/chat">
            <el-icon><ChatDotRound /></el-icon>
            <template #title>{{ t("menu.chat") }}</template>
          </el-menu-item>
          <el-menu-item index="/app/constitution">
            <el-icon><List /></el-icon>
            <template #title>{{ t("menu.constitution") }}</template>
          </el-menu-item>
          <el-menu-item index="/app/rnd">
            <el-icon><Cpu /></el-icon>
            <template #title>{{ t("menu.rnd") }}</template>
          </el-menu-item>
          <el-menu-item index="/app/history">
            <el-icon><Document /></el-icon>
            <template #title>{{ t("menu.history") }}</template>
          </el-menu-item>
          <el-sub-menu v-if="auth.isAdmin" index="/app/admin">
            <template #title>
              <el-icon><Setting /></el-icon>
              <span>{{ t("menu.admin") }}</span>
            </template>
            <el-menu-item index="/app/admin/overview">{{ t("menu.adminOverview") }}</el-menu-item>
            <el-menu-item index="/app/admin/users">{{ t("menu.adminUsers") }}</el-menu-item>
            <el-menu-item index="/app/admin/logs">{{ t("menu.adminLogs") }}</el-menu-item>
            <el-menu-item index="/app/admin/prompts">{{ t("menu.adminPrompts") }}</el-menu-item>
            <el-menu-item index="/app/admin/templates">{{ t("menu.adminTemplates") }}</el-menu-item>
          </el-sub-menu>
        </el-menu>
      </el-scrollbar>
    </el-aside>
    <el-container class="shell-main">
      <el-header class="topbar" height="50px">
        <div class="topbar-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/app' }">{{ t("menu.home") }}</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentRouteName }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="topbar-right">
          <el-dropdown trigger="click">
            <span class="el-dropdown-link user-dropdown">
              <el-avatar :size="30" :src="auth.user?.avatar_url || 'https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png'">
                {{ (auth.displayName || "U").slice(0, 1).toUpperCase() }}
              </el-avatar>
              <span class="user-name">{{ auth.displayName }}</span>
              <el-icon class="el-icon--right"><CaretBottom /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="goAccount">{{ t("menu.account") }}</el-dropdown-item>
                <el-dropdown-item @click="goChangePassword">{{ t("menu.changePassword") }}</el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">{{ t("menu.logout") }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  House,
  ChatDotRound,
  List,
  Cpu,
  Document,
  Setting,
  CaretBottom
} from "@element-plus/icons-vue";

import { useI18n } from "../composables/useI18n";
import { useAuthStore } from "../stores/auth";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const activePath = computed(() => route.path);

const routeNameMap = {
  "/app": "menu.home",
  "/app/chat": "menu.chat",
  "/app/constitution": "menu.constitution",
  "/app/rnd": "menu.rnd",
  "/app/history": "menu.history",
  "/app/account": "menu.account",
  "/app/admin/overview": "menu.adminOverview",
  "/app/admin/users": "menu.adminUsers",
  "/app/admin/logs": "menu.adminLogs",
  "/app/admin/prompts": "menu.adminPrompts",
  "/app/admin/templates": "menu.adminTemplates",
};

const currentRouteName = computed(() => {
  const path = route.path;
  if (routeNameMap[path]) return t(routeNameMap[path]);
  if (path.startsWith("/app/chat")) return t("menu.chat");
  if (path.startsWith("/app/rnd")) return t("menu.rnd");
  if (path.startsWith("/app/admin")) return t("menu.admin");
  return "";
});

const goAccount = () => {
  router.push({ name: "account" });
};

// 修改密码：跳转个人中心「账号安全」页签（原弹窗已移除）
const goChangePassword = () => {
  router.push({ name: "account", query: { tab: "security" } });
};

const handleLogout = async () => {
  await auth.logout();
  await router.replace({ name: "login" });
};
</script>

<style scoped>
.app-shell {
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

.sidebar {
  background-color: #304156;
  display: flex;
  flex-direction: column;
  transition: width 0.28s;
  box-shadow: 2px 0 6px rgba(0, 21, 41, 0.35);
  z-index: 10;
}

.brand-block {
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #2b3643;
  color: #fff;
  overflow: hidden;
  padding: 0 10px;
}

.brand-logo {
  width: 32px;
  height: 32px;
  margin-right: 12px;
}

.brand-title {
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
}

.nav-menu {
  border-right: none;
  width: 100% !important;
}

:deep(.el-menu-item), :deep(.el-sub-menu__title) {
  height: 50px !important;
  line-height: 50px !important;
}

:deep(.el-menu-item:hover), :deep(.el-sub-menu__title:hover) {
  background-color: #263445 !important;
}

:deep(.el-menu-item.is-active) {
  background-color: #1f2d3d !important;
}

.shell-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  background-color: var(--app-bg);
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 50px;
  background: var(--app-panel);
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  padding: 0 20px;
  z-index: 9;
}

.topbar-left {
  display: flex;
  align-items: center;
}

.topbar-right {
  display: flex;
  align-items: center;
}

.user-dropdown {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.user-name {
  margin-left: 8px;
  font-size: 14px;
  color: var(--app-text);
}

.content {
  padding: 20px;
  height: calc(100vh - 50px);
  overflow-y: auto;
  box-sizing: border-box;
}

/* Scrollbar styling for sidebar */
.sidebar .el-scrollbar {
  flex: 1;
}
</style>
