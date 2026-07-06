import Lenis from "lenis";
import { onMounted, onUnmounted } from "vue";

let lenisInstance = null;

export function getLenis() {
  return lenisInstance;
}

export function showcaseScrollTo(target, options = {}) {
  const { offset = -80 } = options;
  if (typeof target === "string") {
    const el = document.querySelector(target);
    if (!el) return;
    target = el;
  }
  if (lenisInstance) {
    lenisInstance.scrollTo(target, { offset, duration: 1.35 });
    return;
  }
  if (target instanceof Element) {
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

export function useSmoothScroll() {
  let rafId = null;

  onMounted(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    document.documentElement.classList.add("lenis", "lenis-smooth");

    lenisInstance = new Lenis({
      lerp: 0.085,
      smoothWheel: true,
      wheelMultiplier: 0.9,
      touchMultiplier: 1.1,
      autoRaf: false,
    });

    const raf = (time) => {
      lenisInstance?.raf(time);
      rafId = requestAnimationFrame(raf);
    };
    rafId = requestAnimationFrame(raf);
  });

  onUnmounted(() => {
    if (rafId) cancelAnimationFrame(rafId);
    lenisInstance?.destroy();
    lenisInstance = null;
    document.documentElement.classList.remove("lenis", "lenis-smooth");
  });

  return { scrollTo: showcaseScrollTo };
}
