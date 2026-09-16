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
        <div
          ref="tiltScope"
          class="audience-grid"
          :class="hoveredSide ? `focus-${hoveredSide}` : null"
          @mousemove="tilt.onMove"
          @mouseleave="tilt.onLeave(); hoveredSide = null"
        >
          <div
            class="reveal-stagger-item panel-wrap panel-wrap--enterprise"
            :style="{ '--reveal-index': 0 }"
            @mouseenter="hoveredSide = 'enterprise'"
            @mouseleave="hoveredSide = null"
          >
            <article
              class="audience-panel enterprise sc-glass sc-card-hover sc-card-glow"
              :class="{ 'route-hit': hitSide === 'enterprise' }"
            >
              <span class="panel-glare" aria-hidden="true" />
              <div class="panel-visual">
                <div class="panel-badge">Enterprise</div>
                <h3>企业端 · 研发协同</h3>
                <p class="panel-lead">面向产品研发、方剂改造与合规决策，强调证据链与 Agent 协同输出。</p>
                <span class="panel-stat">6 类研发任务</span>
              </div>
              <div class="panel-content">
                <ul>
                  <li
                    v-for="(item, i) in enterpriseItems"
                    :key="item.title"
                    :class="{ lit: litList.includes(`e-${i}`) }"
                  >
                    <span class="li-title">{{ item.title }}</span>
                    <small class="li-note">{{ item.note }}</small>
                  </li>
                </ul>
                <div class="panel-samples" aria-label="示例问题">
                  <button
                    v-for="s in enterpriseSamples"
                    :key="s.text"
                    type="button"
                    class="aud-chip"
                    @click="routeSample(s, 'enterprise', $event)"
                  >
                    「{{ s.text }}」
                  </button>
                </div>
              </div>
            </article>
          </div>
          <div
            class="reveal-stagger-item classifier-bridge"
            :style="{ '--reveal-index': 1 }"
            aria-hidden="true"
          >
            <AudienceFlowScene ref="flowScene" v-if="useScene3d" class="classifier-scene" />
            <div ref="coreEl" class="classifier-core">
              <span>Intent Router</span>
              <strong>问题分类器</strong>
              <small>企业研发 / 个人食养</small>
            </div>
          </div>
          <div
            class="reveal-stagger-item panel-wrap panel-wrap--personal"
            :style="{ '--reveal-index': 2 }"
            @mouseenter="hoveredSide = 'personal'"
            @mouseleave="hoveredSide = null"
          >
            <article
              class="audience-panel personal sc-glass sc-card-hover sc-card-glow"
              :class="{ 'route-hit': hitSide === 'personal' }"
            >
              <span class="panel-glare" aria-hidden="true" />
              <div class="panel-visual">
                <div class="panel-badge">Personal</div>
                <h3>个人端 · 体质食养</h3>
                <p class="panel-lead">面向体质辨识、食养推荐与安全提醒，强调个体适配与禁忌边界。</p>
                <span class="panel-stat">5 类食养路径</span>
              </div>
              <div class="panel-content">
                <ul>
                  <li
                    v-for="(item, i) in personalItems"
                    :key="item.title"
                    :class="{ lit: litList.includes(`p-${i}`) }"
                  >
                    <span class="li-title">{{ item.title }}</span>
                    <small class="li-note">{{ item.note }}</small>
                  </li>
                </ul>
                <div class="panel-samples" aria-label="示例问题">
                  <button
                    v-for="s in personalSamples"
                    :key="s.text"
                    type="button"
                    class="aud-chip"
                    @click="routeSample(s, 'personal', $event)"
                  >
                    「{{ s.text }}」
                  </button>
                </div>
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
import { gsap } from "gsap";
import { MotionPathPlugin } from "gsap/MotionPathPlugin";

import AudienceFlowScene from "./AudienceFlowScene.vue";
import ShowcaseReveal3D from "./ShowcaseReveal3D.vue";
import ShowcaseSectionDecor from "./ShowcaseSectionDecor.vue";
import ShowcaseSectionHeader from "./ShowcaseSectionHeader.vue";
import { useMediaQuery, useTilt } from "../../composables/useTilt";
import { useShowcaseMotionPreference } from "../../composables/useShowcaseMotionPreference";

gsap.registerPlugin(MotionPathPlugin);

const { preferReducedMotion } = useShowcaseMotionPreference();
const isNarrow = useMediaQuery("(max-width: 767px)");
const useScene3d = computed(() => !preferReducedMotion.value && !isNarrow.value);

const enterpriseItems = [
  { title: "产品研发与配方生成", note: "从一句需求到一张组方" },
  { title: "名方/方剂药食同源化", note: "经典名方的现代化改造" },
  { title: "单味药替代与 CAN_REPLACE 映射", note: "非同源原料的科学替代" },
  { title: "风味优化与剂型工艺建议", note: "让功效好喝又好用" },
  { title: "竞品市场分析与功效标签对比", note: "看清市场再出手" },
  { title: "食品标准合规审查与宣传边界", note: "每一句宣传都有依据" },
];

