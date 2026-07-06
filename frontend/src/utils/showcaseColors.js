const TYPE_COLORS = {
  Platform: "#78d8b7",
  Herb: "#4ade80",
  Effect: "#fb923c",
  EffectCategory: "#a78bfa",
  Flavor: "#a78bfa",
  Formula: "#fbbf24",
  Product: "#22c55e",
  ConstitutionType: "#ec4899",
  ConstitutionQuestion: "#f472b6",
  ComplianceRule: "#6366f1",
  RiskExpression: "#ef4444",
  Symptom: "#2dd4bf",
  Taboo: "#f87171",
  Source: "#22d3ee",
  NatureFlavor: "#34d399",
  Meridian: "#38bdf8",
};

export function colorByType(type) {
  return TYPE_COLORS[type] || "#94a3b8";
}

export { TYPE_COLORS };
