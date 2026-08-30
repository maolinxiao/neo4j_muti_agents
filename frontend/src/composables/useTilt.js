/**
 * useTilt — 卡片 3D 倾斜 + 高光 glare 跟随 composable。
 *
 * 用法（容器级事件委托，支持多个卡片）：
 *   const { tilt } = useTilt(scopeRef, { selector: ".capability-card", maxDeg: 6 });
 *   <div ref="scopeRef" @mousemove="tilt.onMove" @mouseleave="tilt.onLeave"> ... 卡片 ... </div>
 *
 * 行为：
 *   - mousemove 驱动：命中卡片后按鼠标相对中心位置计算 rotateX/rotateY
 *     （最大 ±maxDeg），并写入 --tilt-gx / --tilt-gy（百分比）供 glare 高光定位；
 *   - rAF 逐帧 lerp 插值，避免 CSS transition 与每帧赋值互相打架；
 *   - 离开命中卡片后目标归零并平滑复位，全部归零后移除 inline transform，恢复原 CSS；
 *   - prefers-reduced-motion: reduce 时完全禁用（不绑定、不改任何 inline 样式）；
 *   - 命中时给元素加 .tilt-hover 类，方便组件做 glare 显隐。
 *
 * 注意：
 *   - 元素原始 transform 声明（如 .sc-card-hover:hover 的 translateY）会被 inline
 *     transform 覆盖，因此 liftY 参数用于补偿（默认 -3px，与全局 hover 视觉一致）；
 *   - 挂载时会把元素的 transition 限制为 box-shadow/border-color + will-change:
 *     transform，避免原 CSS 的 transform transition 与逐帧插值互相拖尾；
 *   - 元素集合在 onMounted + nextTick 收集（v-for 常驻元素均会命中）。
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";

/** 通用媒体查询 ref（返回 boolean 响应式值；setup 时同步求值一次） */
export function useMediaQuery(query) {
  const matches = ref(false);
  let mql = null;

  const update = () => {
    matches.value = mql?.matches ?? false;
  };

  if (typeof window !== "undefined" && window.matchMedia) {
    mql = window.matchMedia(query);
    update();
    mql.addEventListener?.("change", update);
  }

  onMounted(() => {
    // 首次 setup 时 window 不可用（极端场景）则在挂载后补绑
    if (!mql && typeof window !== "undefined" && window.matchMedia) {
      mql = window.matchMedia(query);
      update();
      mql.addEventListener?.("change", update);
    }
  });

  onUnmounted(() => {
    mql?.removeEventListener?.("change", update);
    mql = null;
  });

  return matches;
}

