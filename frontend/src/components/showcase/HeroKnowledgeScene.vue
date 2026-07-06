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

const containerRef = ref(null);

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

const easeInOut = (t) => {
  const x = Math.max(0, Math.min(1, t));
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
};

const smootherStep = (t) => {
  const x = Math.max(0, Math.min(1, t));
  return x * x * x * (x * (x * 6 - 15) + 10);
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

const innerSpherePos = (index, total, radius) => {
  const golden = Math.PI * (3 - Math.sqrt(5));
  const y = 1 - (index / Math.max(total - 1, 1)) * 2;
  const r = Math.sqrt(Math.max(0, 1 - y * y));
  const theta = golden * index;
  // 纵向压扁为环绕带（0.5），绕 Y 轴旋转时卫星明显环绕大节点而非两极几乎不动
  return new THREE.Vector3(Math.cos(theta) * r * radius, y * radius * 0.5, Math.sin(theta) * r * radius);
};

const PLATFORM_INNER_LAYOUT = [
  [-24, -4, -2],
  [-19, 5.5, 5],
  [-8.5, 8.5, -5],
  [8.5, 8.5, 5],
  [19, 5.5, -3],
  [24, -4, 4],
  [10, -9.5, -5],
  [-10, -9.5, 5],
];

const innerNodePosition = (nodeId, index, total, radius, hubRadius) => {
  if (nodeId !== "platform") {
    return innerSpherePos(index, total, radius);
  }

  const base = PLATFORM_INNER_LAYOUT[index % PLATFORM_INNER_LAYOUT.length];
  const scale = Math.max(radius, hubRadius * 2.8) / 24;
  return new THREE.Vector3(base[0] * scale, base[1] * scale, base[2] * scale);
};

const INNER_TUBE_SEGMENTS = 20;
const INNER_TUBE_RADIAL = 6;

const createInnerLink = (from, to) => {
  const dir = new THREE.Vector3().subVectors(to, from);
  const len = dir.length();
  if (len < 0.01) return null;

  const normalized = dir.clone().divideScalar(len);
  const start = from.clone().addScaledVector(normalized, 1.2);
  const end = to.clone().addScaledVector(normalized, -1.2);
  const control = start.clone().add(end).multiplyScalar(0.5);
  const outward = control.clone();
  if (outward.lengthSq() < 0.01) {
    // 两卫星近乎对穿时，中点贴近球心，沿端点连线的法向选一个稳定外凸方向
    outward.crossVectors(start, end);
    if (outward.lengthSq() < 0.01) outward.set(0, 1, 0);
  }
  outward.normalize();
  // 关键修复：让弧线明显外凸到卫星壳层之外，整条连线绕过中心大节点，
  // 形成清晰的“环绕轨道”而非笔直穿心的弦线（贝塞尔 t=0.5 仅移动一半推力，故乘 2）
  const apexTarget = Math.max(start.length(), end.length()) + 2;
  const push = Math.max(3.5, 2 * (apexTarget - control.length()));
  control.addScaledVector(outward, push);

  const curve = new THREE.QuadraticBezierCurve3(start, control, end);
  const geometry = new THREE.TubeGeometry(curve, INNER_TUBE_SEGMENTS, 0.05, INNER_TUBE_RADIAL, false);

  // 沿管长方向端点淡出的顶点色，与主题青绿一致，柔和融入小节点
  const base = new THREE.Color(0x9fe0d0);
  const ring = INNER_TUBE_RADIAL + 1;
  const count = geometry.attributes.position.count;
  const colors = new Float32Array(count * 3);
  for (let i = 0; i < count; i += 1) {
    const u = Math.floor(i / ring) / INNER_TUBE_SEGMENTS;
    const edge = Math.min(u, 1 - u);
    const a = Math.min(1, edge / 0.22);
    colors[i * 3] = base.r * a;
    colors[i * 3 + 1] = base.g * a;
    colors[i * 3 + 2] = base.b * a;
  }
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));

  const mesh = new THREE.Mesh(
    geometry,
    new THREE.MeshBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.5,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  mesh.renderOrder = 15;
  return mesh;
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

  const satellites = config.nodes.map((item, index) => {
    const isPlatformNetwork = nodeId === "platform";
    const pos = innerNodePosition(nodeId, index, config.nodes.length, config.radius || 10, hubRadius);
    const sat = new THREE.Mesh(
      new THREE.SphereGeometry(isPlatformNetwork ? 0.96 : 1.15, 20, 20),
      new THREE.MeshStandardMaterial({
        color: item.color,
        emissive: new THREE.Color(item.color),
        emissiveIntensity: 0.22,
        metalness: 0.3,
        roughness: 0.45,
      }),
    );
    sat.position.copy(pos);
    group.add(sat);

    const label = createMiniLabel(item.name, item.subtitle, item.color);
    if (isPlatformNetwork) {
      label.scale.set(4.6, 1.42, 1);
    }
    label.userData.baseOffsetY = isPlatformNetwork ? 2.7 : 2.2;
    label.position.copy(pos).add(new THREE.Vector3(0, label.userData.baseOffsetY, 0));
    group.add(label);

    return { mesh: sat, label, pos };
  });

  const innerLinks = [];
  config.links.forEach(([a, b]) => {
    if (!satellites[a] || !satellites[b]) return;
    const link = createInnerLink(satellites[a].pos, satellites[b].pos);
    if (link) {
      group.add(link);
      innerLinks.push(link);
    }
  });

  const reachRadius = satellites.reduce((max, sat) => Math.max(max, sat.pos.length() + 3.2), hubRadius * 1.2);

  return { group, cage, satellites, innerLinks, reachRadius };
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
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(r, r + (i === 2 ? 0.5 : 0.4), 128),
      new THREE.MeshBasicMaterial({
        color: i === 0 ? 0x34d399 : i === 1 ? 0x818cf8 : 0x64748b,
        transparent: true,
        opacity: i === 0 ? 0.08 : i === 1 ? 0.055 : 0.04,
        side: THREE.DoubleSide,
        depthWrite: false,
      }),
    );
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
  });

  if (dustField) {
    dustField.rotation.y = -accumulatedRotation * 0.32;
    dustField.rotation.x = Math.sin(elapsed * 0.05) * 0.04;
    dustField.material.opacity = 0.32 - effectiveSpotWeight * 0.14;
  }

  gyroRings.forEach((g) => {
    g.pivot.rotation.y = elapsed * g.spec.speed;
    const angle = elapsed * g.spec.speed * 7 + g.phase;
    g.tracer.position.set(Math.cos(angle) * g.spec.radius, Math.sin(angle) * g.spec.radius, 0);
    const fade = 1 - effectiveSpotWeight * 0.55;
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
    let dimOthers = effectiveSpotWeight > 0.15 && nodeSpot < 0.05 ? 1 - effectiveSpotWeight * 0.32 : 1;
    if (platformFocusWeight > 0.08 && group.userData.nodeId !== "platform") {
      dimOthers *= 1 - platformFocusWeight * 0.55;
    }
    const innerReveal = nodeSpot > 0.02 ? easeInOut(Math.max(0, (nodeSpot - 0.12) / 0.88)) : 0;

    group.getWorldPosition(_worldPos);
    _camToNode.copy(_worldPos).sub(camera.position).normalize();
    const facing = Math.max(0, _camToNode.dot(_viewDirNeg));
    const highlight = facing ** 2.2;

    const pulse = 1 + Math.sin(elapsed * 1.2 + group.userData.phase) * 0.025;
    const scaleBoost = 1 + highlight * 0.04 + spotBoost * 0.045;
    const r = group.userData.baseRadius * pulse * scaleBoost;
    group.userData.currentVisualRadius = r;

    group.userData.core.scale.setScalar(r / group.userData.baseRadius);
    group.userData.glow.scale.setScalar(r / group.userData.baseRadius);
    group.userData.core.material.emissiveIntensity =
      Math.max(0.08, (group.userData.baseEmissive + highlight * 0.045 - spotBoost * 0.11) * dimOthers);
    group.userData.core.material.opacity = (0.78 + spotBoost * 0.02) * dimOthers;
    // 菲涅尔辉光：朝向相机/特写时增强，特写内部展开时收敛避免遮挡
    group.userData.glow.material.uniforms.uIntensity.value =
      (group.userData.baseGlow + highlight * 0.35 + spotBoost * 0.2 - innerReveal * 0.3) * dimOthers;
    group.userData.shell.material.opacity = (0.18 + spotBoost * 0.08) * dimOthers;
    group.userData.surfaceWire.material.opacity = (0.07 + innerReveal * 0.2 + spotBoost * 0.06) * dimOthers;

    if (group.userData.wire) {
      group.userData.wire.rotation.y = elapsed * 0.35;
      group.userData.wire.rotation.x = elapsed * 0.22;
      group.userData.wire.material.opacity = 0.12 + innerReveal * 0.2;
    }
    if (group.userData.label) {
      const isPlatformLabel = group.userData.nodeId === "platform";
      const platformLabelFade = isPlatformLabel ? 1 - innerReveal * PLATFORM_LABEL_FOCUS_FADE : 1;
      group.userData.label.material.opacity = (0.88 + spotBoost * 0.1) * dimOthers * platformLabelFade;
      const base = group.userData.labelBaseScale || 22;
      const nodeConfig = getSpotlightConfig(group.userData.nodeId);
      const labelScaleBoost = isPlatformLabel ? 0.06 : 0.16;
      const s = base * (0.96 + spotBoost * labelScaleBoost);
      group.userData.label.scale.set(s, s * 0.31, 1);
      group.userData.label.position.y =
        group.userData.label.userData.baseY + spotBoost * (nodeConfig.labelLift || CLOSE_LOOK_LIFT);
    }

    const inner = group.userData.innerNetwork;
    group.userData.innerReveal = innerReveal;
    if (inner) {
      inner.group.visible = innerReveal > 0.03;
      const innerScale = 0.45 + innerReveal * 0.55;
      inner.group.scale.setScalar(innerScale);
      // 放慢公转、收敛摆动幅度，让小节点环绕更从容优雅而非机械急转
      inner.group.rotation.y = elapsed * 0.26;
      inner.group.rotation.x = Math.sin(elapsed * 0.22) * 0.1;
      inner.cage.material.opacity = 0.06 + innerReveal * 0.22;
      inner.cage.rotation.y = -elapsed * 0.2;
      inner.satellites.forEach((sat, i) => {
        sat.mesh.material.emissiveIntensity = 0.15 + innerReveal * 0.25;
        sat.label.material.opacity = 0.4 + innerReveal * 0.55;
        sat.mesh.position.copy(sat.pos);
        // 轻柔上下浮动 + 沿半径方向的呼吸，营造环绕的生命感
        const breathe = 1 + Math.sin(elapsed * 0.7 + i * 0.9) * 0.04 * innerReveal;
        sat.mesh.position.multiplyScalar(breathe);
        sat.mesh.position.y += Math.sin(elapsed * 0.9 + i) * 0.14 * innerReveal;
        sat.label.position.copy(sat.mesh.position).add(new THREE.Vector3(0, sat.label.userData.baseOffsetY || 2.2, 0));
      });
      inner.innerLinks.forEach((link) => {
        link.material.opacity = 0.22 + innerReveal * 0.4;
      });
    }
  });

  linkMeshes.forEach(({ mesh, source, target }) => {
    const sourceSpot = nodeSpotWeight(source.userData.nodeId, focusId, spotWeight, secondaryFocusId, secondaryWeight);
    const targetSpot = nodeSpotWeight(target.userData.nodeId, focusId, spotWeight, secondaryFocusId, secondaryWeight);
    const relatedSpot = Math.max(sourceSpot, targetSpot);
    updateLinkMesh(mesh, source, target, (activeConfig.linkArc || DEFAULT_SPOTLIGHT.linkArc) * (1 + relatedSpot * 0.35));
    const base = mesh.userData.baseOpacity ?? 0.62;
    const pulse = Math.sin(elapsed * 2 + source.userData.phase) * 0.06;
    const incidentFade = 1 - relatedSpot * 0.42;
    const spotFade = 1 - effectiveSpotWeight * 0.5;
    mesh.material.opacity = Math.max(0.018, (base * 0.9 + pulse * 0.35) * spotFade * incidentFade);
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
    const particleFade = 1 - effectiveSpotWeight * 0.85;
    mesh.material.opacity = Math.max(0, 0.7 * particleFade * (0.18 + 0.82 * edgeFade));
    const s = 1.9 + edgeFade * 0.9;
    mesh.scale.set(s, s, 1);
  });

  const targetExposure = BASE_EXPOSURE + effectiveSpotWeight * ((activeConfig.exposure || BASE_EXPOSURE) - BASE_EXPOSURE);
  renderer.toneMappingExposure += (targetExposure - renderer.toneMappingExposure) * (1 - Math.exp(-4.5 * delta));
  const targetBloom = BASE_BLOOM_STRENGTH
    + effectiveSpotWeight * ((activeConfig.bloomStrength || BASE_BLOOM_STRENGTH) - BASE_BLOOM_STRENGTH)
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
