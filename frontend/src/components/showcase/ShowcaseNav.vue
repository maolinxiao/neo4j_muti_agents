<template>
  <header class="showcase-nav sc-glass-subtle" :class="{ 'is-scrolled': scrolled }">
    <div class="showcase-container nav-inner">
      <router-link to="/" class="nav-brand sc-nav-brand">
        <span class="brand-dot" />
        <span>药食同源平台</span>
      </router-link>
      <nav class="nav-links" aria-label="展示站导航">
        <a
          v-for="item in navItems"
          :key="item.id"
          :href="item.href"
          class="nav-link"
          @click.prevent="scrollTo(item.id)"
        >
          {{ item.label }}
        </a>
      </nav>
      <div class="nav-actions">
        <router-link :to="{ name: 'login', query: { redirect: '/app' } }" class="showcase-btn showcase-btn-primary nav-btn sc-btn-shine">
          进入工作台
        </router-link>
      </div>
    </div>
  </header>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from "vue";

import { getLenis, showcaseScrollTo } from "../../composables/useSmoothScroll";

const scrolled = ref(false);

const navItems = [
  { id: "capabilities", label: "能力", href: "#capabilities" },
  { id: "knowledge-bases", label: "知识库", href: "#knowledge-bases" },
  { id: "audience", label: "场景", href: "#audience" },
  { id: "agents", label: "流程", href: "#agents" },
  { id: "evidence", label: "证据", href: "#evidence" },
];

const scrollTo = (id) => showcaseScrollTo(`#${id}`);

const updateScrolled = () => {
  const lenis = getLenis();
  scrolled.value = (lenis ? lenis.scroll : window.scrollY) > 20;
};

onMounted(() => {
  updateScrolled();
  window.addEventListener("scroll", updateScrolled, { passive: true });
  const attachLenis = () => {
    const lenis = getLenis();
    if (!lenis) return false;
    lenis.on("scroll", updateScrolled);
    return true;
  };
  if (!attachLenis()) {
    setTimeout(attachLenis, 100);
  }
});

onUnmounted(() => {
  window.removeEventListener("scroll", updateScrolled);
  getLenis()?.off("scroll", updateScrolled);
});
</script>

<style scoped>
.showcase-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  padding: 1rem 0;
  background: rgba(253, 253, 252, 0.75);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--sc-border-subtle);
  transition: transform 0.3s ease;
}

.showcase-nav.is-scrolled {
  background: rgba(253, 253, 252, 0.82);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border-bottom: 1px solid var(--sc-border);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.04);
}

.nav-inner {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.nav-brand {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  color: var(--sc-text);
  text-decoration: none;
  font-weight: 600;
  font-size: 0.9375rem;
  white-space: nowrap;
}

.brand-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--sc-accent);
  box-shadow: 0 0 10px rgba(107, 196, 166, 0.5);
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 1.75rem;
  margin-left: auto;
}

.nav-link {
  color: var(--sc-text-secondary);
  text-decoration: none;
  font-size: 0.875rem;
  font-weight: 500;
  transition: color 0.2s ease;
}

.nav-link:hover,
.nav-link:focus-visible {
  color: var(--sc-accent);
  outline: none;
}

.nav-btn {
  padding: 0.55rem 1.1rem;
  font-size: 0.875rem;
}

@media (max-width: 900px) {
  .nav-links {
    display: none;
  }

  .nav-actions {
    margin-left: auto;
  }
}

@media (max-width: 480px) {
  .showcase-nav {
    padding: 0.85rem 0;
  }

  .nav-actions {
    display: none;
  }
}
</style>
