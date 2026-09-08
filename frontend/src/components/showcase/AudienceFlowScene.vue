<template>
  <div ref="containerRef" class="audience-flow-scene" aria-hidden="true">
    <slot v-if="!ok" name="fallback" />
  </div>
</template>

<script setup>
/**
 * AudienceFlowScene — 企业/个人分流区中央路由核心的迷你 3D 场景（不接入页面，仅供版块引用）。
 *
 * props:
 *   - color:  主色调（默认 '#059669' 翡翠绿，与分流区 accent 一致）
 *   - accent: 次色调（默认 '#eab308' 金色，用于外环，呼应版块 gold 装饰）
 *
 * 场景构成：
 *   - 核心：IcosahedronGeometry(0.9, 1) 半透明青绿实体 + 同尺寸线框 + 中心小核球
 *   - 双环：TorusGeometry r=1.3 / r=1.6，不同倾角（pivot 旋转）绕各自法向自转
 *   - 分叉：两条 QuadraticBezierCurve3 从核心向左右两侧延伸（仅作粒子运动路径，
 *          不渲染静态线条）；每侧 9 个流动粒子（小球按 t 采样，端点 sin(πt) 淡出），
 *          流动节奏与核心自转共享同一时间基准
 *   容器高度由父级控制（约 220px），内容按容器纵横比自适应缩放。
 *   prefers-reduced-motion → 单帧静态；WebGL 失败 → 渲染空（插槽 fallback）
 *
 * expose: mount / dispose / webglOk（ok）/ staticFrame
 */
import { onMounted, onUnmounted, ref } from "vue";
import * as THREE from "three";

import { applySceneFit, useSectionThree } from "../../composables/useSectionThree";

const props = defineProps({
  color: { type: String, default: "#059669" },
  accent: { type: String, default: "#eab308" },
});

const containerRef = ref(null);

const WHITE = new THREE.Color("#ffffff");
const CAMERA_LIFT_Y = 0.35;
const CAMERA_DISTANCE_Z = 5.6;
const REQ_HALF = { w: 3.5, h: 1.8 }; // 分叉端点在 ±3.2 附近，留出光晕余量

let currentApi = null;

const _pos = new THREE.Vector3();

const buildScene = ({ scene, camera }) => {
  const teal = new THREE.Color(props.color);
  const gold = new THREE.Color(props.accent);

  const group = new THREE.Group();
  const coreGroup = new THREE.Group(); // 核心自转
  group.add(coreGroup);

  // —— 中央路由核心 ——
  const core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.9, 1),
    new THREE.MeshBasicMaterial({
      color: teal.clone().lerp(WHITE, 0.1),
      transparent: true,
      opacity: 0.3,
      depthWrite: false,
    }),
  );
  const coreWire = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.9, 1),
    new THREE.MeshBasicMaterial({
      color: teal.clone(),
      wireframe: true,
      transparent: true,
      opacity: 0.18,
      depthWrite: false,
    }),
  );
  const nucleus = new THREE.Mesh(
    new THREE.SphereGeometry(0.2, 24, 24),
    new THREE.MeshBasicMaterial({
      color: teal.clone().lerp(WHITE, 0.55),
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  coreGroup.add(core);
  coreGroup.add(coreWire);
  coreGroup.add(nucleus);

  // —— 双环（不同倾角自转）——
  const ring1Pivot = new THREE.Group();
  ring1Pivot.rotation.set(1.05, 0.28, 0);
  const ring1 = new THREE.Mesh(
    new THREE.TorusGeometry(1.3, 0.028, 8, 96),
    new THREE.MeshBasicMaterial({
      color: teal.clone().lerp(WHITE, 0.15),
      transparent: true,
      opacity: 0.5,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  ring1Pivot.add(ring1);

  const ring2Pivot = new THREE.Group();
  ring2Pivot.rotation.set(0.62, -0.5, 0.35);
  const ring2 = new THREE.Mesh(
    new THREE.TorusGeometry(1.6, 0.022, 8, 96),
    new THREE.MeshBasicMaterial({
      color: gold.clone(),
      transparent: true,
      opacity: 0.38,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  ring2Pivot.add(ring2);
  group.add(ring1Pivot);
  group.add(ring2Pivot);

  // —— 左右分叉曲线 + 流动粒子 ——
  const branches = [
    {
      curve: new THREE.QuadraticBezierCurve3(
        new THREE.Vector3(-0.55, 0.1, 0),
        new THREE.Vector3(-2.1, 1.05, -0.15),
        new THREE.Vector3(-3.2, -0.6, 0),
      ),
      color: teal,
    },
    {
      curve: new THREE.QuadraticBezierCurve3(
        new THREE.Vector3(0.55, 0.1, 0),
        new THREE.Vector3(2.1, 0.95, -0.15),
        new THREE.Vector3(3.2, -0.6, 0),
      ),
      color: gold,
    },
  ];
  const particles = [];
  branches.forEach((branch, side) => {
    for (let i = 0; i < 9; i += 1) {
      const mesh = new THREE.Mesh(
        new THREE.SphereGeometry(0.1, 12, 12),
        new THREE.MeshBasicMaterial({
          color: branch.color.clone().lerp(WHITE, 0.35),
          transparent: true,
          opacity: 0,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        }),
      );
      group.add(mesh);
      particles.push({ mesh, branch, phase: i / 9 + side * 0.05 });
    }
  });

  camera.position.set(0, CAMERA_LIFT_Y, CAMERA_DISTANCE_Z);
  camera.lookAt(0, 0, 0);

  const update = (delta, t) => {
    // 核心自转
    coreGroup.rotation.y += 0.18 * delta;
    coreWire.rotation.y += 0.26 * delta;
    coreWire.rotation.x -= 0.1 * delta;
    nucleus.scale.setScalar(1 + Math.sin(t * 2.2) * 0.12);
    // 双环绕各自法向自转（同一时间基准下与核心同节奏）
    ring1.rotation.z += 0.35 * delta;
    ring2.rotation.z -= 0.22 * delta;
    ring2Pivot.rotation.y += 0.05 * delta;
    // 粒子沿曲线流动，端点淡出
    particles.forEach(({ mesh, branch, phase }) => {
      const tt = (t * 0.16 + phase) % 1;
      branch.curve.getPoint(tt, _pos);
      mesh.position.copy(_pos);
      mesh.material.opacity = 0.85 * Math.sin(tt * Math.PI) + 0.05;
      const s = 0.85 + Math.sin(tt * Math.PI) * 0.4;
      mesh.scale.setScalar(s);
    });
  };

  const dispose = () => {};

  currentApi = { group, update, dispose, half: REQ_HALF };
  scene.add(group);
  return currentApi;
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

defineExpose({
  mount: sceneThree.mount,
  dispose: sceneThree.dispose,
  webglOk: ok,
  staticFrame: sceneThree.staticFrame,
});
</script>

<style scoped>
.audience-flow-scene {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 220px;
  overflow: hidden;
  pointer-events: none;
}

.audience-flow-scene :deep(canvas) {
  position: absolute;
  inset: 0;
  display: block;
  width: 100% !important;
  height: 100% !important;
  pointer-events: none;
}
</style>
