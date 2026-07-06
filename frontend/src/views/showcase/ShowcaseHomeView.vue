<template>
  <div class="showcase-page">
    <div class="showcase-ambient" aria-hidden="true" />
    <ShowcaseScrollProgress />
    <ShowcaseNav />
    <main class="showcase-main">
      <ShowcaseHero />
      <ShowcaseStatsBar />
      <ShowcaseMarquee />
      <CapabilitySection />
      <ShowcaseMarquee variant="light" :items="marqueeSecondary" />
      <KnowledgeBaseMap />
      <AudienceSplitSection />
      <AgentPipeline />
      <EvidenceTrustSection />
    </main>
    <ShowcaseFooter />
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from "vue";
import "../../styles/showcase.css";

import { useSmoothScroll } from "../../composables/useSmoothScroll";
import ShowcaseNav from "../../components/showcase/ShowcaseNav.vue";
import ShowcaseHero from "../../components/showcase/ShowcaseHero.vue";
import ShowcaseStatsBar from "../../components/showcase/ShowcaseStatsBar.vue";
import ShowcaseMarquee from "../../components/showcase/ShowcaseMarquee.vue";
import ShowcaseScrollProgress from "../../components/showcase/ShowcaseScrollProgress.vue";
import CapabilitySection from "../../components/showcase/CapabilitySection.vue";
import KnowledgeBaseMap from "../../components/showcase/KnowledgeBaseMap.vue";
import AudienceSplitSection from "../../components/showcase/AudienceSplitSection.vue";
import AgentPipeline from "../../components/showcase/AgentPipeline.vue";
import EvidenceTrustSection from "../../components/showcase/EvidenceTrustSection.vue";
import ShowcaseFooter from "../../components/showcase/ShowcaseFooter.vue";

let cards = [];

const onMouseMove = (e) => {
  cards.forEach((card) => {
    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    card.style.setProperty("--mouse-x", `${x}px`);
    card.style.setProperty("--mouse-y", `${y}px`);
  });
};

onMounted(() => {
  cards = document.querySelectorAll(".sc-card-glow");
  window.addEventListener("mousemove", onMouseMove, { passive: true });
});

onUnmounted(() => {
  window.removeEventListener("mousemove", onMouseMove);
});

useSmoothScroll();

const marqueeSecondary = [
  "企业端研发决策",
  "个人端体质食养",
  "图谱先召回",
  "证据摘要可追溯",
  "LLM 异常本地兜底",
  "CAN_REPLACE 替代映射",
  "君臣佐使组方",
  "GB2760 合规边界",
];
</script>