export function useTilt(scopeRef, options = {}) {
  const {
    selector = ".tilt-card",
    maxDeg = 6,
    perspective = 900,
    liftY = -3,
    hoverScale = 1.02,
    lerp = 0.16,
  } = options;

  const reducedMotion = useMediaQuery("(prefers-reduced-motion: reduce)");
  const enabled = computed(() => !reducedMotion.value);

  let items = [];
  let rafId = null;
  let attached = false;

  const clearItemStyle = (item) => {
    item.el.style.removeProperty("transform");
    item.el.style.removeProperty("perspective-origin");
  };

  const applyItem = (item) => {
    const { rx, ry, ty, s } = item;
    item.el.style.transform =
      `perspective(${perspective}px) translateY(${ty.toFixed(2)}px) ` +
      `rotateX(${rx.toFixed(2)}deg) rotateY(${ry.toFixed(2)}deg) ` +
      `scale3d(${s.toFixed(4)}, ${s.toFixed(4)}, 1)`;
  };

  const tick = () => {
    rafId = null;
    let active = false;

    for (const item of items) {
      // lerp 插值
      item.rx += (item.trx - item.rx) * lerp;
      item.ry += (item.try - item.ry) * lerp;
      item.ty += (item.tty - item.ty) * lerp;
      item.s += (item.ts - item.s) * lerp;

      const settled =
        Math.abs(item.rx - item.trx) < 0.001 &&
        Math.abs(item.ry - item.try) < 0.001 &&
        Math.abs(item.ty - item.tty) < 0.001 &&
        Math.abs(item.s - item.ts) < 0.0001;

      if (item.hovering) {
        if (settled && item.dirty) {
          applyItem(item);
          item.dirty = false;
          continue; // 已稳定：不再请求下一帧，等 onMove 再次唤醒
        }
        if (!settled) item.dirty = true;
        applyItem(item);
        active = true;
      } else if (
        Math.abs(item.rx) > 0.02 ||
        Math.abs(item.ry) > 0.02 ||
        Math.abs(item.ty) > 0.02 ||
        Math.abs(item.s - 1) > 0.002
      ) {
        applyItem(item);
        active = true;
      } else {
        item.rx = 0;
        item.ry = 0;
        item.ty = 0;
        item.s = 1;
        item.dirty = false;
        clearItemStyle(item);
      }
    }

    if (active) rafId = window.requestAnimationFrame(tick);
    else rafId = null;
  };

  const ensureLoop = () => {
    if (!enabled.value) return;
    if (rafId == null && items.length > 0) rafId = window.requestAnimationFrame(tick);
  };

  const settleAll = (hovering) => {
    for (const item of items) {
      item.hovering = hovering;
      item.trx = 0;
      item.try = 0;
      item.tty = 0;
      item.ts = 1;
      item.el.classList.remove("tilt-hover");
    }
    ensureLoop();
  };

  const onMove = (event) => {
    if (!enabled.value || !scopeRef.value) return;
    for (const item of items) {
      const rect = item.el.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) {
        if (item.hovering) {
          item.hovering = false;
          item.trx = item.try = 0;
          item.tty = 0;
          item.ts = 1;
          item.el.classList.remove("tilt-hover");
        }
        continue;
      }
      const inside =
        event.clientX >= rect.left &&
        event.clientX <= rect.right &&
        event.clientY >= rect.top &&
        event.clientY <= rect.bottom;

      if (inside) {
        const cx = (event.clientX - rect.left) / rect.width;
        const cy = (event.clientY - rect.top) / rect.height;
        item.hovering = true;
        item.trx = (0.5 - cy) * 2 * maxDeg;
        item.try = (cx - 0.5) * 2 * maxDeg;
        item.tty = liftY;
        item.ts = hoverScale;
        item.dirty = true;
        item.el.style.setProperty("--tilt-gx", `${(cx * 100).toFixed(1)}%`);
        item.el.style.setProperty("--tilt-gy", `${(cy * 100).toFixed(1)}%`);
        item.el.classList.add("tilt-hover");
      } else if (item.hovering) {
        item.hovering = false;
        item.trx = 0;
        item.try = 0;
        item.tty = 0;
        item.ts = 1;
        item.dirty = true;
        item.el.classList.remove("tilt-hover");
      }
    }
    ensureLoop();
  };

  const onLeave = () => {
    if (!scopeRef.value) return;
    settleAll(false);
  };

  const attach = () => {
    const scope = scopeRef.value;
    if (!scope || attached || !enabled.value) return;
    items = Array.from(scope.querySelectorAll(selector)).map((el) => ({
      el,
      hovering: false,
      dirty: false,
      rx: 0,
      ry: 0,
      ty: 0,
      s: 1,
      trx: 0,
      try: 0,
      tty: 0,
      ts: 1,
    }));
    items.forEach((item) => {
      // transform 交由 rAF 插值接管，其余 hover 效果保留原 transition
      item.el.style.transition = "box-shadow 0.3s ease, border-color 0.3s ease, background 0.25s ease";
      item.el.style.willChange = "transform";
    });
    attached = true;
  };

  const detach = () => {
    if (rafId != null && typeof window !== "undefined") {
      window.cancelAnimationFrame(rafId);
      rafId = null;
    }
    items.forEach((item) => {
      item.el.classList.remove("tilt-hover");
      clearItemStyle(item);
      item.el.style.removeProperty("transition");
      item.el.style.removeProperty("will-change");
    });
    items = [];
    attached = false;
  };

  // reduced-motion 切换：启用→重新绑定；禁用→全部复位
  watch(
    reducedMotion,
    (reduced) => {
      if (reduced) detach();
      else {
        detach();
        nextTick(attach);
      }
    },
    { flush: "post" },
  );

  onMounted(() => {
    nextTick(attach);
  });

  onUnmounted(detach);

  return { enabled, onMove, onLeave, attach, detach };
}
