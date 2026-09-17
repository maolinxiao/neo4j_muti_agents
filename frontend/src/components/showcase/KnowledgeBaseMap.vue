<template>
  <section id="knowledge-bases" class="sc-section sc-section--deep kb-section">
    <ShowcaseSectionDecor tone="blue" />
    <ShowcaseReveal3D variant="up" stagger>
      <div class="showcase-container kb-container">
        <ShowcaseSectionHeader
          eyebrow="Knowledge Graph"
          title="八类知识库 · 证据底座"
          lead="每张知识库表回答一类核心问题——原料能不能用、功效如何关联、风味是否可接受、如何替代、方剂怎样组成、产品处于什么市场、宣传是否合规、体质如何食养。"
        />
        <div class="kb-layout" @mouseenter="hoveringLayout = true" @mouseleave="hoveringLayout = false">
          <div class="kb-graph-panel sc-glass">
            <KnowledgeHoloScene v-if="useHolo3d" :kb="activeKb" class="kb-holo" @swipe="step">
              <template #fallback>
                <KbRadarSvg :active-id="activeId" :items="knowledgeBases" />
              </template>
            </KnowledgeHoloScene>
            <KbRadarSvg v-else :active-id="activeId" :items="knowledgeBases" />
            <div class="kb-dots" role="tablist" aria-label="切换知识库">
              <button
                v-for="kb in knowledgeBases"
                :key="kb.id"
                type="button"
                class="kb-dot"
                :class="{ active: activeId === kb.id }"
                :style="activeId === kb.id ? { background: kb.color, boxShadow: `0 0 10px ${kb.color}` } : {}"
                :aria-label="kb.name"
                @click="setActive(kb.id)"
              />
            </div>
            <transition name="kb-detail-fade">
              <div v-if="activeKb" class="kb-detail">
                <div class="kb-detail-head">
                  <span :style="{ color: activeKb.color }">{{ activeKb.id }} Evidence</span>
                  <strong>{{ activeKb.name }}</strong>
                </div>
                <p>{{ activeKb.detail }}</p>
                <span class="kb-hint">拖拽旋转 · 点击卡片或左右滑动切换</span>
              </div>
            </transition>
          </div>
          <div class="kb-list">
            <button
              v-for="(kb, index) in knowledgeBases"
              :key="kb.id"
              type="button"
              class="reveal-stagger-item kb-item sc-glass-subtle sc-card-hover sc-card-glow"
              :class="{ active: activeId === kb.id }"
              :style="{ '--reveal-index': index }"
              @mouseenter="preview(kb.id)"
              @focus="setActive(kb.id)"
              @click="setActive(kb.id)"
            >
              <span class="kb-id" :style="{ color: kb.color }">{{ kb.id }}</span>
              <span class="kb-name">{{ kb.name }}</span>
              <span class="kb-purpose">{{ kb.purpose }}</span>
            </button>
          </div>
        </div>
      </div>
    </ShowcaseReveal3D>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";

import KnowledgeHoloScene from "./KnowledgeHoloScene.vue";
import KbRadarSvg from "./KbRadarSvg.vue";
import ShowcaseReveal3D from "./ShowcaseReveal3D.vue";
import ShowcaseSectionDecor from "./ShowcaseSectionDecor.vue";
import ShowcaseSectionHeader from "./ShowcaseSectionHeader.vue";
import { useMediaQuery } from "../../composables/useTilt";
import { useShowcaseMotionPreference } from "../../composables/useShowcaseMotionPreference";

const { preferReducedMotion } = useShowcaseMotionPreference();
const isNarrow = useMediaQuery("(max-width: 767px)");
// 全息球仅在桌面 + 非 reduced-motion 挂载（canvas 预算内的一枚，IO 离屏自动暂停）
const useHolo3d = computed(() => !preferReducedMotion.value && !isNarrow.value);

const activeId = ref("KB1");
const hoveringLayout = ref(false);
let previewTimer = null;
let tourTimer = null;

const palette = ["#6bc4a6", "#6a9ec4", "#c9a962", "#ec4899"];

