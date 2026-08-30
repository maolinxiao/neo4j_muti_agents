/**
 * useSectionThree — 展示版块迷你 Three.js 场景的通用生命周期 composable。
 *
 * 职责：
 * - 创建 WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" })
 * - setPixelRatio(min(devicePixelRatio, 1.5))；ResizeObserver 同步画布尺寸与相机纵横比
 * - IntersectionObserver：进入视口才启动 rAF 循环，离屏暂停
 * - window blur/focus：失焦暂停渲染，聚焦后（且仍在视口内）恢复
 * - prefers-reduced-motion：只渲染一帧静态画面（staticFrame=true），不启动动画循环
 * - WebGL 不可用/渲染器创建失败：ok=false，组件走静态回退（如原 SVG 布局）
 * - 统一封装 delta / elapsed / render 回调与 dispose
 *
 * 用法：
 *   const { ok, staticFrame, mount, dispose } = useSectionThree(containerRef, {
 *     createScene: ({ scene, camera, renderer, container }) => ({ update(delta, elapsed, ctx), dispose() }),
 *     render: (ctx) => {},            // 可选：每帧额外渲染回调
 *     onResize: ({ ctx, width, height }) => {},  // 可选：尺寸变化回调
 *     onDispose: () => {},            // 可选：组件级清理
 *   });
 */
import { ref } from "vue";
import * as THREE from "three";

const DPR_MAX = 1.5;
const DELTA_CAP = 0.05;
const VISION_THRESHOLD = 0.05;

/** 递归释放 Object3D 的 geometry / material / texture（组件场景内部复用） */
export function disposeObject3D(root) {
  if (!root) return;
  root.traverse((obj) => {
    if (obj.geometry) obj.geometry.dispose();
    const material = obj.material;
    if (!material) return;
    const list = Array.isArray(material) ? material : [material];
    list.forEach((m) => {
      if (!m) return;
      Object.keys(m).forEach((key) => {
        const value = m[key];
        if (value && value.isTexture) value.dispose();
      });
      m.dispose();
    });
  });
}

/** WebGL 可用性探测（webgl2 -> webgl -> experimental-webgl） */
function isWebGLAvailable(win, doc) {
  try {
    if (!win || !win.WebGLRenderingContext) return false;
    const test = doc.createElement("canvas");
    const gl =
      test.getContext("webgl2") || test.getContext("webgl") || test.getContext("experimental-webgl");
    return !!gl;
  } catch (err) {
    return false;
  }
}

/**
 * 场景内容自适应：按容器纵横比缩放 group，让内容外接框（±reqHalfW × ±reqHalfH）
 * 完整落进相机视野，同时避免过小（maxScale 上限放大，宽容器时铺满）。
 */
export function applySceneFit(group, camera, containerWidth, containerHeight, reqHalfW, reqHalfH, maxScale = 1.8) {
  if (!group || !camera || !containerWidth || !containerHeight) return;
  camera.aspect = containerWidth / containerHeight;
  camera.updateProjectionMatrix();
  const halfH = Math.tan((camera.fov * Math.PI) / 360) * Math.abs(camera.position.z);
  const halfW = halfH * camera.aspect;
  const sx = halfW / Math.max(0.001, reqHalfW);
  const sy = halfH / Math.max(0.001, reqHalfH);
  group.scale.setScalar(Math.max(0.05, Math.min(sx, sy, maxScale)));
}

