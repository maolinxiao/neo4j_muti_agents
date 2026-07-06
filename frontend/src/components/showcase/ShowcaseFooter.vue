<template>
  <footer class="showcase-footer">
    <div class="showcase-container footer-inner">
      <div class="footer-brand">
        <span class="brand-dot" />
        <span>药食同源多智能体研发协同平台</span>
      </div>
      <p class="footer-copy">基于 Neo4j 知识图谱 · 结构化智能生成 · 多智能体工作台</p>
      <div class="footer-actions">
        <router-link :to="{ name: 'login', query: { redirect: '/app' } }" class="showcase-btn showcase-btn-primary">
          进入工作台
        </router-link>
        <router-link to="/login" class="showcase-btn showcase-btn-ghost">登录</router-link>
      </div>
    </div>
  </footer>
</template>

<style scoped>
.showcase-footer {
  padding: 3rem 0 2.5rem;
  border-top: 1px solid var(--sc-border);
  background: rgba(0, 0, 0, 0.2);
}

.footer-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  text-align: center;
}

.footer-brand {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  font-weight: 600;
  color: var(--sc-text);
}

.brand-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--sc-accent);
}

.footer-copy {
  margin: 0;
  font-size: 0.85rem;
  color: var(--sc-muted);
}

.footer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  justify-content: center;
  margin-top: 0.5rem;
}
</style>