const knowledgeBases = [
  {
    id: "KB1",
    name: "药食同源原料合法性库",
    purpose: "哪些原料能用",
    color: palette[0],
    weight: 1.0,
    entities: ["药食同源目录", "毒性风险", "配伍禁忌", "孕妇慎用", "新食品原料"],
    detail: "定义原料是否进入药食同源目录、合法使用边界、毒性风险与配伍禁忌，是合规审查与风险提示的入口表。",
  },
  {
    id: "KB2",
    name: "功效-病症-性味归经库",
    purpose: "功效如何关联病症",
    color: palette[1],
    weight: 1.6,
    entities: ["功效分类", "病症主治", "四气五味", "归经", "禁忌规则"],
    detail: "组织功效分类、病症主治、中医性味归经与禁忌规则，支撑功效预测、方剂分析与证据召回。",
  },
  {
    id: "KB3",
    name: "风味评价库",
    purpose: "风味是否可接受",
    color: palette[2],
    weight: 0.8,
    entities: ["苦味", "涩感", "香气层次", "药味风险", "接受度"],
    detail: "记录苦味、涩感、药味风险、香气层次与综合接受度，支撑产品风味评估与优化决策。",
  },
  {
    id: "KB4",
    name: "单味药替代评分库",
    purpose: "非同源原料如何替",
    color: palette[0],
    weight: 0.7,
    entities: ["CAN_REPLACE", "替代评分", "非同源原料", "禁忌排除"],
    detail: "维护 CAN_REPLACE 替代评分与多维映射关系，支撑方剂药食同源化改造时的取舍说明。",
  },
  {
    id: "KB5",
    name: "名方/方剂知识库",
    purpose: "经典方如何组成",
    color: palette[1],
    weight: 1.1,
    entities: ["君臣佐使", "方剂组成", "名方出处", "功效主治"],
    detail: "收录名方来源、方剂组成、君臣佐使结构与功效主治，是组方设计与改造的结构化依据。",
  },
  {
    id: "KB6",
    name: "产品与市场库",
    purpose: "产品处于什么市场",
    color: palette[2],
    weight: 0.9,
    entities: ["品牌剂型", "消费场景", "卖点标签", "竞品对照"],
    detail: "覆盖产品档案、品牌剂型、消费场景、卖点标签与竞品对照，支撑市场分析与定位判断。",
  },
  {
    id: "KB7",
    name: "食品标准合规库",
    purpose: "宣传与标签是否合规",
    color: palette[3],
    weight: 0.9,
    entities: ["药食同源目录", "GB2760", "GB7718", "宣传边界", "禁用表述"],
    detail: "汇聚药食同源目录、GB2760/GB7718 与宣传边界规则，定义禁用、慎用表述与审查依据。",
  },
  {
    id: "KB8",
    name: "体质辨识与食养规则库",
    purpose: "不同体质如何食养",
    color: palette[1],
    weight: 1.0,
    entities: ["九种体质", "评分规则", "食养方向", "慎用原料"],
    detail: "包含九种体质问卷、评分规则、食养方向与慎用原料清单，支撑个体化辨识与推荐。",
  },
];

const activeKb = computed(() => knowledgeBases.find((kb) => kb.id === activeId.value));

/** 卡片 hover 预览：短暂停留才切换（避免扫过卡片连续 morph） */
const preview = (id) => {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(() => {
    activeId.value = id;
  }, 260);
};

const setActive = (id) => {
  clearTimeout(previewTimer);
  activeId.value = id;
};

const step = (dir) => {
  const i = knowledgeBases.findIndex((kb) => kb.id === activeId.value);
  const n = (i + (dir === "next" ? 1 : -1) + knowledgeBases.length) % knowledgeBases.length;
  setActive(knowledgeBases[n].id);
};

// 自动巡游：无交互时每 6.8s 切下一库（仅全息球模式；hover 布局区/后台标签暂停）
onMounted(() => {
  tourTimer = setInterval(() => {
    if (useHolo3d.value && !hoveringLayout.value && !document.hidden) step("next");
  }, 6800);
});

onUnmounted(() => {
  clearTimeout(previewTimer);
  clearInterval(tourTimer);
});
</script>

<style scoped>
.kb-section {
  position: relative;
}

.kb-container {
  position: relative;
  z-index: 1;
}

.kb-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
  gap: 1.75rem;
  align-items: start;
}

