<template>
  <section id="audience" class="sc-section sc-section--soft audience-section">
    <ShowcaseSectionDecor tone="gold" />
    <ShowcaseReveal3D variant="up" stagger>
      <div class="showcase-container section-inner">
        <ShowcaseSectionHeader
          eyebrow="Use Cases"
          title="企业端与个人端分流"
          lead="同一图谱底座，服务研发决策与个人食养两类路径——问题先分类，证据先召回。"
        />
        <div ref="tiltScope" class="audience-grid" @mousemove="tilt.onMove" @mouseleave="tilt.onLeave">
          <div class="reveal-stagger-item panel-wrap" :style="{ '--reveal-index': 0 }">
            <article class="audience-panel enterprise sc-glass sc-card-hover sc-card-glow">
              <span class="panel-glare" aria-hidden="true" />
              <div class="panel-visual">
                <div class="panel-badge">Enterprise</div>
                <h3>企业端 · 研发协同</h3>
                <p class="panel-lead">面向产品研发、方剂改造与合规决策，强调证据链与 Agent 协同输出。</p>
                <span class="panel-stat">6 类研发任务</span>
              </div>
              <div class="panel-content">
                <ul>
                  <li v-for="item in enterpriseItems" :key="item">{{ item }}</li>
                </ul>
                <blockquote>「这个配方是否好喝，适合做什么剂型」</blockquote>
              </div>
            </article>
          </div>
          <div class="reveal-stagger-item classifier-bridge" :style="{ '--reveal-index': 1 }" aria-hidden="true">
            <AudienceFlowScene v-if="useScene3d" class="classifier-scene" />
            <div class="classifier-core">
              <span>Intent Router</span>
              <strong>问题分类器</strong>
              <small>企业研发 / 个人食养</small>
            </div>
          </div>
          <div class="reveal-stagger-item panel-wrap" :style="{ '--reveal-index': 2 }">
            <article class="audience-panel personal sc-glass sc-card-hover sc-card-glow">
              <span class="panel-glare" aria-hidden="true" />
              <div class="panel-visual">
                <div class="panel-badge">Personal</div>
                <h3>个人端 · 体质食养</h3>
                <p class="panel-lead">面向体质辨识、食养推荐与安全提醒，强调个体适配与禁忌边界。</p>
                <span class="panel-stat">5 类食养路径</span>
              </div>
              <div class="panel-content">
                <ul>
                  <li v-for="item in personalItems" :key="item">{{ item }}</li>
                </ul>
                <blockquote>「孕妇能不能吃某某原料」</blockquote>
              </div>
            </article>
          </div>
        </div>
      </div>
    </ShowcaseReveal3D>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";

import AudienceFlowScene from "./AudienceFlowScene.vue";
import ShowcaseReveal3D from "./ShowcaseReveal3D.vue";
import ShowcaseSectionDecor from "./ShowcaseSectionDecor.vue";
import ShowcaseSectionHeader from "./ShowcaseSectionHeader.vue";
import { useMediaQuery, useTilt } from "../../composables/useTilt";
import { useShowcaseMotionPreference } from "../../composables/useShowcaseMotionPreference";

const { preferReducedMotion } = useShowcaseMotionPreference();
const isNarrow = useMediaQuery("(max-width: 767px)");
const useScene3d = computed(() => !preferReducedMotion.value && !isNarrow.value);

const enterpriseItems = [
  "产品研发与配方生成",
  "名方/方剂药食同源化",
  "单味药替代与 CAN_REPLACE 映射",
  "风味优化与剂型工艺建议",
  "竞品市场分析与功效标签对比",
  "食品标准合规审查与宣传边界",
];

const personalItems = [
  "九种体质辨识与问卷测评",
  "个性化食养推荐与适宜原料",
  "产品适配判断与场景匹配",
  "成品选购推荐与适用性评估",
  "禁忌风险提醒与慎用边界",
];

