<template>
  <div class="canvas-wrap">
    <svg
      v-if="layoutNodes.length"
      ref="svgRef"
      class="graph-box"
      :viewBox="`0 0 ${viewWidth} ${viewHeight}`"
      preserveAspectRatio="xMidYMid meet"
      @wheel.prevent="onWheel"
      @pointerdown.self="startPan"
      @pointermove="onPointerMove"
      @pointerup="stopDragOrPan"
      @pointerleave="stopDragOrPan"
    >
      <defs>
        <marker id="arrow" markerWidth="10" markerHeight="10" refX="7" refY="3" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L0,6 L9,3 z" fill="#94a3b8" />
        </marker>
      </defs>

      <g :transform="`translate(${panOffset.x},${panOffset.y}) scale(${zoomLevel})`">
        <!-- Sector arcs -->
        <g v-for="sector in visibleSectors" :key="sector.key">
          <path
            :d="sector.arcPath"
            :fill="sector.fill"
            :stroke="sector.stroke"
            stroke-dasharray="8 7"
            opacity="0.6"
          />
          <text
            :x="sector.labelX"
            :y="sector.labelY"
            class="sector-label"
            :transform="sector.labelTransform"
          >{{ sector.label }}</text>
        </g>

        <!-- Edges -->
        <g v-for="edge in layoutEdges" :key="edge.id" class="edge-group" @click="emit('edge-click', edge.id)">
          <line
            :x1="edge.sourceNode.x"
            :y1="edge.sourceNode.y"
            :x2="edge.targetNode.x"
            :y2="edge.targetNode.y"
            :class="['edge-line', { highlighted: edge.highlighted }]"
            marker-end="url(#arrow)"
          />
          <text :x="edge.labelX" :y="edge.labelY" class="edge-label">{{ edge.type }}</text>
        </g>

        <!-- Nodes -->
        <g
          v-for="node in layoutNodes"
          :key="node.id"
          class="node-group"
          @click="handleNodeClick(node)"
          @pointerdown.stop="startDrag($event, node)"
        >
          <circle
            :cx="node.x"
            :cy="node.y"
            :r="node.radius"
            :fill="node.color"
            :class="{ highlighted: node.highlighted, core: node.zoneKey === 'core' }"
          />
          <text :x="node.x" :y="node.y + node.radius + 18" class="node-label">{{ node.label }}</text>
          <text :x="node.x" :y="node.y + 5" class="node-type">{{ node.type }}</text>
        </g>
      </g>
    </svg>
    <div v-else class="empty">暂无证据子图</div>

    <!-- Zoom controls -->
    <div v-if="layoutNodes.length" class="zoom-controls">
      <button class="zoom-btn" @click="zoomIn" title="放大">+</button>
      <span class="zoom-level">{{ Math.round(zoomLevel * 100) }}%</span>
      <button class="zoom-btn" @click="zoomOut" title="缩小">−</button>
      <button class="zoom-btn reset-btn" @click="zoomReset" title="重置">↺</button>
    </div>

    <!-- Path panel -->
    <div v-if="focusPaths.length" class="path-panel">
      <div class="path-title">主路径</div>
      <button
        v-for="(path, index) in focusPaths"
        :key="index"
        type="button"
        class="path-chip"
        @click="emit('path-focus', path)"
      >
        路径 {{ index + 1 }}: {{ path.reason || "图谱证据链" }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  focusPaths: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
});

const emit = defineEmits(["node-click", "edge-click", "path-focus"]);
const viewWidth = 900;
const viewHeight = 520;
const centerX = 450;
const centerY = 260;

const svgRef = ref(null);
const nodePositions = ref({});
const dragging = ref(null);
const panning = ref(null);
const suppressClick = ref({ id: null, until: 0 });
const zoomLevel = ref(1);
const panOffset = ref({ x: 0, y: 0 });

