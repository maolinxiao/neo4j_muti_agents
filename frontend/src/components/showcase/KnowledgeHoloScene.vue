<template>
  <div
    ref="containerRef"
    class="holo-scene"
    aria-hidden="true"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
  >
    <div ref="labelLayer" class="holo-labels">
      <span
        v-for="(name, i) in activeEntities"
        :key="activeId + '-' + name"
        :ref="(el) => (labelEls[i] = el)"
        class="holo-label"
        :style="{ borderColor: labelBorderColor }"
      >{{ name }}</span>
    </div>
    <slot v-if="!ok" name="fallback" />
  </div>
</template>

<script setup>
/**
 * KnowledgeHoloScene — 八类知识库「全息投影球」（不接入页面，仅供 KB 版块引用）。
 *
 * 视觉构成：
 *   - 知识星座球：每 KB 一套确定性点云（Fibonacci 球面分布 + 实体簇聚焦），主题色
 *     additive 微光点 + 双倾斜旋转环 + 内层线框，缓慢自转 + 上下浮动
 *   - 全息舞台：球下椭圆投影光圈（双环 + 光盘）+ 垂直渐隐光锥 + 绕球上下扫描亮环
 *   - 实体标签：核心实体词 DOM 覆盖层，每帧投影跟随球面锚点，背面自动减淡
 *
 * 交互：
 *   - 拖拽旋转（带惯性衰减）；快速横向滑动 emit('swipe', 'prev' | 'next')
 *   - 切换 KB：点云 morph（旧位姿插值到新位姿 0.65s）+ 主题色过渡 + 标签中点换装
 *
 * 门控由外部负责（桌面 + 非 reduced-motion 才挂载）；WebGL 失败 → 渲染 #fallback 插槽。
 *
 * expose: mount / dispose / webglOk（ok）/ staticFrame
 */
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import * as THREE from "three";

import { applySceneFit, useSectionThree } from "../../composables/useSectionThree";

const props = defineProps({
  kb: { type: Object, required: true }, // { id, color, weight, entities }
});
const emit = defineEmits(["swipe"]);

const containerRef = ref(null);
const labelLayer = ref(null);
const labelEls = ref([]);
const activeEntities = ref([]);
const activeId = ref(props.kb.id);

const WHITE = new THREE.Color("#ffffff");
const CAMERA_POS = new THREE.Vector3(0, 0.55, 5.4);
const SPHERE_BASE_RADIUS = 1.38;
const POINT_COUNT = 1300;
const MORPH_DURATION = 0.65;

let currentApi = null;

