from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
VENDOR_DIR = BACKEND_DIR / "_vendor"
PROMPTS_DIR = BACKEND_DIR / "app" / "prompts"
RULES_PATH = PROMPTS_DIR / "qa_route_rules.json"
CASES_PATH = PROMPTS_DIR / "qa_route_eval_cases.json"

for item in (VENDOR_DIR, BACKEND_DIR):
    if item.exists():
        sys.path.insert(0, str(item))

from app.services.question_classifier import QuestionClassifier  # noqa: E402
from app.services.qa_orchestrator import QAOrchestrator  # noqa: E402
from app.services.entity_resolver import EntityResolver  # noqa: E402
from app.services.graph_retriever import GraphRetriever  # noqa: E402


REQUIRED_ROUTE_FIELDS = {
    "task_key",
    "audience",
    "question_type",
    "label",
    "route_label",
    "kb_route",
    "required_kbs",
    "answer_outline",
    "output_boundary",
    "evidence_requirements",
    "preferred_entity_types",
    "graph_scene",
    "priority",
    "match",
    "missing_slots",
}
EXPECTED_AUDIENCES = {"enterprise", "personal", "general"}
PRODUCT_DEVELOPMENT_REQUIRED_HEADINGS = {
    "核心结论",
    "产品定位",
    "名方溯源与借鉴",
    "配方方案",
    "配方调整与替换依据",
    "体质与人群适配",
    "功效逻辑",
    "风味与剂型设计",
    "合规与风险边界",
    "研发验证",
    "追问建议",
}
USER_FACING_BANNED_GAP_PHRASES = {
    "图谱未提供",
    "知识图谱未提供",
    "图谱未命中",
    "未命中",
    "没有检索到",
    "知识库尚不支持",
    "知识库不支持",
    "知识库尚未提供",
    "知识库未提供",
}
ANSWER_LANGUAGE_CASES = [
    (
        "当前知识图谱未提供您指定的目标功效和剂型，因此先给研发草案。",
        "建议先明确目标功效和剂型",
    ),
    (
        "图谱未提供该配方整体的风味协同数据，需在小试阶段验证。",
        "建议在下一阶段补充核验",
    ),
    (
        "图谱未命中直接产品节点，建议补充产品名。",
        "建议补充产品名、配料表、剂型和目标场景",
    ),
    (
        "人参：君。图谱未提供剂量。",
        "剂量建议结合原方出处与专业规范进一步核定",
    ),
    (
        "当前知识库尚不支持直接给出完整方剂出处，因此以下方案为研发假设草案。",
        "建议在定稿前补充核对原方出处",
    ),
]


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"Cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def validate_rules(rules: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    routes = rules.get("routes")
    if not isinstance(routes, list) or not routes:
        return ["qa_route_rules.json must define a non-empty routes array"]

    default_route = rules.get("default_route")
    route_keys = [str(route.get("task_key") or "") for route in routes]
    if len(route_keys) != len(set(route_keys)):
        failures.append("route task_key values must be unique")
    if default_route not in route_keys:
        failures.append(f"default_route {default_route!r} is not present in routes")

    metadata = rules.get("flow_metadata") or {}
    for group_key in ("enterprise_route_keys", "personal_route_keys"):
        for task_key in metadata.get(group_key) or []:
            if task_key not in route_keys:
                failures.append(f"{group_key} contains unknown route {task_key!r}")

    graph_baseline = metadata.get("graph_baseline") or {}
    if graph_baseline.get("compound_count") != 0:
        failures.append("graph_baseline.compound_count must be 0 for the 0604 graph")
    if int(graph_baseline.get("node_count") or 0) < 80000:
        failures.append("graph_baseline.node_count looks too small for the current graph")
    if int(graph_baseline.get("relationship_count") or 0) < 200000:
        failures.append("graph_baseline.relationship_count looks too small for the current graph")

    route_examples = rules.get("route_examples") or {}
    for task_key in route_keys:
        examples = route_examples.get(task_key)
        if not isinstance(examples, dict):
            failures.append(f"route_examples missing route {task_key!r}")
            continue
        for key in ("positive", "negative"):
            values = examples.get(key)
            if not isinstance(values, list) or not any(str(item).strip() for item in values):
                failures.append(f"route_examples.{task_key}.{key} must be a non-empty list")

    for route in routes:
        task_key = str(route.get("task_key") or "")
        missing = sorted(REQUIRED_ROUTE_FIELDS - set(route))
        if missing:
            failures.append(f"{task_key}: missing required fields {', '.join(missing)}")
        if route.get("audience") not in EXPECTED_AUDIENCES:
            failures.append(f"{task_key}: invalid audience {route.get('audience')!r}")
        if not route.get("required_kbs"):
            failures.append(f"{task_key}: required_kbs must not be empty")
        if len(route.get("answer_outline") or []) < 3:
            failures.append(f"{task_key}: answer_outline must contain at least 3 headings")
        if "核心结论" not in (route.get("answer_outline") or []):
            failures.append(f"{task_key}: answer_outline must include 核心结论")
        if "追问建议" not in (route.get("answer_outline") or []):
            failures.append(f"{task_key}: answer_outline must include 追问建议")
        if task_key == "product_development":
            if (route.get("answer_outline") or [])[-2:] != ["核心结论", "追问建议"]:
                failures.append("product_development: final sections must be 核心结论 then 追问建议")
            missing_headings = PRODUCT_DEVELOPMENT_REQUIRED_HEADINGS - set(route.get("answer_outline") or [])
            if missing_headings:
                failures.append(
                    f"{task_key}: answer_outline missing product formula headings {', '.join(sorted(missing_headings))}"
                )
            missing_kbs = {"KB4", "KB5"} - set(route.get("required_kbs") or [])
            if missing_kbs:
                failures.append(
                    f"{task_key}: required_kbs missing provenance/replacement KBs {', '.join(sorted(missing_kbs))}"
                )
        match = route.get("match") or {}
        if not isinstance(match, dict) or "any" not in match:
            failures.append(f"{task_key}: match.any must be defined")
        if not isinstance(route.get("missing_slots"), list):
            failures.append(f"{task_key}: missing_slots must be a list")

    return failures


