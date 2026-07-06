import { onMounted, onUnmounted, ref, unref, watch } from "vue";

import { useShowcaseMotionPreference } from "./useShowcaseMotionPreference";

/**
 * 轻量滚动揭示：离开视口后重置，再次进入可重播动效。
 */
export function useScrollReveal(targetRef, options = {}) {
  const {
    replay = false,
    rootMargin = "0px 0px -7% 0px",
    threshold = 0.06,
  } = options;

  const { preferReducedMotion } = useShowcaseMotionPreference();
  const revealed = ref(false);
  let observer = null;

  const bind = (el) => {
    observer?.disconnect();
    if (!el) return;

    if (preferReducedMotion.value) {
      revealed.value = true;
      return;
    }

    observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry) return;
        if (entry.isIntersecting && entry.intersectionRatio >= threshold) {
          revealed.value = true;
        } else if (replay && !entry.isIntersecting) {
          revealed.value = false;
        }
      },
      { rootMargin, threshold: [0, threshold, 0.15, 0.35] },
    );
    observer.observe(el);
  };

  onMounted(() => {
    bind(unref(targetRef));
    watch(
      () => unref(targetRef),
      (el) => bind(el),
    );
  });

  onUnmounted(() => {
    observer?.disconnect();
    observer = null;
  });

  return { revealed };
}
