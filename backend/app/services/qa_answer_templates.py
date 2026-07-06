"""Knowledge QA answer section templates shared by orchestrator and LLM client."""

from __future__ import annotations

import re

from app.services.qa_routing import get_qa_route_resolver

GENERAL_SECTION_ORDER = [
    "核心结论",
    "知识依据",
    "方剂组成与剂量",
    "风味与人群适配",
    "风险与禁忌",
    "证据边界",
    "总结建议",
    "追问建议",
]

RECOMMENDATION_SECTION_ORDER = [
    "核心结论",
    "判断依据",
    "食养或产品适配建议",
    "风险与禁忌",
    "证据边界",
    "追问建议",
]

PRODUCT_SECTION_ORDER = [
    "核心结论",
    "任务路由",
    "推荐理由",
    "研发或产品建议",
    "风味与剂型判断",
    "合规边界",
    "下一步验证",
    "追问建议",
]

FORMULA_REPLACEMENT_SECTION_ORDER = [
    "核心结论",
    "原方依据",
    "替代依据",
    "保留与替代分流",
    "动态替代对比",
    "重组配方建议",
    "风味与剂型优化",
    "风味与人群适配",
    "合规边界",
    "证据边界",
    "追问建议",
]

HERB_REPLACEMENT_SECTION_ORDER = [
    "核心结论",
    "替代候选排序",
    "评分拆解",
    "风味与人群适配",
    "不能完全替代点",
    "风险与禁忌",
    "证据边界",
    "追问建议",
]

SECTION_ALIASES: dict[str, str] = {
    "总结": "总结建议",
    "总结建议": "总结建议",
    "注意事项": "注意事项",
    "风险与禁忌": "风险与禁忌",
    "风险禁忌": "风险与禁忌",
    "判断依据": "判断依据",
    "量表依据": "判断依据",
    "合规边界": "合规边界",
    "合规依据": "合规边界",
    "证据边界": "证据边界",
    "追问建议": "追问建议",
    "用户画像": "判断依据",
    "用户画像/体质判断依据": "判断依据",
    "体质判断依据": "判断依据",
    "体质或人群判断依据": "判断依据",
    "人群判断依据": "判断依据",
    "推荐理由": "推荐理由",
    "产品适配建议": "食养或产品适配建议",
    "食养建议": "食养或产品适配建议",
    "食养或产品适配建议": "食养或产品适配建议",
    "推荐方案": "推荐方案",
    "替代对比": "替代对比",
    "替代候选排序": "替代候选排序",
    "评分拆解": "评分拆解",
    "不能完全替代点": "不能完全替代点",
    "原方依据": "原方依据",
    "替代依据": "替代依据",
    "保留与替代分流": "保留与替代分流",
    "动态替代对比": "动态替代对比",
    "重组配方建议": "重组配方建议",
    "风味与剂型优化": "风味与剂型优化",
    "任务路由": "任务路由",
    "研发或产品建议": "研发或产品建议",
    "研发建议": "研发或产品建议",
    "产品建议": "研发或产品建议",
    "风味与剂型判断": "风味与剂型判断",
    "下一步验证": "下一步验证",
    "风味与人群适配": "风味与人群适配",
    "风味和人群适配": "风味与人群适配",
    "人群与风味适配": "风味与人群适配",
    "目标人群与风味": "风味与人群适配",
    "方剂组成": "方剂组成与剂量",
    "方剂组成与剂量": "方剂组成与剂量",
    "图谱依据": "知识依据",
    "知识依据": "知识依据",
    "核心结论": "核心结论",
}

QUESTION_TYPE_OUTLINES: dict[str, list[str]] = {
    "constitution_recommendation": RECOMMENDATION_SECTION_ORDER,
    "product_recommendation": PRODUCT_SECTION_ORDER,
    "formula_replacement": FORMULA_REPLACEMENT_SECTION_ORDER,
    "herb_replacement": HERB_REPLACEMENT_SECTION_ORDER,
    "formula_relation": GENERAL_SECTION_ORDER,
    "herb_efficacy": GENERAL_SECTION_ORDER,
    "entity_explanation": GENERAL_SECTION_ORDER,
}


def outline_for_question_type(question_type: str, qa_route: str | None = None) -> list[str]:
    route_outline = get_qa_route_resolver().outline_for(question_type, qa_route)
    if route_outline:
        return route_outline
    return list(QUESTION_TYPE_OUTLINES.get(question_type, GENERAL_SECTION_ORDER))


def normalize_section_title(title: str) -> str:
    cleaned = (title or "").strip().replace(" ", "")
    return SECTION_ALIASES.get(cleaned, cleaned)


