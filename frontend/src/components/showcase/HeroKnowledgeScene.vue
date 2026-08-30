<template>
  <div ref="containerRef" class="hero-knowledge-scene" aria-hidden="true" />
</template>

<script setup>
import * as THREE from "three";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { onMounted, onUnmounted, ref } from "vue";

import heroGraphData from "../../assets/showcase/data/hero-graph.json";
import heroInnerNetworks from "../../assets/showcase/data/hero-inner-networks.json";
import { heroColorByType, HERO_TYPE_LABELS } from "../../utils/heroGraphColors";
import { useShowcaseMotionPreference } from "../../composables/useShowcaseMotionPreference";

const containerRef = ref(null);
const { preferReducedMotion } = useShowcaseMotionPreference();

const SPHERE_RADIUS = 62;
const OUTER_KB_RADIUS = 82;
const ROTATION_SPEED = (Math.PI * 2) / 80;
const TILT_BASE = 0.16;
const TILT_WOBBLE = 0.07;
const CLOSE_CAMERA_DISTANCE = 44;
const CORE_CLOSE_CAMERA_DISTANCE = 64;
const CLOSE_CAMERA_LIFT = 8;
const CLOSE_LOOK_LIFT = 4.8;
const LINK_RADIUS_PADDING = 1.1;
const BASE_EXPOSURE = 0.8;
const BASE_BLOOM_STRENGTH = 0.16;
const LINK_SEGMENTS = 28;
const FOCUS_ZOOM_IN = 2.7;
const FOCUS_ZOOM_OUT = 2.6;
const FOCUS_REST = 0.9;
const PLATFORM_LABEL_FOCUS_FADE = 0.72;

// —— 特写遮挡修复（§3）：视线淡出 / 链接聚焦 / 标签分层 / 内部展开减熵 ——
const OCCLUSION_MIN_OPACITY = 0.02; // 遮挡节点与非相邻链接的淡出下限
const OCCLUSION_DEPTH_MARGIN = 1.25; // 焦点球前表面深度判定余量（×焦点半径）
const OCCLUSION_CONE_MARGIN = 1.35; // 视线遮挡判定锥半径余量（×焦点半径 + 节点当前半径）
const OCCLUSION_FADE_K = 3.2; // 遮挡权重 exp 平滑速率（常规动效）
const OCCLUSION_FADE_K_REDUCED = 9.0; // 减少动效偏好下更直接的淡出
const LINK_FOCUS_WEIGHT_THRESHOLD = 0.55; // 链接聚焦策略生效阈值（特写权重）
const LINK_FOCUS_MIN_OPACITY = 0.02; // 非相邻链接淡出下限
const LINK_FADE_K = 3.0; // 链接透明度 exp 平滑速率
const LINK_MID_FRONT_KEEP = 0.3; // 链路中点位于焦点球与相机之间时的保留比例
const LINK_MID_CONE = 2.4; // 链路中点遮挡判定锥半径（×焦点半径）
const DIM_OTHERS_FADE = 0.42; // 特写时非焦点节点基础淡化强度（增强后）
const DIM_OTHERS_FADE_REDUCED = 0.55; // 减少动效偏好下更激进的淡化
const LABEL_NON_FOCUS_FADE = 0.85; // 非焦点标签 opacity ×(1−spotWeight·0.85)
const LABEL_FOCUS_RENDER_ORDER = 210; // 特写焦点标签置顶渲染
const LABEL_DIST_SORT_BASE = 30; // 标签按相机距离分层的 renderOrder 基础值
const LABEL_DIST_SORT_RANGE = 140; // 标签分层 renderOrder 区间宽度（近者在上）
const LABEL_INNER_FADE_THRESHOLD = 0.7; // 焦点标签 innerReveal 超过后淡出防满屏
const LABEL_INNER_FADE_RANGE = 0.15; // 焦点标签淡出过渡区间
const LABEL_FOCUS_SCALE_BOOST = 0.2; // 焦点标签特写平滑放大系数
const INNER_FADE_THRESHOLD = 0.6; // 内部展开减熵：非焦点大球开始整体淡出
const INNER_FADE_RANGE = 0.3; // 减熵淡出过渡区间
const RING_SPOT_FADE = 0.6; // orbitRings 随特写权重淡出（再降一档）
const GYRO_SPOT_FADE = 0.78; // gyroRings 随特写权重淡出（再降一档）
const DUST_SPOT_FADE = 0.24; // dustField 随特写权重淡出（再降一档）
const BLOOM_CONVERGE_START = 0.86; // 特写极值段 bloom 收敛起点
const BLOOM_CONVERGE_RANGE = 0.14; // bloom 收敛过渡区间
const BLOOM_EXTREME_CONVERGE = 0.28; // 极值段 bloom 提升幅度收敛比例

// —— 特写内部三环轨道（§4）：去连线 + 三环布局 + 绽放动画 + 标签朝向 ——
const INNER_RING_COUNT = 3; // 轨道环数
const INNER_RING_TILTS = [-0.42, 0.08, 0.52]; // 各环倾角（rad），绕 X/Z 轴错开实现
const INNER_RING_TILT_AXES = ["x", "z", "x"]; // 各环倾角作用轴（X 或 Z 错开）
const INNER_RING_RADIUS_STEP = 0.18; // 第 i 环半径 = 基数 × (1 + 0.18·i)
const INNER_RING_SPEEDS = [0.09, 0.12, 0.15]; // 各环公转角速度（rad/s），交替方向
const INNER_RING_SPIN_REDUCED = 0.4; // 减少动效偏好下公转降速系数
const INNER_SAT_RADIUS = 1.05; // 卫星球体半径（原 1.15）
const INNER_SAT_RADIUS_PLATFORM = 0.9; // 平台卫星球体半径（原 0.96）
const INNER_SAT_BREATHE_AMPLITUDE = 0.1; // 卫星环面内相位错开轻呼吸幅度（±0.1）
const INNER_SAT_BREATHE_REDUCED = 0.5; // 减少动效偏好下呼吸幅度系数
const INNER_REVEAL_SCALE_MIN = 0.35; // 绽放展开起始 scale（→1.0）
const INNER_EXTREME_THRESHOLD = 0.85; // 特写极值段起点（innerReveal）
const INNER_EXTREME_EXPAND = 1.06; // 极值段整体外扩倍数
const SAT_OPACITY_REVEAL_START = 0.05; // 卫星 opacity 0→1 揭示起点
const SAT_OPACITY_REVEAL_RANGE = 0.6; // 卫星 opacity 揭示过渡区间
const SAT_LABEL_FACING_OFFSET = 0.1; // 标签朝向判定偏置（背对阈值）
const SAT_LABEL_FACING_RANGE = 0.28; // 标签朝向过渡区间
const SAT_LABEL_FACING_FADE_K = 5; // 标签朝向透明度平滑速率（≈0.2s）
const INNER_GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5)); // 环内黄金相位偏移

/** 关键画面轮播（入场结束后；不含 platform，避免与开场重复） */
const LOOP_SPOTLIGHT_ORDER = [
  "formula1",
  "herb1",
  "effect1",
  "constitution1",
  "compliance1",
  "product1",
  "kb3",
  "kb4",
];
const SPOTLIGHT_CYCLE = 10;
const PHASE_ROTATE_END = 0.16;
const PHASE_ZOOM_IN_END = 0.34;
const PHASE_HOLD_END = 0.48;
const PHASE_ZOOM_OUT_END = 0.78;
const FIRST_CYCLE_ROTATE_END = 0.04;
const LOOP_BRIDGE_HEAD_START = 0.28;

/** 开场：全景 → 推近特写 → 停留 → 拉回，全程可旋转 */
const INTRO_FOCUS = "platform";
const INTRO_ZOOM_IN = 2.4;
const INTRO_HOLD = 2.0;
const INTRO_ZOOM_OUT = 2.2;
const INTRO_TO_LOOP_BRIDGE = 1.1;
const INTRO_DURATION = INTRO_ZOOM_IN + INTRO_HOLD + INTRO_ZOOM_OUT;

const BASE_CAM = new THREE.Vector3(92, 26, 108);
const BASE_LOOK = new THREE.Vector3(0, 0, 0);
const UP_VECTOR = new THREE.Vector3(0, 1, 0);

const DEFAULT_SPOTLIGHT = {
  distance: CLOSE_CAMERA_DISTANCE,
  hold: 2.1,
  exposure: 0.94,
  bloomStrength: 0.28,
  labelLift: 4.8,
  linkArc: 7.5,
};

