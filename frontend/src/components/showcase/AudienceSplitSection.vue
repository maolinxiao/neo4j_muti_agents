<template>
  <section id="audience" class="sc-section sc-section--soft audience-section">
    <ShowcaseSectionDecor tone="gold" />
    <ShowcaseReveal3D variant="up" stagger>
      <div class="showcase-container section-inner">
        <ShowcaseSectionHeader
          eyebrow="Use Cases"
          title="企业端与个人端分流"
          lead="同一图谱底座，服务研发决策与个人食养两类路径——点击角色，看问题如何被分类与回答。"
        />
        <div ref="stageEl" class="mascot-stage">
          <button
            type="button"
            class="mascot mascot--enterprise"
            :class="{ active: activeSide === 'enterprise' }"
            :aria-pressed="activeSide === 'enterprise'"
            @click="switchSide('enterprise')"
          >
            <MascotEnterprise class="mascot-svg" />
            <span class="mascot-name">企业研究员</span>
            <span class="mascot-sub">Enterprise · 研发协同</span>
          </button>
          <div class="mascot-bridge" aria-hidden="true">
            <AudienceFlowScene v-if="useScene3d" ref="flowScene" class="classifier-scene" />
            <div ref="coreEl" class="classifier-core">
              <span>Intent Router</span>
              <strong>问题分类器</strong>
            </div>
          </div>
          <button
            type="button"
            class="mascot mascot--personal"
            :class="{ active: activeSide === 'personal' }"
            :aria-pressed="activeSide === 'personal'"
            @click="switchSide('personal')"
          >
            <MascotPersonal class="mascot-svg" />
            <span class="mascot-name">养生人</span>
            <span class="mascot-sub">Personal · 体质食养</span>
          </button>
        </div>
        <transition name="panel-fade" mode="out-in">
          <article
            :key="activeSide"
            class="audience-panel sc-glass"
            :class="[activeSide, { 'route-hit': hitSide === activeSide }]"
          >
            <span class="panel-glare" aria-hidden="true" />
            <div class="panel-visual">
              <div class="panel-badge">{{ meta.badge }}</div>
              <h3>{{ meta.title }}</h3>
              <p class="panel-lead">{{ meta.lead }}</p>
              <span class="panel-stat">{{ meta.stat }}</span>
            </div>
            <div class="panel-content">
              <ul>
                <li
                  v-for="(item, i) in meta.items"
                  :key="item.title"
                  :class="{ lit: litList.includes(activeSide[0] + '-' + i) }"
                >
                  <span class="li-title">{{ item.title }}</span>
                  <small class="li-note">{{ item.note }}</small>
                </li>
              </ul>
              <div class="panel-samples" aria-label="示例问题">
                <button
                  v-for="s in meta.samples"
                  :key="s.text"
                  type="button"
                  class="aud-chip"
                  @click="routeSample(s, $event)"
                >
                  「{{ s.text }}」
                </button>
              </div>
            </div>
          </article>
        </transition>
      </div>
    </ShowcaseReveal3D>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";
import { gsap } from "gsap";
import { MotionPathPlugin } from "gsap/MotionPathPlugin";

import AudienceFlowScene from "./AudienceFlowScene.vue";
import MascotEnterprise from "./MascotEnterprise.vue";
import MascotPersonal from "./MascotPersonal.vue";
import ShowcaseReveal3D from "./ShowcaseReveal3D.vue";
import ShowcaseSectionDecor from "./ShowcaseSectionDecor.vue";
import ShowcaseSectionHeader from "./ShowcaseSectionHeader.vue";
import { useMediaQuery } from "../../composables/useTilt";
import { useShowcaseMotionPreference } from "../../composables/useShowcaseMotionPreference";

gsap.registerPlugin(MotionPathPlugin);

const { preferReducedMotion } = useShowcaseMotionPreference();
const isNarrow = useMediaQuery("(max-width: 767px)");
const useScene3d = computed(() => !preferReducedMotion.value && !isNarrow.value);

