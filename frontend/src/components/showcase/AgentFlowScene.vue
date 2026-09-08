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
 *   - CatmullRomCurve3 穿过六个节点（z=0 平面）的平滑曲线
 *   - 能量轨道：沿曲线的 TubeGeometry 双层管——内层实色管（vertexColors 绿→金渐变，
 *     呼应版块 token）+ 外层大半径 additive 辉光管；布局/容器尺寸变化时整管重建
 *   - 彗星脉冲：主彗星（亮头 + 7 节渐隐尾迹）沿轨道巡航，另有一枚暗色环境彗星
 *     相位差半圈，让轨道始终有生命感
 *   - setActive(index)：主彗星加速约 1.6s 并向该节点靠拢，贴近时光环增强，
 *     首次抵达触发一次节点处的扩散光环（billboard）
 *   - 节点标记：渐变色小光球，呼吸明灭
 *   - 尺寸自洽：applySceneFit 会把场景组缩放到任意容器纵横比（扁长容器 scale 会
 *     远小于 1），因此管径/彗星/光环全部以「屏幕像素 × pxUnit」反推世界半径，
 *     保证任何容器尺寸下屏幕观感恒定
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
  colorA: { type: String, default: "#059669" }, // 轨道起点（翡翠绿，--sc-accent）
  colorB: { type: String, default: "#d97706" }, // 轨道终点（琥珀金，--sc-highlight）
  nodes: { type: Array, default: null }, // DOM 元素 refs 数组（可选）
});
const emit = defineEmits(["resize"]);

const containerRef = ref(null);

const WHITE = new THREE.Color("#ffffff");
const CAMERA_DISTANCE_Z = 5.6;
const WORLD_BASE_SCALE_DIVISOR = 6; // min(w,h) / 6 → 基础世界缩放
const RAIL_TUBULAR_SEGMENTS = 140;
const RAIL_RADIAL_SEGMENTS = 10;
const TAIL_COUNT = 7;
const RING_DURATION = 0.7; // 到达光环扩散时长（s）
// 屏幕像素基准（fit 缩放后仍保持的观感尺寸）
const PX_RAIL_CORE = 2.6; // 轨道实色管半径
const PX_RAIL_GLOW = 8.5; // 轨道辉光管半径
const PX_COMET_HEAD = 6.5; // 主彗星头部半径
const PX_COMET_HEAD_DIM = 4.2; // 环境彗星头部半径
const PX_MARKER = 4.5; // 节点标记光球半径

/** 未接入节点时的默认六点布局（世界坐标，占位用） */
const DEFAULT_POINTS = [
  [-2.5, 0.8],
  [-1.5, -0.6],
  [-0.5, 0.5],
  [0.5, -0.7],
  [1.5, 0.5],
  [2.5, -0.5],
];

let currentApi = null; // { fitGroup, curve, railCore, railGlow, markers, comets, halo, ring, rects, points, progress, ... }

const _pos = new THREE.Vector3();
const _tailPos = new THREE.Vector3();
const _color = new THREE.Color();

/** TubeGeometry 顶点渐变色：顶点按 tubular 段生成，t = 段序 / 段数 */
const applyGradientColors = (geo, tubular, radial, cA, cB, whiteLerp) => {
  const count = geo.attributes.position.count;
  const colors = new Float32Array(count * 3);
  const start = cA.clone().lerp(WHITE, whiteLerp);
  const end = cB.clone().lerp(WHITE, whiteLerp);
  const stride = radial + 1;
  for (let i = 0; i < count; i += 1) {
    const t = Math.min(1, Math.floor(i / stride) / tubular);
    _color.copy(start).lerp(end, t);
    colors[i * 3] = _color.r;
    colors[i * 3 + 1] = _color.g;
    colors[i * 3 + 2] = _color.b;
  }
  geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
};

