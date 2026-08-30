<template>
  <div ref="containerRef" class="agent-flow-scene" aria-hidden="true" />
</template>

<script setup>
/**
 * AgentFlowScene — 研发协同流程（六步 Agent）的迷你 3D 场景（不接入页面，仅供版块引用）。
 *
 * 数据接入（由 fe-ui 计算后传入，二选一）：
 *   1. props.nodes：六步节点 DOM 元素 refs 数组（组件内部取 getBoundingClientRect 换算中心坐标）
 *   2. expose.setNodes(rects)：外部直接传入节点中心坐标数组 [{ x, y }]（容器内局部 px）
 *
 * 场景构成：
 *   - CatmullRomCurve3 穿过六个节点（z=0 平面）的平滑曲线 + 节点标记小球
 *   - 能量脉冲（亮球 + RingGeometry 光晕）沿曲线循环流动
 *   - setActive(index)：脉冲加速约 1.6s，并向该节点靠拢——脉冲到达该节点附近时光晕增强
 *   - 容器 resize：重新按最新容器尺寸投影 rects 并 emit('resize')，由 fe-ui 补一次最新的
 *     setNodes（DOM 布局随宽度变化时坐标会漂移）
 *   - canvas 绝对定位在 z-index:0 层，pointer-events:none，不遮挡 DOM 节点
 *   prefers-reduced-motion → 单帧静态；WebGL 失败 → ok=false（组件外部 v-if 回退）
 *
 * expose: mount / dispose / setNodes / setActive / webglOk（ok）/ staticFrame
 */
import { onMounted, onUnmounted, ref } from "vue";
import * as THREE from "three";

import { applySceneFit, useSectionThree } from "../../composables/useSectionThree";

const props = defineProps({
  color: { type: String, default: "#6366f1" },
  nodes: { type: Array, default: null }, // DOM 元素 refs 数组（可选）
});
const emit = defineEmits(["resize"]);

const containerRef = ref(null);

const WHITE = new THREE.Color("#ffffff");
const CAMERA_DISTANCE_Z = 5.6;
const WORLD_BASE_SCALE_DIVISOR = 6; // min(w,h) / 6 → 基础世界缩放

/** 未接入节点时的默认六点布局（世界坐标，占位用） */
const DEFAULT_POINTS = [
  [-2.5, 0.8],
  [-1.5, -0.6],
  [-0.5, 0.5],
  [0.5, -0.7],
  [1.5, 0.5],
  [2.5, -0.5],
];

let currentApi = null; // { fitGroup, curve, curveLine, markers, pulse, halo, rects, points, progress, boostEnd, targetT, elapsed, half, ... }

