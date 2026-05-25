const SECTION_ALIASES = {
  总结: "总结建议",
  总结建议: "总结建议",
  注意事项: "注意事项",
  "风险与禁忌": "风险与禁忌",
  风险禁忌: "风险与禁忌",
  证据边界: "证据边界",
  追问建议: "追问建议",
  用户画像: "用户画像/体质判断依据",
  体质判断依据: "用户画像/体质判断依据",
  "用户画像/体质判断依据": "用户画像/体质判断依据",
  推荐方案: "推荐方案",
  替代对比: "替代对比",
  方剂组成: "方剂组成与剂量",
  "方剂组成与剂量": "方剂组成与剂量",
  图谱依据: "图谱依据",
  核心结论: "核心结论",
};

export const SECTION_ORDER = [
  "核心结论",
  "用户画像/体质判断依据",
  "推荐方案",
  "替代对比",
  "图谱依据",
  "方剂组成与剂量",
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
  if (normalized === "图谱依据" || normalized === "证据边界") {
    return { tone: "info", icon: "evidence" };
  }
  if (
    normalized === "注意事项" ||
    normalized === "风险与禁忌" ||
    normalized === "风险禁忌"
  ) {
    return { tone: "warning", icon: "caution" };
  }
  if (normalized === "推荐方案" || normalized === "替代对比") {
    return { tone: "success", icon: "plan" };
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

const isListLine = (line) => /^(\d+[.)、]|[-*•])\s+/.test(line.trim());

export const formatSectionBody = (body) => {
  const lines = (body || "").split("\n").map((line) => line.trimEnd());
  const blocks = [];
  let listItems = [];
  let listOrdered = false;
  let paragraph = [];

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push({ type: "paragraph", text: paragraph.join("\n") });
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
    if (isListLine(trimmed)) {
      flushParagraph();
      const ordered = /^\d+[.)、]/.test(trimmed);
      if (listItems.length && listOrdered !== ordered) {
        flushList();
      }
      listOrdered = ordered;
      listItems.push(trimmed.replace(/^(\d+[.)、]|[-*•])\s+/, ""));
      return;
    }
    flushList();
    paragraph.push(trimmed);
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
