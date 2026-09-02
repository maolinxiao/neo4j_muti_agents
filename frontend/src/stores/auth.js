import { ElMessage } from "element-plus";
import { defineStore } from "pinia";

import { api } from "../api/client";
import { useChatStore } from "./chat";
import { useRndStore } from "./rnd";

const readStoredUser = () => {
  try {
    return JSON.parse(localStorage.getItem("ys_auth_user") || "null");
  } catch {
    return null;
  }
};

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: localStorage.getItem("ys_auth_token") || "",
    user: readStoredUser(),
    loading: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token),
    isAdmin: (state) => state.user?.role === "admin",
    displayName: (state) => state.user?.display_name || state.user?.username || "管理员",
  },
  actions: {
    setSession(token, user) {
      const prevUserId = this.user?.id || null;
      this.token = token;
      this.user = user;
      localStorage.setItem("ys_auth_token", token);
      localStorage.setItem("ys_auth_user", JSON.stringify(user || {}));
      // 同浏览器切换账号（A 登出 -> B 登录）时清空聊天/研发会话缓存，避免渲染上一账号的历史记录
      if (prevUserId && user?.id && prevUserId !== user.id) {
        useChatStore().resetAll();
        useRndStore().resetAll();
      }
    },
    clearSession() {
      this.token = "";
      this.user = null;
      localStorage.removeItem("ys_auth_token");
      localStorage.removeItem("ys_auth_user");
      // 登出事件：清空会话缓存，防止下一账号看到残留数据
      useChatStore().resetAll();
      useRndStore().resetAll();
    },
    async login(username, password, captcha = {}) {
      this.loading = true;
      try {
        const { data } = await api.login({ username, password, ...captcha });
        this.setSession(data.access_token, data.user);
        return data.user;
      } finally {
        this.loading = false;
      }
    },
    async fetchCurrentUser() {
      if (!this.token) return null;
      const { data } = await api.getCurrentUser();
      this.user = data;
      localStorage.setItem("ys_auth_user", JSON.stringify(data));
      return data;
    },
    async logout() {
      try {
        if (this.token) {
          await api.logout();
        }
      } catch {
        ElMessage.warning("登录状态已清理。");
      } finally {
        this.clearSession();
      }
    },
  },
});
