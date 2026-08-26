"""Machine-readable QA route rules for enterprise/personal knowledge QA."""

from __future__ import annotations

from dataclasses import dataclass
import json
from functools import lru_cache
from pathlib import Path
import re
from typing import Any


@dataclass(frozen=True)
class QARoute:
    task_key: str
    audience: str
    question_type: str
    label: str
    route_label: str
    kb_route: str
    required_kbs: list[str]
    answer_outline: list[str]
    missing_slots: list[dict[str, Any]]
    output_boundary: str
    evidence_requirements: list[str]
    preferred_entity_types: list[str]
    graph_scene: str
    priority: int
    offer_constitution_panel: bool
    match: dict[str, list[str]]
    reasoning_steps: list[str]

    def to_context(self) -> dict[str, Any]:
        return {
            "audience": self.audience,
            "task_key": self.task_key,
            "question_type": self.question_type,
            "label": self.label,
            "route_label": self.route_label,
            "kb_route": self.kb_route,
            "required_kbs": self.required_kbs,
            "answer_outline": self.answer_outline,
            "missing_slots": self.missing_slots,
            "output_boundary": self.output_boundary,
            "evidence_requirements": self.evidence_requirements,
            "preferred_entity_types": self.preferred_entity_types,
            "graph_scene": self.graph_scene,
            "reasoning_steps": self.reasoning_steps,
        }