const colorByType = (type) => {
  const palette = {
    Question: "#1e293b",
    Herb: "#4ade80",
    Compound: "#60a5fa",
    Effect: "#fb923c",
    EffectCategory: "#a78bfa",
    Flavor: "#a78bfa",
    Formula: "#fbbf24",
    Product: "#22c55e",
    ConsumerProfile: "#06b6d4",
    ConsumerSegment: "#0ea5e9",
    ConstitutionType: "#ec4899",
    ConstitutionQuestion: "#f472b6",
    Symptom: "#2dd4bf",
    Taboo: "#f87171",
    Source: "#22d3ee",
    NatureFlavor: "#34d399",
    Meridian: "#38bdf8",
    Attribute: "#2dd4bf",
    EvidenceNote: "#f97316",
  };
  return palette[type] || "#94a3b8";
};

const zoneKeyByType = (type) => {
  if (type === "Question") return "core";
  return type || "other";
};

const highlightedNodeIds = computed(() => new Set(props.focusPaths.flatMap((path) => path.node_ids || [])));
const highlightedEdgeIds = computed(() => new Set(props.focusPaths.flatMap((path) => path.edge_ids || [])));

// Group non-core nodes by type, determine sectors
const typeGroups = computed(() => {
  const groups = {};
  for (const node of props.nodes) {
    const type = node.type || node.entity_type || "Entity";
    if (type === "Question") continue;
    if (!groups[type]) groups[type] = [];
    groups[type].push(node);
  }
  return groups;
});

const sectorKeys = computed(() => Object.keys(typeGroups.value));

const sectorFillColors = {
  Herb: "rgba(74,222,128,0.10)", Compound: "rgba(96,165,250,0.10)",
  Effect: "rgba(251,146,60,0.10)", EffectCategory: "rgba(167,139,250,0.10)",
  Flavor: "rgba(167,139,250,0.10)", Formula: "rgba(251,191,36,0.10)",
  Product: "rgba(34,197,94,0.10)", ConsumerProfile: "rgba(6,182,212,0.10)",
  ConsumerSegment: "rgba(14,165,233,0.10)", ConstitutionType: "rgba(236,72,153,0.10)",
  ConstitutionQuestion: "rgba(244,114,182,0.10)",
  Symptom: "rgba(45,212,191,0.10)", Taboo: "rgba(248,113,113,0.10)",
  Source: "rgba(34,211,238,0.10)", NatureFlavor: "rgba(52,211,153,0.10)",
  Meridian: "rgba(56,189,248,0.10)", Attribute: "rgba(45,212,191,0.10)",
  EvidenceNote: "rgba(249,115,22,0.10)",
};

const sectorStrokeColors = {
  Herb: "rgba(74,222,128,0.28)", Compound: "rgba(96,165,250,0.28)",
  Effect: "rgba(251,146,60,0.28)", EffectCategory: "rgba(167,139,250,0.28)",
  Flavor: "rgba(167,139,250,0.28)", Formula: "rgba(251,191,36,0.28)",
  Product: "rgba(34,197,94,0.28)", ConsumerProfile: "rgba(6,182,212,0.28)",
  ConsumerSegment: "rgba(14,165,233,0.28)", ConstitutionType: "rgba(236,72,153,0.28)",
  ConstitutionQuestion: "rgba(244,114,182,0.28)",
  Symptom: "rgba(45,212,191,0.28)", Taboo: "rgba(248,113,113,0.28)",
  Source: "rgba(34,211,238,0.28)", NatureFlavor: "rgba(52,211,153,0.28)",
  Meridian: "rgba(56,189,248,0.28)", Attribute: "rgba(45,212,191,0.28)",
  EvidenceNote: "rgba(249,115,22,0.28)",
};

