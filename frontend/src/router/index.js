import { createRouter, createWebHistory } from "vue-router";
import { ElMessage } from "element-plus";

import MainLayout from "../layouts/MainLayout.vue";
import LoginView from "../views/LoginView.vue";
import RegisterView from "../views/RegisterView.vue";
import ShowcaseHomeView from "../views/showcase/ShowcaseHomeView.vue";
import HomeView from "../views/portal/HomeView.vue";
import ChatView from "../views/portal/ChatView.vue";
import ConstitutionView from "../views/portal/ConstitutionView.vue";
import RndWorkspaceView from "../views/portal/RndWorkspaceView.vue";
import HistoryView from "../views/portal/HistoryView.vue";
import OverviewView from "../views/admin/OverviewView.vue";
import UsersView from "../views/admin/UsersView.vue";
import PromptView from "../views/admin/PromptView.vue";
import TemplateView from "../views/admin/TemplateView.vue";
import LogsView from "../views/admin/LogsView.vue";
import { useAuthStore } from "../stores/auth";

const routes = [
  { path: "/", name: "showcase", component: ShowcaseHomeView, meta: { public: true } },
  { path: "/login", name: "login", component: LoginView, meta: { public: true } },
  { path: "/register", name: "register", component: RegisterView, meta: { public: true } },
  {
    path: "/app",
    component: MainLayout,
    children: [
      { path: "", name: "app-home", component: HomeView },
      { path: "chat/:sessionId?", name: "chat", component: ChatView },
      { path: "constitution", name: "constitution", component: ConstitutionView },
      { path: "rnd/:sessionId?", name: "rnd", component: RndWorkspaceView },
      { path: "history", name: "history", component: HistoryView },
      { path: "admin/overview", name: "admin-overview", component: OverviewView, meta: { requiresAdmin: true } },
      { path: "admin/users", name: "admin-users", component: UsersView, meta: { requiresAdmin: true } },
      { path: "admin/prompts", name: "admin-prompts", component: PromptView, meta: { requiresAdmin: true } },
      { path: "admin/templates", name: "admin-templates", component: TemplateView, meta: { requiresAdmin: true } },
      { path: "admin/logs", name: "admin-logs", component: LogsView, meta: { requiresAdmin: true } },
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
      return { name: "app-home" };
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
  if (to.meta.requiresAdmin && !auth.isAdmin) {
    ElMessage.warning("当前账号无管理员权限，无法访问管理后台。");
    return { name: "app-home" };
  }
  return true;
});

export default router;
