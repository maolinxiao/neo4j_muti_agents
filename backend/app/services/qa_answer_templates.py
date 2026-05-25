"""Knowledge QA answer section templates shared by orchestrator and LLM client."""

from __future__ import annotations

import re

# General 5-section outline (entity explanation, herb efficacy, formula relation)
GENERAL_SECTION_ORDER = [
    "核心结论",
    "图谱依据",
    "方剂组成与剂量",
    "注意事项",
    "总结建议",
]

RECOMMENDATION_SECTION_ORDER = [
    "核心结论",
    "用户画像/体质判断依据",
    "推荐方案",
    "图谱依据",
    "风险与禁忌",
    "证据边界",
    "追问建议",
]

REPLACEMENT_SECTION_ORDER = [
    "核心结论",
    "替代对比",
    "图谱依据",
    "风险与禁忌",
    "证据边界",
    "总结建议",
]

SECTION_ALIASES: dict[str, str] = {
    "总结": "总结建议",
    "总结建议": "总结建议",
    "注意事项": "注意事项",
    "风险与禁忌": "风险与禁忌",
    "风险禁忌": "风险与禁忌",
    "证据边界": "证据边界",
    "追问建议": "追问建议",
    "用户画像": "用户画像/体质判断依据",
    "体质判断依据": "用户画像/体质判断依据",
    "用户画像/体质判断依据": "用户画像/体质判断依据",
    "推荐方案": "推荐方案",
    "替代对比": "替代对比",
    "方剂组成": "方剂组成与剂量",
    "方剂组成与剂量": "方剂组成与剂量",
    "图谱依据": "图谱依据",
    "核心结论": "核心结论",
}

QUESTION_TYPE_OUTLINES: dict[str, list[str]] = {
    "constitution_recommendation": RECOMMENDATION_SECTION_ORDER,
    "product_recommendation": RECOMMENDATION_SECTION_ORDER,
    "formula_replacement": REPLACEMENT_SECTION_ORDER,
    "formula_relation": GENERAL_SECTION_ORDER,
    "herb_efficacy": GENERAL_SECTION_ORDER,
    "entity_explanation": GENERAL_SECTION_ORDER,
}


def outline_for_question_type(question_type: str) -> list[str]:
    return list(QUESTION_TYPE_OUTLINES.get(question_type, GENERAL_SECTION_ORDER))


def normalize_section_title(title: str) -> str:
    cleaned = (title or "").strip().replace(" ", "")
    return SECTION_ALIASES.get(cleaned, cleaned)


def format_section_header(title: str) -> str:
    return f"【{normalize_section_title(title)}】"


def outline_headers(question_type: str) -> list[str]:
    return [format_section_header(title) for title in outline_for_question_type(question_type)]


def context_answer_rules(question_type: str) -> list[str]:
    headers = "、".join(outline_headers(question_type))
    rules = [
        "只能使用提供的 Neo4j 图谱证据和实体属性回答。",
        "如果问题中出现多个实体或多个症状，必须整体回答，不能只回答其中一个。",
        "如果知识图谱缺少直接关系，要明确说缺少哪一类证据，不能编造。",
        f"conclusion 必须按以下小标题组织（不适用可省略）：{headers}。",
        "【图谱依据】必须把图谱获得的方剂、药材、功效、症状、禁忌、证据边界分点展示，不能只给笼统回答。",
        "conclusion 不要写成笼统建议，不要照抄 evidence_summary。",
        "evidence_summary 只保留支撑结论的关键图谱证据，不要和 conclusion 大面积重复。",
        "不要在 conclusion 中输出 <think>、</think> 或任何内部推理标签。",
        "输出 JSON，字段必须包含 conclusion, evidence_summary, cautions, related_entities, follow_up_questions。",
    ]
    if question_type in {"constitution_recommendation", "product_recommendation"}:
        rules.extend(
            [
                "推荐类问题必须覆盖用户约束（体质/人群、功效、剂型、风味、价格、禁忌等）。",
                "体质推荐不得输出诊断结论；产品推荐只能引用聚合画像与统计数据。",
            ]
        )
    if question_type == "formula_replacement":
        rules.extend(
            [
                "药材替代优先使用 CAN_REPLACE 的 final_score、effect_similarity、flavor_acceptance、rank 排序说明。",
                "存在禁忌排除时必须明确反对推荐。",
            ]
        )
    if question_type in {"formula_relation", "herb_efficacy", "formula_replacement"}:
        rules.append(
            "涉及方剂时必须列出组成、君臣佐使与剂量；缺少剂量时逐味写「图谱未提供剂量」。"
        )
    return rules


def stream_output_instructions(question_type: str) -> str:
    headers = "、".join(outline_headers(question_type))
    return (
        "\n\n【流式输出模式】\n"
        "请用自然语言直接回答用户问题，不要输出 JSON 对象、字段名、代码块或 Markdown 标题符号（#）。\n"
        f"正文必须用小标题分段，优先顺序：{headers}；不适用的小标题可以省略。\n"
        "【图谱依据】分点展示图谱实体、关系与证据边界，禁止笼统判断。\n"
        "缺少剂量时逐味写「图谱未提供剂量」，不要用「若干」「适量」等图谱外补充。\n"
        "不要把 <think>、</think> 或内部推理标签写入正式回答正文。"
    )


_SECTION_PATTERN = re.compile(r"【([^】]+)】")


def parse_conclusion_sections(conclusion: str) -> dict[str, str]:
    text = (conclusion or "").strip()
    if not text:
        return {}
    matches = list(_SECTION_PATTERN.finditer(text))
    if not matches:
        return {}
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        title = normalize_section_title(match.group(1))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections[title] = body
    return sections


def enforce_conclusion_structure(conclusion: str, question_type: str) -> str:
    """Normalize section titles and reorder paragraphs to the expected outline."""
    text = (conclusion or "").strip()
    if not text:
        return text

    sections = parse_conclusion_sections(text)
    if not sections:
        header = format_section_header("核心结论")
        if text.startswith("【"):
            return text
        return f"{header}\n{text}"

    outline = outline_for_question_type(question_type)
    ordered_parts: list[str] = []
    used: set[str] = set()

    for title in outline:
        body = sections.get(title)
        if body:
            ordered_parts.append(f"{format_section_header(title)}\n{body}")
            used.add(title)

    for title, body in sections.items():
        if title in used:
            continue
        ordered_parts.append(f"{format_section_header(title)}\n{body}")

    return "\n\n".join(ordered_parts).strip()


def compose_constraints_block(question_type: str) -> str:
    headers = "、".join(outline_headers(question_type))
    return (
        "补充约束：\n"
        f"1. conclusion 写成结构化自然语言，小标题顺序优先：{headers}；若某部分不适用可省略。\n"
        "1.1 【图谱依据】必须分点展示图谱获得的实体、方剂、药材、功效、症状、禁忌和证据边界。\n"
        "2. evidence_summary 只写关键证据，不要重复 conclusion。\n"
        "3. 不能补充知识图谱里没有提供的功效、禁忌、临床建议。\n"
        "4. related_entities 返回对象数组，每项至少包含 id、name、entity_type。\n"
        "5. 如果证据不足，要明确写「知识图谱未提供直接证据」。\n"
        "6. conclusion 里不要出现节点 id 或「证据：」这种摘要式写法。\n"
        "7. 问到体质/产品推荐时遵守推荐类规则；问到替代时说明 CAN_REPLACE 评分依据。\n"
        "8. conclusion 必须保留【】小标题分段，禁止把分段合并成一整段。\n"
        "9. 禁止把 <think>、</think> 或内部推理标签输出到 conclusion。"
    )