// —— 3D 倾斜：两个面板（mousemove 事件委托 + glare 跟随；reduced-motion 自动禁用）——
const tiltScope = ref(null);
const tilt = useTilt(tiltScope, {
  selector: ".audience-panel",
  maxDeg: 6,
  perspective: 900,
  liftY: -3,
  hoverScale: 1,
});
</script>

<style scoped>
.audience-section {
  position: relative;
}

.section-inner {
  position: relative;
  z-index: 1;
}

.audience-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 150px minmax(0, 1fr);
  gap: 1rem;
  align-items: stretch;
}

/* reveal 包装层：负责滚动显现 transform，面板 tilt 的可变 transform 不与其冲突 */
.panel-wrap {
  display: flex;
}

.panel-wrap .audience-panel {
  flex: 1;
  width: 100%;
}

.audience-panel {
  display: flex;
  flex-direction: column;
  border-radius: var(--sc-radius-md);
  height: 100%;
  position: relative;
  overflow: hidden;
  background: var(--sc-bg-panel);
  border: 1px solid rgba(15, 23, 42, 0.08);
  transform-style: preserve-3d;
  will-change: transform;
}

/* —— 渐变描边（hover 淡入）—— */
.audience-panel::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 1.5px;
  background: linear-gradient(135deg, var(--panel-border-a, rgba(217, 119, 6, 0.55)), rgba(255, 255, 255, 0.08) 45%, var(--panel-border-b, rgba(5, 150, 105, 0.5)));
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  mask-composite: exclude;
  opacity: 0;
  transition: opacity 0.4s ease;
  pointer-events: none;
  z-index: 2;
}

.audience-panel:hover::after {
  opacity: 1;
}

/* —— 高光 glare —— */
.panel-glare {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  border-radius: inherit;
  background: radial-gradient(
    320px circle at var(--tilt-gx, 50%) var(--tilt-gy, 50%),
    rgba(255, 255, 255, 0.3),
    rgba(255, 255, 255, 0) 55%
  );
  mix-blend-mode: overlay;
  opacity: 0;
  transition: opacity 0.35s ease;
}

.audience-panel.tilt-hover .panel-glare {
  opacity: 1;
}

/* —— 中央列：3D 分叉场景铺满中列，CSS 圆环叠于其上 —— */
.classifier-bridge {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  overflow: hidden;
}

.classifier-bridge .classifier-scene {
  position: absolute;
  inset: 0;
  z-index: 0;
  min-height: 0;
  min-width: 0;
}

/* 白色玻璃圆核 + accent 双环描边，统一浅色主题 */
.classifier-core {
  position: relative;
  z-index: 1;
  width: 132px;
  min-height: 132px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--sc-text);
  background:
    radial-gradient(circle at 35% 25%, rgba(255, 255, 255, 0.9), transparent 42%),
    rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(14px) saturate(1.3);
  -webkit-backdrop-filter: blur(14px) saturate(1.3);
  border: 1px solid rgba(5, 150, 105, 0.28);
  box-shadow:
    0 0 0 5px rgba(5, 150, 105, 0.06),
    0 18px 44px rgba(15, 23, 42, 0.12),
    0 1px 0 rgba(255, 255, 255, 0.95) inset;
  /* 呼吸缩放：±1.5%，4s，与分叉粒子流同节奏 */
  animation: classifierBreathe 4s ease-in-out infinite;
}

@keyframes classifierBreathe {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.015); }
}

.classifier-core::before {
  content: "";
  position: absolute;
  inset: -14px;
  border-radius: inherit;
  border: 1px dashed rgba(5, 150, 105, 0.35);
  animation: classifierSpin 22s linear infinite;
}

.classifier-core::after {
  content: "";
  position: absolute;
  inset: -6px;
  border-radius: inherit;
  border: 1px solid rgba(5, 150, 105, 0.16);
}

.classifier-core span,
.classifier-core small {
  font-size: 0.68rem;
  color: var(--sc-text-secondary);
}