const SPOTLIGHT_CONFIG = {
  platform: {
    distance: CORE_CLOSE_CAMERA_DISTANCE,
    hold: 2.2,
    exposure: 0.92,
    bloomStrength: 0.24,
    labelLift: 6.2,
    linkArc: 8.5,
  },
  formula1: {
    distance: 40,
    hold: 2.4,
    exposure: 0.98,
    bloomStrength: 0.31,
    labelLift: 5.8,
    linkArc: 9.2,
  },
  herb1: {
    distance: 41,
    hold: 2.15,
    exposure: 0.95,
    bloomStrength: 0.28,
    labelLift: 5,
    linkArc: 8,
  },
  effect1: {
    distance: 41,
    hold: 2.15,
    exposure: 0.96,
    bloomStrength: 0.29,
    labelLift: 5.2,
    linkArc: 8,
  },
  constitution1: {
    distance: 40,
    hold: 2.15,
    exposure: 0.95,
    bloomStrength: 0.29,
    labelLift: 5.3,
    linkArc: 8,
  },
  compliance1: {
    distance: 40,
    hold: 2.15,
    exposure: 0.96,
    bloomStrength: 0.3,
    labelLift: 5.2,
    linkArc: 8,
  },
  product1: {
    distance: 42,
    hold: 2.1,
    exposure: 0.94,
    bloomStrength: 0.27,
    labelLift: 4.8,
    linkArc: 7.4,
  },
  kb3: {
    distance: 30,
    hold: 2,
    exposure: 0.98,
    bloomStrength: 0.32,
    labelLift: 3.7,
    linkArc: 6.8,
  },
  kb4: {
    distance: 30,
    hold: 2,
    exposure: 0.98,
    bloomStrength: 0.32,
    labelLift: 3.7,
    linkArc: 6.8,
  },
};

const getSpotlightConfig = (id) => SPOTLIGHT_CONFIG[id] || DEFAULT_SPOTLIGHT;

const LOOP_TOTAL_DURATION = LOOP_SPOTLIGHT_ORDER.reduce((total, id) => {
  const config = getSpotlightConfig(id);
  return total + FOCUS_ZOOM_IN + config.hold + FOCUS_ZOOM_OUT + FOCUS_REST;
}, 0);

let renderer = null;
let composer = null;
let bloomPass = null;
let scene = null;
let camera = null;
let graphGroup = null;
let nodeMap = new Map();
let nodeEntries = [];
let linkMeshes = [];
let particles = [];
let orbitRings = [];
let gyroRings = [];
let dustField = null;
let rafId = null;
let resizeObserver = null;
let visibilityObserver = null;
let clock = null;
let isPaused = false;
let accumulatedRotation = 0;
let prevSpotWeight = 0;
let rotWeightSmooth = 0;
let linkFocusSmooth = 0;
let labelEntries = [];
let labelDistances = new Float32Array(0);

const _worldPos = new THREE.Vector3();
const _worldPosB = new THREE.Vector3();
const _blendFocus = new THREE.Vector3();
const _viewDir = new THREE.Vector3();
const _camToNode = new THREE.Vector3();
const _linkDir = new THREE.Vector3();
const _linkMid = new THREE.Vector3();
const _viewDirNeg = new THREE.Vector3();
const _camDesired = new THREE.Vector3();
const _lookDesired = new THREE.Vector3();
const _closeCam = new THREE.Vector3();
const _camSmooth = new THREE.Vector3(92, 26, 108);
const _lookSmooth = new THREE.Vector3(0, 0, 0);
const _closeDir = new THREE.Vector3();
const _closeTangent = new THREE.Vector3();
const _closeLook = new THREE.Vector3();
const _viewRight = new THREE.Vector3();
const _desiredDir = new THREE.Vector3();
const _linkStart = new THREE.Vector3();
const _linkEnd = new THREE.Vector3();
const _linkControl = new THREE.Vector3();
const _linkOut = new THREE.Vector3();
const _linkCurvePoint = new THREE.Vector3();
const _nodePush = new THREE.Vector3();
const _focusViewDir = new THREE.Vector3();
const _nodeToCamRaw = new THREE.Vector3();
const _linkMidWorld = new THREE.Vector3();
const _linkMidCam = new THREE.Vector3();
const _labelWorldPos = new THREE.Vector3();
const _satLabelOffset = new THREE.Vector3();
const _satWorldPos = new THREE.Vector3();

const easeInOut = (t) => {
  const x = Math.max(0, Math.min(1, t));
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
};

const smootherStep = (t) => {
  const x = Math.max(0, Math.min(1, t));
  return x * x * x * (x * (x * 6 - 15) + 10);
};

const clamp01 = (x) => Math.max(0, Math.min(1, x));

/** 特写权重 → 内部子网络展开度（与主循环 innerReveal 同式） */
const innerRevealOf = (weight) => (weight > 0.02 ? easeInOut(clamp01((weight - 0.12) / 0.88)) : 0);

/** 主/次焦点半径按权重混合，供视线遮挡与链路中点遮挡判定 */
const blendFocusRadius = (primaryId, primaryWeight, secondaryId, secondaryWeight) => {
  let radius = 0;
  let total = 0;
  if (primaryWeight > 0.001) {
    const primary = nodeMap.get(primaryId);
    if (primary) {
      radius += (primary.userData.baseRadius || 4.8) * primaryWeight;
      total += primaryWeight;
    }
  }
  if (secondaryId && secondaryWeight > 0.001) {
    const secondary = nodeMap.get(secondaryId);
    if (secondary) {
      radius += (secondary.userData.baseRadius || 4.8) * secondaryWeight;
      total += secondaryWeight;
    }
  }
  return total > 0.001 ? radius / total : 4.8;
};

/**
 * 轮播段状态：推近从 HEAD_START 接续上一段的桥接权重；
 * 拉回后段与 REST 期间向下一焦点交叉过渡，镜头不完全归位，消除停顿感。
 */
const stateForFocus = (focusId, nextFocusId, localTime, phase) => {
  const config = getSpotlightConfig(focusId);
  const head = phase === "loop" ? LOOP_BRIDGE_HEAD_START : 0;
  const zoomOutStart = FOCUS_ZOOM_IN + config.hold;
  const segmentEnd = zoomOutStart + FOCUS_ZOOM_OUT + FOCUS_REST;

  let weight = 0;
  if (localTime < FOCUS_ZOOM_IN) {
    weight = head + (1 - head) * smootherStep(localTime / FOCUS_ZOOM_IN);
  } else if (localTime < zoomOutStart) {
    weight = 1;
  } else if (localTime < zoomOutStart + FOCUS_ZOOM_OUT) {
    weight = 1 - smootherStep((localTime - zoomOutStart) / FOCUS_ZOOM_OUT);
  }

  // 桥接窗口：拉回中后段开始向下一焦点过渡
  let secondaryFocusId = null;
  let secondaryWeight = 0;
  if (phase === "loop" && nextFocusId) {
    const bridgeStart = zoomOutStart + FOCUS_ZOOM_OUT * 0.45;
    if (localTime >= bridgeStart) {
      const bridgeT = smootherStep((localTime - bridgeStart) / (segmentEnd - bridgeStart));
      secondaryFocusId = nextFocusId;
      secondaryWeight = bridgeT * LOOP_BRIDGE_HEAD_START;
    }
  }

  return {
    focusId,
    weight,
    secondaryFocusId,
    secondaryWeight,
    phase,
    config,
    secondaryConfig: secondaryFocusId ? getSpotlightConfig(secondaryFocusId) : null,
  };
};

const getSpotlightState = (elapsed) => {
  const emptySecondary = { secondaryFocusId: null, secondaryWeight: 0 };

  if (elapsed < INTRO_DURATION) {
    const zoomOutStart = INTRO_ZOOM_IN + INTRO_HOLD;
    let weight = 0;
    if (elapsed < INTRO_ZOOM_IN) {
      weight = easeInOut(elapsed / INTRO_ZOOM_IN);
    } else if (elapsed < zoomOutStart) {
      weight = 1;
    } else {
      weight = 1 - easeInOut((elapsed - zoomOutStart) / INTRO_ZOOM_OUT);
    }

    const bridgeStart = INTRO_DURATION - INTRO_TO_LOOP_BRIDGE;
    if (elapsed >= bridgeStart) {
      const bridgeT = easeInOut((elapsed - bridgeStart) / INTRO_TO_LOOP_BRIDGE);
      const nextFocus = LOOP_SPOTLIGHT_ORDER[0];
      return {
        focusId: INTRO_FOCUS,
        weight: weight * (1 - bridgeT),
        secondaryFocusId: nextFocus,
        secondaryWeight: bridgeT * LOOP_BRIDGE_HEAD_START,
        config: getSpotlightConfig(INTRO_FOCUS),
        secondaryConfig: getSpotlightConfig(nextFocus),
        phase: "intro-bridge",
      };
    }

    return { focusId: INTRO_FOCUS, weight, ...emptySecondary, config: getSpotlightConfig(INTRO_FOCUS), phase: "intro" };
  }

  let loopT = (elapsed - INTRO_DURATION) % LOOP_TOTAL_DURATION;
  for (let i = 0; i < LOOP_SPOTLIGHT_ORDER.length; i += 1) {
    const focusId = LOOP_SPOTLIGHT_ORDER[i];
    const nextFocusId = LOOP_SPOTLIGHT_ORDER[(i + 1) % LOOP_SPOTLIGHT_ORDER.length];
    const config = getSpotlightConfig(focusId);
    const segment = FOCUS_ZOOM_IN + config.hold + FOCUS_ZOOM_OUT + FOCUS_REST;
    if (loopT <= segment) {
      return stateForFocus(focusId, nextFocusId, loopT, "loop");
    }
    loopT -= segment;
  }

  return stateForFocus(LOOP_SPOTLIGHT_ORDER[0], LOOP_SPOTLIGHT_ORDER[1], 0, "loop");
};

