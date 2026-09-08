/**
 * 体质辨识（KB8 / CCMQ 中医体质分类与判定量表）英文展示映射。
 *
 * 图谱中的题干（ConstitutionQuestion.question_text）、体质名（constitution_type_name）、
 * 选项描述（score_1..score_5）与食养方向（diet_direction）均为中文数据；界面切换到
 * en-US 时按本映射渲染，缺失条目回退中文原文。题目英译采用 CCMQ 量表通行译法。
 */

/** 体质类型名 → 英文 */
export const CONSTITUTION_TYPE_EN = {
  平和质: "Balanced",
  气虚质: "Qi Deficiency",
  阳虚质: "Yang Deficiency",
  阴虚质: "Yin Deficiency",
  痰湿质: "Phlegm-Dampness",
  湿热质: "Damp-Heat",
  血瘀质: "Blood Stasis",
  气郁质: "Qi Stagnation",
  特禀质: "Special Constitution",
};

/** 题干（按 question_code）→ 英文 */
export const QUESTION_TEXT_EN = {
  "A.1-1": "Do you feel full of energy?",
  "A.1-2": "Do you tire easily?",
  "A.1-3": "Do you feel unhappy or low-spirited?",
  "A.1-4": "Are you less tolerant of cold than most people (winter cold, summer air-conditioning, fans, etc.)?",
  "A.2-1": "Do you tire easily?",
  "A.2-2": "Do you get short of breath easily (shallow breathing, feeling you cannot catch your breath)?",
  "A.2-3": "Does your heart race or palpitate easily?",
  "A.3-1": "Do you dislike cold in your stomach or abdomen, back, or lower back and knees?",
  "A.3-2": "Do you feel cold and wear more clothing than others?",
  "A.3-3": "Are you less tolerant of cold than most people (winter cold, summer air-conditioning, fans, etc.)?",
  "A.4-1": "Do you feel heat in your body or on your face?",
  "A.4-2": "Is your skin or are your lips dry?",
  "A.4-3": "Do your cheeks look flushed or reddish?",
  "A.5-1": "Do you feel heavy, sluggish, or unrefreshed in your body?",
  "A.5-2": "Is your abdomen plump and flabby?",
  "A.5-3": "Does your mouth feel sticky?",
  "A.6-1": "Does your face or nose feel oily or look shiny?",
  "A.6-2": "Do you feel heat in your urethra when urinating, or is your urine dark?",
  "A.6-3": "Is your vaginal discharge yellow in color?",
  "A.6-4": "Is your scrotal area damp?",
  "A.7-1": "Do you have pain anywhere in your body?",
  "A.7-2": "Is your complexion dull, or do you get brown patches on your face easily?",
  "A.7-3": "Are your lips darkish in color?",
  "A.8-1": "Do you feel unhappy or low-spirited?",
  "A.8-2": "Do you feel tense, anxious, or on edge easily?",
  "A.8-3": "Are you sentimental and emotionally fragile?",
  "A.9-1": "Do you sneeze even when you do not have a cold?",
  "A.9-2": "Are you prone to allergies (to medicines, foods, smells, pollen, or when seasons or weather change)?",
  "A.9-3": "Does your skin break out in hives (wheals) easily?",
  "A.9-4": "Does your skin turn red and mark easily when scratched?",
};

/** 选项分数描述（图谱通用量表文案）→ 英文 */
export const SCORE_DESC_EN = {
  "没有（根本不）": "Not at all",
  "很少（有一点）": "Rarely (a little)",
  "有时（有些）": "Sometimes (somewhat)",
  "经常（相当）": "Often (quite a bit)",
  "总是（非常）": "Always (very much)",
};

/** 食养方向（diet_direction）→ 英文 */
export const DIET_DIRECTION_EN = {
  "维持均衡，五味适中，避免长期偏食偏嗜。":
    "Keep a balanced diet with moderate flavors; avoid long-term food preferences or biases.",
  "益气健脾，兼顾温和易消化。":
    "Boost qi and strengthen the spleen; favor mild, easy-to-digest foods.",
  "温阳散寒，减少生冷。":
    "Warm yang and dispel cold; cut down on raw and cold foods.",
  "滋阴润燥，少辛辣燥烈。":
    "Nourish yin and moisten dryness; limit spicy and drying foods.",
  "健脾化湿，少油腻甜黏。":
    "Strengthen the spleen and resolve dampness; limit greasy, sweet, and sticky foods.",
  "清利湿热，少辛辣油炸甜腻。":
    "Clear damp-heat; limit spicy, fried, and sweet foods.",
  "行气活血，避免寒凝。":
    "Move qi and invigorate blood; avoid cold-congealing foods.",
  "疏肝理气，芳香悦情，避免过度刺激。":
    "Soothe the liver and regulate qi with fragrant, mood-lifting foods; avoid over-stimulation.",
  "避敏为先，配方简单，明确过敏原提示。":
    "Prioritize allergen avoidance; keep formulas simple and flag allergens clearly.",
};

/**
 * 按当前语言取映射文案；非 en-US 或映射缺失时回退原文。
 * @param {string} locale 当前语言（useI18n 的 locale）
 * @param {Record<string, string>} map 中文 → 英文映射表
 * @param {string} fallback 图谱原文（中文）
 */
export function localizedText(locale, map, fallback) {
  if (!fallback) return "";
  if (locale === "en-US" && map[fallback] != null) return map[fallback];
  return fallback;
}
