/** Hero 深色背景下的高对比节点配色 */
export const HERO_NODE_COLORS = {
  Platform: "#6ee7b7",
  Herb: "#5eead4",
  Formula: "#fcd34d",
  Effect: "#fdba74",
  Product: "#86efac",
  ComplianceRule: "#a5b4fc",
  ConstitutionType: "#f9a8d4",
  KBMarker: "#94a3b8",
};

export const HERO_TYPE_LABELS = {
  Platform: "Platform",
  Herb: "Herb",
  Formula: "Formula",
  Effect: "Effect",
  Product: "Product",
  ComplianceRule: "Compliance",
  ConstitutionType: "Constitution",
  KBMarker: "Knowledge Base",
};

export function heroColorByType(type) {
  return HERO_NODE_COLORS[type] || "#cbd5e1";
}
