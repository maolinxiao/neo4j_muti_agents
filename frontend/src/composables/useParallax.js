import { computed, onMounted, onUnmounted, ref } from "vue";

import { useLenisScroll } from "./useLenisScroll";
import { useShowcaseMotionPreference } from "./useShowcaseMotionPreference";

/**
 * Scroll parallax helper. Returns a reactive translateY style for background layers.
 */
export function useParallax(speed = 0.35) {
  const { enableRichMotion } = useShowcaseMotionPreference();
  const { scrollY } = useLenisScroll();

  const style = computed(() => {
    if (!enableRichMotion.value) return {};
    const offset = scrollY.value * speed;
    if (Math.abs(offset) < 0.5) return {};
    return {
      transform: `translate3d(0, ${offset.toFixed(1)}px, 0)`,
    };
  });

  return { style, scrollY };
}

/**
 * Mouse parallax for hero foreground elements (subtle depth).
 */
export function useMouseParallax(intensity = 8) {
  const { enableRichMotion } = useShowcaseMotionPreference();
  const offset = ref({ x: 0, y: 0 });

  const onMove = (event) => {
    if (!enableRichMotion.value) return;
    const cx = window.innerWidth / 2;
    const cy = window.innerHeight / 2;
    offset.value = {
      x: ((event.clientX - cx) / cx) * intensity,
      y: ((event.clientY - cy) / cy) * intensity,
    };
  };

  const onLeave = () => {
    offset.value = { x: 0, y: 0 };
  };

  onMounted(() => {
    window.addEventListener("mousemove", onMove, { passive: true });
    window.addEventListener("mouseleave", onLeave);
  });

  onUnmounted(() => {
    window.removeEventListener("mousemove", onMove);
    window.removeEventListener("mouseleave", onLeave);
  });

  const style = computed(() => {
    if (!enableRichMotion.value) return {};
    const { x, y } = offset.value;
    if (Math.abs(x) < 0.3 && Math.abs(y) < 0.3) return {};
    return {
      transform: `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0)`,
    };
  });

  return { style };
}