export function useSectionThree(containerRef, options = {}) {
  const { createScene, render, onResize, onDispose } = options;

  const ok = ref(false);
  const staticFrame = ref(false);

  let mounted = false;
  let disposed = false;

  let renderer = null;
  let scene = null;
  let camera = null;
  let sceneApi = null;
  let ctx = null;
  let clock = null;
  let elapsed = 0;
  let rafId = null;
  let resizeObserver = null;
  let visibilityObserver = null;
  let mediaQuery = null;
  let inViewport = true;
  let windowFocused = true;
  let reducedMotion = false;

  const onBlur = () => {
    windowFocused = false;
    applyVisibility();
  };
  const onFocus = () => {
    windowFocused = true;
    applyVisibility();
  };

  const syncSize = () => {
    const container = containerRef.value;
    if (!container || !renderer || !camera) return;
    const width = container.clientWidth;
    const height = container.clientHeight;
    if (width <= 0 || height <= 0) return;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    onResize?.({ ctx, width, height });
    if (reducedMotion && renderer && scene) renderer.render(scene, camera);
  };

  const renderSingleFrame = () => {
    if (!renderer || !scene || !camera) return;
    sceneApi?.update?.(0, elapsed, ctx);
    render?.(ctx);
    renderer.render(scene, camera);
  };

  const tick = () => {
    rafId = null;
    if (!mounted || disposed || reducedMotion) return;
    if (!inViewport || !windowFocused) return;
    const delta = Math.min(clock.getDelta(), DELTA_CAP);
    elapsed += delta;
    sceneApi?.update?.(delta, elapsed, ctx);
    render?.(ctx);
    renderer.render(scene, camera);
    rafId = window.requestAnimationFrame(tick);
  };

  const startLoop = () => {
    if (rafId != null || !mounted || disposed || reducedMotion) return;
    if (!inViewport || !windowFocused) return;
    clock.getDelta(); // 丢弃暂停期间累积的时间，避免恢复时 delta 跳变
    rafId = window.requestAnimationFrame(tick);
  };

  const stopLoop = () => {
    if (rafId != null && window) {
      window.cancelAnimationFrame(rafId);
      rafId = null;
    }
  };

  const applyVisibility = () => {
    if (!mounted || disposed || reducedMotion) return;
    if (inViewport && windowFocused) startLoop();
    else stopLoop();
  };

  const onMotionChange = (event) => {
    reducedMotion = event?.matches ?? false;
    if (!mounted || disposed) return;
    if (reducedMotion) {
      staticFrame.value = true;
      stopLoop();
      syncSize();
      renderSingleFrame();
    } else {
      staticFrame.value = false;
      applyVisibility();
    }
  };

  const mount = () => {
    if (mounted) return;
    const container = containerRef.value;
    const win = typeof window !== "undefined" ? window : null;
    if (!container || !win) return;
    disposed = false;

    if (!isWebGLAvailable(win, document)) return; // ok 保持 false，组件走静态回退

    reducedMotion = win.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false;

    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        powerPreference: "low-power",
      });
    } catch (err) {
      renderer = null;
      return; // ok 保持 false
    }
    renderer.setPixelRatio(Math.min(win.devicePixelRatio || 1, DPR_MAX));
    renderer.setClearColor(0x000000, 0);
    const canvas = renderer.domElement;
    canvas.style.display = "block";
    canvas.style.width = "100%";
    canvas.style.height = "100%";
    container.appendChild(canvas);

    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    clock = new THREE.Clock();
    ctx = { scene, camera, renderer, container, canvas };
    try {
      sceneApi = createScene?.(ctx) || null;
    } catch (err) {
      sceneApi = null;
    }

    resizeObserver = new ResizeObserver(syncSize);
    resizeObserver.observe(container);
    mounted = true;
    ok.value = true;
    syncSize();

    if (reducedMotion) {
      staticFrame.value = true;
    } else {
      visibilityObserver = new IntersectionObserver(
        ([entry]) => {
          inViewport = entry?.isIntersecting ?? false;
          applyVisibility();
        },
        { threshold: VISION_THRESHOLD },
      );
      visibilityObserver.observe(container);
      win.addEventListener("blur", onBlur);
      win.addEventListener("focus", onFocus);
      startLoop();
    }

    mediaQuery = win.matchMedia?.("(prefers-reduced-motion: reduce)");
    mediaQuery?.addEventListener?.("change", onMotionChange);
  };

  const dispose = () => {
    if (disposed) return;
    disposed = true;
    mounted = false;
    stopLoop();
    resizeObserver?.disconnect();
    resizeObserver = null;
    visibilityObserver?.disconnect();
    visibilityObserver = null;
    mediaQuery?.removeEventListener?.("change", onMotionChange);
    mediaQuery = null;
    if (typeof window !== "undefined") {
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("focus", onFocus);
    }
    try {
      sceneApi?.dispose?.();
    } catch (err) {
      /* 场景清理异常不阻断卸载 */
    }
    if (scene) disposeObject3D(scene);
    renderer?.dispose();
    renderer?.domElement?.remove();
    try {
      onDispose?.();
    } catch (err) {
      /* 组件级清理异常不阻断卸载 */
    }
    renderer = null;
    scene = null;
    camera = null;
    sceneApi = null;
    ctx = null;
    clock = null;
    ok.value = false;
    staticFrame.value = false;
  };

  return { ok, staticFrame, mount, dispose };
}