// —— 确定性随机（种子来自 KB 编号，点云形状稳定可复现）——
const mulberry32 = (seed) => () => {
  seed |= 0;
  seed = (seed + 0x6d2b79f5) | 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
const hashSeed = (str) => {
  let h = 2166136261;
  for (const ch of String(str)) {
    h ^= ch.codePointAt(0);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
};

/** 实体名 → 球面锚点方向（标签与点云簇共用，词同向同） */
const entityDir = (name) => {
  const rnd = mulberry32(hashSeed(name));
  const y = rnd() * 1.5 - 0.75;
  const r = Math.sqrt(Math.max(0.05, 1 - y * y));
  const theta = rnd() * Math.PI * 2;
  return new THREE.Vector3(Math.cos(theta) * r, y, Math.sin(theta) * r).normalize();
};

/** KB → 点云坐标（70% 均匀 Fibonacci + 30% 向实体簇聚焦，词同向同） */
const genCloud = (kb) => {
  const rnd = mulberry32(hashSeed(kb.id));
  const radius = SPHERE_BASE_RADIUS + kb.weight * 0.2;
  const clusterDirs = (kb.entities || []).map((name) => entityDir(name));
  const arr = new Float32Array(POINT_COUNT * 3);
  for (let i = 0; i < POINT_COUNT; i += 1) {
    const y = 1 - (i / (POINT_COUNT - 1)) * 2;
    const r = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = 2.399963 * i + rnd() * 0.4;
    let vx = Math.cos(theta) * r;
    let vy = y;
    let vz = Math.sin(theta) * r;
    if (clusterDirs.length && rnd() < 0.3) {
      const dir = clusterDirs[Math.floor(rnd() * clusterDirs.length)];
      vx = dir.x + (rnd() - 0.5) * 0.38;
      vy = dir.y + (rnd() - 0.5) * 0.38;
      vz = dir.z + (rnd() - 0.5) * 0.38;
      const len = Math.max(0.2, Math.hypot(vx, vy, vz));
      vx /= len;
      vy /= len;
      vz /= len;
    }
    const j = radius * (1 + (rnd() - 0.5) * 0.14);
    arr[i * 3] = vx * j;
    arr[i * 3 + 1] = vy * j;
    arr[i * 3 + 2] = vz * j;
  }
  return arr;
};

const labelBorderColor = computed(() => `${props.kb.color}59`);

const buildScene = ({ scene, camera }) => {
  camera.position.copy(CAMERA_POS);
  camera.lookAt(0, -0.35, 0);

  const api = {
    fitGroup: new THREE.Group(),
    root: new THREE.Group(), // 拖拽/自转层（球体）
    stage: new THREE.Group(), // 全息舞台（不随拖拽）
    sizeW: 0,
    sizeH: 0,
    pxUnit: null,
    elapsed: 0,
    drag: { active: false, lastX: 0, lastY: 0, velY: 0, startX: 0, startY: 0, startT: 0, moved: 0 },
    idleT: 0,
    morph: { t: 1, from: null, to: null, fromColor: new THREE.Color(), toColor: new THREE.Color() },
    dirs: [],
    radiusNow: SPHERE_BASE_RADIUS + props.kb.weight * 0.2,
    tinted: [],
  };
  api.fitGroup.add(api.root);
  api.fitGroup.add(api.stage);

  const tint = (material) => {
    material.color.set(props.kb.color);
    api.tinted.push(material);
    return material;
  };

  // —— 点云球 ——
  const cloudGeo = new THREE.BufferGeometry();
  const cloudArr = genCloud(props.kb);
  cloudGeo.setAttribute("position", new THREE.BufferAttribute(cloudArr.slice(), 3));
  const cloudMat = new THREE.PointsMaterial({
    color: new THREE.Color(props.kb.color).lerp(WHITE, 0.25),
    size: 0.03,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.8,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const cloud = new THREE.Points(cloudGeo, cloudMat);
  api.root.add(cloud);
  api.cloud = { geo: cloudGeo, mat: cloudMat };

  // —— 线框 + 双倾斜环 ——
  const wire = new THREE.Mesh(
    new THREE.SphereGeometry(SPHERE_BASE_RADIUS + 0.12, 22, 14),
    new THREE.MeshBasicMaterial({
      color: new THREE.Color(props.kb.color).lerp(WHITE, 0.3),
      wireframe: true,
      transparent: true,
      opacity: 0.05,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  api.root.add(wire);
  api.wire = wire;

  const ring1 = new THREE.Mesh(
    new THREE.TorusGeometry(SPHERE_BASE_RADIUS + 0.24, 0.007, 8, 96),
    tint(new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.32, blending: THREE.AdditiveBlending, depthWrite: false })),
  );
  ring1.rotation.set(1.05, 0.2, 0.35);
  const ring2 = new THREE.Mesh(
    new THREE.TorusGeometry(SPHERE_BASE_RADIUS + 0.34, 0.005, 8, 96),
    tint(new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.2, blending: THREE.AdditiveBlending, depthWrite: false })),
  );
  ring2.rotation.set(-0.7, 0.5, -0.4);
  api.root.add(ring1);
  api.root.add(ring2);
  api.ring1 = ring1;
  api.ring2 = ring2;

  // —— 扫描亮环（沿球上下移动）——
  const scan = new THREE.Mesh(
    new THREE.TorusGeometry(SPHERE_BASE_RADIUS + 0.06, 0.012, 8, 80),
    tint(new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.3, blending: THREE.AdditiveBlending, depthWrite: false })),
  );
  scan.rotation.x = Math.PI / 2;
  api.root.add(scan);
  api.scan = scan;

  // —— 全息舞台：光圈 / 光盘 / 光锥 ——
  const stageY = -2.2;
  const mkRing = (inner, outer, opacity) => {
    const m = new THREE.Mesh(
      new THREE.RingGeometry(inner, outer, 80),
      tint(new THREE.MeshBasicMaterial({ transparent: true, opacity, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false })),
    );
    m.rotation.x = -Math.PI / 2;
    m.position.y = stageY;
    api.stage.add(m);
    return m;
  };
  mkRing(0.96, 1.02, 0.5);
  mkRing(1.28, 1.31, 0.26);
  const disc = new THREE.Mesh(
    new THREE.CircleGeometry(0.95, 64),
    tint(new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.1, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false })),
  );
  disc.rotation.x = -Math.PI / 2;
  disc.position.y = stageY;
  api.stage.add(disc);
  api.disc = disc;

  const cone = new THREE.Mesh(
    new THREE.CylinderGeometry(SPHERE_BASE_RADIUS + 0.2, 0.92, 2.2, 48, 1, true),
    tint(new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.05, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false })),
  );
  cone.position.y = stageY + 1.1;
  api.stage.add(cone);

  scene.add(api.fitGroup);

  // —— 尺寸自适应 + 像素换算（点尺寸屏幕恒定）——
  const refreshPxUnit = (w, h) => {
    if (w <= 0 || h <= 0) return;
    applySceneFit(api.fitGroup, camera, w, h, 2.5, 2.9);
    const visibleHalf = Math.tan((camera.fov * Math.PI) / 180 / 2) * camera.position.distanceTo(new THREE.Vector3(0, -0.35, 0));
    api.pxUnit = 1 / Math.max(1e-6, (api.fitGroup.scale.x || 1) * ((h * 0.5) / visibleHalf));
    cloudMat.size = Math.max(0.012, 2.6 * api.pxUnit);
  };
  refreshPxUnit(containerRef.value?.clientWidth || 0, containerRef.value?.clientHeight || 0);
  api.refreshPxUnit = refreshPxUnit;

  // —— 标签投影（DOM 覆盖层每帧跟随）——
  const setActiveLabels = (kb) => {
    activeEntities.value = kb.entities || [];
    api.dirs = (kb.entities || []).map((name) => entityDir(name));
    activeId.value = kb.id;
  };
  setActiveLabels(props.kb);
  api.setActiveLabels = setActiveLabels;

  const _anchor = new THREE.Vector3();
  const updateLabels = () => {
    const container = containerRef.value;
    if (!container) return;
    const w = container.clientWidth;
    const h = container.clientHeight;
    if (!w || !h) return;
    api.root.updateWorldMatrix(true, false);
    for (let i = 0; i < api.dirs.length; i += 1) {
      const el = labelEls.value[i];
      if (!el) continue;
      _anchor.copy(api.dirs[i]).multiplyScalar(api.radiusNow + 0.16).applyMatrix4(api.root.matrixWorld);
      const frontness = _anchor.z / Math.max(0.4, api.radiusNow);
      _anchor.project(camera);
      const x = (_anchor.x * 0.5 + 0.5) * w;
      const y = (-_anchor.y * 0.5 + 0.5) * h;
      const opacity = 0.14 + 0.86 * Math.min(1, Math.max(0, (frontness + 0.15) / 0.55));
      el.style.transform = `translate(-50%, -50%) translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
      el.style.opacity = opacity.toFixed(2);
    }
  };
  api.updateLabels = updateLabels;

  // —— morph：切换 KB 时点云插值 + 主题色过渡 ——
  api.beginMorph = (kb) => {
    const attr = api.cloud.geo.getAttribute("position");
    api.morph.from = attr.array.slice();
    api.morph.to = genCloud(kb);
    api.morph.fromColor.copy(api.cloud.mat.color);
    api.morph.toColor = new THREE.Color(kb.color).lerp(WHITE, 0.25);
    api.morph.t = 0;
    api.radiusNow = SPHERE_BASE_RADIUS + kb.weight * 0.2;
    api.pendingLabels = kb;
  };

  const easeInOutCubic = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
  const _blend = new THREE.Color();
  const applyMorph = (delta) => {
    if (api.morph.t >= 1) return;
    api.morph.t = Math.min(1, api.morph.t + delta / MORPH_DURATION);
    const e = easeInOutCubic(api.morph.t);
    const attr = api.cloud.geo.getAttribute("position");
    const { from, to } = api.morph;
    for (let i = 0; i < attr.array.length; i += 1) {
      attr.array[i] = from[i] + (to[i] - from[i]) * e;
    }
    attr.needsUpdate = true;
    _blend.copy(api.morph.fromColor).lerp(api.morph.toColor, e);
    api.tinted.forEach((m) => m.color.copy(_blend));
    if (api.morph.t >= 0.5 && api.pendingLabels) {
      api.setActiveLabels(api.pendingLabels);
      api.pendingLabels = null;
    }
  };

  const update = (delta, t) => {
    api.elapsed = t;
    applyMorph(delta);

    // 自转 / 惯性 / 拖拽
    if (!api.drag.active) {
      api.drag.velY *= Math.pow(0.06, delta); // 惯性衰减
      api.root.rotation.y += api.drag.velY * delta;
      api.idleT += delta;
      if (api.idleT > 3) api.root.rotation.y += 0.14 * delta; // 无操作缓慢自转
    }
    api.root.position.y = Math.sin(t * 0.8) * 0.06; // 呼吸浮动

    // 双环反向慢转 + 扫描环上下
    api.ring1.rotation.z += 0.18 * delta;
    api.ring2.rotation.y += 0.12 * delta;
    api.scan.position.y = Math.sin(t * 0.55) * (SPHERE_BASE_RADIUS * 0.72);
    api.scan.material.opacity = 0.2 + 0.16 * (0.5 + 0.5 * Math.sin(t * 0.55 + 1.2));
    api.disc.material.opacity = 0.08 + 0.05 * (0.5 + 0.5 * Math.sin(t * 1.4));

    updateLabels();
  };

  api.update = update;
  currentApi = api;
  return api;
};

// —— 拖拽旋转 + 横滑切换 ——
const onPointerDown = (event) => {
  const api = currentApi;
  if (!api || !ok.value) return;
  api.drag.active = true;
  api.drag.lastX = event.clientX;
  api.drag.lastY = event.clientY;
  api.drag.startX = event.clientX;
  api.drag.startY = event.clientY;
  api.drag.startT = performance.now();
  api.drag.moved = 0;
  api.drag.velY = 0;
  api.idleT = 0;
  containerRef.value?.setPointerCapture?.(event.pointerId);
};

const onPointerMove = (event) => {
  const api = currentApi;
  if (!api || !api.drag.active) return;
  const dx = event.clientX - api.drag.lastX;
  const dy = event.clientY - api.drag.lastY;
  api.drag.lastX = event.clientX;
  api.drag.lastY = event.clientY;
  api.drag.moved += Math.abs(dx) + Math.abs(dy);
  api.root.rotation.y += dx * 0.0055;
  api.root.rotation.x = Math.max(-0.5, Math.min(0.62, api.root.rotation.x + dy * 0.0032));
  api.drag.velY = dx * 0.22;
  api.idleT = 0;
};

const onPointerUp = (event) => {
  const api = currentApi;
  if (!api || !api.drag.active) return;
  api.drag.active = false;
  const dt = performance.now() - api.drag.startT;
  const dx = event.clientX - api.drag.startX;
  const dy = event.clientY - api.drag.startY;
  if (dt < 380 && Math.abs(dx) > 56 && Math.abs(dx) > Math.abs(dy) * 1.8) {
    emit("swipe", dx < 0 ? "next" : "prev");
  }
};

const sceneThree = useSectionThree(containerRef, {
  createScene: buildScene,
  onResize: ({ ctx, width, height }) => {
    if (!currentApi || !ctx) return;
    currentApi.sizeW = width;
    currentApi.sizeH = height;
    currentApi.refreshPxUnit(width, height);
  },
});

const { ok } = sceneThree;

// 切换 KB → 触发 morph（外部 activeId 变化）
watch(
  () => props.kb.id,
  () => {
    if (currentApi) currentApi.beginMorph(props.kb);
  },
);

onMounted(() => {
  sceneThree.mount();
});

onUnmounted(() => {
  sceneThree.dispose();
});

defineExpose({
  mount: sceneThree.mount,
  dispose: sceneThree.dispose,
  webglOk: ok,
  staticFrame: sceneThree.staticFrame,
});
</script>

<style scoped>
.holo-scene {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  touch-action: pan-y;
  cursor: grab;
}

.holo-scene:active {
  cursor: grabbing;
}

.holo-scene :deep(canvas) {
  position: absolute;
  inset: 0;
  display: block;
  width: 100% !important;
  height: 100% !important;
  pointer-events: none;
}

.holo-labels {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 2;
}

.holo-label {
  position: absolute;
  top: 0;
  left: 0;
  padding: 0.14rem 0.6rem;
  border-radius: 999px;
  border: 1px solid;
  background: rgba(6, 20, 17, 0.6);
  color: #e9fbf4;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.03em;
  white-space: nowrap;
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  will-change: transform, opacity;
  opacity: 0;
}
</style>
