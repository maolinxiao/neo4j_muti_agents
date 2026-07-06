<template>
  <header class="sc-section-head" :class="{ centered }">
    <div v-if="eyebrow || $slots.eyebrow" class="sc-head-top">
      <p v-if="eyebrow" class="sc-eyebrow">{{ eyebrow }}</p>
      <span class="sc-head-accent" aria-hidden="true" />
    </div>
    <h2 class="sc-section-head-title">{{ title }}</h2>
    <p v-if="lead" class="sc-section-head-lead">{{ lead }}</p>
  </header>
</template>

<script setup>
defineProps({
  eyebrow: { type: String, default: "" },
  title: { type: String, required: true },
  lead: { type: String, default: "" },
  centered: { type: Boolean, default: false },
});
</script>

<style scoped>
.sc-section-head.centered {
  text-align: center;
  margin-inline: auto;
}

.sc-head-top {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.65rem;
}

.centered .sc-head-top {
  justify-content: center;
}

.sc-head-accent {
  flex: 1;
  max-width: 3rem;
  height: 2px;
  background: linear-gradient(90deg, var(--sc-accent), transparent);
  border-radius: 2px;
}

.centered .sc-head-accent {
  display: none;
}

.sc-eyebrow {
  margin: 0 0 0.75rem;
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--sc-accent);
}

.sc-section-head-title {
  margin: 0 0 1rem;
  font-family: var(--sc-font-display);
  font-size: clamp(2rem, 3.5vw, 2.5rem);
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -0.03em;
  color: var(--sc-text);
}

.sc-section-head-lead {
  margin: 0;
  font-size: 1.125rem;
  line-height: 1.8;
  color: var(--sc-text-secondary);
}
</style>