.kb-graph-panel {
  position: sticky;
  top: 6rem;
  padding: 0.9rem;
  border-radius: var(--sc-radius-lg);
  text-align: center;
  color: #e5f8f1;
  background:
    radial-gradient(circle at 50% 40%, rgba(94, 234, 212, 0.16), transparent 42%),
    linear-gradient(145deg, rgba(5, 24, 20, 0.94), rgba(10, 18, 17, 0.9));
  border: 1px solid rgba(148, 216, 198, 0.2);
  box-shadow: 0 28px 70px rgba(10, 18, 17, 0.22);
  overflow: hidden;
}

.kb-graph-panel::before {
  content: "";
  position: absolute;
  inset: 0;
  background:
    linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.045) 1px, transparent 1px);
  background-size: 34px 34px;
  mask-image: radial-gradient(circle at 50% 42%, #000 0%, transparent 75%);
  pointer-events: none;
}

.kb-holo {
  height: 500px;
}

.kb-dots {
  position: relative;
  z-index: 3;
  display: flex;
  justify-content: center;
  gap: 0.55rem;
  margin-top: 0.55rem;
}

.kb-dot {
  width: 9px;
  height: 9px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: rgba(148, 163, 184, 0.38);
  cursor: pointer;
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), background 0.25s ease;
}

.kb-dot:hover {
  transform: scale(1.3);
}

.kb-dot.active {
  transform: scale(1.28);
}

/* 说明卡悬浮在球面板内底部，减少面板堆叠留白 */
.kb-detail {
  position: absolute;
  left: 1rem;
  right: 1rem;
  bottom: 3.4rem;
  z-index: 3;
  padding: 0.9rem 1.05rem 0.8rem;
  border-radius: 14px;
  text-align: left;
  background: rgba(8, 22, 19, 0.78);
  border: 1px solid rgba(148, 216, 198, 0.24);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  box-shadow: 0 14px 38px rgba(4, 12, 10, 0.35);
}

.kb-detail-head {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  margin-bottom: 0.4rem;
}

.kb-detail-head span {
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  white-space: nowrap;
}

.kb-detail-head strong {
  color: #f8fafc;
  font-size: 0.98rem;
}

.kb-detail p {
  margin: 0;
  color: rgba(229, 248, 241, 0.74);
  font-size: 0.84rem;
  line-height: 1.6;
}

.kb-hint {
  display: block;
  margin-top: 0.5rem;
  font-size: 0.7rem;
  color: rgba(229, 248, 241, 0.45);
}

.kb-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.kb-item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.35rem;
  width: 100%;
  min-height: 118px;
  padding: 1.2rem 1.25rem;
  border-radius: var(--sc-radius-md);
  color: var(--sc-text);
  text-align: left;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(15, 23, 42, 0.06);
  overflow: hidden;
  transition: border-color 0.25s ease, background 0.25s ease, transform 0.3s ease, box-shadow 0.3s ease;
}

/* active 卡片左侧 accent 竖条 */
.kb-item::after {
  content: "";
  position: absolute;
  left: 0;
  top: 12%;
  bottom: 12%;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--sc-accent);
  transform: scaleY(0);
  transform-origin: center;
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.kb-item.active::after {
  transform: scaleY(1);
}

.kb-item:hover,
.kb-item:focus,
.kb-item.active {
  outline: none;
  border-color: rgba(5, 150, 105, 0.2);
  background: rgba(5, 150, 105, 0.04);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.05);
}

.kb-id {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.05em;
}

.kb-name {
  font-size: 1.05rem;
  font-weight: 700;
}

.kb-purpose {
  font-size: 0.85rem;
  color: var(--sc-text-secondary);
}

.kb-detail {
  margin-top: 1.1rem;
  padding: 1rem 1.1rem;
  border-radius: 14px;
  text-align: left;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.11);
}

.kb-detail span {
  display: block;
  margin-bottom: 0.35rem;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.kb-detail strong {
  display: block;
  margin-bottom: 0.45rem;
  color: #f8fafc;
  font-size: 1rem;
}

.kb-detail p {
  margin: 0;
  color: rgba(229, 248, 241, 0.72);
  font-size: 0.86rem;
  line-height: 1.65;
}

.kb-detail-fade-enter-active,
.kb-detail-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.kb-detail-fade-enter-from,
.kb-detail-fade-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

@media (max-width: 1080px) {
  .kb-holo {
    height: 380px;
  }
}

@media (max-width: 900px) {
  .kb-layout {
    grid-template-columns: 1fr;
  }

  .kb-graph-panel {
    position: static;
  }

  .kb-list {
    grid-template-columns: 1fr;
  }
}
</style>