const sideMeta = {
  enterprise: {
    badge: "Enterprise",
    title: "企业端 · 研发协同",
    lead: "面向产品研发、方剂改造与合规决策，强调证据链与 Agent 协同输出。",
    stat: "6 类研发任务",
    items: [
      { title: "产品研发与配方生成", note: "从一句需求到一张组方" },
      { title: "名方/方剂药食同源化", note: "经典名方的现代化改造" },
      { title: "单味药替代与 CAN_REPLACE 映射", note: "非同源原料的科学替代" },
      { title: "风味优化与剂型工艺建议", note: "让功效好喝又好用" },
      { title: "竞品市场分析与功效标签对比", note: "看清市场再出手" },
      { title: "食品标准合规审查与宣传边界", note: "每一句宣传都有依据" },
    ],
    samples: [
      { text: "把四君子汤改成代餐粉", lit: [0, 1] },
      { text: "麻黄有什么可替代", lit: [2] },
      { text: "这个配方合规吗", lit: [5] },
    ],
  },
  personal: {
    badge: "Personal",
    title: "个人端 · 体质食养",
    lead: "面向体质辨识、食养推荐与安全提醒，强调个体适配与禁忌边界。",
    stat: "5 类食养路径",
    items: [
      { title: "九种体质辨识与问卷测评", note: "三十问读懂你的身体" },
      { title: "个性化食养推荐与适宜原料", note: "适合你的才是好的" },
      { title: "产品适配判断与场景匹配", note: "买对不买贵" },
      { title: "成品选购推荐与适用性评估", note: "货比三家，一问便知" },
      { title: "禁忌风险提醒与慎用边界", note: "安全面前不打折" },
    ],
    samples: [
      { text: "我是什么体质", lit: [0] },
      { text: "痰湿体质怎么吃", lit: [1, 2] },
      { text: "孕妇能吃人参吗", lit: [4] },
    ],
  },
};

const activeSide = ref("enterprise");
const meta = computed(() => sideMeta[activeSide.value]);

const stageEl = ref(null);
const coreEl = ref(null);
const flowScene = ref(null);
const hitSide = ref(null);
const litList = ref([]);
const routing = ref(false);

const switchSide = (side) => {
  if (routing.value || activeSide.value === side) return;
  activeSide.value = side;
  litList.value = [];
  hitSide.value = null;
};

/** 点击示例问题 → 胶囊飞行：问题 → 分类器（脉冲）→ 内容面板（点亮匹配条目） */
const routeSample = (sample, event) => {
  if (routing.value) return;
  routing.value = true;
  const side = activeSide.value;

  const stage = stageEl.value;
  const core = coreEl.value;
  const panel = stage?.parentElement?.querySelector(".audience-panel");
  const chip = event?.currentTarget;
  if (!stage || !core || !panel || !chip) {
    routing.value = false;
    return;
  }

  const stageRect = stage.getBoundingClientRect();
  const chipRect = chip.getBoundingClientRect();
  const coreRect = core.getBoundingClientRect();
  const panelRect = panel.getBoundingClientRect();
  const rel = (r) => ({
    x: r.left + r.width / 2 - stageRect.left,
    y: r.top + r.height / 2 - stageRect.top,
  });
  const from = rel(chipRect);
  const toCore = rel(coreRect);
  const toPanel = { x: panelRect.left + panelRect.width / 2 - stageRect.left, y: panelRect.top + 78 - stageRect.top };

  const finish = () => {
    hitSide.value = side;
    sample.lit.forEach((idx, k) => {
      window.setTimeout(() => {
        litList.value = [...litList.value, `${side[0]}-${idx}`];
      }, k * 130);
    });
    window.setTimeout(() => {
      litList.value = [];
      hitSide.value = null;
      routing.value = false;
    }, 1250);
  };

  // reduced-motion：跳过飞行，直接点亮 + 面板提示
  if (preferReducedMotion.value) {
    finish();
    return;
  }

  flowScene.value?.boostSide?.(side);
  flowScene.value?.pulse?.();

  const capsule = document.createElement("div");
  capsule.className = "route-capsule";
  capsule.textContent = `「${sample.text}」`;
  stage.appendChild(capsule);

  const tl = gsap.timeline({
    onComplete: () => {
      capsule.remove();
      flowScene.value?.boostSide?.(null);
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
      motionPath: { path: [{ x: from.x, y: from.y }, { x: (from.x + toCore.x) / 2, y: Math.min(from.y, toCore.y) - 70 }, { x: toCore.x, y: toCore.y }] },
    },
    0.1,
  );
  // 分类器收缩脉冲
  tl.to(core, { scale: 0.9, duration: 0.12, ease: "power2.in" }, ">-0.02");
  tl.to(core, { scale: 1.05, duration: 0.16, ease: "power2.out" });
  tl.to(core, { scale: 1, duration: 0.14, ease: "power2.out" });
  tl.call(() => flowScene.value?.pulse?.());
  // 第二程：分类器 → 内容面板
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
  tl.call(finish, null, ">-0.05");
};
</script>

<style scoped>
.audience-section {
  position: relative;
}

.section-inner {
  position: relative;
  z-index: 1;
}

/* —— 双卡通角色 + 分类器桥 —— */
.mascot-stage {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 170px 1fr;
  align-items: end;
  gap: 1rem;
  margin: 0.5rem 0 1.4rem;
}

.mascot {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.3rem;
  padding: 0.7rem 0.5rem 0.35rem;
  background: none;
  border: none;
  cursor: pointer;
  font-family: inherit;
  filter: grayscale(0.85) opacity(0.5);
  transform: scale(0.94);
  transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1), filter 0.35s ease, opacity 0.35s ease;
}

