<template>
  <el-config-provider :locale="elLocale">
    <router-view />
  </el-config-provider>
</template>

<script setup>
import { computed } from "vue";
import en from "element-plus/es/locale/lang/en";
import zhCn from "element-plus/es/locale/lang/zh-cn";

import { useI18n } from "./composables/useI18n";

const { locale } = useI18n();
const elLocale = computed(() => (locale.value === "en-US" ? en : zhCn));
</script>

<style>
:root {
  --app-bg: #f0f2f5;
  --app-panel: #ffffff;
  --app-panel-2: #f8fafc;
  --app-text: #303133;
  --app-text-2: #606266;
  --app-text-3: #909399;
  --app-border: #e4e7ed;
  --app-hover: #f5f7fa;
  --app-active: #ecf5ff;
  --app-active-border: #409eff;
}

html.dark {
  --app-bg: #0f1419;
  --app-panel: #1a2129;
  --app-panel-2: #141a21;
  --app-text: #e5eaf3;
  --app-text-2: #a3a6ad;
  --app-text-3: #73767a;
  --app-border: #333a45;
  --app-hover: #232b35;
  --app-active: rgba(64, 158, 255, 0.14);
  --app-active-border: #409eff;
}

body {
  margin: 0;
  padding: 0;
  font-family: "Helvetica Neue", Helvetica, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "微软雅黑", Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: var(--app-bg);
  color: var(--app-text);
}

#app {
  min-height: 100vh;
  width: 100%;
}

/* Custom Scrollbar */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: #c0c4cc;
}
</style>