const visibleSectors = computed(() => {
  const keys = sectorKeys.value;
  const n = keys.length;
  if (n === 0) return [];
  const anglePerSector = (2 * Math.PI) / n;
  const outerR = 240;
  const innerR = 100;

  return keys.map((key, i) => {
    const startAngle = i * anglePerSector - Math.PI / 2;
    const endAngle = startAngle + anglePerSector;
    const midAngle = startAngle + anglePerSector / 2;
    const arcPath = describeArc(centerX, centerY, outerR, startAngle, endAngle)
      + " " + describeArc(centerX, centerY, innerR, endAngle, startAngle, true)
      + " Z";

    const labelR = (outerR + innerR) / 2;
    const rawLx = centerX + labelR * Math.cos(midAngle);
    const rawLy = centerY + labelR * Math.sin(midAngle);
    const labelAngleDeg = (midAngle * 180) / Math.PI;

    return {
      key,
      label: key,
      arcPath,
      fill: sectorFillColors[key] || "rgba(100,116,139,0.06)",
      stroke: sectorStrokeColors[key] || "rgba(100,116,139,0.25)",
      labelX: rawLx,
      labelY: rawLy,
      labelTransform: `rotate(${labelAngleDeg}, ${rawLx}, ${rawLy})`,
    };
  });
});

const describeArc = (cx, cy, r, startAngle, endAngle, reverse) => {
  const sweep = reverse ? 0 : 1;
  const large = endAngle - startAngle > Math.PI ? 1 : 0;
  const x1 = cx + r * Math.cos(startAngle);
  const y1 = cy + r * Math.sin(startAngle);
  const x2 = cx + r * Math.cos(endAngle);
  const y2 = cy + r * Math.sin(endAngle);
  return `M ${x1} ${y1} A ${r} ${r} 0 ${large} ${sweep} ${x2} ${y2}`;
};

const createCircularLayout = (nodes) => {
  const positions = {};
  const types = {};
  for (const node of nodes) {
    const type = node.type || node.entity_type || "Entity";
    if (!types[type]) types[type] = [];
    types[type].push(node);
  }

  const coreNodes = types["Question"] || [];
  delete types["Question"];

  coreNodes.forEach((node, i) => {
    const offs = coreOffsets[i] || { x: 0, y: 10 + 20 * i };
    positions[node.id] = { x: centerX + offs.x, y: centerY + offs.y };
  });

  const typeKeys = Object.keys(types);
  const n = typeKeys.length;
  if (n === 0) return positions;

  const anglePerSector = (2 * Math.PI) / n;
  const innerR = 105;
  const outerR = 250;
  const ringGap = 52;

  typeKeys.forEach((typeKey, i) => {
    const items = types[typeKey];
    const m = items.length;
    const sectorMid = i * anglePerSector - Math.PI / 2;

    // Max nodes per ring before angular overlap (arc at mid-radius / node span)
    const midR = (innerR + outerR) / 2;
    const arcAtMid = anglePerSector * midR;
    const maxPerRing = Math.max(1, Math.floor(arcAtMid / 56));
    const maxRings = Math.floor((outerR - innerR) / ringGap) + 1;
    const ringCount = Math.min(maxRings, Math.max(1, Math.ceil(m / maxPerRing)));

    // Distribute nodes across rings evenly
    const nodesPerRing = [];
    let remaining = m;
    for (let r = 0; r < ringCount; r++) {
      const count = r < ringCount - 1
        ? Math.max(1, Math.ceil(remaining / (ringCount - r)))
        : remaining;
      nodesPerRing.push(count);
      remaining -= count;
    }

    let nodeIdx = 0;
    for (let ring = 0; ring < ringCount; ring++) {
      const count = nodesPerRing[ring];
      const r = ringCount === 1
        ? midR
        : innerR + (outerR - innerR) * ((ring + 0.5) / ringCount);
      // Use 75% of sector angular width to avoid cross-sector label collision
      const spreadAngle = anglePerSector * 0.72;

      for (let j = 0; j < count; j++) {
        if (nodeIdx >= m) break;
        const angle = count === 1
          ? sectorMid
          : sectorMid - spreadAngle / 2 + spreadAngle * (j / (count - 1));
        positions[items[nodeIdx].id] = {
          x: centerX + r * Math.cos(angle),
          y: centerY + r * Math.sin(angle),
        };
        nodeIdx++;
      }
    }
  });

  return positions;
};

