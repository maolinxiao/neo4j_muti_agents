import { createRouter, createWebHistory } from "vue-router";

import MainLayout from "../layouts/MainLayout.vue";
import LoginView from "../views/LoginView.vue";
import HomeView from "../views/portal/HomeView.vue";
import ChatView from "../views/portal/ChatView.vue";
import RndWorkspaceView from "../views/portal/RndWorkspaceView.vue";
import HistoryView from "../views/portal/HistoryView.vue";
import OverviewView from "../views/admin/OverviewView.vue";
import PromptView from "../views/admin/PromptView.vue";
import TemplateView from "../views/admin/TemplateView.vue";
import LogsView from "../views/admin/LogsView.vue";
import { useAuthStore } from "../stores/auth";

const routes = [
  { path: "/login", name: "login", component: LoginView, meta: { public: true } },
  {
    path: "/",
    component: MainLayout,
    children: [
      { path: "", name: "home", component: HomeView },
      { path: "chat/:sessionId?", name: "chat", component: ChatView },
      { path: "rnd/:sessionId?", name: "rnd", component: RndWorkspaceView },
      { path: "history", name: "history", component: HistoryView },
      { path: "admin/overview", name: "admin-overview", component: OverviewView },
      { path: "admin/prompts", name: "admin-prompts", component: PromptView },
      { path: "admin/templates", name: "admin-templates", component: TemplateView },
      { path: "admin/logs", name: "admin-logs", component: LogsView },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (to.meta.public) {
    if (to.name === "login" && auth.isAuthenticated) {
      return { name: "home" };
    }
    return true;
  }
  if (!auth.isAuthenticated) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (!auth.user) {
    try {
      await auth.fetchCurrentUser();
    } catch {
      auth.clearSession();
      return { name: "login", query: { redirect: to.fullPath } };
    }
  }
  return true;
});

export default router;
