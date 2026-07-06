import { computed, onMounted, onUnmounted, ref } from "vue";

export function useShowcaseMotionPreference() {
  const preferReducedMotion = ref(false);
  const preferStatic = ref(false);

  const evaluate = () => {
    if (typeof window === "undefined") return;
    preferReducedMotion.value = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    preferStatic.value = preferReducedMotion.value || window.matchMedia("(max-width: 640px)").matches;
  };

  const enableRichMotion = computed(() => !preferReducedMotion.value);

  onMounted(() => {
    evaluate();
    window.addEventListener("resize", evaluate);
  });

  onUnmounted(() => {
    window.removeEventListener("resize", evaluate);
  });

  return { preferStatic, preferReducedMotion, enableRichMotion };
}