const buildScene = ({ scene, camera }) => {
  camera.position.set(0, 0, CAMERA_DISTANCE_Z);
  camera.lookAt(0, 0, 0);

  const api = {
    fitGroup: new THREE.Group(),
    curve: null,
    curveLine: null,
    markers: [],
    pulse: null,
    halo: null,
    camera,
    rects: null,
    points: null,
    progress: 0,
    speed: 0.09,
    boostEnd: -1,
    targetT: -1,
    elapsed: 0,
    sizeW: 0,
    sizeH: 0,
    half: { w: 4, h: 2 },
  };

  const accent = new THREE.Color(props.color);

  api.curveLine = new THREE.Line(
    new THREE.BufferGeometry(),
    new THREE.LineBasicMaterial({
      color: accent.clone().lerp(WHITE, 0.24),
      transparent: true,
      opacity: 0.32,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  api.fitGroup.add(api.curveLine);

  api.pulse = new THREE.Mesh(
    new THREE.SphereGeometry(0.2, 20, 20),
    new THREE.MeshBasicMaterial({
      color: accent.clone().lerp(WHITE, 0.5),
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  api.pulse.userData.baseColor = accent.clone().lerp(WHITE, 0.5);
  api.pulse.userData.accent = accent.clone();
  api.halo = new THREE.Mesh(
    new THREE.RingGeometry(0.3, 0.44, 40),
    new THREE.MeshBasicMaterial({
      color: accent.clone(),
      transparent: true,
      opacity: 0.3,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  api.fitGroup.add(api.pulse);
  api.fitGroup.add(api.halo);

  scene.add(api.fitGroup);

  // 初始六点占位（fe-ui 后续通过 setNodes 覆盖）
  if (props.nodes && props.nodes.length >= 2) {
    const rects = props.nodes
      .map((node) => node && node.getBoundingClientRect && node.getBoundingClientRect())
      .filter(Boolean)
      .map((rect) => rectToLocalCenter(rect));
    api.rects = rects.length >= 2 ? rects : null;
  }
  rebuildCurve(api, camera);
  api.update = update; // 由 composable 逐帧驱动（在模块初始化完成后才执行）
  currentApi = api;
  return api;
};

const rectToLocalCenter = (rect) => {
  const container = containerRef.value;
  if (!container) return { x: 0, y: 0 };
  const box = container.getBoundingClientRect();
  return {
    x: rect.left + rect.width / 2 - box.left,
    y: rect.top + rect.height / 2 - box.top,
  };
};

const worldFromRects = (api) => {
  const w = api.sizeW || containerRef.value?.clientWidth || 600;
  const h = api.sizeH || containerRef.value?.clientHeight || 260;
  const base = Math.min(w, h) / WORLD_BASE_SCALE_DIVISOR;
  return api.rects.map((r) => new THREE.Vector3((r.x - w / 2) / base, (h / 2 - r.y) / base, 0));
};

const rebuildCurve = (api, camera) => {
  if (!api) return;
  const points =
    api.rects && api.rects.length >= 2
      ? worldFromRects(api)
      : DEFAULT_POINTS.map(([x, y]) => new THREE.Vector3(x, y, 0));

  api.points = points;
  api.curve = new THREE.CatmullRomCurve3(points, false, "catmullrom", 0.5);
  api.targetT = -1; // 节点布局变化后旧的激活目标失效

  const linePositions = api.curve.getPoints(64);
  api.curveLine.geometry.dispose();
  api.curveLine.geometry = new THREE.BufferGeometry().setFromPoints(linePositions);

  // 节点标记小球
  const accent = api.pulse.userData.accent;
  api.markers.forEach((marker) => api.fitGroup.remove(marker));
  api.markers = points.map((point, i) => {
    const marker = new THREE.Mesh(
      new THREE.SphereGeometry(0.16, 16, 16),
      new THREE.MeshBasicMaterial({
        color: accent.clone().lerp(WHITE, i % 3 === 1 ? 0.35 : 0.12),
        transparent: true,
        opacity: 0.55,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    marker.position.copy(point);
    marker.userData.phase = i * 1.05;
    api.fitGroup.add(marker);
    return marker;
  });

  // 外接框更新 + 自适应
  let maxX = 0;
  let maxY = 0;
  points.forEach((p) => {
    maxX = Math.max(maxX, Math.abs(p.x));
    maxY = Math.max(maxY, Math.abs(p.y));
  });
  api.half = { w: maxX + 0.8, h: maxY + 0.9 };
  const w = api.sizeW || containerRef.value?.clientWidth || 0;
  const h = api.sizeH || containerRef.value?.clientHeight || 0;
  if (w > 0 && h > 0) applySceneFit(api.fitGroup, camera, w, h, api.half.w, api.half.h);
};

const sceneThree = useSectionThree(containerRef, {
  createScene: buildScene,
  onResize: ({ ctx, width, height }) => {
    if (!currentApi || !ctx) return;
    currentApi.sizeW = width;
    currentApi.sizeH = height;
    rebuildCurve(currentApi, ctx.camera);
    emit("resize");
  },
});

const { ok, staticFrame } = sceneThree;

const _pos = new THREE.Vector3();

const update = (delta, elapsed) => {
  const api = currentApi;
  if (!api || !api.curve) return;
  api.elapsed = elapsed;

  // setActive 加速窗口（余量 1.2s 内线性衰减回 1）
  let speedMul = 1;
  const remaining = api.boostEnd - elapsed;
  if (remaining > 0) speedMul = 1 + 1.8 * Math.min(1, Math.max(0, remaining / 1.2));
  else if (api.boostEnd >= 0) {
    api.boostEnd = -1;
    api.targetT = -1;
  }

  api.progress += delta * api.speed * speedMul;
  const t = api.progress % 1;
  api.curve.getPoint(t, _pos);
  api.pulse.position.copy(_pos);
  api.halo.position.copy(_pos);
  api.halo.quaternion.copy(api.camera.quaternion); // billboard：光晕始终面向相机

  // 到达目标节点附近的亮度增强
  let intensity = 0;
  if (api.targetT >= 0 && remaining > 0) {
    const dist = Math.abs(t - api.targetT);
    const circ = Math.min(dist, 1 - dist);
    intensity = Math.exp(-circ * 14);
  }
  const pulseK = 1 - Math.exp(-8 * delta);
  api.pulse.material.color.lerp(
    api.pulse.userData.baseColor.clone().lerp(WHITE, intensity * 0.6),
    pulseK,
  );
  api.halo.material.opacity += (0.26 + intensity * 0.5 - api.halo.material.opacity) * pulseK;
  api.halo.material.color.lerp(
    api.pulse.userData.accent.clone().lerp(WHITE, intensity * 0.4),
    pulseK,
  );
  const s = 1 + intensity * 0.35 + Math.sin(elapsed * 6) * 0.08;
  api.pulse.scale.setScalar(s);
  api.halo.scale.setScalar(0.85 + intensity * 0.4 + Math.sin(elapsed * 6) * 0.1);

  api.markers.forEach((marker) => {
    marker.scale.setScalar(1 + Math.sin(elapsed * 1.2 + marker.userData.phase) * 0.1);
  });
};

onMounted(() => {
  sceneThree.mount();
});

onUnmounted(() => {
  sceneThree.dispose();
});

/**
 * 外部接入节点中心坐标（容器内局部 px）。
 * @param {Array<{x:number,y:number}>} rects 至少 2 个点
 */
const setNodes = (rects) => {
  if (!Array.isArray(rects) || rects.length < 2) return;
  currentApi.rects = rects.map((r) => ({ x: Number(r.x) || 0, y: Number(r.y) || 0 }));
  if (currentApi) rebuildCurve(currentApi, currentApi.camera);
};

/** 激活第 index 个节点：脉冲加速约 1.6s，靠近该节点时光晕增强 */
const setActive = (index) => {
  const api = currentApi;
  if (!api || !api.curve || !api.points || api.points.length < 2) return;
  const i = Math.max(0, Math.min(index, api.points.length - 1));
  api.targetT = i / (api.points.length - 1);
  api.boostEnd = api.elapsed + 1.6;
};

defineExpose({
  mount: sceneThree.mount,
  dispose: sceneThree.dispose,
  setNodes,
  setActive,
  webglOk: ok,
  staticFrame,
});
</script>

<style scoped>
/* canvas 垫底（z-index:0），DOM 节点由父级叠放其上，互不遮挡 */
.agent-flow-scene {
  position: relative;
  z-index: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  pointer-events: none;
}

.agent-flow-scene :deep(canvas) {
  position: absolute;
  inset: 0;
  z-index: 0;
  display: block;
  width: 100% !important;
  height: 100% !important;
  pointer-events: none;
}
</style>
