<template>
  <div ref="containerRef" class="use-case-scene" aria-hidden="true">
    <slot v-if="!ok" name="fallback" />
  </div>
</template>

<script setup>
/**
 * UseCaseScene — 三大核心能力卡片的迷你 3D 场景（不接入页面，仅供版块引用）。
 *
 * props:
 *   - variant: 'graph' | 'constellation' | 'pipeline'（默认 'graph'）
 *   - color:   主色调（默认 '#0d9488' 青绿），变体会围绕该色做明暗派生
 *
 * 行为：
 *   - graph:        7 颗半透明 additive 小球（r 0.35/0.45/0.55）+ 连线，整体 y 轴 0.25rad/s
 *                   缓慢自转，随容器鼠标移动产生 ±0.12rad 视差（window mousemove + 容器 rect 换算，
 *                   容器 pointer-events:none 也可生效）
 *   - constellation: 中心球 0.5 + 9 颗小球沿黄金角环带（纵向 0.5 压扁）分布，
 *                   缓慢自转 + 各球 0.92–1.08 相位错开呼吸
 *   - pipeline:     6 颗小球沿二次贝塞尔拱形等距排布，能量点（亮球 + RingGeometry 光晕）
 *                   沿曲线 t 0→1→0 往复循环
 *   三个变体共同遵守：prefers-reduced-motion → 单帧静态；WebGL 失败 → 渲染空（插槽 fallback 由外部放原 SVG）
 *
 * expose: mount / dispose / webglOk（ok）/ staticFrame
 */
import { onMounted, onUnmounted, ref, watch } from "vue";
import * as THREE from "three";

import { applySceneFit, useSectionThree } from "../../composables/useSectionThree";

const props = defineProps({
  variant: {
    type: String,
    default: "graph",
    validator: (v) => ["graph", "constellation", "pipeline"].includes(v),
  },
  color: { type: String, default: "#0d9488" },
});

const containerRef = ref(null);

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));
const WHITE = new THREE.Color("#ffffff");
const CAMERA_LIFT_Y = 0.2;
const CAMERA_DISTANCE_Z = 5.6;

/** 场景内容外接框（世界坐标半宽/半高），用于按容器比例自适应缩放 */
const REQ_HALF = {
  graph: { w: 2.35, h: 1.5 },
  constellation: { w: 1.55, h: 1.15 },
  pipeline: { w: 2.95, h: 1.6 },
};

let currentApi = null; // 当前场景 API（onResize 时重新 fit）