const coreOffsets = [
  { x: 0, y: -10 }, { x: -55, y: 28 }, { x: 55, y: 28 },
  { x: -55, y: -36 }, { x: 55, y: -36 }, { x: 0, y: 52 },
];

watch(
  () => props.nodes,
  (nodes) => {
    const defaults = createCircularLayout(nodes);
    const next = {};
    for (const node of nodes) {
      next[node.id] = nodePositions.value[node.id] || defaults[node.id];
    }
    nodePositions.value = next;
  },
  { immediate: true, deep: true },
);

const layoutNodes = computed(() => {
  if (!props.nodes.length) return [];
  const defaults = createCircularLayout(props.nodes);

  return props.nodes.map((node) => {
    const type = node.type || node.entity_type || "Entity";
    const zoneKey = zoneKeyByType(type);
    const position = nodePositions.value[node.id] || defaults[node.id];
    return {
      ...node,
      x: position.x,
      y: position.y,
      radius: zoneKey === "core" ? 27 : highlightedNodeIds.value.has(node.id) ? 26 : 22,
      color: colorByType(type),
      highlighted: highlightedNodeIds.value.has(node.id),
      label: node.label || node.name || node.id,
      type,
      zoneKey,
    };
  });
});

const nodeMap = computed(() => Object.fromEntries(layoutNodes.value.map((node) => [node.id, node])));

const layoutEdges = computed(() =>
  props.edges
    .map((edge) => {
      const sourceNode = nodeMap.value[edge.source];
      const targetNode = nodeMap.value[edge.target];
      if (!sourceNode || !targetNode) return null;
      return {
        ...edge,
        sourceNode,
        targetNode,
        labelX: (sourceNode.x + targetNode.x) / 2,
        labelY: (sourceNode.y + targetNode.y) / 2 - 8,
        highlighted: highlightedEdgeIds.value.has(edge.id),
      };
    })
    .filter(Boolean),
);

// Zoom
const zoomIn = () => { zoomLevel.value = Math.min(2.5, zoomLevel.value + 0.2); };
const zoomOut = () => { zoomLevel.value = Math.max(0.4, zoomLevel.value - 0.2); };
const zoomReset = () => { zoomLevel.value = 1; panOffset.value = { x: 0, y: 0 }; };

const onWheel = (event) => {
  const delta = event.deltaY > 0 ? -0.1 : 0.1;
  const newZoom = Math.max(0.4, Math.min(2.5, zoomLevel.value + delta));
  // Zoom toward cursor position
  const svg = svgRef.value;
  if (svg) {
    const rect = svg.getBoundingClientRect();
    const scaleX = viewWidth / rect.width;
    const scaleY = viewHeight / rect.height;
    const mouseX = (event.clientX - rect.left) * scaleX;
    const mouseY = (event.clientY - rect.top) * scaleY;
    const zoomRatio = newZoom / zoomLevel.value;
    panOffset.value = {
      x: mouseX - zoomRatio * (mouseX - panOffset.value.x),
      y: mouseY - zoomRatio * (mouseY - panOffset.value.y),
    };
  }
  zoomLevel.value = newZoom;
};

// Pan
const startPan = (event) => {
  if (event.target !== svgRef.value && event.target.tagName !== "svg") return;
  panning.value = { startX: event.clientX, startY: event.clientY, origX: panOffset.value.x, origY: panOffset.value.y };
};