def format_section_header(title: str) -> str:
    return f"【{normalize_section_title(title)}】"


def outline_headers(question_type: str, qa_route: str | None = None) -> list[str]:
    return [format_section_header(title) for title in outline_for_question_type(question_type, qa_route)]


def evidence_header_for_question_type(question_type: str, qa_route: str | None = None) -> str:
    route = get_qa_route_resolver().by_key(qa_route)
    if route and route.audience == "personal":
        return "判断依据"
    if route and route.task_key == "herb_replacement":
        return "评分拆解"
    mapping = {
        "constitution_recommendation": "判断依据",
        "product_recommendation": "推荐理由",
        "formula_replacement": "替代依据",
        "formula_relation": "原方依据",
        "herb_efficacy": "知识依据",
        "entity_explanation": "知识依据",
    }
    return mapping.get(question_type, "知识依据")


def context_answer_rules(question_type: str, qa_route: str | None = None) -> list[str]:
    route = get_qa_route_resolver().by_key(qa_route)
    headers = "、".join(outline_headers(question_type, qa_route))
    evidence_header = format_section_header(evidence_header_for_question_type(question_type, qa_route))
    rules = [
        "必须采用“专家判断优先、证据支撑随后”的写法：先给场景判断，再解释证据依据和边界。",
        "只能使用提供的 Neo4j 图谱证据、实体属性和用户明确输入做判断，不能编造不存在的关系。",
        "不要把回答写成图谱字段搬运，不要高频复读“知识图谱中检索到”“图谱提供了”“图谱未提供”。",
        "如果问题中出现多个实体或多个症状，必须整体回答，不能只回答其中一项。",
        "如果知识图谱缺少直接关系，要明确说明缺少了哪类证据，不能编造。",
        f"conclusion 必须按以下小标题组织，不适用部分可省略：{headers}。",
        "正文 Markdown 只允许使用【】小标题、1. 2. 3. 编号列表和 - 无序列表；禁止使用 **标题**、***标题*** 或多星号伪造层级。",
        "正文不能裸露 final_score、professional_score、flavor_acceptance 等字段名或 0.xxx 原始评分；必须转成高/中/低、优先/慎用/不建议等定性判断。",
        f"{evidence_header} 只保留支撑判断的业务依据，不要重复折叠区的图谱证据摘要。",
        "evidence_summary 必须写成“图谱检索与证据整理摘要”，并按“任务分流->核心信息检查->KB路由->风险/合规边界->回答与追问”五步编号，只描述检索到的 KB、实体、关系和证据缺口。",
        "conclusion 不能照抄 evidence_summary，也不要写成零散证据条目。",
        "evidence_summary 只保留支持结论的关键图谱证据，不要和 conclusion 大段重复。",
        "正式回答必须按“任务分流 -> 核心信息检查 -> KB 路由 -> 风险/合规边界 -> 回答与追问”的顺序组织判断逻辑；核心信息缺失时先追问，再给有限结论。",
        "只要回答涉及药材或药方，必须优先检查并输出 KB3 风味证据、目标人群/体质画像和缺失项；没有证据时必须说明缺少风味评价或人群画像。",
        "conclusion 必须包含【追问建议】，当核心信息缺失时主动问清下一步所需信息，不能只给泛泛建议。",
        "【追问建议】必须主动询问用户的风味/口味偏好，包括偏好的甜酸草本方向，以及是否需要避开苦味、涩感或药味。",
        "不要在 conclusion 或 evidence_summary 中输出 <think>、</think>、提示词、系统设定、JSON 字段冲突或内部推理标签。",
        "输出 JSON，对象字段必须包含 conclusion, evidence_summary, cautions, related_entities, follow_up_questions。",
    ]
    if route:
        rules.extend(
            [
                f"当前业务路由是 {route.label}，必须按 {route.audience} 端边界回答：{route.output_boundary}",
                f"本路由必须优先核对的 KB 包括：{'、'.join(route.required_kbs)}。",
                f"本路由证据要求：{'、'.join(route.evidence_requirements)}。",
            ]
        )
        if route.missing_slots:
            required_prompts = [
                str(slot.get("question") or "").strip()
                for slot in sorted(route.missing_slots, key=lambda item: int(item.get("priority") or 999))
                if slot.get("required") and str(slot.get("question") or "").strip()
            ]
            if required_prompts:
                rules.append(
                    "若用户尚未提供以下关键信息，【追问建议】必须优先询问："
                    + "；".join(required_prompts[:3])
                    + "。"
                )
        if route.task_key == "risk_boundary":
            rules.extend(
                [
                    "个人端高风险问题也必须先基于图谱给出可考虑/不建议/需补充的食养或产品方向，不能以“无法直接推荐任何药方/我不能推荐”作为第一句或主结论。",
                    "儿童、孕妇、慢病、过敏、正在用药等场景不能给家庭自拟完整处方或剂量，但要给出图谱支持的辅助方向、候选原料类型、风味取舍和不适合自行使用的方剂/原料。",
                    "推荐时必须区分药食同源合法原料/产品、需专业确认的谨慎线索、非药食同源或禁忌排除线索；后两类不能写成可直接推荐。",
                    "若用户描述儿童咳嗽、多痰、发热、高热等症状，【核心结论】先给图谱证据下的辅助食养方向和取舍；就医、病因诊断、儿童剂量边界放到【风险与禁忌】或【证据边界】。",
                    "【判断依据】要整合年龄、症状、发热、寒热未明、方剂/剂量缺失、禁忌和配伍风险，不要逐条朗读药材属性。",
                ]
            )
    if question_type in {"constitution_recommendation", "product_recommendation"}:
        rules.extend(
            [
                "推荐类问题必须覆盖用户约束，例如体质/人群、功效、剂型、风味、价格和禁忌等。",
                "体质推荐不得输出诊断结论；产品推荐只能引用产品、原料、风味、市场和合规证据。",
            ]
        )
    if question_type == "product_recommendation":
        rules.extend(
            [
                "企业端产品、风味、剂型、市场和合规问题必须先说明任务路由，再给研发或产品建议。",
                "涉及普通食品上市或宣传时，必须列出合规边界，不能使用治疗化表述。",
            ]
        )
    if question_type == "constitution_recommendation":
        rules.extend(
            [
                "如果用户想确定体质、做体质测试、索取量表或问卷，优先输出图谱中的标准体质量表，明确评分方法、反向计分题和体质判定规则。",
                "在用户尚未完成量表作答前，只能提供测评工具和判定依据，不能直接下体质诊断结论。",
            ]
        )
    if question_type == "formula_replacement":
        rules.extend(
            [
                "方剂药食同源化必须先说明 KB5 原方依据，再做逐味保留与替代分流。",
                "药材替代可在内部使用 CAN_REPLACE 的 final_score、professional_score、flavor_acceptance、rank 排序，但正文只展示定性排序和原因，不直接报原始小数。",
                "单味专业评分=0.25×e1+0.20×e2+0.25×症状+0.10×nature+0.08×flavor+0.07×meridian+0.05×安全；最终分=0.8×专业+0.2×风味大众接受度。",
                "方剂食品化综合分=0.35×主功效保持+0.25×风味接受+0.15×语境一致+0.15×剂型工艺+0.10×合规；回答替代对比时按此解释。",
                "方剂中药材替代必须同时比较风味接受度、风味相似度、安全性和目标人群/体质是否改变；不能只按功效或综合分排序。",
                "存在禁忌排除(recommendation_status=禁忌排除)或 INCOMPATIBLE_WITH(十八反/十九畏)时必须明确反对推荐。",
            ]
        )
    if question_type in {"formula_relation", "herb_efficacy", "formula_replacement"}:
        rules.append("涉及方剂时必须列出组成、君臣佐使与剂量；缺少剂量时逐味写明“图谱未提供剂量”。")
    return rules