const buildScene = ({ scene, camera }) => {
  camera.position.set(0, 0, CAMERA_DISTANCE_Z);
  camera.lookAt(0, 0, 0);

  const api = {
    fitGroup: new THREE.Group(),
    curve: null,
    railCore: null,
    railGlow: null,
    markers: [],
    comets: [],
    halo: null,
    ring: null,
    camera,
    rects: null,
    points: null,
    progress: 0,
    speed: 0.09,
    boostEnd: -1,
    targetT: -1,
    elapsed: 0,
    ringT: 1,
    lastIntensity: 0,
    sizeW: 0,
    sizeH: 0,
    half: { w: 4, h: 2 },
    pxUnit: null, // 1 屏幕像素对应的世界单位（fit 后回填）
    cA: new THREE.Color(props.colorA),
    cB: new THREE.Color(props.colorB),
  };
  api.colorAt = (t, out) => out.copy(api.cA).lerp(api.cB, Math.min(1, Math.max(0, t)));

  // —— 到达光环（billboard，闲置时透明；半径 1 单位球，scale = px × pxUnit）——
  api.ring = new THREE.Mesh(
    new THREE.RingGeometry(0.82, 1, 40),
    new THREE.MeshBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  api.fitGroup.add(api.ring);

  // —— 主彗星光晕（跟随主彗星，接近目标节点时增强）——
  api.halo = new THREE.Mesh(
    new THREE.RingGeometry(0.82, 1, 40),
    new THREE.MeshBasicMaterial({
      color: api.colorA,
      transparent: true,
      opacity: 0.2,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  api.fitGroup.add(api.halo);

  // —— 彗星：主彗星 + 相位差半圈的暗色环境彗星（单位球，userData.baseR 按像素回填）——
  const buildComet = ({ dim, offset }) => {
    const head = new THREE.Mesh(
      new THREE.SphereGeometry(1, 18, 18),
      new THREE.MeshBasicMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: dim ? 0.45 : 0.95,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    api.fitGroup.add(head);
    const tail = [];
    for (let k = 1; k <= TAIL_COUNT; k += 1) {
      const seg = new THREE.Mesh(
        new THREE.SphereGeometry(1, 10, 10),
        new THREE.MeshBasicMaterial({
          color: 0xffffff,
          transparent: true,
          opacity: 0,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        }),
      );
      api.fitGroup.add(seg);
      tail.push(seg);
    }
    return { head, tail, dim, offset };
  };
  api.comets = [buildComet({ dim: false, offset: 0 }), buildComet({ dim: true, offset: 0.5 })];

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

/** fit 自适应后回填 pxUnit：屏幕像素 → 世界单位换算系数 */
const refreshPxUnit = (api, camera, w, h) => {
  if (w <= 0 || h <= 0) return;
  applySceneFit(api.fitGroup, camera, w, h, api.half.w, api.half.h);
  const visibleHalf = Math.tan((camera.fov * Math.PI) / 180 / 2) * CAMERA_DISTANCE_Z;
  const pxPerWorld = (h * 0.5) / visibleHalf;
  api.pxUnit = 1 / Math.max(1e-6, (api.fitGroup.scale.x || 1) * pxPerWorld);
};

/** 移除旧轨道管并按当前曲线重建（内层实色渐变管 + 外层辉光管，屏幕恒定粗细） */
const rebuildRail = (api) => {
  if (api.railCore) {
    api.railCore.geometry.dispose();
    api.fitGroup.remove(api.railCore);
    api.railCore = null;
  }
  if (api.railGlow) {
    api.railGlow.geometry.dispose();
    api.fitGroup.remove(api.railGlow);
    api.railGlow = null;
  }

  const unit = api.pxUnit || 0.045;
  const coreRadius = Math.max(PX_RAIL_CORE * unit, 0.006);
  const glowRadius = Math.max(PX_RAIL_GLOW * unit, 0.018);

  const coreGeo = new THREE.TubeGeometry(api.curve, RAIL_TUBULAR_SEGMENTS, coreRadius, RAIL_RADIAL_SEGMENTS, false);
  applyGradientColors(coreGeo, RAIL_TUBULAR_SEGMENTS, RAIL_RADIAL_SEGMENTS, api.cA, api.cB, 0.22);
  api.railCore = new THREE.Mesh(
    coreGeo,
    new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.72, depthWrite: false }),
  );

  const glowGeo = new THREE.TubeGeometry(api.curve, RAIL_TUBULAR_SEGMENTS, glowRadius, RAIL_RADIAL_SEGMENTS, false);
  applyGradientColors(glowGeo, RAIL_TUBULAR_SEGMENTS, RAIL_RADIAL_SEGMENTS, api.cA, api.cB, 0.35);
  api.railGlow = new THREE.Mesh(
    glowGeo,
    new THREE.MeshBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.14,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );

  api.fitGroup.add(api.railCore);
  api.fitGroup.add(api.railGlow);
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

  // 外接框更新 + 自适应 + 像素换算（管径/彗星尺寸依赖 pxUnit，须先于建轨）
  let maxX = 0;
  let maxY = 0;
  points.forEach((p) => {
    maxX = Math.max(maxX, Math.abs(p.x));
    maxY = Math.max(maxY, Math.abs(p.y));
  });
  api.half = { w: maxX + 0.8, h: maxY + 0.9 };
  const w = api.sizeW || containerRef.value?.clientWidth || 0;
  const h = api.sizeH || containerRef.value?.clientHeight || 0;
  refreshPxUnit(api, camera, w, h);

  rebuildRail(api);

  // 节点标记光球：沿轨道取渐变色，屏幕恒定半径
  const markerUnit = api.pxUnit || 0.045;
  api.markers.forEach((marker) => api.fitGroup.remove(marker));
  api.markers = points.map((point, i) => {
    const tt = i / (points.length - 1);
    const marker = new THREE.Mesh(
      new THREE.SphereGeometry(1, 16, 16),
      new THREE.MeshBasicMaterial({
        color: api.colorAt(tt, new THREE.Color()).lerp(WHITE, 0.15),
        transparent: true,
        opacity: 0.6,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    marker.position.copy(point);
    marker.userData.phase = i * 1.05;
    marker.userData.baseR = PX_MARKER * markerUnit;
    api.fitGroup.add(marker);
    return marker;
  });

  // 彗星头部/尾迹半径回填（几何为单位球）
  const cometUnit = api.pxUnit || 0.045;
  api.comets.forEach((comet) => {
    comet.head.userData.baseR = (comet.dim ? PX_COMET_HEAD_DIM : PX_COMET_HEAD) * cometUnit;
    comet.tail.forEach((seg, k) => {
      seg.userData.baseR =
        (comet.dim ? PX_COMET_HEAD_DIM : PX_COMET_HEAD) * 0.75 * (1 - (k + 1) / (TAIL_COUNT + 1)) * cometUnit;
    });
  });
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

/** 彗星沿曲线推进：头部取所在位置的轨道渐变色，尾迹逐节取样、渐隐 */
const updateComet = (api, comet, t, elapsed) => {
  const tt = (t - comet.offset + 1) % 1;
  api.curve.getPoint(tt, _pos);
  comet.head.position.copy(_pos);
  comet.head.material.color.copy(api.colorAt(tt, _color)).lerp(WHITE, comet.dim ? 0.35 : 0.55);
  comet.head.material.opacity = comet.dim ? 0.45 : 0.95;
  comet.head.scale.setScalar((comet.head.userData.baseR || 0.05) * (1 + Math.sin(elapsed * 6 + comet.offset * 6.2832) * 0.08));
  comet.tail.forEach((seg, k) => {
    const st = (tt - (k + 1) * 0.014 + 1) % 1;
    api.curve.getPoint(st, _tailPos);
    seg.position.copy(_tailPos);
    seg.material.color.copy(api.colorAt(st, _color));
    seg.material.opacity = (comet.dim ? 0.16 : 0.4) * (1 - (k + 1) / (TAIL_COUNT + 1));
    seg.scale.setScalar(seg.userData.baseR || 0.03);
  });
};

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

  updateComet(api, api.comets[0], t, elapsed);
  updateComet(api, api.comets[1], t, elapsed);

  // 光晕跟随主彗星，接近目标节点时增强（屏幕半径约 22px + 到达增益）
  const head = api.comets[0].head;
  api.halo.position.copy(head.position);
  api.halo.quaternion.copy(api.camera.quaternion); // billboard：光晕始终面向相机
  const unit = api.pxUnit || 0.045;

  let intensity = 0;
  if (api.targetT >= 0 && remaining > 0) {
    const dist = Math.abs(t - api.targetT);
    const circ = Math.min(dist, 1 - dist);
    intensity = Math.exp(-circ * 14);
  }
  const pulseK = 1 - Math.exp(-8 * delta);
  api.halo.material.opacity += (0.2 + intensity * 0.5 - api.halo.material.opacity) * pulseK;
  api.halo.material.color.lerp(api.colorAt(t, _color).lerp(WHITE, intensity * 0.4), pulseK);
  api.halo.scale.setScalar(unit * (24 + intensity * 13 + Math.sin(elapsed * 6) * 3));

  // 首次贴近目标节点：在节点处触发一次扩散光环（18px → 48px）
  // 位置/颜色在触发时锁定——targetT 会在加速窗口结束时被重置，不能延迟读取
  if (api.targetT >= 0 && intensity > 0.5 && api.lastIntensity <= 0.5) {
    api.ringT = 0;
    const idx = Math.max(0, Math.min(Math.round(api.targetT * (api.points.length - 1)), api.points.length - 1));
    api.ring.position.copy(api.points[idx]);
    api.ring.quaternion.copy(api.camera.quaternion);
    api.ring.material.color.copy(api.colorAt(api.targetT, _color)).lerp(WHITE, 0.3);
  }
  api.lastIntensity = intensity;
  if (api.ringT < 1) {
    api.ringT = Math.min(1, api.ringT + delta / RING_DURATION);
    api.ring.scale.setScalar(unit * (18 + api.ringT * 30));
    api.ring.material.opacity = 0.55 * (1 - api.ringT);
  } else {
    api.ring.material.opacity = 0;
  }

  api.markers.forEach((marker) => {
    marker.scale.setScalar((marker.userData.baseR || 0.035) * (1 + Math.sin(elapsed * 1.2 + marker.userData.phase) * 0.1));
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

/** 激活第 index 个节点：主彗星加速约 1.6s，贴近该节点时光环增强并触发扩散 */
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