const onPointerMove = (event) => {
  if (dragging.value) {
    const point = getPoint(event);
    const movedDistance = Math.hypot(point.x - dragging.value.startX, point.y - dragging.value.startY);
    if (movedDistance > 6) dragging.value.moved = true;
    nodePositions.value = {
      ...nodePositions.value,
      [dragging.value.id]: {
        x: Math.max(42, Math.min(viewWidth - 42, point.x - dragging.value.offsetX)),
        y: Math.max(42, Math.min(viewHeight - 42, point.y - dragging.value.offsetY)),
      },
    };
    return;
  }
  if (panning.value) {
    panOffset.value = {
      x: panning.value.origX + (event.clientX - panning.value.startX),
      y: panning.value.origY + (event.clientY - panning.value.startY),
    };
  }
};

const stopDragOrPan = () => {
  if (dragging.value?.moved) {
    suppressClick.value = { id: dragging.value.id, until: Date.now() + 250 };
  }
  dragging.value = null;
  panning.value = null;
};

const getPoint = (event) => {
  const svg = svgRef.value;
  if (!svg) return { x: 0, y: 0 };
  const rect = svg.getBoundingClientRect();
  const scaleX = viewWidth / rect.width;
  const scaleY = viewHeight / rect.height;
  return {
    x: (event.clientX - rect.left) * scaleX,
    y: (event.clientY - rect.top) * scaleY,
  };
};

const startDrag = (event, node) => {
  const point = getPoint(event);
  dragging.value = {
    id: node.id,
    offsetX: point.x - node.x,
    offsetY: point.y - node.y,
    startX: point.x,
    startY: point.y,
    moved: false,
  };
};

const handleNodeClick = (node) => {
  if (suppressClick.value.id === node.id && Date.now() < suppressClick.value.until) return;
  emit("node-click", node.id);
};
</script>

<style scoped>
.canvas-wrap {
  position: relative;
  min-height: 520px;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  overflow: hidden;
}

.graph-box {
  width: 100%;
  height: 520px;
  display: block;
  background:
    radial-gradient(circle at center, rgba(59, 130, 246, 0.06), transparent 50%),
    linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  cursor: grab;
}
.graph-box:active { cursor: grabbing; }

.empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
}

.sector-label {
  fill: #64748b;
  font-size: 11px;
  font-weight: 600;
  text-anchor: middle;
  dominant-baseline: middle;
}

.edge-line {
  stroke: #cbd5e1;
  stroke-width: 1.6;
}
.edge-line.highlighted {
  stroke: #475569;
  stroke-width: 2.4;
}

.edge-label {
  fill: #475569;
  font-size: 12px;
  text-anchor: middle;
}

.node-group {
  cursor: pointer;
  user-select: none;
}
.node-group circle {
  stroke: #64748b;
  stroke-width: 1.2;
}
.node-group circle.highlighted {
  stroke: #f97316;
  stroke-width: 2.8;
}
.node-group circle.core {
  stroke-width: 2.2;
}

.node-label {
  fill: #0f172a;
  font-size: 13px;
  font-weight: 600;
  text-anchor: middle;
}
.node-type {
  fill: rgba(255, 255, 255, 0.94);
  font-size: 10px;
  font-weight: 700;
  text-anchor: middle;
}

/* Zoom controls */
.zoom-controls {
  position: absolute;
  bottom: 60px;
  right: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  padding: 4px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.zoom-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  color: #475569;
  font-size: 18px;
  font-weight: 600;
  cursor: pointer;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}
.zoom-btn:hover { background: #f1f5f9; color: #0f172a; }
.zoom-level { font-size: 11px; color: #94a3b8; padding: 2px 0; user-select: none; }
.reset-btn { font-size: 14px; color: #64748b; }

/* Path panel */
.path-panel {
  border-top: 1px solid #e5e7eb;
  padding: 12px 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  background: #f8fafc;
}
.path-title {
  width: 100%;
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
}
.path-chip {
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #334155;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  cursor: pointer;
}
</style>
