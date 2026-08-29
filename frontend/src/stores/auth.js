import { ElMessage } from "element-plus";
import { defineStore } from "pinia";

import { api } from "../api/client";

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
      this.token = token;
      this.user = user;
      localStorage.setItem("ys_auth_token", token);
      localStorage.setItem("ys_auth_user", JSON.stringify(user || {}));
    },
    clearSession() {
      this.token = "";
      this.user = null;
      localStorage.removeItem("ys_auth_token");
      localStorage.removeItem("ys_auth_user");
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