const blendFocusWorld = (primaryId, primaryWeight, secondaryId, secondaryWeight, out) => {
  out.set(0, 0, 0);
  let total = 0;
  if (primaryWeight > 0.001) {
    const node = nodeMap.get(primaryId);
    if (node) {
      node.getWorldPosition(_worldPos);
      out.addScaledVector(_worldPos, primaryWeight);
      total += primaryWeight;
    }
  }
  if (secondaryWeight > 0.001 && secondaryId) {
    const node = nodeMap.get(secondaryId);
    if (node) {
      node.getWorldPosition(_worldPosB);
      out.addScaledVector(_worldPosB, secondaryWeight);
      total += secondaryWeight;
    }
  }
  if (total > 0.001) out.divideScalar(total);
  return total;
};

const nodeSpotWeight = (nodeId, focusId, spotWeight, secondaryFocusId, secondaryWeight) => {
  if (nodeId === focusId) return spotWeight;
  if (nodeId === secondaryFocusId) return secondaryWeight;
  return 0;
};

const nodeRadius = (node) => {
  if (node.id === "platform") return 8;
  if (node.type === "KBMarker") return 2.8;
  return 4.8;
};

const spherePosition = (index, total, radius) => {
  const golden = Math.PI * (3 - Math.sqrt(5));
  const y = 1 - (index / Math.max(total - 1, 1)) * 2;
  const r = Math.sqrt(Math.max(0, 1 - y * y));
  const theta = golden * index;
  return [Math.cos(theta) * r * radius, y * radius * 0.85, Math.sin(theta) * r * radius];
};

const initWideCamera = () => {
  _camSmooth.copy(BASE_CAM);
  _lookSmooth.copy(BASE_LOOK);
  camera?.position.copy(_camSmooth);
  camera?.lookAt(_lookSmooth);
};

const createLabelSprite = (title, subtitle, colorHex) => {
  // 2x 画布分辨率，消除高分屏文字发糊
  const canvas = document.createElement("canvas");
  canvas.width = 1024;
  canvas.height = 320;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  const panel = ctx.createLinearGradient(168, 48, 856, 264);
  panel.addColorStop(0, "rgba(5, 16, 14, 0.82)");
  panel.addColorStop(1, "rgba(10, 27, 23, 0.62)");
  ctx.fillStyle = panel;
  ctx.strokeStyle = "rgba(226, 232, 240, 0.18)";
  ctx.lineWidth = 4;
  roundRect(ctx, 140, 40, 744, 232, 48);
  ctx.fill();
  ctx.stroke();

  const drawStroked = (text, x, y, font, fill, stroke = "rgba(6, 14, 12, 0.92)") => {
    ctx.font = font;
    ctx.lineWidth = 10;
    ctx.strokeStyle = stroke;
    ctx.strokeText(text, x, y);
    ctx.fillStyle = fill;
    ctx.fillText(text, x, y);
  };

  drawStroked(title, 512, 116, "600 88px 'PingFang SC', 'Microsoft YaHei', sans-serif", "#f1f5f9");
  drawStroked(subtitle, 512, 216, "500 56px 'PingFang SC', 'Microsoft YaHei', sans-serif", colorHex, "rgba(6, 14, 12, 0.88)");

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthWrite: false,
    opacity: 0.98,
  });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(22, 6.8, 1);
  sprite.renderOrder = 20;
  return sprite;
};

const roundRect = (ctx, x, y, width, height, radius) => {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + width, y, x + width, y + height, r);
  ctx.arcTo(x + width, y + height, x, y + height, r);
  ctx.arcTo(x, y + height, x, y, r);
  ctx.arcTo(x, y, x + width, y, r);
  ctx.closePath();
};

const createMiniLabel = (title, subtitle, colorHex) => {
  // 2x 画布分辨率
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 160;
  const ctx = canvas.getContext("2d");
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.font = "600 36px 'PingFang SC', 'Microsoft YaHei', sans-serif";
  ctx.lineWidth = 6;
  ctx.strokeStyle = "rgba(6, 14, 12, 0.9)";
  ctx.strokeText(title, 256, 56);
  ctx.fillStyle = "#e2e8f0";
  ctx.fillText(title, 256, 56);
  ctx.font = "500 28px 'PingFang SC', 'Microsoft YaHei', sans-serif";
  ctx.strokeText(subtitle, 256, 104);
  ctx.fillStyle = colorHex;
  ctx.fillText(subtitle, 256, 104);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false, opacity: 0.95 }),
  );
  sprite.scale.set(5.5, 1.7, 1);
  sprite.renderOrder = 25;
  return sprite;
};

/** 菲涅尔边缘光着色器：球体边缘发光、中心深邃，高端 3D 网站常用质感 */
const FRESNEL_VERTEX = `
  varying vec3 vNormal;
  varying vec3 vView;
  void main() {
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    vNormal = normalize(normalMatrix * normal);
    vView = normalize(-mvPosition.xyz);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const FRESNEL_FRAGMENT = `
  uniform vec3 uColor;
  uniform float uIntensity;
  uniform float uPower;
  varying vec3 vNormal;
  varying vec3 vView;
  void main() {
    float fresnel = pow(1.0 - abs(dot(normalize(vNormal), normalize(vView))), uPower);
    gl_FragColor = vec4(uColor, fresnel * uIntensity);
  }
