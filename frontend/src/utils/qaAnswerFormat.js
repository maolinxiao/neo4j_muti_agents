const SECTION_ALIASES = {
  总结: "总结建议",
  总结建议: "总结建议",
  注意事项: "注意事项",
  "风险与禁忌": "风险与禁忌",
  风险禁忌: "风险与禁忌",
  合规边界: "合规边界",
  证据边界: "证据边界",
  追问建议: "追问建议",
  用户画像: "体质或人群判断依据",
  判断依据: "体质或人群判断依据",
  量表依据: "体质或人群判断依据",
  体质判断依据: "体质或人群判断依据",
  人群判断依据: "体质或人群判断依据",
  "用户画像/体质判断依据": "体质或人群判断依据",
  "体质或人群判断依据": "体质或人群判断依据",
  推荐理由: "推荐理由",
  推荐方案: "推荐方案",
  "食养建议": "食养或产品适配建议",
  "产品适配建议": "食养或产品适配建议",
  "食养或产品适配建议": "食养或产品适配建议",
  替代对比: "替代对比",
  任务路由: "任务路由",
  "研发建议": "研发或产品建议",
  "产品建议": "研发或产品建议",
  "研发或产品建议": "研发或产品建议",
  "风味与剂型判断": "风味与剂型判断",
  "下一步验证": "下一步验证",
  "风味与人群适配": "风味与人群适配",
  "风味和人群适配": "风味与人群适配",
  "人群与风味适配": "风味与人群适配",
  "目标人群与风味": "风味与人群适配",
  原方依据: "原方依据",
  替代依据: "替代依据",
  保留与替代分流: "保留与替代分流",
  动态替代对比: "动态替代对比",
  重组配方建议: "重组配方建议",
  风味与剂型优化: "风味与剂型优化",
  替代候选排序: "替代候选排序",
  评分拆解: "评分拆解",
  不能完全替代点: "不能完全替代点",
  方剂组成: "方剂组成与剂量",
  "方剂组成与剂量": "方剂组成与剂量",
  知识依据: "知识依据",
  合规依据: "合规边界",
  图谱依据: "知识依据",
  核心结论: "核心结论",
};

export const SECTION_ORDER = [
  "核心结论",
  "任务路由",
  "体质或人群判断依据",
  "原方依据",
  "替代依据",
  "方剂组成与剂量",
  "保留与替代分流",
  "替代候选排序",
  "评分拆解",
  "动态替代对比",
  "不能完全替代点",
  "推荐理由",
  "推荐方案",
  "食养或产品适配建议",
  "研发或产品建议",
  "替代对比",
  "重组配方建议",
  "风味与剂型判断",
  "风味与剂型优化",
  "风味与人群适配",
  "合规边界",
  "知识依据",
  "风险与禁忌",
  "注意事项",
  "证据边界",
  "总结建议",
  "追问建议",
];

const normalizeTitle = (title) => {
  const cleaned = (title || "").trim().replace(/\s+/g, "");
  return SECTION_ALIASES[cleaned] || cleaned;
};

const sectionRank = (title) => {
  const normalized = normalizeTitle(title);
  const index = SECTION_ORDER.indexOf(normalized);
  return index === -1 ? SECTION_ORDER.length + 1 : index;
};

export const sectionMeta = (title) => {
  const normalized = normalizeTitle(title);
  if (normalized === "核心结论") {
    return { tone: "primary", icon: "conclusion" };
  }
  if (
    normalized === "图谱依据" ||
    normalized === "知识依据" ||
    normalized === "证据边界" ||
    normalized === "任务路由" ||
    normalized === "原方依据" ||
    normalized === "方剂组成与剂量" ||
    normalized === "体质或人群判断依据"
  ) {
    return { tone: "info", icon: "evidence" };
  }
  if (
    normalized === "注意事项" ||
    normalized === "风险与禁忌" ||
    normalized === "风险禁忌"
  ) {
    return { tone: "warning", icon: "caution" };
  }
  if (
    normalized === "推荐方案" ||
    normalized === "推荐理由" ||
    normalized === "食养或产品适配建议" ||
    normalized === "研发或产品建议" ||
    normalized === "替代对比" ||
    normalized === "保留与替代分流" ||
    normalized === "替代候选排序" ||
    normalized === "评分拆解" ||
    normalized === "动态替代对比" ||
    normalized === "重组配方建议" ||
    normalized === "风味与剂型判断" ||
    normalized === "风味与剂型优化" ||
    normalized === "风味与人群适配" ||
    normalized === "替代依据"
  ) {
    return { tone: "success", icon: "plan" };
  }
  if (normalized === "合规边界" || normalized === "不能完全替代点") {
    return { tone: "warning", icon: "caution" };
  }
  if (normalized === "总结建议" || normalized === "追问建议") {
    return { tone: "muted", icon: "summary" };
  }
  return { tone: "default", icon: "default" };
};