def validate_eval_cases(cases_doc: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    cases = cases_doc.get("cases")
    if not isinstance(cases, list) or not cases:
        return ["qa_route_eval_cases.json must define a non-empty cases array"]

    classifier = QuestionClassifier()
    for idx, case in enumerate(cases, start=1):
        question = str(case.get("question") or "").strip()
        if not question:
            failures.append(f"case #{idx}: question is required")
            continue
        route = classifier.classify_route(question)
        expected_route = case.get("expected_qa_route")
        expected_type = case.get("expected_question_type")
        expected_audience = case.get("expected_audience")
        actual = {
            "qa_route": route.task_key,
            "question_type": route.question_type,
            "audience": route.audience,
        }
        if route.task_key != expected_route:
            failures.append(
                f"case #{idx} route mismatch: {question!r}, expected {expected_route!r}, got {actual}"
            )
        if route.question_type != expected_type:
            failures.append(
                f"case #{idx} question_type mismatch: {question!r}, expected {expected_type!r}, got {actual}"
            )
        if route.audience != expected_audience:
            failures.append(
                f"case #{idx} audience mismatch: {question!r}, expected {expected_audience!r}, got {actual}"
            )
        if not failures or not failures[-1].startswith(f"case #{idx}"):
            print(f"PASS case #{idx}: {question} -> {route.task_key}/{route.question_type}/{route.audience}")
    return failures


def validate_answer_language() -> list[str]:
    failures: list[str] = []
    for idx, (source, expected) in enumerate(ANSWER_LANGUAGE_CASES, start=1):
        if not QAOrchestrator._contains_system_gap_language(source):
            failures.append(
                f"answer language case #{idx}: source phrase was not detected for stream safety reset"
            )
            continue
        cleaned = QAOrchestrator._sanitize_user_facing_answer_text(source)
        banned = [phrase for phrase in USER_FACING_BANNED_GAP_PHRASES if phrase in cleaned]
        if banned:
            failures.append(
                f"answer language case #{idx}: banned phrases remain {banned!r} in {cleaned!r}"
            )
        if expected not in cleaned:
            failures.append(
                f"answer language case #{idx}: expected {expected!r}, got {cleaned!r}"
            )
        if not banned and expected in cleaned:
            print(f"PASS answer language case #{idx}: {cleaned}")
    return failures


def validate_formula_provenance() -> list[str]:
    graph = {
        "nodes": [
            {
                "id": "生脉散",
                "label": "生脉散",
                "type": "Formula",
                "props": {
                    "formula_name": "生脉散",
                    "source": "《医学启源》",
                    "ingredients": "人参、麦冬、五味子",
                    "prototype_rank": 1,
                    "prototype_match_score": 92,
                    "prototype_match_type": "direct_core_herb",
                    "prototype_evidence_type": "图谱直接证据",
                    "prototype_match_reasons": ["核心原料直接见于原方", "功效匹配：益气、生津"],
                    "prototype_sources": ["《医学启源》"],
                },
            },
            {"id": "人参", "label": "人参", "type": "Herb", "props": {"herb_name": "人参"}},
            {"id": "麦冬", "label": "麦冬", "type": "Herb", "props": {"herb_name": "麦冬"}},
            {"id": "五味子", "label": "五味子", "type": "Herb", "props": {"herb_name": "五味子"}},
            {"id": "桑椹", "label": "桑椹", "type": "Herb", "props": {"herb_name": "桑椹"}},
        ],
        "edges": [
            {"id": "人参-生脉散", "source": "人参", "target": "生脉散", "type": "IN_FORMULA", "props": {}},
            {"id": "麦冬-生脉散", "source": "麦冬", "target": "生脉散", "type": "IN_FORMULA", "props": {}},
            {"id": "五味子-生脉散", "source": "五味子", "target": "生脉散", "type": "IN_FORMULA", "props": {}},
            {
                "id": "麦冬-桑椹",
                "source": "麦冬",
                "target": "桑椹",
                "type": "CAN_REPLACE",
                "props": {
                    "rank": 1,
                    "final_score": 0.78,
                    "professional_score": 0.74,
                    "effect_similarity": 0.82,
                    "flavor_acceptance": 0.8,
                    "safety_score": 0.9,
                    "formula_context_similarity": 0.7,
                    "recommendation_status": "可推荐",
                    "source_type": "KB4_0604",
                },
            },
        ],
    }
    orchestrator = QAOrchestrator.__new__(QAOrchestrator)
    context = orchestrator._build_formula_provenance_context(graph)
    failures: list[str] = []
    prototypes = context.get("formula_prototypes") or []
    replacements = context.get("replacement_options") or []
    if not prototypes or prototypes[0].get("formula_name") != "生脉散":
        failures.append("formula provenance: expected 生脉散 as the primary prototype")
    elif prototypes[0].get("prototype_match_score_100") != 92:
        failures.append("formula provenance: prototype score must remain an integer percentage")
    if not replacements or replacements[0].get("kb4_original_score_100") != 78:
        failures.append("formula provenance: KB4 score must be converted to an integer percentage")
    if not replacements or replacements[0].get("system_composite_confidence_100") is None:
        failures.append("formula provenance: system composite confidence is required")

    adjustment_text = "\n".join(
        orchestrator._build_formula_adjustment_lines(
            context,
            ["人参", "桑椹", "山楂"],
        )
    )
    for action in ("保留", "替换", "新增", "删除"):
        if action not in adjustment_text:
            failures.append(f"formula provenance: adjustment output missing {action}")

    valid_conclusion = """
【名方溯源与借鉴】
参考原型：生脉散；出处：《医学启源》；证据性质：图谱直接证据；原型匹配度：92/100。

【配方调整与替换依据】
1. 保留：人参。
2. 替换：麦冬 → 桑椹；KB4原始分78/100；系统综合可信度80/100。
3. 新增：山楂。
4. 删除：五味子。
"""
    grounding_errors = orchestrator._product_development_grounding_errors(valid_conclusion, graph)
    if grounding_errors:
        failures.append(
            f"formula provenance: valid grounded answer was rejected: {grounding_errors}"
        )

    invalid_conclusion = """
【名方溯源与借鉴】
参考原型：生脉饮；出处：《其他来源》；证据性质：系统推导。

【配方调整与替换依据】
1. 保留：人参。
2. 替换：麦冬 → 党参；系统综合可信度高。
3. 新增：山楂。
4. 删除：五味子。
"""
    grounding_errors = orchestrator._product_development_grounding_errors(invalid_conclusion, graph)
    if not grounding_errors:
        failures.append("formula provenance: ungrounded formula and replacement must be rejected")
    if failures:
        return failures
    print(
        "PASS formula provenance: source, KB4 score, composite confidence, "
        "four adjustment actions, and hallucination guard"
    )
    return []


def validate_product_core_resolution() -> list[str]:
    class ExactHerbRepository:
        def __init__(self) -> None:
            self.exact_calls: list[list[str]] = []

        def find_herbs_exact(self, names: list[str]) -> list[dict]:
            self.exact_calls.append(names)
            return [
                {
                    "id": name,
                    "name": name,
                    "entity_type": "Herb",
                    "props": {"herb_name": name},
                    "score": 130,
                    "aliases": [],
                }
                for name in names
            ]

        def search_entities(self, *_args, **_kwargs) -> list[dict]:
            raise AssertionError("product core ingredient must not trigger broad entity search")

    repository = ExactHerbRepository()
    resolver = EntityResolver(repository)
    entities = resolver.resolve_product_core_ingredients(
        "以人参药材为主向60岁以上老年人提供微酸偏甜的食药两用配方"
    )
    if repository.exact_calls != [["人参"]]:
        return [f"product core resolution: unexpected exact lookup {repository.exact_calls!r}"]
    if [entity.get("name") for entity in entities] != ["人参"]:
        return [f"product core resolution: unexpected entities {entities!r}"]
    print("PASS product core resolution: exact Herb lookup without broad entity scan")
    return []


def validate_product_formula_intent_retrieval() -> list[str]:
    class FormulaRepository:
        def __init__(self) -> None:
            self.prototype_calls: list[dict[str, Any]] = []

        def find_formula_prototypes(
            self,
            core_herb_names: list[str],
            effect_terms: list[str],
            audience_terms: list[str],
            **kwargs: Any,
        ) -> list[dict]:
            self.prototype_calls.append(
                {
                    "core_herb_names": core_herb_names,
                    "effect_terms": effect_terms,
                    "audience_terms": audience_terms,
                }
            )
            return [
                {
                    "formula_name": "甘麦大枣汤",
                    "rank": 1,
                    "match_score": 43,
                    "match_type": "inferred_reference",
                    "evidence_type": "系统推导的参考原型",
                    "match_reasons": ["功效匹配：安神、养心", "人群线索：老年"],
                    "sources": ["方剂学各论"],
                    "core_matches": [],
                    "effect_hits": ["安神", "养心"],
                    "audience_hits": ["老年"],
                    "ingredients": [{"name": "甘草"}, {"name": "大枣"}],
                }
            ]

        @staticmethod
        def retrieve_formula_graph(_formula_names: list[str]) -> dict:
            return {
                "nodes": [
                    {
                        "id": "甘麦大枣汤",
                        "label": "甘麦大枣汤",
                        "type": "Formula",
                        "props": {
                            "formula_name": "甘麦大枣汤",
                            "ingredients": "甘草、小麦、大枣",
                            "source": "方剂学各论",
                        },
                    }
                ],
                "edges": [],
            }

        @staticmethod
        def retrieve_replacement_graph(_source_names: list[str], **_kwargs: Any) -> dict:
            return {"nodes": [], "edges": []}

    repository = FormulaRepository()
    retriever = GraphRetriever(repository, None)  # type: ignore[arg-type]
    graph = retriever._augment_product_development_provenance(
        "我想研发一款可以改善长老年睡眠的饮品，价格可以做到中等价位，需要细致到工艺 炮制等方面",
        [],
        {"nodes": [], "edges": [], "focus_paths": [], "legend": {}, "metrics": {}},
    )
    failures: list[str] = []
    if not repository.prototype_calls:
        failures.append("formula intent retrieval: KB5 prototype search was not called")
        return failures
    call = repository.prototype_calls[0]
    if call["core_herb_names"]:
        failures.append("formula intent retrieval: core herbs should remain empty when unspecified")
    if not {"睡眠", "安神", "养心"}.issubset(set(call["effect_terms"])):
        failures.append(f"formula intent retrieval: missing sleep effect terms {call['effect_terms']!r}")
    if "老年" not in call["audience_terms"]:
        failures.append(f"formula intent retrieval: missing elderly audience terms {call['audience_terms']!r}")
    formula_nodes = [node for node in graph.get("nodes", []) if node.get("type") == "Formula"]
    if not formula_nodes or formula_nodes[0].get("label") != "甘麦大枣汤":
        failures.append(f"formula intent retrieval: concrete KB5 formula missing from graph {formula_nodes!r}")
    orchestrator = QAOrchestrator.__new__(QAOrchestrator)
    orchestrator.route_resolver = retriever.route_resolver
    answer = orchestrator._build_local_answer(
        "我想研发一款可以改善长老年睡眠的饮品，价格可以做到中等价位，需要细致到工艺 炮制等方面",
        "product_recommendation",
        [],
        graph,
        "",
        qa_route="product_development",
    )
    conclusion = str(answer.get("conclusion") or "")
    if "参考原型：甘麦大枣汤" not in conclusion:
        failures.append("formula intent retrieval: local answer omitted the concrete reference formula")
    if "甘麦大枣汤：君" in conclusion:
        failures.append("formula intent retrieval: formula node was incorrectly rendered as a core herb")
    if "水提小试" not in conclusion or "净制与炮制对照" not in conclusion:
        failures.append("formula intent retrieval: requested process and processing detail is incomplete")
    process_index = conclusion.rfind("【研发验证】")
    summary_index = conclusion.rfind("【核心结论】")
    follow_up_index = conclusion.rfind("【追问建议】")
    if not process_index < summary_index < follow_up_index:
        failures.append("formula intent retrieval: final order must be 研发验证 -> 核心结论 -> 追问建议")
    if failures:
        return failures
    print("PASS formula intent retrieval: no-core sleep brief recalls a concrete KB5 formula and process plan")
    return []


def validate_product_trial_dosage() -> list[str]:
    orchestrator = QAOrchestrator.__new__(QAOrchestrator)
    ginseng = orchestrator._product_trial_dose(
        "人参",
        {"ordinary_food_daily_limit_g": 3},
        role="君",
    )
    emblic = orchestrator._product_trial_dose(
        "余甘子",
        {"sour_contribution": 0.75, "astringent_risk": 0.75},
        role="臣",
    )
    jujube = orchestrator._product_trial_dose(
        "大枣",
        {"sweet_contribution": 0.9},
        role="佐",
    )
    failures: list[str] = []
    if ginseng.get("baseline_g") != 1.0 or ginseng.get("daily_limit_g") != 3:
        failures.append(f"product dosage: unexpected ginseng dose {ginseng!r}")
    if emblic.get("baseline_g") != 1.5:
        failures.append(f"product dosage: unexpected emblic dose {emblic!r}")
    if jujube.get("baseline_g") != 3.0:
        failures.append(f"product dosage: unexpected jujube dose {jujube!r}")
    total = sum(item["baseline_g"] for item in (ginseng, emblic, jujube))
    if total != 5.5:
        failures.append(f"product dosage: expected 5.5g baseline total, got {total!r}")
    formatted = orchestrator._format_product_trial_dose(ginseng)
    if "1g/份" not in formatted or "0.5/1/1.5g/份" not in formatted or "不超过3g" not in formatted:
        failures.append(f"product dosage: incomplete formatted ginseng dose {formatted!r}")
    sanitized = orchestrator._sanitize_user_facing_answer_text(
        "低/中/高梯度：0.5/1/1.5g/份；接受度评分0.72。"
    )
    if "0.5/1/1.5g/份" not in sanitized or "接受度评分中等" not in sanitized:
        failures.append(f"product dosage: sanitizer corrupted dosage or exposed score {sanitized!r}")
    if failures:
        return failures
    print("PASS product dosage: per-serving grams, gradients, total, and ginseng daily limit")
    return []


def main() -> int:
    rules = load_json(RULES_PATH)
    cases = load_json(CASES_PATH)
    failures = (
        validate_rules(rules)
        + validate_eval_cases(cases)
        + validate_answer_language()
        + validate_formula_provenance()
        + validate_product_core_resolution()
        + validate_product_formula_intent_retrieval()
        + validate_product_trial_dosage()
    )
    if failures:
        print("\nQA routing validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    route_count = len(rules.get("routes") or [])
    case_count = len(cases.get("cases") or [])
    print(f"\nQA routing validation passed: {route_count} routes, {case_count} eval cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