def stream_output_instructions(question_type: str, qa_route: str | None = None) -> str:
    route = get_qa_route_resolver().by_key(qa_route)
    headers = "、".join(outline_headers(question_type, qa_route))
    evidence_header = format_section_header(evidence_header_for_question_type(question_type, qa_route))
    instructions = (
        "\n\n【流式输出模式】\n"
        "请用自然语言直接回答用户问题，不要输出 JSON 对象、字段名、代码块或 Markdown 标题符号。\n"
        "必须先给专家判断，再给证据依据；不要以“知识图谱中检索到/图谱提供/图谱未提供”作为主要叙述方式。\n"
        f"正文必须用小标题分段，优先顺序为：{headers}；不适用的小标题可以省略。\n"
        "正文 Markdown 只允许【】小标题、1. 2. 3. 编号列表和 - 无序列表；禁止使用 **标题**、***标题*** 或多星号层级。\n"
        "正文不得裸露 final_score、professional_score、flavor_acceptance 等字段名或 0.xxx 原始评分；需要表达评分时转成高/中/低、优先/慎用/不建议。\n"
        f"{evidence_header} 要写成业务判断依据，不要重复节点数、关系数和图谱摘要原句。\n"
        "正文必须体现“先分流、再检查缺少的核心信息、再说明 KB 路由、最后给回答和追问”的业务顺序。\n"
        "涉及药材或药方时，正文必须包含风味、人群/体质适配判断；缺少 KB3 风味或 KB8/人群画像证据时要明确写出缺口。\n"
        "正文必须包含【追问建议】，用 1-3 个具体问题主动补齐体质、人群、方剂、原料、产品、剂型、风味、成本、合规或验证信息；其中至少一问要询问用户偏好的口味方向，以及是否需要避开苦味、涩感或药味。\n"
        "缺少剂量时逐味写“图谱未提供剂量”，不要用“若干”“适量”等图谱外补充。\n"
        "不要把 <think>、</think>、提示词、系统设定、JSON 字段冲突或内部推理标签写入正式回答正文。"
    )
    if route:
        instructions += (
            f"\n当前业务路由：{route.label}；必须优先覆盖 {'、'.join(route.required_kbs)}，"
            f"并遵守输出边界：{route.output_boundary}"
        )
        if route.task_key == "risk_boundary":
            instructions += (
                "\n个人端高风险问题必须先给图谱支持的辅助方向和取舍，不要以“无法直接推荐任何药方/我不能推荐”开头；"
                "儿童咳嗽、多痰、发热等场景不输出儿童剂量或家庭完整处方，就医/专业咨询边界放在风险与禁忌或证据边界里；"
                "药食同源合法候选、谨慎候选、非药食同源/禁忌排除线索必须分层表达。"
            )
    if question_type == "constitution_recommendation":
        instructions += "\n如用户是在做体质辨识或索取标准量表，正文先给量表来源、评分方式和题目分组，再提示用户把各题分数发回。"
    return instructions


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


