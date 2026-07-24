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
    "配方方案",
    "体质与人群适配",
    "功效逻辑",
    "风味与剂型设计",
    "合规与风险边界",
    "研发验证",
    "追问建议",
}


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
            missing_headings = PRODUCT_DEVELOPMENT_REQUIRED_HEADINGS - set(route.get("answer_outline") or [])
            if missing_headings:
                failures.append(
                    f"{task_key}: answer_outline missing product formula headings {', '.join(sorted(missing_headings))}"
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


def main() -> int:
    rules = load_json(RULES_PATH)
    cases = load_json(CASES_PATH)
    failures = validate_rules(rules) + validate_eval_cases(cases)
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