class QARouteResolver:
    def __init__(self, rules: dict[str, Any]) -> None:
        self.rules = rules
        self.routes = [self._build_route(item) for item in rules.get("routes", [])]
        default_key = rules.get("default_route") or "entity_explanation"
        self.default_route = self.by_key(default_key) or (self.routes[-1] if self.routes else self._fallback_route())

    @classmethod
    def from_file(cls, path: Path | None = None) -> "QARouteResolver":
        rules_path = path or Path(__file__).resolve().parents[1] / "prompts" / "qa_route_rules.json"
        try:
            rules = json.loads(rules_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            rules = {"default_route": "entity_explanation", "routes": []}
        return cls(rules)

    def by_key(self, task_key: str | None) -> QARoute | None:
        if not task_key:
            return None
        for route in self.routes:
            if route.task_key == task_key:
                return route
        return None

    def resolve(self, question: str, fallback_question_type: str | None = None) -> QARoute:
        compact = self._compact(question)
        high_risk_route = self._high_risk_override(compact)
        if high_risk_route:
            return high_risk_route

        product_development_route = self._product_development_override(compact)
        if product_development_route:
            return product_development_route

        best_route: QARoute | None = None
        best_score = -1
        for route in self.routes:
            score = self._score(route, compact, fallback_question_type)
            if score > best_score:
                best_route = route
                best_score = score
        if best_route and best_score > 0:
            return best_route
        if fallback_question_type:
            for route in sorted(self.routes, key=lambda item: item.priority, reverse=True):
                if route.question_type == fallback_question_type:
                    return route
        return self.default_route

    def outline_for(self, question_type: str, qa_route: str | None = None) -> list[str]:
        route = self.by_key(qa_route)
        if route and route.answer_outline:
            return list(route.answer_outline)
        return []

    def preferred_types_for(self, question_type: str, qa_route: str | None = None) -> list[str]:
        route = self.by_key(qa_route)
        if route and route.preferred_entity_types:
            return list(route.preferred_entity_types)
        return []

    def missing_slot_questions(
        self,
        question: str,
        qa_route: str | None,
        *,
        constitution_profile: dict | None = None,
        max_items: int = 4,
        required_only: bool = False,
    ) -> list[str]:
        route = self.by_key(qa_route)
        if not route:
            return []
        compact = self._compact(question)
        questions: list[str] = []
        slots = sorted(route.missing_slots, key=lambda item: int(item.get("priority") or 999))
        for slot in slots:
            if required_only and not bool(slot.get("required")):
                continue
            key = str(slot.get("key") or "")
            if key == "constitution" and constitution_profile:
                continue
            any_of = [str(item) for item in slot.get("any_of") or [] if str(item).strip()]
            if any_of and any(token in compact for token in any_of):
                continue
            prompt = str(slot.get("question") or "").strip()
            if prompt and prompt not in questions:
                questions.append(prompt)
            if len(questions) >= max_items:
                break
        return questions

    def reasoning_steps_for(self, qa_route: str | None) -> list[str]:
        route = self.by_key(qa_route)
        if route and route.reasoning_steps:
            return list(route.reasoning_steps)
        templates = self.rules.get("reasoning_templates") or {}
        if route:
            specific = templates.get(route.task_key)
            if specific:
                return list(specific)
            if route.audience == "personal":
                return list(templates.get("personal_default") or [])
            if route.audience == "enterprise":
                return list(templates.get("enterprise_default") or [])
        return list((templates.get("enterprise_default") or [])[:5])

    def detect_audience(self, question: str, qa_route: str | None = None) -> str:
        route = self.by_key(qa_route)
        if route and route.audience in {"personal", "enterprise"}:
            return route.audience
        compact = self._compact(question)
        signals = self.rules.get("audience_signals") or {}
        enterprise_tokens = signals.get("enterprise") or []
        personal_tokens = signals.get("personal") or []
        enterprise_score = sum(1 for token in enterprise_tokens if token and token in compact)
        personal_score = sum(1 for token in personal_tokens if token and token in compact)
        if personal_score > enterprise_score:
            return "personal"
        if enterprise_score > personal_score:
            return "enterprise"
        return "general"

    def data_gap_notes(self) -> list[str]:
        metadata = self.rules.get("flow_metadata") or {}
        return list(metadata.get("data_gaps_no_model_fill") or [])

    def graph_scene_for(self, question_type: str, qa_route: str | None = None) -> str:
        route = self.by_key(qa_route)
        if route and route.graph_scene:
            return route.graph_scene
        return question_type

    def should_offer_constitution_panel(self, qa_route: str | None) -> bool:
        route = self.by_key(qa_route)
        return bool(route and route.offer_constitution_panel)

    @staticmethod
    def _build_route(item: dict[str, Any]) -> QARoute:
        return QARoute(
            task_key=str(item.get("task_key") or "entity_explanation"),
            audience=str(item.get("audience") or "general"),
            question_type=str(item.get("question_type") or "entity_explanation"),
            label=str(item.get("label") or item.get("task_key") or "通用问答"),
            route_label=str(item.get("route_label") or item.get("label") or ""),
            kb_route=str(item.get("kb_route") or ""),
            required_kbs=list(item.get("required_kbs") or []),
            answer_outline=list(item.get("answer_outline") or []),
            missing_slots=list(item.get("missing_slots") or []),
            output_boundary=str(item.get("output_boundary") or ""),
            evidence_requirements=list(item.get("evidence_requirements") or []),
            preferred_entity_types=list(item.get("preferred_entity_types") or []),
            graph_scene=str(item.get("graph_scene") or item.get("question_type") or "entity_explanation"),
            priority=int(item.get("priority") or 1),
            offer_constitution_panel=bool(item.get("offer_constitution_panel", False)),
            match={key: list((item.get("match") or {}).get(key) or []) for key in ("any", "boost", "negative")},
            reasoning_steps=list(item.get("reasoning_steps") or []),
        )

    @staticmethod
    def _compact(question: str) -> str:
        return re.sub(r"\s+", "", question or "")

    def _high_risk_override(self, compact_question: str) -> QARoute | None:
        """Personal high-risk safety routes must beat generic herb/formula routes."""
        if not compact_question:
            return None

        enterprise_intent = (
            "开发",
            "研发",
            "产品开发",
            "配方开发",
            "上市",
            "卖点",
            "竞品",
            "市场",
        )
        if any(token in compact_question for token in enterprise_intent):
            return None

        hard_risk_people = (
            "孕妇",
            "孕期",
            "哺乳",
            "儿童",
            "小孩",
            "孩子",
            "男童",
            "女童",
            "幼儿",
            "少儿",
            "慢病",
            "过敏",
            "用药",
            "正在用药",
            "高血压",
            "糖尿病",
        )
        soft_risk_people = ("老人", "中老年", "长辈")
        symptom_or_request = (
            "推荐",
            "药方",
            "方剂",
            "方子",
            "开药",
            "能不能吃",
            "能吃吗",
            "可不可以吃",
            "适合",
            "咳嗽",
            "多痰",
            "痰",
            "发热",
            "发烧",
            "高热",
            "症状",
            "调理",
        )
        explicit_risk_context = (
            "能不能吃",
            "能吃吗",
            "可不可以吃",
            "禁忌",
            "慎用",
            "慢病",
            "过敏",
            "用药",
            "高血压",
            "糖尿病",
            "症状",
            "咳嗽",
            "多痰",
            "发热",
            "发烧",
            "高热",
        )
        shopping_context = ("送礼", "礼盒", "产品", "成药", "成品", "购买", "购物", "品牌", "怕苦", "好喝", "口味")

        has_high_risk_person = any(token in compact_question for token in hard_risk_people)
        if not has_high_risk_person and re.search(r"\d{1,2}岁", compact_question):
            has_high_risk_person = True
        has_soft_risk_person = any(token in compact_question for token in soft_risk_people)
        has_risk_intent = any(token in compact_question for token in symptom_or_request)
        has_explicit_risk_context = any(token in compact_question for token in explicit_risk_context)
        if has_soft_risk_person and has_risk_intent and not has_high_risk_person:
            if any(token in compact_question for token in shopping_context) and not has_explicit_risk_context:
                return None
            has_high_risk_person = has_explicit_risk_context
        if has_high_risk_person and has_risk_intent:
            return self.by_key("risk_boundary")
        return None

    def _product_development_override(self, compact_question: str) -> QARoute | None:
        """Keep complete R&D briefs from being reduced to one constraint sub-route."""
        if not compact_question:
            return None

        development_intent = (
            "开发",
            "研发",
            "新品",
            "新产品",
            "产品开发",
            "产品研发",
            "配方设计",
            "生成配方",
        )
        product_signals = (
            "产品",
            "配方",
            "饮品",
            "饮料",
            "固体饮料",
            "茶包",
            "软糖",
            "代餐粉",
            "口服液",
            "剂型",
        )
        if not any(token in compact_question for token in development_intent):
            return None
        if not any(token in compact_question for token in product_signals):
            return None
        return self.by_key("product_development")

    @staticmethod
    def _score(route: QARoute, compact_question: str, fallback_question_type: str | None) -> int:
        if not compact_question:
            return 0
        negatives = route.match.get("negative", [])
        if any(token and token in compact_question for token in negatives):
            return 0

        score = 0
        matched = False
        for token in route.match.get("any", []):
            if token and token in compact_question:
                matched = True
                score += 12 + min(len(token), 8)
        for token in route.match.get("boost", []):
            if token and token in compact_question:
                score += 5
        if fallback_question_type and route.question_type == fallback_question_type:
            matched = True
            score += 4
        if not matched and fallback_question_type != route.question_type:
            return 0
        return score + route.priority

    @staticmethod
    def _fallback_route() -> QARoute:
        return QARoute(
            task_key="entity_explanation",
            audience="general",
            question_type="entity_explanation",
            label="通用：实体解释与图谱证据整理",
            route_label="通用：实体解释与图谱证据整理",
            kb_route="按命中实体在 KB1-KB8 中扩展相邻证据",
            required_kbs=[],
            answer_outline=["核心结论", "知识依据", "风险与禁忌", "证据边界", "总结建议", "追问建议"],
            missing_slots=[],
            output_boundary="只基于命中实体和相邻证据解释。",
            evidence_requirements=[],
            preferred_entity_types=["Herb", "Formula", "Effect", "Symptom", "ComplianceRule"],
            graph_scene="entity_explanation",
            priority=1,
            offer_constitution_panel=False,
            match={"any": [], "boost": [], "negative": []},
            reasoning_steps=[],
        )


@lru_cache(maxsize=1)
def get_qa_route_resolver() -> QARouteResolver:
    return QARouteResolver.from_file()
