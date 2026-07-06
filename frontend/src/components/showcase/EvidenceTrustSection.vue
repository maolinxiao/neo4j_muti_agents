<template>
  <section id="evidence" class="sc-section evidence-section">
    <div class="evidence-fade evidence-fade--top" aria-hidden="true" />
    <div class="evidence-fade evidence-fade--bottom" aria-hidden="true" />
    <ShowcaseSectionDecor tone="green" />
    <ShowcaseReveal3D variant="up" stagger>
      <div class="showcase-container section-inner">
        <ShowcaseSectionHeader
          eyebrow="Trust & Evidence"
          title="可信证据 · 图谱先行"
          lead="回答建立在图谱召回与证据整理之上，大模型负责结构化生成，异常时有本地兜底。"
        />
        <div class="evidence-grid">
          <div
            v-for="(item, index) in evidenceItems"
            :key="item.title"
            class="reveal-stagger-item evidence-item sc-glass-subtle sc-card-hover sc-card-glow"
            :style="{ '--reveal-index': index }"
          >
            <span class="evidence-num">{{ item.step }}</span>
            <div>
              <h3>{{ item.title }}</h3>
              <p>{{ item.description }}</p>
            </div>
          </div>
        </div>
        <div class="evidence-cta">
          <p>从问题理解到证据摘要，平台始终把可追溯图谱放在生成之前。</p>
          <router-link :to="{ name: 'login', query: { redirect: '/app' } }" class="showcase-btn showcase-btn-primary sc-btn-shine">
            进入工作台体验
          </router-link>
        </div>
      </div>
    </ShowcaseReveal3D>
  </section>
</template>

<script setup>
import ShowcaseReveal3D from "./ShowcaseReveal3D.vue";
import ShowcaseSectionDecor from "./ShowcaseSectionDecor.vue";
import ShowcaseSectionHeader from "./ShowcaseSectionHeader.vue";

const evidenceItems = [
  { step: "01", title: "图谱先召回", description: "基于 Neo4j KB1–KB8 子图检索，先组织实体、关系、路径与证据缺口。" },
  { step: "02", title: "证据摘要可追溯", description: "回答正文之外保留检索摘要与证据子图，让用户知道结论来自哪里。" },
  { step: "03", title: "合规边界前置", description: "禁忌、慎用和宣传边界来自 KB7 等规则库，研发建议不越过食品合规红线。" },
  { step: "04", title: "异常本地兜底", description: "模型调用失败时降级到本地图谱回答，问答与研发流程不因外部服务中断。" },
];
</script>

<style scoped>
.evidence-section {
  position: relative;
  color: #e5f8f1;
  background:
    radial-gradient(circle at 18% 18%, rgba(94, 234, 212, 0.14), transparent 34%),
    radial-gradient(circle at 82% 12%, rgba(217, 119, 6, 0.12), transparent 28%),
    linear-gradient(145deg, #071310, #0b1815 48%, #06100e);
  overflow: hidden;
}

.evidence-section::before {
  display: none;
}

/* 浅色正文与暗色段之间的渐变过渡带 */
.evidence-fade {
  position: absolute;
  left: 0;
  right: 0;
  height: 120px;
  pointer-events: none;
  z-index: 0;
}

.evidence-fade--top {
  top: 0;
  background: linear-gradient(180deg, var(--sc-bg-base, #f8f8f7) 0%, rgba(248, 248, 247, 0.4) 38%, transparent 100%);
}

.evidence-fade--bottom {
  bottom: 0;
  background: linear-gradient(0deg, var(--sc-bg-base, #f8f8f7) 0%, rgba(248, 248, 247, 0.35) 40%, transparent 100%);
}

.evidence-section::after {
  content: "";
  position: absolute;
  inset: 0;
  background:
    linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px);
  background-size: 40px 40px;
  mask-image: linear-gradient(180deg, transparent, #000 18%, #000 82%, transparent);
  pointer-events: none;
}

.section-inner {
  position: relative;
  z-index: 1;
}

.evidence-section :deep(.sc-eyebrow) {
  color: #6ee7b7;
}

.evidence-section :deep(.sc-section-head-title) {
  color: #f8fafc;
}

.evidence-section :deep(.sc-section-head-lead) {
  color: rgba(229, 248, 241, 0.72);
}

.evidence-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1rem;
}

.evidence-item {
  display: flex;
  flex-direction: column;
  gap: 1.05rem;
  padding: 1.35rem;
  border-radius: var(--sc-radius-md);
  height: 100%;
  background: rgba(255, 255, 255, 0.075);
  border: 1px solid rgba(255, 255, 255, 0.12);
  transition: border-color 0.3s ease, background 0.3s ease;
}

.evidence-item:hover {
  border-color: rgba(110, 231, 183, 0.34);
  background: rgba(255, 255, 255, 0.1);
}

.evidence-num {
  flex-shrink: 0;
  font-family: var(--sc-font-display);
  font-size: 1.75rem;
  font-weight: 700;
  color: #6ee7b7;
  opacity: 0.9;
}

.evidence-item h3 {
  margin: 0 0 0.5rem;
  font-size: 1.15rem;
  font-weight: 700;
  color: #f8fafc;
}

.evidence-item p {
  margin: 0;
  font-size: 0.95rem;
  color: rgba(229, 248, 241, 0.68);
  line-height: 1.65;
}

.evidence-cta {
  margin-top: 2rem;
  padding: 1.25rem 1.4rem;
  border-radius: var(--sc-radius-md);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.evidence-cta p {
  margin: 0;
  color: rgba(229, 248, 241, 0.78);
}

@media (max-width: 980px) {
  .evidence-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .evidence-grid {
    grid-template-columns: 1fr;
  }

  .evidence-cta {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