const personalItems = [
  { title: "九种体质辨识与问卷测评", note: "三十问读懂你的身体" },
  { title: "个性化食养推荐与适宜原料", note: "适合你的才是好的" },
  { title: "产品适配判断与场景匹配", note: "买对不买贵" },
  { title: "成品选购推荐与适用性评估", note: "货比三家，一问便知" },
  { title: "禁忌风险提醒与慎用边界", note: "安全面前不打折" },
];

// —— 意图路由剧场：点击示例问题，胶囊飞向分类器再入对应面板，点亮匹配能力 ——
const enterpriseSamples = [
  { text: "把四君子汤改成代餐粉", lit: [0, 1] },
  { text: "麻黄有什么可替代", lit: [2] },
  { text: "这个配方合规吗", lit: [5] },
];
const personalSamples = [
  { text: "我是什么体质", lit: [0] },
  { text: "痰湿体质怎么吃", lit: [1, 2] },
  { text: "孕妇能吃人参吗", lit: [4] },
];

const tiltScope = ref(null);
const coreEl = ref(null);
const flowScene = ref(null);
const hoveredSide = ref(null);
const hitSide = ref(null);
const litList = ref([]);
const routing = ref(false);

const clearHover = () => {
  hoveredSide.value = null;
};

/** 点击示例问题 → 胶囊飞行：问题 → 分类器（脉冲）→ 目标面板（点亮匹配条目） */
const routeSample = (sample, side, event) => {
  if (routing.value) return;
  routing.value = true;
  hoveredSide.value = side;

  const grid = tiltScope.value;
  const core = coreEl.value;
  const panel = grid?.querySelector(`.panel-wrap--${side} .audience-panel`);
  const chip = event?.currentTarget;
  if (!grid || !core || !panel || !chip) {
    routing.value = false;
    return;
  }

  const gridRect = grid.getBoundingClientRect();
  const chipRect = chip.getBoundingClientRect();
  const coreRect = core.getBoundingClientRect();
  const panelRect = panel.getBoundingClientRect();
  const rel = (r) => ({
    x: r.left + r.width / 2 - gridRect.left,
    y: r.top + r.height / 2 - gridRect.top,
  });
  const from = rel(chipRect);
  const toCore = rel(coreRect);
  const toPanel = { x: panelRect.left + panelRect.width / 2 - gridRect.left, y: panelRect.top + 78 - gridRect.top };

  // reduced-motion：跳过飞行，直接点亮 + 面板提示
  if (preferReducedMotion.value) {
    applyHit(sample, side);
    return;
  }

  flowScene.value?.boostSide?.(side);
  flowScene.value?.pulse?.();

  const capsule = document.createElement("div");
  capsule.className = "route-capsule";
  capsule.textContent = `「${sample.text}」`;
  grid.appendChild(capsule);

  const tl = gsap.timeline({
    onComplete: () => {
      capsule.remove();
      flowScene.value?.boostSide?.(null);
      window.setTimeout(() => {
        litList.value = [];
        hitSide.value = null;
        routing.value = false;
      }, 1250);
    },
  });

  tl.set(capsule, { left: 0, top: 0, x: from.x, y: from.y, opacity: 0, scale: 0.85 });
  tl.to(capsule, { opacity: 1, scale: 1, duration: 0.22 }, 0);
  // 第一程：问题 → 分类器（弧线拱起）
  tl.to(
    capsule,
    {
      duration: 0.72,
      ease: "power2.inOut",
      motionPath: { path: [{ x: from.x, y: from.y }, { x: (from.x + toCore.x) / 2, y: Math.min(from.y, toCore.y) - 84 }, { x: toCore.x, y: toCore.y }] },
    },
    0.1,
  );
  // 分类器收缩脉冲
  tl.to(core, { scale: 0.9, duration: 0.12, ease: "power2.in" }, ">-0.02");
  tl.to(core, { scale: 1.05, duration: 0.16, ease: "power2.out" });
  tl.to(core, { scale: 1, duration: 0.14, ease: "power2.out" });
  tl.call(() => flowScene.value?.pulse?.());
  // 第二程：分类器 → 目标面板
  tl.to(
    capsule,
    {
      duration: 0.6,
      ease: "power2.out",
      motionPath: { path: [{ x: toCore.x, y: toCore.y }, { x: (toCore.x + toPanel.x) / 2, y: Math.min(toCore.y, toPanel.y) - 60 }, { x: toPanel.x, y: toPanel.y }] },
    },
    ">-0.05",
  );
  tl.to(capsule, { opacity: 0, scale: 0.7, duration: 0.16 }, ">-0.12");
  tl.call(() => applyHit(sample, side), null, ">-0.05");

  function applyHit(s, sd) {
    hitSide.value = sd;
    s.lit.forEach((idx, k) => {
      window.setTimeout(() => {
        litList.value = [...litList.value, `${sd === "enterprise" ? "e" : "p"}-${idx}`];
      }, k * 130);
    });
  }
};

// —— 3D 倾斜：两个面板（mousemove 事件委托 + glare 跟随；reduced-motion 自动禁用）——
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
  position: relative;
  display: flex;
  gap: 1rem;
  align-items: stretch;
}