const buildGraph = ({ camera }) => {
  const accent = new THREE.Color(props.color);
  const palette = [
    accent.clone(),
    accent.clone().lerp(WHITE, 0.3),
    accent.clone().lerp(WHITE, 0.12),
    accent.clone().lerp(new THREE.Color("#0f172a"), 0.18),
  ];

  const group = new THREE.Group();
  const pivot = new THREE.Group(); // 鼠标视差层
  const spin = new THREE.Group(); // 自转层
  pivot.add(spin);
  group.add(pivot);

  const RADIUS = 2.0;
  const spheres = [];
  for (let i = 0; i < 7; i += 1) {
    const y = 1 - (i / 6) * 2;
    const r = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = GOLDEN_ANGLE * i;
    const mesh = new THREE.Mesh(
      new THREE.SphereGeometry([0.35, 0.45, 0.55][i % 3], 20, 20),
      new THREE.MeshBasicMaterial({
        color: palette[i % palette.length],
        transparent: true,
        opacity: [0.55, 0.42, 0.66][i % 3],
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    mesh.position.set(Math.cos(theta) * r * RADIUS, y * RADIUS * 0.62, Math.sin(theta) * r * RADIUS);
    mesh.userData.baseOpacity = mesh.material.opacity;
    mesh.userData.breathePhase = i * 0.85;
    spheres.push(mesh);
    spin.add(mesh);
  }

  const linkPairs = [
    [0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [6, 0], [0, 3], [1, 4], [2, 5],
  ];
  for (const [a, b] of linkPairs) {
    const geometry = new THREE.BufferGeometry().setFromPoints([
      spheres[a].position.clone(),
      spheres[b].position.clone(),
    ]);
    const material = new THREE.LineBasicMaterial({
      color: accent.clone().lerp(WHITE, 0.2),
      transparent: true,
      opacity: 0.26,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    spin.add(new THREE.Line(geometry, material));
  }

  // 容器 mousemove → ±0.12 rad 视差（挂在 window，容器 pointer-events 无关）
  const parallax = { tx: 0, ty: 0 };
  const onPointerMove = (event) => {
    const container = containerRef.value;
    if (!container) return;
    const rect = container.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    const nx = ((event.clientX - rect.left) / rect.width - 0.5) * 2;
    const ny = ((event.clientY - rect.top) / rect.height - 0.5) * 2;
    parallax.tx = Math.max(-1, Math.min(1, nx)) * 0.12;
    parallax.ty = Math.max(-1, Math.min(1, ny)) * 0.12;
  };
  window.addEventListener("mousemove", onPointerMove);

  camera.position.set(0, CAMERA_LIFT_Y, CAMERA_DISTANCE_Z);
  camera.lookAt(0, 0, 0);

  const update = (delta, t) => {
    spin.rotation.y += 0.25 * delta;
    const k = 1 - Math.exp(-3.5 * delta);
    pivot.rotation.x += (parallax.ty - pivot.rotation.x) * k;
    pivot.rotation.z += (-parallax.tx - pivot.rotation.z) * k;
    spheres.forEach((mesh) => {
      const breathe = 1 + Math.sin(t * 1.15 + mesh.userData.breathePhase) * 0.06;
      mesh.scale.setScalar(breathe);
      mesh.material.opacity = mesh.userData.baseOpacity * breathe;
    });
  };

  const dispose = () => {
    window.removeEventListener("mousemove", onPointerMove);
  };

  return { group, update, dispose, half: REQ_HALF.graph };
};

const buildConstellation = () => {
  const accent = new THREE.Color(props.color);

  const group = new THREE.Group();
  const spin = new THREE.Group();
  group.add(spin);

  const center = new THREE.Mesh(
    new THREE.SphereGeometry(0.5, 32, 32),
    new THREE.MeshBasicMaterial({
      color: accent.clone().lerp(WHITE, 0.18),
      transparent: true,
      opacity: 0.8,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  const centerWire = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.62, 1),
    new THREE.MeshBasicMaterial({
      color: accent.clone(),
      wireframe: true,
      transparent: true,
      opacity: 0.16,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  spin.add(center);
  spin.add(centerWire);

  const satellites = [];
  const count = 9;
  for (let i = 0; i < count; i += 1) {
    const y = (i / (count - 1)) * 2 - 1;
    const r = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = GOLDEN_ANGLE * i;
    const mesh = new THREE.Mesh(
      new THREE.SphereGeometry(0.14, 16, 16),
      new THREE.MeshBasicMaterial({
        color: accent.clone().lerp(WHITE, (i % 3) * 0.14),
        transparent: true,
        opacity: 0.78,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    // 黄金角环带：纵向（y）压扁 0.5
    mesh.position.set(Math.cos(theta) * r, y * 0.5, Math.sin(theta) * r).multiplyScalar(1.35);
    mesh.userData.breathePhase = i * 0.7;
    satellites.push(mesh);
    spin.add(mesh);
  }

  const update = (delta, t) => {
    spin.rotation.y += 0.3 * delta;
    centerWire.rotation.x -= 0.12 * delta;
    centerWire.rotation.z += 0.08 * delta;
    satellites.forEach((mesh) => {
      const s = 0.92 + 0.08 * (1 + Math.sin(t * 1.6 + mesh.userData.breathePhase)); // 0.92–1.08
      mesh.scale.setScalar(s);
    });
  };

  const dispose = () => {};

  return { group, update, dispose, half: REQ_HALF.constellation };
};

const buildPipeline = ({ camera }) => {
  const accent = new THREE.Color(props.color);

  const group = new THREE.Group();
  const curve = new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(-2.6, -0.55, 0),
    new THREE.Vector3(0, 1.2, 0),
    new THREE.Vector3(2.6, -0.55, 0),
  );

  const line = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(curve.getPoints(48)),
    new THREE.LineBasicMaterial({
      color: accent.clone().lerp(WHITE, 0.22),
      transparent: true,
      opacity: 0.2,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  group.add(line);

  const stations = [];
  for (let i = 0; i < 6; i += 1) {
    const t = i / 5;
    const mesh = new THREE.Mesh(
      new THREE.SphereGeometry(0.17, 18, 18),
      new THREE.MeshBasicMaterial({
        color: accent.clone().lerp(WHITE, i % 2 ? 0.24 : 0.06),
        transparent: true,
        opacity: 0.72,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    mesh.position.copy(curve.getPoint(t));
    mesh.userData.breathePhase = i * 0.9;
    group.add(mesh);
    stations.push(mesh);
  }

  const energy = new THREE.Mesh(
    new THREE.SphereGeometry(0.2, 20, 20),
    new THREE.MeshBasicMaterial({
      color: accent.clone().lerp(WHITE, 0.5),
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  const halo = new THREE.Mesh(
    new THREE.RingGeometry(0.3, 0.42, 40),
    new THREE.MeshBasicMaterial({
      color: accent.clone(),
      transparent: true,
      opacity: 0.35,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  group.add(energy);
  group.add(halo);

  const _pos = new THREE.Vector3();
  camera.position.set(0, CAMERA_LIFT_Y, CAMERA_DISTANCE_Z);
  camera.lookAt(0, 0, 0);

  const update = (delta, t) => {
    const cycle = (t * 0.32) % 2; // 单程约 3.1s
    const tt = cycle <= 1 ? cycle : 2 - cycle;
    curve.getPoint(tt, _pos);
    energy.position.copy(_pos);
    halo.position.copy(_pos);
    const pulse = 0.5 + 0.5 * Math.sin(t * 5);
    halo.material.opacity = 0.24 + pulse * 0.2;
    halo.scale.setScalar(0.9 + pulse * 0.2);
    stations.forEach((mesh) => {
      mesh.scale.setScalar(1 + Math.sin(t * 1.3 + mesh.userData.breathePhase) * 0.08);
    });
  };

  const dispose = () => {};

  return { group, update, dispose, half: REQ_HALF.pipeline };
};

const buildScene = ({ scene, camera }) => {
  const api = props.variant === "graph"
    ? buildGraph({ camera })
    : props.variant === "constellation"
      ? buildConstellation()
      : buildPipeline({ camera });
  currentApi = api;
  scene.add(api.group);
  return api;
};

const sceneThree = useSectionThree(containerRef, {
  createScene: buildScene,
  onResize: ({ ctx, width, height }) => {
    if (!currentApi || !ctx) return;
    applySceneFit(currentApi.group, ctx.camera, width, height, currentApi.half.w, currentApi.half.h);
  },
});

const { ok } = sceneThree;

onMounted(() => {
  sceneThree.mount();
});

onUnmounted(() => {
  sceneThree.dispose();
});

// variant / color 变化时整体重建（开发期切换方便，生产为静态 props）
watch(
  () => [props.variant, props.color],
  () => {
    if (!ok.value) return;
    sceneThree.dispose();
    sceneThree.mount();
  },
);

defineExpose({
  mount: sceneThree.mount,
  dispose: sceneThree.dispose,
  webglOk: ok,
  staticFrame: sceneThree.staticFrame,
});
</script>

<style scoped>
.use-case-scene {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  pointer-events: none;
}

.use-case-scene :deep(canvas) {
  position: absolute;
  inset: 0;
  display: block;
  width: 100% !important;
  height: 100% !important;
  pointer-events: none;
}
</style>