.classifier-core span {
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 650;
  color: var(--sc-accent);
}

.classifier-core strong {
  margin: 0.15rem 0;
  font-size: 1rem;
  color: var(--sc-text);
}

@keyframes classifierSpin {
  to { transform: rotate(360deg); }
}

.panel-visual {
  padding: 2.5rem 2.5rem 1.5rem;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.4), transparent);
}

.panel-content {
  padding: 0 2.5rem 2.5rem;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.audience-panel::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
}

.enterprise::before {
  background: linear-gradient(90deg, var(--sc-highlight), transparent);
}

.personal::before {
  background: linear-gradient(90deg, var(--sc-accent), transparent);
}

.panel-badge {
  display: inline-block;
  margin-bottom: 1.25rem;
  padding: 0.35rem 0.85rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  background: rgba(0, 0, 0, 0.04);
  color: var(--sc-text-secondary);
}

.enterprise .panel-badge {
  color: var(--sc-highlight);
  background: rgba(217, 119, 6, 0.1);
}

.personal .panel-badge {
  color: var(--sc-accent);
  background: rgba(5, 150, 105, 0.1);
}

/* —— 统计徽章 —— */
.panel-stat {
  display: inline-flex;
  align-items: center;
  margin-top: 1.15rem;
  padding: 0.42rem 0.95rem;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 750;
  letter-spacing: 0.02em;
  border: 1px solid transparent;
}

.enterprise .panel-stat {
  color: var(--sc-highlight);
  background: rgba(217, 119, 6, 0.09);
  border-color: rgba(217, 119, 6, 0.22);
}

.personal .panel-stat {
  color: var(--sc-accent);
  background: rgba(5, 150, 105, 0.09);
  border-color: rgba(5, 150, 105, 0.22);
}

.audience-panel h3 {
  margin: 0 0 0.85rem;
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--sc-text);
}

.enterprise h3 {
  color: var(--sc-highlight);
}

.personal h3 {
  color: var(--sc-accent);
}

.panel-lead {
  margin: 0;
  color: var(--sc-text-secondary);
  font-size: 0.95rem;
  line-height: 1.6;
}

.audience-panel ul {
  margin: 0 0 auto;
  padding-left: 1.2rem;
  color: var(--sc-text);
  font-size: 0.95rem;
}

.audience-panel li {
  margin-bottom: 0.65rem;
  position: relative;
  transition: transform 0.28s cubic-bezier(0.22, 1, 0.36, 1), color 0.28s ease;
}

.audience-panel li::marker {
  color: var(--sc-muted);
}

/* 列表项 hover：整体平移 + 尾部箭头滑入 */
.audience-panel li::after {
  content: "→";
  display: inline-block;
  margin-left: 0.4rem;
  opacity: 0;
  transform: translateX(-6px);
  transition: opacity 0.28s ease, transform 0.28s cubic-bezier(0.22, 1, 0.36, 1);
  font-weight: 700;
}

.enterprise li::after {
  color: var(--sc-highlight);
}

.personal li::after {
  color: var(--sc-accent);
}

.audience-panel li:hover {
  transform: translateX(6px);
}

.audience-panel li:hover::after {
  opacity: 1;
  transform: translateX(0);
}

.audience-panel blockquote {
  margin: 2rem 0 0;
  padding: 1rem 1.25rem;
  border-radius: 8px;
  font-size: 0.9rem;
  color: var(--sc-text-secondary);
  background: rgba(0, 0, 0, 0.02);
  border-left: 3px solid var(--sc-accent);
}

.enterprise blockquote {
  border-left-color: var(--sc-highlight);
  background: rgba(217, 119, 6, 0.04);
}

.personal blockquote {
  border-left-color: var(--sc-accent);
  background: rgba(5, 150, 105, 0.04);
}

@media (max-width: 980px) {
  .audience-grid {
    grid-template-columns: 1fr;
  }

  .classifier-bridge {
    min-height: 130px;
  }
}
</style>
