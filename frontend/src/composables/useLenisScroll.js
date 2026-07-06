import { onMounted, onUnmounted, ref } from "vue";

import { getLenis } from "./useSmoothScroll";

const scrollY = ref(0);
let listenerCount = 0;
let lenisHandler = null;
let windowHandler = null;
let attachAttempts = 0;

function attachWindowFallback() {
  windowHandler = () => {
    scrollY.value = window.scrollY;
  };
  window.addEventListener("scroll", windowHandler, { passive: true });
  windowHandler();
}

function attach() {
  const lenis = getLenis();
  if (lenis) {
    lenisHandler = ({ scroll }) => {
      scrollY.value = scroll;
    };
    lenis.on("scroll", lenisHandler);
    scrollY.value = lenis.scroll ?? window.scrollY;
    return;
  }
  if (attachAttempts < 24) {
    attachAttempts += 1;
    requestAnimationFrame(attach);
    return;
  }
  attachWindowFallback();
}

function detach() {
  const lenis = getLenis();
  if (lenis && lenisHandler) {
    lenis.off("scroll", lenisHandler);
    lenisHandler = null;
  }
  if (windowHandler) {
    window.removeEventListener("scroll", windowHandler);
    windowHandler = null;
  }
}

/** 与 Lenis 同步的 scrollY，避免 window.scroll 与平滑滚动脱节造成卡顿 */
export function useLenisScroll() {
  onMounted(() => {
    listenerCount += 1;
    if (listenerCount === 1) attach();
  });

  onUnmounted(() => {
    listenerCount = Math.max(0, listenerCount - 1);
    if (listenerCount === 0) detach();
  });

  return { scrollY };
}