.mascot .mascot-svg {
  width: 120px;
  height: auto;
  transition: transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* 选中态：放大 + 全彩 + 底部光圈 + bounce */
.mascot.active {
  filter: none;
  opacity: 1;
  transform: translateY(-6px) scale(1.04);
}

.mascot.active .mascot-svg {
  animation: mascotBounce 0.55s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes mascotBounce {
  0% { transform: scale(0.9); }
  55% { transform: scale(1.09); }
  100% { transform: scale(1); }
}

.mascot::after {
  content: "";
  position: absolute;
  bottom: 6px;
  left: 50%;
  transform: translateX(-50%);
  width: 140px;
  height: 16px;
  border-radius: 50%;
  background: radial-gradient(ellipse, rgba(5, 150, 105, 0.35), transparent 70%);
  opacity: 0;
  transition: opacity 0.35s ease;
}

.mascot--enterprise.active::after {
  background: radial-gradient(ellipse, rgba(217, 119, 6, 0.32), transparent 70%);
  opacity: 1;
}

.mascot--personal.active::after {
  background: radial-gradient(ellipse, rgba(5, 150, 105, 0.35), transparent 70%);
  opacity: 1;
}

.mascot:hover:not(.active) {
  filter: grayscale(0.35) opacity(0.8);
  transform: translateY(-3px) scale(0.97);
}

.mascot-name {
  font-size: 1rem;
  font-weight: 750;
  color: var(--sc-text);
}

.mascot-sub {
  font-size: 0.7rem;
  letter-spacing: 0.06em;
  color: var(--sc-muted);
}

.mascot-bridge {
  position: relative;
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: visible;
}

.mascot-bridge .classifier-scene {
  position: absolute;
  inset: -20% -30%;
  z-index: 0;
}

.classifier-core {
  position: relative;
  z-index: 1;
  width: 116px;
  min-height: 116px;
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
  animation: classifierBreathe 4s ease-in-out infinite;
}

@keyframes classifierBreathe {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.015); }
}

.classifier-core::before {
  content: "";
  position: absolute;
  inset: -13px;
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

.classifier-core span {
  font-size: 0.62rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 650;
  color: var(--sc-accent);
}

.classifier-core strong {
  margin: 0.14rem 0;
  font-size: 0.92rem;
  color: var(--sc-text);
}

@keyframes classifierSpin {
  to { transform: rotate(360deg); }
}

/* —— 内容面板（单面板，随角色切换）—— */
.audience-panel {
  position: relative;
  border-radius: var(--sc-radius-md);
  overflow: hidden;
  background: var(--sc-bg-panel);
  border: 1px solid rgba(15, 23, 42, 0.08);
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

/* 命中面板描边光晕 */
.audience-panel.route-hit {
  border-color: rgba(5, 150, 105, 0.42);
  box-shadow: 0 0 0 3px rgba(5, 150, 105, 0.1), 0 14px 40px rgba(5, 150, 105, 0.13);
}

.audience-panel.enterprise.route-hit {
  border-color: rgba(217, 119, 6, 0.42);
  box-shadow: 0 0 0 3px rgba(217, 119, 6, 0.1), 0 14px 40px rgba(217, 119, 6, 0.13);
}

.panel-visual {
  padding: 2.2rem 2.5rem 1.3rem;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.4), transparent);
}

.panel-badge {
  display: inline-block;
  margin-bottom: 1.1rem;
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

.panel-stat {
  display: inline-flex;
  align-items: center;
  margin-top: 1.1rem;
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

.panel-content {
  padding: 0 2.5rem 2.2rem;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.audience-panel ul {
  list-style: none;
  margin: 0 0 auto;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
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

.audience-panel li:hover {
  transform: translateX(4px);
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

/* 面板切换过渡 */
.panel-fade-enter-active {
  transition: opacity 0.32s cubic-bezier(0.16, 1, 0.3, 1), transform 0.32s cubic-bezier(0.16, 1, 0.3, 1);
}

.panel-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.panel-fade-enter-from {
  opacity: 0;
  transform: translateY(14px) scale(0.99);
}

.panel-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

@media (max-width: 980px) {
  .mascot-stage {
    grid-template-columns: 1fr 120px 1fr;
    gap: 0.6rem;
  }

  .mascot .mascot-svg {
    width: 92px;
  }

  .mascot-bridge {
    height: 160px;
  }

  .audience-panel ul {
    grid-template-columns: 1fr;
  }

  .panel-visual {
    padding: 1.8rem 1.6rem 1rem;
  }

  .panel-content {
    padding: 0 1.6rem 1.8rem;
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
