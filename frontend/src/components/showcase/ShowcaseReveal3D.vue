<template>
  <div
    ref="rootRef"
    class="showcase-reveal-3d"
    :class="[
      `showcase-reveal-3d--${variant}`,
      { 'is-revealed': revealed, 'has-stagger': stagger },
    ]"
    :style="styleVars"
  >
    <slot />
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

import { useScrollReveal } from "../../composables/useScrollReveal";

const props = defineProps({
  delay: { type: Number, default: 0 },
  stagger: { type: Boolean, default: false },
  variant: {
    type: String,
    default: "up",
    validator: (v) => ["up", "left", "right", "scale"].includes(v),
  },
});

const rootRef = ref(null);
const { revealed } = useScrollReveal(rootRef, { replay: true });

const styleVars = computed(() => ({
  "--reveal-delay": `${props.delay}ms`,
}));
</script>