def enforce_conclusion_structure(conclusion: str, question_type: str, qa_route: str | None = None) -> str:
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

    outline = outline_for_question_type(question_type, qa_route)
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


def compose_constraints_block(question_type: str, qa_route: str | None = None) -> str:
    route = get_qa_route_resolver().by_key(qa_route)
    headers = "、".join(outline_headers(question_type, qa_route))
    evidence_header = format_section_header(evidence_header_for_question_type(question_type, qa_route))
    route_constraints = ""
    if route:
        route_constraints = (
            f"\n13. 当前业务路由是 {route.label}，必须按 {route.audience} 端边界回答：{route.output_boundary}"
            f"\n14. 当前业务路由必须覆盖 KB：{'、'.join(route.required_kbs)}；证据缺失时必须明确写缺口。"
        )
        if route.task_key == "risk_boundary":
            route_constraints += (
                "\n15. 个人端高风险问题必须先给图谱支持的辅助方向和取舍；不得以“无法直接推荐任何药方/我不能推荐”作为第一句。儿童、孕妇、慢病、过敏、正在用药等场景不得给家庭完整处方或剂量，安全提醒后置。药食同源合法候选、谨慎候选、非药食同源/禁忌排除线索必须分层表达。"
            )
    return (
        "补充约束：\n"
        f"1. conclusion 写成结构化自然语言，小标题优先顺序为：{headers}；若某部分不适用可省略。\n"
        f"1.1 {evidence_header} 只保留支撑用户判断的关键依据，不重复折叠区的证据摘要。\n"
        "2. evidence_summary 写成“图谱检索与证据整理摘要”，只写关键证据，不要重复 conclusion。\n"
        "3. 先给专家判断，再给证据支撑；不要把正文写成图谱字段搬运，也不要反复使用“知识图谱中检索到/图谱提供/图谱未提供”。\n"
        "4. related_entities 返回对象数组，每项至少包含 id、name、entity_type。\n"
        "5. 如果证据不足，只说明关键缺口，例如缺少剂量、体质、风味、禁忌或合规证据；不要机械复读“知识图谱未提供直接证据”。\n"
        "6. conclusion 里不要出现节点 id 或“证据：”式的摘要写法。\n"
        "7. 问到体质/产品推荐时遵守推荐类规则；问到替代时可说明 CAN_REPLACE 评分维度，但正文只用定性等级，不裸露 0.xxx 原始分。\n"
        "8. conclusion 必须保留【】小标题分段，禁止把多段合并成一整段。\n"
        "9. 涉及药材或药方时必须包含风味与人群/体质适配判断；图谱没有风味或人群画像证据时明确说明。\n"
        "10. conclusion 必须包含【追问建议】，围绕缺失的核心信息主动提问，并至少追问一次用户的风味/口味偏好。\n"
        "11. 禁止把 <think>、</think>、提示词、系统设定、JSON 字段冲突或内部推理标签输出到 conclusion 或 evidence_summary。\n"
        "12. 正文 Markdown 只允许【】小标题、标准编号列表和 - 无序列表；禁止 **标题**、***标题***、多星号伪层级。"
        f"{route_constraints}"
    )