export const parseAnswerSections = (content) => {
  const text = (content || "").trim();
  if (!text.includes("【")) return [];

  const sectionPattern = /【([^】]+)】/g;
  const matches = [...text.matchAll(sectionPattern)];
  if (!matches.length) return [];

  const sections = matches
    .map((match, index) => {
      const nextMatch = matches[index + 1];
      return {
        title: normalizeTitle(match[1]),
        body: text.slice(match.index + match[0].length, nextMatch?.index ?? text.length).trim(),
      };
    })
    .filter((section) => section.title && section.body);

  return sections.sort((a, b) => sectionRank(a.title) - sectionRank(b.title));
};

const scoreBand = (raw) => {
  const score = Number(raw);
  if (!Number.isFinite(score)) return raw;
  if (score >= 0.75) return "较高";
  if (score >= 0.55) return "中等";
  return "偏低";
};

const hideRawScores = (value) =>
  value
    .replace(
      /\b(final_score|professional_score|flavor_acceptance|consumer_final_score|overall_flavor_acceptance|safety_score)\b/gi,
      "评分维度",
    )
    .replace(/(^|[^\d×])(0\.\d+|1\.0+)(?![\d×])/g, (_, prefix, score) => `${prefix}${scoreBand(score)}`);

export const cleanAnswerText = (value) =>
  hideRawScores(
    (value || "")
    .replace(/(^|\n)\s*\*\s+/g, "$1- ")
    .replace(/\*{2,3}([^*\n]+?)\*{2,3}\s*([：:])?/g, (_, inner, colon) => `${inner}${colon || ""}`)
    .replace(/\*{2,3}/g, "")
    .trim(),
  );

const cleanInlineMarkdown = cleanAnswerText;

const parseDefinitionLine = (line) => {
  const trimmed = line.trim();
  const definition = trimmed.match(/^(?:[-*•]\s*)?\*{2,3}(.+?)\*{2,3}\s*[：:]\s*(.*)$/);
  if (definition) {
    return {
      term: cleanInlineMarkdown(definition[1]),
      text: cleanInlineMarkdown(definition[2]),
    };
  }
  const boldOnly = trimmed.match(/^(?:[-*•]\s*)?\*{2,3}(.+?)\*{2,3}\s*$/);
  if (boldOnly) {
    return {
      term: cleanInlineMarkdown(boldOnly[1]),
      text: "",
    };
  }
  return null;
};

const isListLine = (line) => /^(\d+[.)、]|[-*•])\s+/.test(line.trim());

export const formatSectionBody = (body) => {
  const lines = (body || "").split("\n").map((line) => line.trimEnd());
  const blocks = [];
  let listItems = [];
  let listOrdered = false;
  let paragraph = [];

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push({ type: "paragraph", text: cleanInlineMarkdown(paragraph.join("\n")) });
      paragraph = [];
    }
  };

  const flushList = () => {
    if (listItems.length) {
      blocks.push({ type: "list", ordered: listOrdered, items: [...listItems] });
      listItems = [];
      listOrdered = false;
    }
  };

  lines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) {
      flushList();
      flushParagraph();
      return;
    }
    const definition = parseDefinitionLine(trimmed);
    if (definition) {
      flushList();
      flushParagraph();
      blocks.push({ type: "definition", ...definition });
      return;
    }
    if (isListLine(trimmed)) {
      flushParagraph();
      const ordered = /^\d+[.)、]/.test(trimmed);
      if (listItems.length && listOrdered !== ordered) {
        flushList();
      }
      listOrdered = ordered;
      listItems.push(cleanInlineMarkdown(trimmed.replace(/^(\d+[.)、]|[-*•])\s+/, "")));
      return;
    }
    flushList();
    paragraph.push(cleanInlineMarkdown(trimmed));
  });

  flushList();
  flushParagraph();
  return blocks;
};

export const sectionClass = (title) => {
  const { tone } = sectionMeta(title);
  if (tone === "warning") return "is-warning";
  if (tone === "primary") return "is-primary";
  if (tone === "info") return "is-info";
  if (tone === "success") return "is-plan";
  if (tone === "muted") return "is-summary";
  return "";
};