`;

const createFresnelShell = (color, radius, intensity = 0.7, power = 2.6) => {
  const mesh = new THREE.Mesh(
    new THREE.SphereGeometry(radius, 48, 48),
    new THREE.ShaderMaterial({
      uniforms: {
        uColor: { value: new THREE.Color(color) },
        uIntensity: { value: intensity },
        uPower: { value: power },
      },
      vertexShader: FRESNEL_VERTEX,
      fragmentShader: FRESNEL_FRAGMENT,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  mesh.renderOrder = 8;
  return mesh;
};

const createGlowSphere = (colorHex, radius, isCore = false) => {
  const color = new THREE.Color(colorHex);
  const group = new THREE.Group();

  const core = new THREE.Mesh(
    new THREE.SphereGeometry(radius, 64, 64),
    new THREE.MeshPhysicalMaterial({
      color,
      emissive: color,
      emissiveIntensity: isCore ? 0.26 : 0.2,
      metalness: 0.46,
      roughness: 0.3,
      clearcoat: 0.65,
      clearcoatRoughness: 0.22,
      transparent: true,
      opacity: 0.88,
    }),
  );
  group.add(core);

  const shell = new THREE.Mesh(
    new THREE.SphereGeometry(radius * 1.02, 48, 48),
    new THREE.MeshPhysicalMaterial({
      color: 0x0a1210,
      transparent: true,
      opacity: 0.22,
      roughness: 0.9,
      metalness: 0.05,
      depthWrite: false,
    }),
  );
  group.add(shell);

  // 菲涅尔边缘辉光取代旧的整球 additive 光晕
  const glow = createFresnelShell(color, radius * 1.1, isCore ? 0.8 : 0.62, isCore ? 2.2 : 2.6);
  group.add(glow);

  const surfaceWire = new THREE.Mesh(
    new THREE.IcosahedronGeometry(radius * 1.08, 2),
    new THREE.MeshBasicMaterial({
      color: 0xcbd5e1,
      wireframe: true,
      transparent: true,
      opacity: 0.1,
      depthWrite: false,
    }),
  );
  group.add(surfaceWire);

  if (isCore) {
    const wire = new THREE.Mesh(
      new THREE.IcosahedronGeometry(radius * 1.28, 1),
      new THREE.MeshBasicMaterial({
        color: 0x6ee7b7,
        wireframe: true,
        transparent: true,
        opacity: 0.2,
        depthWrite: false,
      }),
    );
    group.add(wire);
    group.userData.wire = wire;
  }

  group.userData.core = core;
  group.userData.shell = shell;
  group.userData.glow = glow;
  group.userData.surfaceWire = surfaceWire;
  group.userData.baseRadius = radius;
  group.userData.labelBaseScale = isCore ? 26 : 22;
  group.userData.baseEmissive = isCore ? 0.26 : 0.2;
  group.userData.baseGlow = isCore ? 0.8 : 0.62;
  return group;
};

/** 三环轨道：第 index 个卫星所属环编号（按 index % RING_COUNT 轮询分配） */
const innerRingOf = (index) => index % INNER_RING_COUNT;

/** 第 ringIndex 环的卫星数（轮询分配后的每环数量） */
const innerRingNodeCount = (total, ringIndex) =>
  Math.floor(total / INNER_RING_COUNT) + (ringIndex < total % INNER_RING_COUNT ? 1 : 0);

/** 第 ringIndex 环半径：基数 × (1 + 0.18·i)，环间错开形成原子模型层 */
const innerRingRadiusOf = (radius, ringIndex) => radius * (1 + INNER_RING_RADIUS_STEP * ringIndex);

/**
 * 三环轨道卫星位置（环局部坐标，落在环面圆周上）：
 * 每环内等角间距 2π/n_i，叠加黄金相位 π(3−√5) 与节点种子相位错开各环；
 * 位置相对所属环 Group，环 Group 负责倾角与公转。
 */
const ringPosition = (nodeId, index, total, radius) => {
  const ringIndex = innerRingOf(index);
  const countInRing = innerRingNodeCount(total, ringIndex);
  const k = Math.floor(index / INNER_RING_COUNT);
  let seed = 0;
  for (let i = 0; i < nodeId.length; i += 1) seed += nodeId.charCodeAt(i);
  const angle =
    (k / Math.max(countInRing, 1)) * Math.PI * 2
    + INNER_GOLDEN_ANGLE * (ringIndex + 1)
    + seed * 0.013;
  const ringRadius = innerRingRadiusOf(radius, ringIndex);
  return new THREE.Vector3(Math.cos(angle) * ringRadius, 0, Math.sin(angle) * ringRadius);
};

const buildInnerNetwork = (nodeId, hubRadius) => {
  const config = heroInnerNetworks[nodeId];
  if (!config) return null;

  const group = new THREE.Group();
  group.visible = false;
  group.renderOrder = 12;

  const cage = new THREE.Mesh(
    new THREE.IcosahedronGeometry(hubRadius * 1.15, 2),
    new THREE.MeshBasicMaterial({
      color: 0x94a3b8,
      wireframe: true,
      transparent: true,
      opacity: 0.1,
      depthWrite: false,
    }),
  );
  group.add(cage);

  const isPlatformNetwork = nodeId === "platform";
  // 平台节点沿用同一算法，仅半径基数更大（保持其 8 个卫星与名称/副标题）
  const layoutRadius = isPlatformNetwork
    ? Math.max(config.radius || 10, hubRadius * 2.8)
    : config.radius || 10;

  // 三环轨道：每环一个子 Group（记录环参数），卫星 pos 相对环局部坐标落在环面圆周上；
  // animate 中环绕各自法向轴缓慢公转（交替方向），卫星随环转动
  const ringGroups = [];
  for (let i = 0; i < INNER_RING_COUNT; i += 1) {
    const ringGroup = new THREE.Group();
    const axis = INNER_RING_TILT_AXES[i] === "z" ? "z" : "x";
    ringGroup.rotation[axis] = INNER_RING_TILTS[i];
    ringGroup.userData.radius = innerRingRadiusOf(layoutRadius, i);
    ringGroup.userData.tilt = INNER_RING_TILTS[i];
    ringGroup.userData.axis = axis;
    ringGroup.userData.speed = INNER_RING_SPEEDS[i];
    ringGroup.userData.direction = i % 2 === 0 ? 1 : -1;
    ringGroup.userData.phase = INNER_GOLDEN_ANGLE * (i + 1);
    group.add(ringGroup);
    ringGroups.push(ringGroup);
  }

  const satellites = config.nodes.map((item, index) => {
    const ringIndex = innerRingOf(index);
    const ringGroup = ringGroups[ringIndex];
    const pos = ringPosition(nodeId, index, config.nodes.length, layoutRadius);
    const sat = new THREE.Mesh(
      new THREE.SphereGeometry(isPlatformNetwork ? INNER_SAT_RADIUS_PLATFORM : INNER_SAT_RADIUS, 20, 20),
      new THREE.MeshStandardMaterial({
        color: item.color,
        emissive: new THREE.Color(item.color),
        emissiveIntensity: 0.22,
        metalness: 0.3,
        roughness: 0.45,
        transparent: true,
        opacity: 1,
      }),
    );
    sat.position.copy(pos);
    ringGroup.add(sat);

    const label = createMiniLabel(item.name, item.subtitle, item.color);
    if (isPlatformNetwork) {
      label.scale.set(4.6, 1.42, 1);
    }
    label.userData.baseOffsetY = isPlatformNetwork ? 2.7 : 2.2;
    label.position.copy(pos).add(_satLabelOffset.set(0, label.userData.baseOffsetY, 0));
    ringGroup.add(label);
    labelEntries.push({ label });

    return { mesh: sat, label, pos, ringGroup, ringIndex, phase: index * 0.9 };
  });

  // config.links 数据字段保留不动；连线视觉已去除（三环轨道替代）
  const reachRadius = ringGroups.reduce(
    (max, ringGroup) => Math.max(max, ringGroup.userData.radius + 3.2),
    hubRadius * 1.2,
  );

  return { group, cage, satellites, ringGroups, reachRadius };
};

/** 柔和发光圆点纹理：径向渐变（白芯 → 青绿 → 透明），用于流动光点，避免“生硬绿球” */
let glowPointTexture = null;
const getGlowPointTexture = () => {
  if (glowPointTexture) return glowPointTexture;
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  const grad = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  grad.addColorStop(0, "rgba(255, 255, 255, 1)");
  grad.addColorStop(0.22, "rgba(214, 250, 238, 0.92)");
  grad.addColorStop(0.5, "rgba(140, 226, 205, 0.4)");
  grad.addColorStop(1, "rgba(140, 226, 205, 0)");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);
  glowPointTexture = new THREE.CanvasTexture(canvas);
  glowPointTexture.colorSpace = THREE.SRGBColorSpace;
  return glowPointTexture;
};

/** 沿线长方向把端点淡出的渐变烘焙进顶点色，让连线柔和融入两端节点而非硬接头 */
const buildEdgeFadeColors = (colorHex, segments, fadeRatio = 0.16) => {
  const base = new THREE.Color(colorHex);
  const colors = new Float32Array((segments + 1) * 3);
  for (let i = 0; i <= segments; i += 1) {
    const t = i / segments;
    const edge = Math.min(t, 1 - t);
    const a = Math.min(1, edge / fadeRatio);
    colors[i * 3] = base.r * a;
    colors[i * 3 + 1] = base.g * a;
    colors[i * 3 + 2] = base.b * a;
  }
  return colors;
};

const LINK_BASE_OPACITY = 0.46;

const createLinkMesh = () => {
  const positions = new Float32Array((LINK_SEGMENTS + 1) * 3);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute(
    "color",
    new THREE.BufferAttribute(buildEdgeFadeColors(0x9fe0d0, LINK_SEGMENTS, 0.18), 3),
  );
  const material = new THREE.LineBasicMaterial({
    vertexColors: true,
    transparent: true,
    opacity: LINK_BASE_OPACITY,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const line = new THREE.Line(geometry, material);
  line.renderOrder = 1;
  line.userData.baseOpacity = LINK_BASE_OPACITY;
  // 存储当前弧线控制点，供线上光点沿同一条贝塞尔曲线运动
  line.userData.cStart = new THREE.Vector3();
  line.userData.cControl = new THREE.Vector3();
  line.userData.cEnd = new THREE.Vector3();
  return line;
};

const getLinkRadius = (group) => {
  const visualRadius = group.userData.currentVisualRadius || group.userData.baseRadius || 1;
  const innerReveal = group.userData.innerReveal || 0;
  const baseRadius = visualRadius + LINK_RADIUS_PADDING;
  const innerReach = group.userData.innerNetwork?.reachRadius || 0;
  if (innerReach <= baseRadius) return baseRadius + innerReveal * 1.4;
  return baseRadius + innerReveal * (innerReach - baseRadius + 1.4);
};

const computeLinkEndpoints = (source, target, startOut, endOut) => {
  startOut.copy(source.position);
  endOut.copy(target.position);
  _linkDir.subVectors(endOut, startOut);
  const len = _linkDir.length();
  if (len < 0.01) return 0;

  const dir = _linkDir.divideScalar(len);
  const maxTrim = len * 0.42;
  const sourceTrim = Math.min(maxTrim, getLinkRadius(source));
  const targetTrim = Math.min(maxTrim, getLinkRadius(target));
  startOut.addScaledVector(dir, sourceTrim);
  endOut.addScaledVector(dir, -targetTrim);
  return Math.max(0.01, startOut.distanceTo(endOut));
};

const updateLinkMesh = (mesh, source, target, arcHeight = DEFAULT_SPOTLIGHT.linkArc) => {
  const len = computeLinkEndpoints(source, target, _linkStart, _linkEnd);
  if (len < 0.01) return;
  _linkMid.copy(_linkStart).add(_linkEnd).multiplyScalar(0.5);
  _linkOut.copy(_linkMid);
  if (_linkOut.lengthSq() < 0.01) {
    _linkOut.crossVectors(_linkStart, _linkEnd);
    if (_linkOut.lengthSq() < 0.01) _linkOut.copy(UP_VECTOR);
  }
  _linkOut.normalize();
  _linkControl.copy(_linkMid).addScaledVector(_linkOut, Math.min(arcHeight, len * 0.18));

  // 记录本帧弧线，供线上流动光点沿同一曲线采样（消除“光点不在线上”）
  mesh.userData.cStart.copy(_linkStart);
  mesh.userData.cControl.copy(_linkControl);
  mesh.userData.cEnd.copy(_linkEnd);

  const positionAttr = mesh.geometry.getAttribute("position");
  for (let i = 0; i <= LINK_SEGMENTS; i += 1) {
    const t = i / LINK_SEGMENTS;
    const inv = 1 - t;
    _linkCurvePoint
      .copy(_linkStart)
      .multiplyScalar(inv * inv)
      .addScaledVector(_linkControl, 2 * inv * t)
      .addScaledVector(_linkEnd, t * t);
    positionAttr.setXYZ(i, _linkCurvePoint.x, _linkCurvePoint.y, _linkCurvePoint.z);
  }
  positionAttr.needsUpdate = true;
  mesh.geometry.computeBoundingSphere();
};

const computeCloseCamera = (focusWorld, out, config = DEFAULT_SPOTLIGHT) => {
  _closeDir.copy(focusWorld);
  if (_closeDir.lengthSq() < 0.01) {
    _closeDir.set(0.42, 0.22, 0.88);
  }
  _closeDir.normalize();
  _closeTangent.set(-_closeDir.z, 0, _closeDir.x);
  if (_closeTangent.lengthSq() < 0.01) _closeTangent.set(1, 0, 0);
  _closeTangent.normalize();
  _closeDir
    .multiplyScalar(0.88)
    .addScaledVector(_closeTangent, 0.24)
    .add(new THREE.Vector3(0, 0.16, 0))
    .normalize();
  const distance = focusWorld.lengthSq() < 4 ? CORE_CLOSE_CAMERA_DISTANCE : config.distance;
  out.copy(focusWorld).addScaledVector(_closeDir, distance);
  out.y += CLOSE_CAMERA_LIFT;
  return out;
};

const buildScene = () => {
  scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x0c1513, 0.0038);

  camera = new THREE.PerspectiveCamera(36, 1, 0.5, 600);
  _camSmooth.copy(BASE_CAM);
  camera.position.copy(_camSmooth);

  renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true,
    powerPreference: "high-performance",
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x0c1513, 0);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = BASE_EXPOSURE;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  containerRef.value.appendChild(renderer.domElement);

  composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  bloomPass = new UnrealBloomPass(new THREE.Vector2(1, 1), BASE_BLOOM_STRENGTH, 0.26, 0.84);
  bloomPass.threshold = 0.46;
  bloomPass.strength = 0.14;
  bloomPass.radius = 0.2;
  composer.addPass(bloomPass);

  scene.add(new THREE.AmbientLight(0x8fdcc8, 0.42));
  const key = new THREE.DirectionalLight(0xffffff, 1.15);
  key.position.set(60, 100, 80);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x6366f1, 0.55);
  rim.position.set(-80, 20, -70);
  scene.add(rim);
  const fill = new THREE.PointLight(0x34d399, 0.38, 320);
  fill.position.set(30, -20, 90);
  scene.add(fill);

  graphGroup = new THREE.Group();
  scene.add(graphGroup);
  nodeMap = new Map();

  const shellNodes = heroGraphData.nodes.filter((n) => n.id !== "platform");
  const mainShell = shellNodes.filter((n) => n.type !== "KBMarker");
  const kbMarkers = shellNodes.filter((n) => n.type === "KBMarker");

  heroGraphData.nodes.forEach((node) => {
    const isCore = node.id === "platform";
    let pos;
    if (isCore) {
      pos = [0, 0, 0];
    } else if (node.type === "KBMarker") {
      const idx = kbMarkers.indexOf(node);
      const angle = (idx / kbMarkers.length) * Math.PI * 2 + Math.PI / 4;
      pos = [Math.cos(angle) * OUTER_KB_RADIUS, Math.sin(angle) * 18, Math.sin(angle) * OUTER_KB_RADIUS];
    } else {
      pos = spherePosition(mainShell.indexOf(node), mainShell.length, SPHERE_RADIUS);
    }

    const color = heroColorByType(node.type);
    const mesh = createGlowSphere(color, nodeRadius(node), isCore);
    mesh.position.set(...pos);
    mesh.userData.basePos = new THREE.Vector3(...pos);
    mesh.userData.nodeId = node.id;
    mesh.userData.nodeName = node.name;
    mesh.userData.nodeTag = node.tag || HERO_TYPE_LABELS[node.type] || node.type;
    mesh.userData.phase = Math.random() * Math.PI * 2;

    const innerNetwork = buildInnerNetwork(node.id, nodeRadius(node));
    if (innerNetwork) {
      mesh.add(innerNetwork.group);
      mesh.userData.innerNetwork = innerNetwork;
    }

    if (!isCore && node.type !== "KBMarker") {
      const label = createLabelSprite(node.name, node.tag || node.type, color);
      label.position.set(0, nodeRadius(node) + 5.5, 0);
      mesh.add(label);
      mesh.userData.label = label;
    } else if (isCore) {
      const label = createLabelSprite("知识图谱", "八库联动 · 证据底座", color);
      label.position.set(0, nodeRadius(node) + 7, 0);
      label.scale.set(26, 8, 1);
      mesh.add(label);
      mesh.userData.label = label;
    } else {
      const label = createLabelSprite(node.name, node.tag, color);
      label.position.set(0, nodeRadius(node) + 4, 0);
      label.scale.set(14, 4.2, 1);
      mesh.add(label);
      mesh.userData.label = label;
      mesh.userData.labelBaseScale = 14;
    }
    if (mesh.userData.label) {
      mesh.userData.label.userData.baseY = mesh.userData.label.position.y;
      labelEntries.push({ label: mesh.userData.label });
    }

    graphGroup.add(mesh);
    nodeEntries.push(mesh);
    nodeMap.set(node.id, mesh);
  });

  heroGraphData.links.forEach((link) => {
    const sourceId = typeof link.source === "string" ? link.source : link.source.id;
    const targetId = typeof link.target === "string" ? link.target : link.target.id;
    const source = nodeMap.get(sourceId);
    const target = nodeMap.get(targetId);
    if (!source || !target) return;

    const tube = createLinkMesh();
    graphGroup.add(tube);
    linkMeshes.push({ mesh: tube, source, target });

    const particle = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: getGlowPointTexture(),
        color: 0xa6f2dd,
        transparent: true,
        opacity: 0,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    );
    particle.scale.set(2.4, 2.4, 1);
    particle.renderOrder = 6;
    particle.userData.t = Math.random();
    particle.userData.speed = 0.08 + Math.random() * 0.05;
    graphGroup.add(particle);
    particles.push({ mesh: particle, link: tube });
  });

  [SPHERE_RADIUS * 1.02, SPHERE_RADIUS * 1.18, OUTER_KB_RADIUS * 1.02].forEach((r, i) => {
    const baseOpacity = i === 0 ? 0.08 : i === 1 ? 0.055 : 0.04;
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(r, r + (i === 2 ? 0.5 : 0.4), 128),
      new THREE.MeshBasicMaterial({
        color: i === 0 ? 0x34d399 : i === 1 ? 0x818cf8 : 0x64748b,
        transparent: true,
        opacity: baseOpacity,
        side: THREE.DoubleSide,
        depthWrite: false,
      }),
    );
    ring.userData.baseOpacity = baseOpacity;
    ring.rotation.x = Math.PI / 2;
    graphGroup.add(ring);
    orbitRings.push(ring);
  });

  // 陀螺环：倾斜细环 + 滑行光点，营造精密仪器般的科技感
  const gyroSpecs = [
    { radius: SPHERE_RADIUS * 1.36, tiltX: Math.PI / 2.7, tiltZ: 0.35, color: 0x5eead4, opacity: 0.13, speed: 0.085 },
    { radius: SPHERE_RADIUS * 1.54, tiltX: -Math.PI / 3.4, tiltZ: -0.55, color: 0x818cf8, opacity: 0.09, speed: -0.06 },
  ];
  gyroSpecs.forEach((spec) => {
    const pivot = new THREE.Group();
    pivot.rotation.x = spec.tiltX;
    pivot.rotation.z = spec.tiltZ;
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(spec.radius, 0.13, 8, 180),
      new THREE.MeshBasicMaterial({
        color: spec.color,
        transparent: true,
        opacity: spec.opacity,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    );
    pivot.add(ring);
    const tracer = new THREE.Mesh(
      new THREE.SphereGeometry(0.7, 12, 12),
      new THREE.MeshBasicMaterial({
        color: spec.color,
        transparent: true,
        opacity: 0.8,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    );
    pivot.add(tracer);
    graphGroup.add(pivot);
    gyroRings.push({ pivot, ring, tracer, spec, phase: Math.random() * Math.PI * 2 });
  });

  // 星尘氛围层：球壳分布的低透明度粒子，增强空间纵深
  const dustCount = 900;
  const dustPositions = new Float32Array(dustCount * 3);
  for (let i = 0; i < dustCount; i += 1) {
    const radius = 120 + Math.random() * 90;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    dustPositions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
    dustPositions[i * 3 + 1] = radius * Math.cos(phi) * 0.72;
    dustPositions[i * 3 + 2] = radius * Math.sin(phi) * Math.sin(theta);
  }
  const dustGeometry = new THREE.BufferGeometry();
  dustGeometry.setAttribute("position", new THREE.BufferAttribute(dustPositions, 3));
  dustField = new THREE.Points(
    dustGeometry,
    new THREE.PointsMaterial({
      color: 0x9bd8c4,
      size: 0.85,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.32,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  );
  scene.add(dustField);

  labelDistances = new Float32Array(labelEntries.length);
};

const syncSize = () => {
  if (!containerRef.value || !renderer || !camera) return;
  const { clientWidth, clientHeight } = containerRef.value;
  if (clientWidth <= 0 || clientHeight <= 0) return;
  renderer.setSize(clientWidth, clientHeight, false);
  composer?.setSize(clientWidth, clientHeight);
  bloomPass?.setSize(clientWidth, clientHeight);
  camera.aspect = clientWidth / clientHeight;
  camera.updateProjectionMatrix();
};

const animate = () => {
  rafId = requestAnimationFrame(animate);
  if (!renderer || !scene || !camera || !clock || isPaused) return;

  const delta = Math.min(clock.getDelta(), 0.05);
  const elapsed = clock.getElapsedTime();
  const {
    focusId,
    weight: spotWeight,
    secondaryFocusId,
    secondaryWeight,
    config: focusConfig = DEFAULT_SPOTLIGHT,
    secondaryConfig = null,
  } = getSpotlightState(elapsed);
  const effectiveSpotWeight = Math.min(1, spotWeight + secondaryWeight);
  const activeConfig = effectiveSpotWeight > 0.001 ? focusConfig : DEFAULT_SPOTLIGHT;
  const reducedMotion = preferReducedMotion.value;

  // 入场预热：前 ~2.4s 让旋转/相机从静止平滑加速，避免一进首页就满速、节奏突兀
  const warmup = smootherStep(Math.min(1, elapsed / 2.4));

  // 旋转速度低通滤波：消除阶段切换时角速度跳变
  rotWeightSmooth += (effectiveSpotWeight - rotWeightSmooth) * (1 - Math.exp(-2.6 * delta));
  const rotationMul = 1 - rotWeightSmooth * 0.26;
  accumulatedRotation += ROTATION_SPEED * rotationMul * warmup * delta;
  graphGroup.rotation.y = accumulatedRotation;
  graphGroup.rotation.x = TILT_BASE + Math.sin(elapsed * 0.09) * TILT_WOBBLE;
  graphGroup.rotation.z = Math.sin(elapsed * 0.06) * 0.025;

  orbitRings.forEach((ring, i) => {
    ring.rotation.z = elapsed * (i === 0 ? 0.025 : i === 1 ? -0.018 : 0.012);
    // 轨道环随特写权重收敛（在原有氛围基础上再降一档）
    ring.material.opacity = ring.userData.baseOpacity * (1 - effectiveSpotWeight * RING_SPOT_FADE);
  });

  if (dustField) {
    dustField.rotation.y = -accumulatedRotation * 0.32;
    dustField.rotation.x = Math.sin(elapsed * 0.05) * 0.04;
    dustField.material.opacity = 0.32 - effectiveSpotWeight * DUST_SPOT_FADE;
  }

  gyroRings.forEach((g) => {
    g.pivot.rotation.y = elapsed * g.spec.speed;
    const angle = elapsed * g.spec.speed * 7 + g.phase;
    g.tracer.position.set(Math.cos(angle) * g.spec.radius, Math.sin(angle) * g.spec.radius, 0);
    const fade = 1 - effectiveSpotWeight * GYRO_SPOT_FADE;
    g.ring.material.opacity = g.spec.opacity * fade;
    g.tracer.material.opacity = 0.8 * fade;
  });

  const focusBlend = blendFocusWorld(focusId, spotWeight, secondaryFocusId, secondaryWeight, _blendFocus);
  const platformFocusWeight = nodeSpotWeight("platform", focusId, spotWeight, secondaryFocusId, secondaryWeight);

  _closeLook.copy(_blendFocus).addScaledVector(UP_VECTOR, (activeConfig.labelLift || CLOSE_LOOK_LIFT) * effectiveSpotWeight);
  _lookDesired.copy(BASE_LOOK).lerp(_closeLook, effectiveSpotWeight * 0.92);
  if (focusBlend > 0.001) {
    computeCloseCamera(_blendFocus, _closeCam, activeConfig);
  } else {
    _closeCam.copy(BASE_CAM);
  }
  _camDesired.copy(BASE_CAM).lerp(_closeCam, effectiveSpotWeight);

  // 视线右向量：用于构图偏移与弧线推近
  _desiredDir.copy(_lookDesired).sub(_camDesired).normalize();
  _viewRight.crossVectors(_desiredDir, UP_VECTOR).normalize();

  // A1 构图偏移：特写时 lookAt 向左偏，让焦点球稳定落在画面右侧 ~62%
  const lateralShift = (activeConfig.distance || CLOSE_CAMERA_DISTANCE) * 0.13 * effectiveSpotWeight;
  _lookDesired.addScaledVector(_viewRight, -lateralShift);

  // A2 弧线推近：推近/拉回途中给相机一条横向正弦弧，避免机械直推
  const arcAmp = Math.sin(Math.min(1, effectiveSpotWeight) * Math.PI) * 9;
  _camDesired.addScaledVector(_viewRight, arcAmp);

  // 相机平滑：基础响应稳定 + 适度自适应；入场期降低响应让首段推近更从容
  const weightDelta = Math.abs(effectiveSpotWeight - prevSpotWeight);
  const camResponse = (3.6 + weightDelta * 5) * (0.42 + 0.58 * warmup);
  const smoothK = 1 - Math.exp(-camResponse * delta);
  prevSpotWeight = effectiveSpotWeight;
  _camSmooth.lerp(_camDesired, smoothK);
  _lookSmooth.lerp(_lookDesired, smoothK);
  camera.position.copy(_camSmooth);
  camera.lookAt(_lookSmooth);

  camera.getWorldDirection(_viewDir);
  _viewDirNeg.copy(_viewDir).negate();

  // —— 焦点深度基准：视线遮挡与链路中点遮挡共用 ——
  let focusDist = Infinity;
  let focusFrontDepth = Infinity;
  let focusConeRadius = 0;
  if (focusBlend > 0.001) {
    _focusViewDir.copy(_blendFocus).sub(camera.position).normalize();
    focusDist = camera.position.distanceTo(_blendFocus);
    focusConeRadius = blendFocusRadius(focusId, spotWeight, secondaryFocusId, secondaryWeight);
    focusFrontDepth = focusDist - focusConeRadius * OCCLUSION_DEPTH_MARGIN;
  }

  // 内部展开减熵 / 链接聚焦的帧级权重（exp 平滑，无跳变）
  const globalInnerReveal = Math.max(innerRevealOf(spotWeight), innerRevealOf(secondaryWeight));
  const entropyFadeBase = 1 - smootherStep(clamp01((globalInnerReveal - INNER_FADE_THRESHOLD) / INNER_FADE_RANGE));
  const linkFocusActive = effectiveSpotWeight > LINK_FOCUS_WEIGHT_THRESHOLD ? 1 : 0;
  const linkK = 1 - Math.exp(-LINK_FADE_K * delta);
  linkFocusSmooth += (linkFocusActive - linkFocusSmooth) * linkK;

  graphGroup.updateMatrixWorld();

  nodeEntries.forEach((group) => {
    group.position.copy(group.userData.basePos);
    if (platformFocusWeight > 0.01 && group.userData.nodeId !== "platform") {
      _nodePush.copy(group.userData.basePos);
      if (_nodePush.lengthSq() > 0.01) {
        const pushDistance = group.userData.nodeId?.startsWith("kb") ? 12 : 8;
        group.position.addScaledVector(_nodePush.normalize(), platformFocusWeight * pushDistance);
      }
    }
    group.position.y += Math.sin(elapsed * 0.75 + group.userData.phase) * 0.28;

    const nodeSpot = nodeSpotWeight(
      group.userData.nodeId,
      focusId,
      spotWeight,
      secondaryFocusId,
      secondaryWeight,
    );
    const spotBoost = nodeSpot;
    const isFocusNode = nodeSpot > 0.02;
    // 特写时非焦点节点整体淡化（增强后的 dimOthers），减少动效偏好下更激进
    let dimOthers = effectiveSpotWeight > 0.15 && !isFocusNode
      ? 1 - effectiveSpotWeight * (reducedMotion ? DIM_OTHERS_FADE_REDUCED : DIM_OTHERS_FADE)
      : 1;
    if (platformFocusWeight > 0.08 && group.userData.nodeId !== "platform") {
      dimOthers *= 1 - platformFocusWeight * 0.55;
    }
    const innerReveal = innerRevealOf(nodeSpot);

    group.getWorldPosition(_worldPos);
    _camToNode.copy(_worldPos).sub(camera.position).normalize();
    const facing = Math.max(0, _camToNode.dot(_viewDirNeg));
    const highlight = facing ** 2.2;

    const pulse = 1 + Math.sin(elapsed * 1.2 + group.userData.phase) * 0.025;
    const scaleBoost = 1 + highlight * 0.04 + spotBoost * 0.045;
    const r = group.userData.baseRadius * pulse * scaleBoost;
    group.userData.currentVisualRadius = r;

    // —— 视线遮挡淡出：位于相机与焦点球之间的非焦点节点整体收敛到 ~0.02 ——
    let occlusionTarget = 0;
    if (!isFocusNode && effectiveSpotWeight > 0.05 && focusBlend > 0.001) {
      _nodeToCamRaw.copy(_worldPos).sub(camera.position);
      const nodeDepth = _nodeToCamRaw.dot(_focusViewDir);
      const offAxisSq = Math.max(0, _nodeToCamRaw.lengthSq() - nodeDepth * nodeDepth);
      const cone = focusConeRadius * OCCLUSION_CONE_MARGIN + r;
      if (nodeDepth < focusFrontDepth && offAxisSq < cone * cone) occlusionTarget = 1;
    }
    const occlusionK = 1 - Math.exp(-(reducedMotion ? OCCLUSION_FADE_K_REDUCED : OCCLUSION_FADE_K) * delta);
    const occlusionSmooth =
      (group.userData.occlusionSmooth || 0) + (occlusionTarget - (group.userData.occlusionSmooth || 0)) * occlusionK;
    group.userData.occlusionSmooth = occlusionSmooth;
    const occlusionFade = 1 - occlusionSmooth * effectiveSpotWeight * (1 - OCCLUSION_MIN_OPACITY);
    group.userData.occlusionFade = occlusionFade;

    // —— 内部展开减熵：焦点内部网络展开过半时，非焦点大球整体淡出 ——
    const entropyFade = isFocusNode ? 1 : entropyFadeBase;

    group.userData.core.scale.setScalar(r / group.userData.baseRadius);
    group.userData.glow.scale.setScalar(r / group.userData.baseRadius);
    group.userData.core.material.emissiveIntensity =
      Math.max(0.08, (group.userData.baseEmissive + highlight * 0.045 - spotBoost * 0.11) * dimOthers)
      * entropyFade * occlusionFade;
    group.userData.core.material.opacity = (0.78 + spotBoost * 0.02) * dimOthers * entropyFade * occlusionFade;
    // 菲涅尔辉光：朝向相机/特写时增强，特写内部展开时收敛避免遮挡
    group.userData.glow.material.uniforms.uIntensity.value =
      (group.userData.baseGlow + highlight * 0.35 + spotBoost * 0.2 - innerReveal * 0.3)
      * dimOthers * entropyFade * occlusionFade;
    group.userData.shell.material.opacity = (0.18 + spotBoost * 0.08) * dimOthers * entropyFade * occlusionFade;
    group.userData.surfaceWire.material.opacity =
      (0.07 + innerReveal * 0.2 + spotBoost * 0.06) * dimOthers * entropyFade * occlusionFade;

    if (group.userData.wire) {
      group.userData.wire.rotation.y = elapsed * 0.35;
      group.userData.wire.rotation.x = elapsed * 0.22;
      group.userData.wire.material.opacity = (0.12 + innerReveal * 0.2) * dimOthers * occlusionFade;
    }
    if (group.userData.label) {
      const label = group.userData.label;
      const isPlatformLabel = group.userData.nodeId === "platform";
      const platformLabelFade = isPlatformLabel ? 1 - innerReveal * PLATFORM_LABEL_FOCUS_FADE : 1;
      // 焦点标签：inner 展开过深时淡出防满屏；特写时关深度测试并置顶渲染保证可读
      const labelInnerFade = isFocusNode
        ? 1 - clamp01((innerReveal - LABEL_INNER_FADE_THRESHOLD) / LABEL_INNER_FADE_RANGE)
        : 1;
      // 非焦点标签：随特写权重更激进淡出，避免文字满屏互叠
      const nonFocusLabelFade = isFocusNode ? 1 : 1 - effectiveSpotWeight * LABEL_NON_FOCUS_FADE;
      label.material.opacity =
        (0.88 + nodeSpot * 0.1) * dimOthers * platformLabelFade * labelInnerFade * nonFocusLabelFade * occlusionFade;
      label.material.depthTest = !isFocusNode;
      label.userData.focusOverride = isFocusNode;
      if (isFocusNode) label.renderOrder = LABEL_FOCUS_RENDER_ORDER;
      const base = group.userData.labelBaseScale || 22;
      const nodeConfig = getSpotlightConfig(group.userData.nodeId);
      // 焦点标签特写平滑放大；减少动效偏好下不放大
      const labelScaleBoost = reducedMotion ? 0 : isPlatformLabel ? 0.06 : LABEL_FOCUS_SCALE_BOOST;
      const s = base * (0.96 + nodeSpot * labelScaleBoost);
      label.scale.set(s, s * 0.31, 1);
      label.position.y =
        label.userData.baseY + nodeSpot * (nodeConfig.labelLift || CLOSE_LOOK_LIFT);
    }

    const inner = group.userData.innerNetwork;
    group.userData.innerReveal = innerReveal;
    if (inner) {
      inner.group.visible = innerReveal > 0.03;
      // 绽放展开：innerReveal 提升时环整体 scale 0.35→1.0 平滑展开（揭示节奏与 innerReveal 同源）；
      // 特写极值（>0.85）整体 ×1.06 轻微外扩
      const extremeExpand = innerReveal > INNER_EXTREME_THRESHOLD
        ? 1
          + clamp01((innerReveal - INNER_EXTREME_THRESHOLD) / (1 - INNER_EXTREME_THRESHOLD))
            * (INNER_EXTREME_EXPAND - 1)
        : 1;
      const innerScale =
        (INNER_REVEAL_SCALE_MIN + innerReveal * (1 - INNER_REVEAL_SCALE_MIN)) * extremeExpand;
      inner.group.scale.setScalar(innerScale);
      // 三环轨道：各环绕自身法向轴缓慢公转（交替方向）；减少动效偏好下减速
      const spinMul = reducedMotion ? INNER_RING_SPIN_REDUCED : 1;
      const breatheMul = reducedMotion ? INNER_SAT_BREATHE_REDUCED : 1;
      inner.ringGroups.forEach((ringGroup) => {
        ringGroup.rotation.y += ringGroup.userData.speed * ringGroup.userData.direction * spinMul * delta;
      });
      // inner 子网络（cage/satellite/labels）一并参与视线遮挡淡出
      inner.cage.material.opacity = (0.06 + innerReveal * 0.22) * occlusionFade;
      inner.cage.rotation.y = -elapsed * 0.2;
      // 绽放展开：卫星 opacity 0→1 随揭示同步
      const satOpacity = clamp01((innerReveal - SAT_OPACITY_REVEAL_START) / SAT_OPACITY_REVEAL_RANGE) * occlusionFade;
      inner.satellites.forEach((sat) => {
        sat.mesh.material.emissiveIntensity = 0.15 + innerReveal * 0.25;
        sat.mesh.material.opacity = satOpacity;
        // 环面内相位错开的轻呼吸（±0.1）：卫星沿所在环径向伸缩，标签同步跟随
        const breathe =
          1 + Math.sin(elapsed * 0.8 + sat.phase) * INNER_SAT_BREATHE_AMPLITUDE * innerReveal * breatheMul;
        sat.mesh.position.copy(sat.pos).multiplyScalar(breathe);
        sat.label.position
          .copy(sat.mesh.position)
          .add(_satLabelOffset.set(0, sat.label.userData.baseOffsetY || 2.2, 0));
        // 标签朝向：dot(卫星世界方向, 相机视线) 判背面/正面 — 卫星位于相机与球心之间（视线同侧）时
        // 正面显示；绕到球心背对相机一侧时标签平滑淡出（≈0.2s exp 平滑），保证不挡大球
        sat.mesh.getWorldPosition(_satWorldPos);
        _satWorldPos.sub(_worldPos).normalize();
        const facingDot = _satWorldPos.dot(_viewDir);
        const facingTarget = clamp01((SAT_LABEL_FACING_OFFSET - facingDot) / SAT_LABEL_FACING_RANGE);
        const facingK = 1 - Math.exp(-SAT_LABEL_FACING_FADE_K * delta);
        sat.label.userData.facingSmooth =
          (sat.label.userData.facingSmooth || 0)
          + (facingTarget - (sat.label.userData.facingSmooth || 0)) * facingK;
        sat.label.material.opacity = (0.4 + innerReveal * 0.55) * occlusionFade * sat.label.userData.facingSmooth;
      });
    }
  });

  // —— 标签分层：每帧按相机距离赋 renderOrder（近者在上），焦点标签置顶，避免文字互叠 ——
  if (labelEntries.length) {
    let minDist = Infinity;
    let maxDist = 0;
    for (let i = 0; i < labelEntries.length; i += 1) {
      const entry = labelEntries[i];
      if (entry.label.userData.focusOverride) continue;
      const d = entry.label.getWorldPosition(_labelWorldPos).distanceToSquared(camera.position);
      labelDistances[i] = d;
      if (d < minDist) minDist = d;
      if (d > maxDist) maxDist = d;
    }
    if (Number.isFinite(minDist)) {
      const span = Math.max(1e-4, maxDist - minDist);
      for (let i = 0; i < labelEntries.length; i += 1) {
        const entry = labelEntries[i];
        if (entry.label.userData.focusOverride) continue;
        const norm = 1 - (labelDistances[i] - minDist) / span;
        entry.label.renderOrder = Math.round(LABEL_DIST_SORT_BASE + norm * LABEL_DIST_SORT_RANGE);
      }
    }
  }

  linkMeshes.forEach(({ mesh, source, target }) => {
    const sourceSpot = nodeSpotWeight(source.userData.nodeId, focusId, spotWeight, secondaryFocusId, secondaryWeight);
    const targetSpot = nodeSpotWeight(target.userData.nodeId, focusId, spotWeight, secondaryFocusId, secondaryWeight);
    const relatedSpot = Math.max(sourceSpot, targetSpot);
    const isAdjacent = relatedSpot > 0.02;
    updateLinkMesh(mesh, source, target, (activeConfig.linkArc || DEFAULT_SPOTLIGHT.linkArc) * (1 + relatedSpot * 0.35));
    const base = mesh.userData.baseOpacity ?? 0.62;
    const pulse = Math.sin(elapsed * 2 + source.userData.phase) * 0.06;
    let targetOpacity = base * 0.9 + pulse * 0.35;
    if (isAdjacent) {
      // 相邻链接保持，作为焦点节点的视线引导
      targetOpacity *= 1 - relatedSpot * 0.42;
    } else {
      targetOpacity *= 1 - effectiveSpotWeight * 0.5;
      // 链接聚焦：特写权重超阈值后非相邻链接整体淡出至 0.02
      if (linkFocusSmooth > 0.001) {
        targetOpacity += (LINK_FOCUS_MIN_OPACITY - targetOpacity) * linkFocusSmooth;
      }
    }
    // 链路中点位于焦点球与相机之间时额外淡出，防“线盖球”
    let midFrontTarget = 0;
    if (focusBlend > 0.001 && effectiveSpotWeight > 0.05) {
      _linkMidWorld
        .copy(mesh.userData.cStart)
        .multiplyScalar(0.25)
        .addScaledVector(mesh.userData.cControl, 0.5)
        .addScaledVector(mesh.userData.cEnd, 0.25)
        .applyMatrix4(graphGroup.matrixWorld);
      _linkMidCam.copy(_linkMidWorld).sub(camera.position);
      const midDepth = _linkMidCam.dot(_focusViewDir);
      const midOffAxisSq = Math.max(0, _linkMidCam.lengthSq() - midDepth * midDepth);
      const midCone = focusConeRadius * LINK_MID_CONE + 2;
      if (midDepth < focusFrontDepth && midOffAxisSq < midCone * midCone) midFrontTarget = 1;
    }
    const midFrontSmooth =
      (mesh.userData.midFrontSmooth || 0) + (midFrontTarget - (mesh.userData.midFrontSmooth || 0)) * linkK;
    mesh.userData.midFrontSmooth = midFrontSmooth;
    targetOpacity *= 1 - midFrontSmooth * effectiveSpotWeight * (1 - LINK_MID_FRONT_KEEP);
    targetOpacity = Math.max(LINK_FOCUS_MIN_OPACITY, targetOpacity);
    mesh.material.opacity += (targetOpacity - mesh.material.opacity) * linkK;
    mesh.userData.currentOpacity = mesh.material.opacity;
  });

  particles.forEach(({ mesh, link }) => {
    mesh.userData.t = (mesh.userData.t + mesh.userData.speed * 0.006) % 1;
    const t = mesh.userData.t;
    const inv = 1 - t;
    // 沿连线同一条二次贝塞尔曲线采样，确保光点始终贴合弧线
    _linkCurvePoint
      .copy(link.userData.cStart)
      .multiplyScalar(inv * inv)
      .addScaledVector(link.userData.cControl, 2 * inv * t)
      .addScaledVector(link.userData.cEnd, t * t);
    mesh.position.copy(_linkCurvePoint);
    // 两端淡出，中段最亮，像一束流动的能量而非生硬的点
    const edgeFade = Math.sin(t * Math.PI);
    // 光点与所属链接的透明度挂钩：链接淡出（聚焦/遮挡）时粒子同步淡出
    const particleFade = Math.min(1, (link.userData.currentOpacity || 0) / LINK_BASE_OPACITY);
    mesh.material.opacity = Math.max(0, 0.7 * particleFade * (0.18 + 0.82 * edgeFade));
    const s = 1.9 + edgeFade * 0.9;
    mesh.scale.set(s, s, 1);
  });

  const targetExposure = BASE_EXPOSURE + effectiveSpotWeight * ((activeConfig.exposure || BASE_EXPOSURE) - BASE_EXPOSURE);
  renderer.toneMappingExposure += (targetExposure - renderer.toneMappingExposure) * (1 - Math.exp(-4.5 * delta));
  // 特写极值段收敛 bloom，防焦点球过曝成白斑
  const bloomConverge = smootherStep(clamp01((effectiveSpotWeight - BLOOM_CONVERGE_START) / BLOOM_CONVERGE_RANGE));
  const targetBloom = BASE_BLOOM_STRENGTH
    + effectiveSpotWeight * ((activeConfig.bloomStrength || BASE_BLOOM_STRENGTH) - BASE_BLOOM_STRENGTH)
      * (1 - bloomConverge * BLOOM_EXTREME_CONVERGE)
    + Math.sin(elapsed * 0.4) * 0.01;
  bloomPass.strength += (targetBloom - bloomPass.strength) * (1 - Math.exp(-4.2 * delta));
  composer.render();
};

const dispose = () => {
  if (rafId) cancelAnimationFrame(rafId);
  resizeObserver?.disconnect();
  visibilityObserver?.disconnect();
  nodeEntries = [];
  linkMeshes = [];
  particles = [];
  orbitRings = [];
  gyroRings = [];
  labelEntries = [];
  labelDistances = new Float32Array(0);
  linkFocusSmooth = 0;
  dustField?.geometry?.dispose();
  dustField?.material?.dispose();
  dustField = null;
  glowPointTexture?.dispose();
  glowPointTexture = null;
  nodeMap.clear();
  composer?.dispose();
  renderer?.dispose();
  renderer?.domElement?.remove();
  renderer = null;
  composer = null;
  scene = null;
  camera = null;
  graphGroup = null;
};

onMounted(() => {
  if (!containerRef.value) return;
  clock = new THREE.Clock();
  buildScene();
  initWideCamera();
  syncSize();
  resizeObserver = new ResizeObserver(syncSize);
  resizeObserver.observe(containerRef.value);
  visibilityObserver = new IntersectionObserver(
    ([entry]) => {
      isPaused = !entry?.isIntersecting;
    },
    { threshold: 0.02 },
  );
  visibilityObserver.observe(containerRef.value);
  rafId = requestAnimationFrame(animate);
});

onUnmounted(dispose);
</script>

<style scoped>
.hero-knowledge-scene {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  /* 多层径向渐变：青绿主调中掺入一缕靛蓝，增加色彩深度 */
  background:
    radial-gradient(ellipse 55% 45% at 82% 22%, rgba(73, 88, 158, 0.16), transparent 62%),
    radial-gradient(ellipse 45% 55% at 30% 80%, rgba(13, 78, 60, 0.2), transparent 58%),
    radial-gradient(ellipse 90% 95% at 62% 48%, #142420 0%, #0c1513 48%, #081110 100%);
}

.hero-knowledge-scene :deep(canvas) {
  display: block;
  width: 100% !important;
  height: 100% !important;
}

/* 底部渐隐：深色 3D 区自然过渡到浅色正文 */
.hero-knowledge-scene::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 18%;
  pointer-events: none;
  background: linear-gradient(180deg, transparent 0%, rgba(248, 248, 247, 0.45) 62%, #f8f8f7 100%);
}
</style>