/* hover 聚焦：悬停侧弹性展开，另一侧退后（仅宽屏） */
@media (min-width: 981px) {
  .panel-wrap {
    transition: flex-grow 0.5s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.35s ease;
  }

  .audience-grid.focus-enterprise .panel-wrap--enterprise,
  .audience-grid.focus-personal .panel-wrap--personal {
    flex-grow: 1.24;
  }

  .audience-grid.focus-enterprise .panel-wrap--personal,
  .audience-grid.focus-personal .panel-wrap--enterprise {
    flex-grow: 0.8;
    opacity: 0.78;
  }
}

/* reveal 包装层：负责滚动显现 transform，面板 tilt 的可变 transform 不与其冲突 */
.panel-wrap {
  display: flex;
  flex: 1 1 0;
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
  flex: 0 0 150px;
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
  list-style: none;
  margin: 0 0 auto;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  color: var(--sc-text);
  font-size: 0.93rem;
}

/* 能力条目卡：标题 + 升华小注，路由命中时点亮 */
.audience-panel li {
  position: relative;
  padding: 0.55rem 0.8rem 0.55rem 1.65rem;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.025);
  transition: transform 0.28s cubic-bezier(0.22, 1, 0.36, 1), background 0.28s ease, box-shadow 0.28s ease;
}

.audience-panel li::before {
  content: "";
  position: absolute;
  left: 0.72rem;
  top: 1rem;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--sc-muted);
  transition: background 0.28s ease, box-shadow 0.28s ease;
}

.audience-panel li .li-title {
  display: block;
  font-weight: 600;
  color: var(--sc-text);
}

.audience-panel li .li-note {
  display: block;
  margin-top: 0.12rem;
  font-size: 0.76rem;
  color: var(--sc-muted);
  transition: color 0.28s ease;
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

/* 路由命中：条目逐个点亮 */
.audience-panel li.lit {
  background: rgba(5, 150, 105, 0.09);
  transform: translateX(4px);
  box-shadow: 0 6px 18px rgba(5, 150, 105, 0.12);
}

.audience-panel li.lit::before {
  background: var(--sc-accent);
  box-shadow: 0 0 10px rgba(5, 150, 105, 0.6);
}

.audience-panel li.lit .li-note {
  color: var(--sc-text-secondary);
}

.enterprise li.lit {
  background: rgba(217, 119, 6, 0.08);
  box-shadow: 0 6px 18px rgba(217, 119, 6, 0.13);
}

.enterprise li.lit::before {
  background: var(--sc-highlight);
  box-shadow: 0 0 10px rgba(217, 119, 6, 0.55);
}

/* 命中面板描边光晕 */
.audience-panel.route-hit {
  border-color: rgba(5, 150, 105, 0.42);
  box-shadow: 0 0 0 3px rgba(5, 150, 105, 0.1), 0 14px 40px rgba(5, 150, 105, 0.13);
}

.audience-panel.enterprise.route-hit {
  border-color: rgba(217, 119, 6, 0.42);
  box-shadow: 0 0 0 3px rgba(217, 119, 6, 0.1), 0 14px 40px rgba(217, 119, 6, 0.13);
}

/* —— 示例问题 chips（路由剧场入口）—— */
.panel-samples {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 1.4rem;
}

.aud-chip {
  cursor: pointer;
  padding: 0.5rem 0.85rem;
  border-radius: 999px;
  border: 1px solid rgba(15, 23, 42, 0.1);
  background: rgba(255, 255, 255, 0.72);
  color: var(--sc-text-secondary);
  font-size: 0.82rem;
  font-family: inherit;
  transition: border-color 0.25s ease, color 0.25s ease, transform 0.25s ease, box-shadow 0.25s ease;
}

.aud-chip:hover {
  border-color: rgba(5, 150, 105, 0.42);
  color: var(--sc-accent);
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(5, 150, 105, 0.12);
}

.enterprise .aud-chip:hover {
  border-color: rgba(217, 119, 6, 0.45);
  color: var(--sc-highlight);
  box-shadow: 0 8px 20px rgba(217, 119, 6, 0.12);
}

@media (max-width: 980px) {
  .audience-grid {
    flex-direction: column;
  }

  .classifier-bridge {
    min-height: 130px;
  }

  .panel-samples {
    margin-top: 1.1rem;
  }
}
</style>

<style>
/* 路由胶囊由 JS 动态创建（无 scoped 属性），使用全局唯一类名 */
.route-capsule {
  position: absolute;
  z-index: 6;
  top: 0;
  left: 0;
  padding: 0.45rem 0.9rem;
  border-radius: 999px;
  border: 1px solid rgba(5, 150, 105, 0.35);
  background: rgba(255, 255, 255, 0.94);
  color: #1c1917;
  font-size: 0.82rem;
  font-weight: 600;
  white-space: nowrap;
  pointer-events: none;
  box-shadow: 0 10px 28px rgba(5, 150, 105, 0.18);
  will-change: transform, opacity;
}
</style>
