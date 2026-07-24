"""Rebuild the 2026-06-04 agent knowledge graph in Neo4j.

The 0604 graph uses KB1-KB8 as the source of truth, plus the current 0512
consumer/persona workbooks under the same data root. It intentionally does not
import the old Compound / ingredient network.

Examples:
    python scripts/import_agent_kg_0604.py --dry-run
    python scripts/import_agent_kg_0604.py --clear
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_VENDOR = Path(__file__).resolve().parents[1] / "backend" / "_vendor"
if BACKEND_VENDOR.exists():
    sys.path.insert(0, str(BACKEND_VENDOR))

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from import_neo4j_kg import read_sheet_rows
from neo4j import GraphDatabase


DEFAULT_DATA_ROOT = Path(r"D:\工作\多智能体-宋\最新数据\6-4\药食同源agent项目")
DEFAULT_REGULATORY_OVERRIDES_PATH = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "app"
    / "data"
    / "ingredient_regulatory_overrides.json"
)
DEFAULT_NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
DEFAULT_NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
DEFAULT_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
KB_DIR_NAME = "药食同源Agent_8类知识库-0531"


NODE_KEYS = {
    "Herb": "herb_name",
    "EffectCategory": "effect_category_name",
    "Effect": "effect_name",
    "Symptom": "symptom_name",
    "NatureFlavor": "nature_flavor_name",
    "Meridian": "meridian_name",
    "Flavor": "flavor_name",
    "Taboo": "taboo_name",
    "Formula": "formula_name",
    "Source": "source_name",
    "Product": "product_id",
    "ComplianceRule": "rule_id",
    "RiskExpression": "expression",
    "ConstitutionType": "constitution_type_name",
    "ConstitutionQuestion": "question_code",
    "ConsumerProfile": "profile_id",
    "ConsumerSegment": "segment_key",
    "ConsumerReview": "review_id",
}


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).replace("\u0000", "").strip()
    return text or None


def safe_float(value: Any) -> float | None:
    text = clean_text(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def safe_int(value: Any) -> int | None:
    number = safe_float(value)
    return int(number) if number is not None else None


def compact_props(props: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in props.items():
        if value is None:
            continue
        if isinstance(value, bool):
            cleaned[key] = value
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            cleaned[key] = value
            continue
        if isinstance(value, list):
            items = []
            for item in value:
                text = clean_text(item)
                if text and text not in items:
                    items.append(text)
            if items:
                cleaned[key] = items
            continue
        text = clean_text(value)
        if text is not None:
            cleaned[key] = text
    return cleaned


def split_items(value: Any) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    for sep in ["；", ";", "，", ",", "/", "\n", "\r", "|"]:
        text = text.replace(sep, "、")
    items: list[str] = []
    for item in text.split("、"):
        cleaned = clean_text(item)
        if cleaned and cleaned not in items:
            items.append(cleaned)
    return items


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(clean_text(part) or "" for part in parts)
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def product_id(row: dict[str, Any]) -> str:
    name = clean_text(row.get("商品名")) or "未知产品"
    brand = clean_text(row.get("品牌")) or ""
    return stable_id("PRD", brand, name)


def source_product_id(row: dict[str, Any]) -> str:
    product = clean_text(row.get("product_id"))
    if product:
        return product
    platform = clean_text(row.get("platform") or row.get("source_platform")) or ""
    source_no = clean_text(row.get("source_product_no")) or ""
    name = clean_text(row.get("product_name")) or "未知产品"
    return stable_id("SRC_PRD", platform, source_no, name)


def review_id(row: dict[str, Any], source: str) -> str:
    value = clean_text(row.get("review_id"))
    if value:
        return value
    return stable_id("REV", source, row.get("product_id"), row.get("review_text"), row.get("review_time"))


def consumer_segment_key(crowd: Any, scenario: Any, effect: Any) -> str:
    raw = "|".join(clean_text(part) or "未识别" for part in (crowd, scenario, effect))
    return stable_id("SEG", raw)


def read_rows(path: Path, sheet: str) -> list[dict[str, Any]]:
    if not path.exists():
        print(f"File not found, skip: {path}")
        return []
    return list(read_sheet_rows(path, sheet))


class GraphBuild:
    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        self.edges: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}

    def add_node(self, label: str, key_value: Any, props: dict[str, Any] | None = None) -> str | None:
        key_name = NODE_KEYS[label]
        value = clean_text(key_value)
        if not value:
            return None
        record = self.nodes[label].setdefault(value, {key_name: value})
        for key, prop_value in compact_props(props or {}).items():
            if key == key_name:
                continue
            if prop_value in ("", None, []):
                continue
            current = record.get(key)
            if current in (None, "", [], "待核验", "未知"):
                record[key] = prop_value
            elif current != prop_value and key in {"data_sources", "source_sheets"}:
                merged = current if isinstance(current, list) else [current]
                incoming = prop_value if isinstance(prop_value, list) else [prop_value]
                for item in incoming:
                    if item not in merged:
                        merged.append(item)
                record[key] = merged
        return value

    def add_edge(
        self,
        start_label: str,
        start_value: Any,
        rel_type: str,
        end_label: str,
        end_value: Any,
        props: dict[str, Any] | None = None,
    ) -> None:
        start = clean_text(start_value)
        end = clean_text(end_value)
        if not start or not end:
            return
        identity = (start_label, start, rel_type, end_label, end)
        record = self.edges.setdefault(identity, {})
        record.update(compact_props(props or {}))

    def merge_can_replace_edge(self, source: Any, target: Any, props: dict[str, Any] | None = None) -> None:
        start = clean_text(source)
        end = clean_text(target)
        if not start or not end:
            return
        identity = ("Herb", start, "CAN_REPLACE", "Herb", end)
        record = self.edges.setdefault(identity, {})
        incoming = compact_props(props or {})
        preserve_if_set = {
            "final_score",
            "professional_score",
            "rank",
            "candidate_source",
            "effect_level1_similarity",
            "effect_level2_similarity",
            "symptom_similarity",
            "nature_similarity",
            "flavor_similarity",
            "meridian_similarity",
            "safety_score",
            "recommendation_status",
        }
        for key, value in incoming.items():
            if key not in record or record[key] in (None, ""):
                record[key] = value
            elif key == "source_type" and value and value not in str(record[key]):
                record[key] = f"{record[key]}+{value}"
            elif key in preserve_if_set and record.get(key) not in (None, ""):
                continue
            elif key.startswith("consumer_") or key in {"embedding_similarity", "structure_similarity", "formula_context_similarity", "effect_similarity"}:
                record[key] = value
            else:
                record[key] = value

    def herb_names(self) -> list[str]:
        return sorted(self.nodes["Herb"], key=len, reverse=True)

    def stats(self) -> dict[str, Any]:
        return {
            "nodes": {label: len(items) for label, items in sorted(self.nodes.items())},
            "relationships": dict(sorted(Counter(edge[2] for edge in self.edges).items())),
            "total_nodes": sum(len(items) for items in self.nodes.values()),
            "total_relationships": len(self.edges),
        }


def extract_known_herbs(text: Any, herb_names: list[str]) -> list[str]:
    source = clean_text(text) or ""
    if not source:
        return []
    found: list[tuple[int, str]] = []
    for name in herb_names:
        index = source.find(name)
        if index >= 0:
            found.append((index, name))
    output: list[str] = []
    for _, name in sorted(found):
        if name not in output:
            output.append(name)
    return output


def add_effects(graph: GraphBuild, owner_label: str, owner_value: str, value: Any, source: str) -> None:
    for effect in split_items(value):
        graph.add_node("Effect", effect, {"data_sources": [source]})
        graph.add_edge(owner_label, owner_value, "HAS_EFFECT", "Effect", effect, {"source": source})


def add_symptoms(graph: GraphBuild, owner_label: str, owner_value: str, value: Any, source: str) -> None:
    for symptom in split_items(value):
        graph.add_node("Symptom", symptom, {"data_sources": [source]})
        graph.add_edge(owner_label, owner_value, "TREATS" if owner_label == "Herb" else "TARGETS_SYMPTOM", "Symptom", symptom, {"source": source})


def build_kb1_to_kb3(graph: GraphBuild, kb_root: Path) -> None:
    for row in read_rows(kb_root / "KB1_药食同源原料合法性库.xlsx", "KB1_合法性库"):
        herb = graph.add_node(
            "Herb",
            row.get("herb_name"),
            {
                "herb_name": row.get("herb_name"),
                "food_homology": row.get("is_food_homology"),
                "is_food_homology": row.get("is_food_homology"),
                "directory_source": row.get("目录来源"),
                "is_toxic": row.get("是否有毒"),
                "toxicity_level": row.get("毒性等级"),
                "pregnancy_taboo": row.get("孕妇禁忌"),
                "usage_note": row.get("使用注意"),
                "data_sources": ["KB1_药食同源原料合法性库"],
            },
        )
        if row.get("孕妇禁忌") and herb:
            taboo = f"孕妇禁忌：{row.get('孕妇禁忌')}"
            graph.add_node("Taboo", taboo, {"taboo_type": "pregnancy", "data_sources": ["KB1"]})
            graph.add_edge("Herb", herb, "HAS_TABOO", "Taboo", taboo, {"source": "KB1"})

    for row in read_rows(kb_root / "KB2_功效-病症-性味归经库.xlsx", "KB2_功效病症库"):
        herb = graph.add_node(
            "Herb",
            row.get("herb_name"),
            {
                "effect_level1": row.get("effect_level1"),
                "effect_level2": row.get("effect_level2"),
                "efficacy": row.get("功效"),
                "symptom_text": row.get("主治病症"),
                "nature": row.get("nature"),
                "flavor": row.get("flavor"),
                "meridian": row.get("meridian"),
                "contraindication": row.get("contraindication"),
                "usage_precautions": row.get("usage_precautions"),
                "data_sources": ["KB2_功效-病症-性味归经库"],
            },
        )
        if not herb:
            continue
        for level, category in [("level1", row.get("effect_level1")), ("level2", row.get("effect_level2"))]:
            if graph.add_node("EffectCategory", category, {"category_level": level, "data_sources": ["KB2"]}):
                graph.add_edge("Herb", herb, "BELONGS_TO_EFFECT_CATEGORY", "EffectCategory", category, {"source": "KB2", "category_level": level})
        add_effects(graph, "Herb", herb, row.get("功效"), "KB2")
        add_symptoms(graph, "Herb", herb, row.get("主治病症"), "KB2")
        for nature_flavor in split_items(row.get("nature")) + split_items(row.get("flavor")):
            graph.add_node("NatureFlavor", nature_flavor, {"data_sources": ["KB2"]})
            graph.add_edge("Herb", herb, "HAS_NATURE_FLAVOR", "NatureFlavor", nature_flavor, {"source": "KB2"})
        for meridian in split_items(row.get("meridian")):
            graph.add_node("Meridian", meridian, {"data_sources": ["KB2"]})
            graph.add_edge("Herb", herb, "ENTERS_MERIDIAN", "Meridian", meridian, {"source": "KB2"})
        contraindication = clean_text(row.get("contraindication"))
        if contraindication:
            graph.add_node("Taboo", contraindication, {"taboo_type": "contraindication", "data_sources": ["KB2"]})
            graph.add_edge("Herb", herb, "HAS_TABOO", "Taboo", contraindication, {"source": "KB2"})

    for row in read_rows(kb_root / "KB3_风味评价库.xlsx", "KB3_风味评价库"):
        herb = graph.add_node(
            "Herb",
            row.get("herb_name"),
            {
                "bitter_risk": safe_float(row.get("苦味风险")),
                "astringent_risk": safe_float(row.get("涩感风险")),
                "sweet_contribution": safe_float(row.get("甜味贡献")),
                "sour_contribution": safe_float(row.get("酸味贡献")),
                "herbal_medicine_risk": safe_float(row.get("草本/药味风险")),
                "aroma_description": row.get("香气描述"),
                "aftertaste_risk": safe_float(row.get("后味风险")),
                "overall_flavor_acceptance": safe_float(row.get("整体风味接受度")),
                "pungentdb_taste_type": row.get("PungentDB_taste_type"),
                "pungentdb_compound": row.get("PungentDB_compound"),
                "data_sources": ["KB3_风味评价库"],
            },
        )
        if not herb:
            continue
        for flavor in split_items(row.get("PungentDB_taste_type")) + split_items(row.get("香气描述")):
            graph.add_node("Flavor", flavor, {"data_sources": ["KB3"]})
            graph.add_edge(
                "Herb",
                herb,
                "HAS_FLAVOR",
                "Flavor",
                flavor,
                {"source": "KB3", "intensity": safe_float(row.get("整体风味接受度"))},
            )


def build_kb4_replacements(graph: GraphBuild, kb_root: Path) -> None:
    for row in read_rows(kb_root / "KB4_药食同源_替换.xlsx", "Top10_药食同源替换非药食同源"):
        source = graph.add_node(
            "Herb",
            row.get("原非药食同源药材"),
            {
                "food_homology": "否",
                "effect_level1": row.get("原药材effect_level1"),
                "effect_level2": row.get("原药材effect_level2"),
                "symptom_text": row.get("原药材主治病症"),
                "nature": row.get("原药材nature"),
                "flavor": row.get("原药材flavor"),
                "meridian": row.get("原药材meridian"),
                "data_sources": ["KB4_单味药替代评分库"],
            },
        )
        target = graph.add_node(
            "Herb",
            row.get("候选替代药材"),
            {
                "food_homology": "是",
                "effect_level1": row.get("候选effect_level1"),
                "effect_level2": row.get("候选effect_level2"),
                "symptom_text": row.get("候选主治病症"),
                "nature": row.get("候选nature"),
                "flavor": row.get("候选flavor"),
                "meridian": row.get("候选meridian"),
                "usage_precautions": row.get("候选使用注意"),
                "contraindication": row.get("候选contraindication"),
                "data_sources": ["KB4_单味药替代评分库"],
            },
        )
        if source and target:
            graph.add_edge(
                "Herb",
                source,
                "CAN_REPLACE",
                "Herb",
                target,
                {
                    "model": "replacement_0604",
                    "rank": safe_int(row.get("替换排名")),
                    "candidate_source": row.get("候选替代来源"),
                    "final_score": safe_float(row.get("最终综合评分")),
                    "professional_score": safe_float(row.get("专业评分")),
                    "flavor_acceptance": safe_float(row.get("flavor大众接受度")),
                    "effect_level1_similarity": safe_float(row.get("effect_level1相似度")),
                    "effect_level2_similarity": safe_float(row.get("effect_level2相似度")),
                    "symptom_similarity": safe_float(row.get("主治病症相似度")),
                    "nature_similarity": safe_float(row.get("性相似度")),
                    "flavor_similarity": safe_float(row.get("味相似度")),
                    "meridian_similarity": safe_float(row.get("归经相似度")),
                    "safety_score": safe_float(row.get("安全性评分")),
                    "recommendation_status": row.get("推荐状态"),
                    "source_type": "KB4_0604",
                },
            )


def build_kb4_rules_and_incompat(graph: GraphBuild, kb_root: Path) -> None:
    kb4_path = kb_root / "KB4_药食同源_替换.xlsx"
    for row in read_rows(kb4_path, "十八反十九畏规则库"):
        herb_a = graph.add_node("Herb", row.get("药材A"), {"data_sources": ["KB4_十八反十九畏"]})
        herb_b = graph.add_node("Herb", row.get("药材B"), {"data_sources": ["KB4_十八反十九畏"]})
        if not herb_a or not herb_b or herb_a == herb_b:
            continue
        edge_props = {
            "rule_type": row.get("规则类型"),
            "description": row.get("规则说明"),
            "source": "KB4_十八反十九畏",
        }
        graph.add_edge("Herb", herb_a, "INCOMPATIBLE_WITH", "Herb", herb_b, edge_props)
        graph.add_edge("Herb", herb_b, "INCOMPATIBLE_WITH", "Herb", herb_a, edge_props)

    for row in read_rows(kb4_path, "评分规则_详细"):
        rule_name = clean_text(row.get("评分项"))
        if not rule_name:
            continue
        rule_id = stable_id("CR", "替代评分规则", rule_name, row.get("使用字段"))
        graph.add_node(
            "ComplianceRule",
            rule_id,
            {
                "rule_id": rule_id,
                "rule_type": "替代评分规则",
                "rule_name": rule_name,
                "weight": safe_float(row.get("权重")),
                "used_fields": row.get("使用字段"),
                "rule_content": row.get("计算逻辑"),
                "plain_explanation": row.get("外行解释"),
                "data_sources": ["KB4_评分规则"],
            },
        )

    for row in read_rows(kb4_path, "flavor接受度规则"):
        feature = clean_text(row.get("药味/口感特征"))
        if not feature:
            continue
        rule_id = stable_id("CR", "风味接受度规则", feature, row.get("接受度分值"))
        graph.add_node(
            "ComplianceRule",
            rule_id,
            {
                "rule_id": rule_id,
                "rule_type": "风味接受度规则",
                "rule_name": feature,
                "acceptance_score": safe_float(row.get("接受度分值")),
                "rule_content": row.get("原因"),
                "data_sources": ["KB4_flavor接受度规则"],
            },
        )


def build_kb4_excluded_candidates(graph: GraphBuild, kb_root: Path) -> None:
    kb4_path = kb_root / "KB4_药食同源_替换.xlsx"
    for row in read_rows(kb4_path, "禁忌命中候选_已排除"):
        source = graph.add_node(
            "Herb",
            row.get("原非药食同源药材"),
            {"food_homology": "否", "data_sources": ["KB4_禁忌排除候选"]},
        )
        target = graph.add_node(
            "Herb",
            row.get("候选替代药材"),
            {"food_homology": "是", "data_sources": ["KB4_禁忌排除候选"]},
        )
        if source and target:
            graph.add_edge(
                "Herb",
                source,
                "CAN_REPLACE",
                "Herb",
                target,
                {
                    "model": "replacement_0604",
                    "rank": safe_int(row.get("替换排名")),
                    "candidate_source": row.get("候选替代来源"),
                    "final_score": safe_float(row.get("最终综合评分")),
                    "professional_score": safe_float(row.get("专业评分")),
                    "flavor_acceptance": safe_float(row.get("flavor大众接受度")),
                    "effect_level1_similarity": safe_float(row.get("effect_level1相似度")),
                    "effect_level2_similarity": safe_float(row.get("effect_level2相似度")),
                    "symptom_similarity": safe_float(row.get("主治病症相似度")),
                    "nature_similarity": safe_float(row.get("性相似度")),
                    "flavor_similarity": safe_float(row.get("味相似度")),
                    "meridian_similarity": safe_float(row.get("归经相似度")),
                    "safety_score": safe_float(row.get("安全性评分")),
                    "recommendation_status": "禁忌排除",
                    "exclusion_reason": row.get("排除原因") or row.get("禁忌命中说明") or "禁忌命中已排除",
                    "source_type": "KB4_禁忌排除",
                },
            )


def build_consumer_aware_substitutes(graph: GraphBuild, data_root: Path) -> None:
    csv_path = data_root / "consumer_aware_substitute_results.csv"
    if not csv_path.exists():
        print(f"File not found, skip: {csv_path}")
        return
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            source = graph.add_node(
                "Herb",
                row.get("source_herb"),
                {"data_sources": ["consumer_aware_substitute_results"]},
            )
            target = graph.add_node(
                "Herb",
                row.get("candidate_food_homology_herb"),
                {"food_homology": "是", "data_sources": ["consumer_aware_substitute_results"]},
            )
            if not source or not target:
                continue
            graph.merge_can_replace_edge(
                source,
                target,
                {
                    "model": "consumer_aware",
                    "rank": safe_int(row.get("rank")),
                    "consumer_final_score": safe_float(row.get("final_score")),
                    "flavor_acceptance": safe_float(row.get("flavor_acceptance")),
                    "effect_similarity": safe_float(row.get("effect_similarity")),
                    "embedding_similarity": safe_float(row.get("embedding_similarity")),
                    "structure_similarity": safe_float(row.get("structure_similarity")),
                    "formula_context_similarity": safe_float(row.get("formula_context_similarity")),
                    "source_type": "consumer_aware",
                },
            )


def normalize_formula_name(name: Any) -> str | None:
    text = clean_text(name)
    if not text:
        return None
    text = re.sub(r"[（(].*?[）)]", "", text).strip()
    text = text.replace(" ", "")
    return text or None


def build_meandqi_formulas(graph: GraphBuild, data_root: Path) -> None:
    path = data_root / "0524" / "方剂" / "meandqi方剂数据_中文整理.xlsx"
    if not path.exists():
        print(f"File not found, skip: {path}")
        return
    herb_names = graph.herb_names()
    existing_formulas = set(graph.nodes.get("Formula", {}))
    for row in read_rows(path, "中文整理"):
        formula_name = normalize_formula_name(row.get("方剂中文名"))
        if not formula_name or formula_name in existing_formulas:
            continue
        source_name = clean_text(row.get("来源/出处（中文提取）")) or clean_text(row.get("来源/出处"))
        graph.add_node(
            "Formula",
            formula_name,
            {
                "formula_name": formula_name,
                "source": source_name,
                "efficacy": row.get("应用方向（中文）") or row.get("核心概要"),
                "monarch_herb": row.get("君药"),
                "minister_herb": row.get("臣药"),
                "assistant_herb": row.get("佐药"),
                "guide_herb": row.get("使药"),
                "ingredients": row.get("组成药材（中文初译）"),
                "formula_category": row.get("方剂类别（中文）"),
                "data_sources": ["0524_meandqi"],
            },
        )
        existing_formulas.add(formula_name)
        if source_name:
            graph.add_node("Source", source_name, {"data_sources": ["0524_meandqi"]})
            graph.add_edge("Formula", formula_name, "FROM_SOURCE", "Source", source_name, {"source": "0524_meandqi"})
        add_role_edges(graph, formula_name, row, "0524_meandqi")
        ingredients = row.get("组成药材（中文初译）")
        add_formula_herb_edges(graph, formula_name, ingredients, herb_names, "0524_meandqi")
        add_effects(graph, "Formula", formula_name, row.get("应用方向（中文）") or row.get("核心概要"), "0524_meandqi")


def add_formula_herb_edges(graph: GraphBuild, formula: str, ingredients: Any, herb_names: list[str], source: str, role: str | None = None) -> None:
    for herb in extract_known_herbs(ingredients, herb_names):
        graph.add_edge("Herb", herb, "IN_FORMULA", "Formula", formula, {"role": role or "角色未标注", "source": source})


def add_role_edges(graph: GraphBuild, formula: str, row: dict[str, Any], source: str) -> None:
    role_columns = {
        "monarch_herb": ("MONARCH_HERB", "君药"),
        "minister_herb": ("MINISTER_HERB", "臣药"),
        "assistant_herb": ("ASSISTANT_HERB", "佐药"),
        "guide_herb": ("GUIDE_HERB", "使药"),
        "君药": ("MONARCH_HERB", "君药"),
        "臣药": ("MINISTER_HERB", "臣药"),
        "佐药": ("ASSISTANT_HERB", "佐药"),
        "使药": ("GUIDE_HERB", "使药"),
    }
    for column, (rel_type, role_name) in role_columns.items():
        for herb in split_items(row.get(column)):
            graph.add_node("Herb", herb, {"data_sources": [source]})
            graph.add_edge("Formula", formula, rel_type, "Herb", herb, {"source": source})
            graph.add_edge("Herb", herb, "IN_FORMULA", "Formula", formula, {"role": role_name, "source": source})


def build_kb5_formulas(graph: GraphBuild, kb_root: Path) -> None:
    herb_names = graph.herb_names()
    kb5_root = kb_root / "KB5_名方-名剂知识库"
    for row in read_rows(kb5_root / "100经典名方-处理过.xlsx", "Sheet1"):
        formula = graph.add_node(
            "Formula",
            row.get("prescription_name"),
            {
                "formula_id": row.get("id"),
                "formula_name": row.get("prescription_name"),
                "source": row.get("source"),
                "efficacy": row.get("efficacy"),
                "monarch_herb": row.get("monarch_herb"),
                "minister_herb": row.get("minister_herb"),
                "assistant_herb": row.get("assistant_herb"),
                "guide_herb": row.get("guide_herb"),
                "ingredients": row.get("ingredients"),
                "ratio": row.get("ratio"),
                "crowd": row.get("crowd"),
                "taboo": row.get("taboo"),
                "data_sources": ["KB5_100经典名方"],
            },
        )
        if not formula:
            continue
        source = clean_text(row.get("source"))
        if source:
            graph.add_node("Source", source, {"data_sources": ["KB5"]})
            graph.add_edge("Formula", formula, "FROM_SOURCE", "Source", source, {"source": "KB5"})
        add_effects(graph, "Formula", formula, row.get("efficacy"), "KB5")
        add_symptoms(graph, "Formula", formula, row.get("crowd"), "KB5")
        for taboo in split_items(row.get("taboo")):
            graph.add_node("Taboo", taboo, {"data_sources": ["KB5"]})
            graph.add_edge("Formula", formula, "HAS_TABOO", "Taboo", taboo, {"source": "KB5"})
        add_formula_herb_edges(graph, formula, row.get("ingredients"), herb_names, "KB5_100经典名方")
        add_role_edges(graph, formula, row, "KB5_100经典名方")

    for row in read_rows(kb5_root / "TCMM_3000条.xlsx", "方剂数据"):
        formula = graph.add_node(
            "Formula",
            row.get("名称"),
            {
                "tcmm_id": row.get("TCMM ID"),
                "formula_name": row.get("名称"),
                "source": row.get("出处"),
                "ingredients": row.get("药方"),
                "crowd": row.get("适应症"),
                "original_text": row.get("原始文本"),
                "data_sources": ["KB5_TCMM_3000条"],
            },
        )
        if not formula:
            continue
        source = clean_text(row.get("出处"))
        if source:
            graph.add_node("Source", source, {"data_sources": ["KB5"]})
            graph.add_edge("Formula", formula, "FROM_SOURCE", "Source", source, {"source": "KB5_TCMM"})
        add_symptoms(graph, "Formula", formula, row.get("适应症"), "KB5_TCMM")
        add_formula_herb_edges(graph, formula, row.get("药方"), herb_names, "KB5_TCMM")

    for row in read_rows(kb5_root / "方剂学_伤寒论.xlsx", "方剂总表"):
        formula = graph.add_node(
            "Formula",
            row.get("方剂名"),
            {
                "formula_name": row.get("方剂名"),
                "category": row.get("一级分类"),
                "subcategory": row.get("二级分类"),
                "ingredients": row.get("组成"),
                "efficacy": row.get("功用"),
                "crowd": row.get("主治"),
                "source": row.get("来源"),
                "attached_formula": row.get("附方"),
                "notes": row.get("补充依据/备注"),
                "data_sources": ["KB5_方剂学_伤寒论"],
            },
        )
        if not formula:
            continue
        source = clean_text(row.get("来源"))
        if source:
            graph.add_node("Source", source, {"data_sources": ["KB5"]})
            graph.add_edge("Formula", formula, "FROM_SOURCE", "Source", source, {"source": "KB5_伤寒论"})
        add_effects(graph, "Formula", formula, row.get("功用"), "KB5_伤寒论")
        add_symptoms(graph, "Formula", formula, row.get("主治"), "KB5_伤寒论")
        add_formula_herb_edges(graph, formula, row.get("组成"), herb_names, "KB5_伤寒论")


def build_kb6_products(graph: GraphBuild, kb_root: Path) -> None:
    herb_names = graph.herb_names()
    for row in read_rows(kb_root / "KB6_产品与市场库.xlsx", "KB6_产品与市场库"):
        pid = product_id(row)
        ingredient_text = row.get("配料")
        match_source = "配料"
        if not clean_text(ingredient_text):
            ingredient_text = row.get("商品名")
            match_source = "商品名"
        matched_herbs = extract_known_herbs(ingredient_text, herb_names)
        graph.add_node(
            "Product",
            pid,
            {
                "product_id": pid,
                "product_name": row.get("商品名"),
                "brand": row.get("品牌"),
                "dosage_form": row.get("剂型"),
                "ingredients": row.get("配料"),
                "selling_points": row.get("卖点"),
                "price": row.get("价格"),
                "sales": row.get("销量"),
                "comments": row.get("评论"),
                "scenario": row.get("场景"),
                "claimed_effect": row.get("竞品功效标签"),
                "ingredient_match_source": match_source if matched_herbs else None,
                "inferred_ingredients": matched_herbs if not clean_text(row.get("配料")) else None,
                "data_sources": ["KB6_产品与市场库"],
            },
        )
        for herb in matched_herbs:
            graph.add_edge("Product", pid, "USES_HERB", "Herb", herb, {"source": "KB6", "match_source": match_source})
        for effect in split_items(row.get("竞品功效标签")) + split_items(row.get("卖点")):
            graph.add_node("Effect", effect, {"data_sources": ["KB6"]})
            graph.add_edge("Product", pid, "CLAIMS_EFFECT", "Effect", effect, {"source": "KB6"})


def build_consumer_products(graph: GraphBuild, data_root: Path) -> None:
    path = data_root / "0512-消费者_体质" / "消费者评价数据" / "药食同源消费者数据_评论标签化_人群分组.xlsx"
    herb_names = graph.herb_names()
    for row in read_rows(path, "1_产品"):
        pid = source_product_id(row)
        matched_herbs = extract_known_herbs(row.get("ingredients"), herb_names)
        graph.add_node(
            "Product",
            pid,
            {
                "product_id": pid,
                "source_product_no": row.get("source_product_no"),
                "platform": row.get("platform"),
                "product_name": row.get("product_name"),
                "brand": row.get("brand"),
                "category": row.get("category"),
                "dosage_form": row.get("dosage_form"),
                "claimed_effect": row.get("claimed_effect"),
                "ingredients": row.get("ingredients"),
                "origin": row.get("origin"),
                "price": safe_float(row.get("price")),
                "sales": safe_int(row.get("sales")),
                "rating": safe_float(row.get("rating")),
                "packaging": row.get("packaging"),
                "product_standard": row.get("product_standard"),
                "food_production_standard": row.get("food_production_standard"),
                "approval_no": row.get("approval_no"),
                "specification": row.get("specification"),
                "ingredient_detail": row.get("ingredient_detail"),
                "primary_age_group": row.get("主要年龄段"),
                "secondary_age_group": row.get("次要年龄段"),
                "effect_category": row.get("功效大类"),
                "main_material_category": row.get("主要原材料大类"),
                "review_count": safe_int(row.get("评论量_影响因素表")),
                "positive_rate": safe_float(row.get("好评率_影响因素表")),
                "price_level": row.get("价格档次分类"),
                "heat_level": row.get("消费热度分类"),
                "product_form_category": row.get("商品形态分类"),
                "brand_category": row.get("品牌归属分类"),
                "data_sources": ["0512_消费者产品表"],
            },
        )
        for herb in matched_herbs:
            graph.add_edge("Product", pid, "USES_HERB", "Herb", herb, {"source": "0512_product_ingredients"})
        for effect in split_items(row.get("claimed_effect")) + split_items(row.get("功效大类")):
            graph.add_node("Effect", effect, {"data_sources": ["0512_消费者产品表"]})
            graph.add_edge("Product", pid, "CLAIMS_EFFECT", "Effect", effect, {"source": "0512_product_claims"})


def build_consumer_profiles(graph: GraphBuild, data_root: Path) -> list[dict[str, Any]]:
    path = data_root / "0512-消费者_体质" / "消费者评价数据" / "consumer_profile_table_商品对应消费者画像表.xlsx"
    product_edges: list[dict[str, Any]] = []
    for row in read_rows(path, "consumer_profile_table_full"):
        profile_id = clean_text(row.get("profile_id"))
        pid = source_product_id(row)
        if not profile_id or not pid:
            continue
        graph.add_node(
            "Product",
            pid,
            {
                "product_id": pid,
                "product_name": row.get("product_name"),
                "brand": row.get("brand"),
                "data_sources": ["0512_消费者画像"],
            },
        )
        graph.add_node(
            "ConsumerProfile",
            profile_id,
            {
                "profile_id": profile_id,
                "product_id": pid,
                "product_name": row.get("product_name"),
                "brand": row.get("brand"),
                "crowd_type": row.get("crowd_type"),
                "core_need": row.get("core_need"),
                "preferred_dosage": row.get("preferred_dosage"),
                "preferred_flavor": row.get("preferred_flavor"),
                "disliked_flavor": row.get("disliked_flavor"),
                "price_sensitivity": row.get("price_sensitivity"),
                "concern_points": row.get("concern_points"),
                "high_frequency_words": row.get("high_frequency_words"),
                "agent_strategy": row.get("agent_strategy"),
                "review_count": safe_int(row.get("review_count")),
                "valid_review_count": safe_int(row.get("valid_review_count")),
                "positive_rate": safe_float(row.get("positive_rate")),
                "avg_quality_score": safe_float(row.get("avg_quality_score")),
                "top_effect_tags_count": row.get("top_effect_tags_count"),
                "top_flavor_tags_count": row.get("top_flavor_tags_count"),
                "top_dosage_tags_count": row.get("top_dosage_tags_count"),
                "top_complaint_tags_count": row.get("top_complaint_tags_count"),
                "primary_age_group": row.get("主要年龄段"),
                "effect_category": row.get("功效大类"),
                "product_form_category": row.get("商品形态分类"),
                "data_sources": ["0512_消费者画像"],
            },
        )
        edge_props = {
            "review_count": safe_int(row.get("review_count")),
            "positive_rate": safe_float(row.get("positive_rate")),
            "source": "0512_consumer_profile_table",
        }
        graph.add_edge("Product", pid, "HAS_CONSUMER_PROFILE", "ConsumerProfile", profile_id, edge_props)
        product_edges.append({"product_id": pid, "profile_id": profile_id})
        for flavor in split_items(row.get("preferred_flavor")):
            graph.add_node("Flavor", flavor, {"data_sources": ["0512_消费者画像"]})
            graph.add_edge("ConsumerProfile", profile_id, "PREFERS_FLAVOR", "Flavor", flavor, {"source": "0512_consumer_profile"})
        for flavor in split_items(row.get("disliked_flavor")):
            graph.add_node("Flavor", flavor, {"data_sources": ["0512_消费者画像"]})
            graph.add_edge("ConsumerProfile", profile_id, "DISLIKES_FLAVOR", "Flavor", flavor, {"source": "0512_consumer_profile"})
    return product_edges


def build_consumer_segments(graph: GraphBuild, data_root: Path) -> list[dict[str, Any]]:
    path = data_root / "0512-消费者_体质" / "消费者评价数据" / "药食同源消费者数据_评论标签化_人群分组.xlsx"
    top_edges: list[dict[str, Any]] = []
    for row in read_rows(path, "4_人群场景功效分组"):
        crowd = clean_text(row.get("crowd_tags"))
        scenario = clean_text(row.get("scenario_tags"))
        effect = clean_text(row.get("effect_tags"))
        key = consumer_segment_key(crowd, scenario, effect)
        graph.add_node(
            "ConsumerSegment",
            key,
            {
                "segment_key": key,
                "segment_label": " / ".join(part for part in [crowd, scenario, effect] if part),
                "crowd_tags": crowd,
                "scenario_tags": scenario,
                "effect_tags": effect,
                "review_count": safe_int(row.get("review_count")),
                "avg_quality_score": safe_float(row.get("avg_quality_score")),
                "positive_rate": safe_float(row.get("positive_rate")),
                "negative_rate": safe_float(row.get("negative_rate")),
                "top_product_ids": row.get("top_product_ids"),
                "top_flavor_tags": row.get("top_flavor_tags"),
                "top_dosage_tags": row.get("top_dosage_tags"),
                "top_complaint_tags": row.get("top_complaint_tags"),
                "example_reviews": row.get("example_reviews"),
                "data_sources": ["0512_人群场景功效分组"],
            },
        )
        for flavor in split_items(row.get("top_flavor_tags")):
            graph.add_node("Flavor", flavor, {"data_sources": ["0512_人群场景功效分组"]})
            graph.add_edge("ConsumerSegment", key, "SEGMENT_PREFERS_FLAVOR", "Flavor", flavor, {"source": "0512_consumer_segment"})
        for rank, pid in enumerate(split_items(row.get("top_product_ids")), start=1):
            graph.add_node("Product", pid, {"product_id": pid, "data_sources": ["0512_人群场景功效分组"]})
            graph.add_edge("ConsumerSegment", key, "TOP_PRODUCT", "Product", pid, {"rank": rank, "source": "0512_consumer_segment"})
            top_edges.append({"segment_key": key, "product_id": pid, "rank": rank})
    return top_edges


def build_consumer_reviews(graph: GraphBuild, data_root: Path) -> None:
    path = data_root / "0512-消费者_体质" / "消费者评价数据" / "药食同源消费者数据_评论标签化_人群分组.xlsx"
    for sheet in ["2_京东评论数据", "3_淘宝评论数据"]:
        for row in read_rows(path, sheet):
            rid = review_id(row, sheet)
            pid = source_product_id(row)
            graph.add_node("Product", pid, {"product_id": pid, "data_sources": [f"0512_{sheet}"]})
            graph.add_node(
                "ConsumerReview",
                rid,
                {
                    "review_id": rid,
                    "product_id": pid,
                    "source_product_no": row.get("source_product_no"),
                    "source_platform": row.get("source_platform"),
                    "review_text": row.get("review_text"),
                    "cleaned_text": row.get("cleaned_text"),
                    "rating": safe_float(row.get("rating")),
                    "review_time": row.get("review_time"),
                    "is_valid": safe_int(row.get("is_valid")),
                    "quality_score": safe_float(row.get("quality_score")),
                    "sentiment": row.get("sentiment"),
                    "flavor_tags": row.get("flavor_tags"),
                    "effect_tags": row.get("effect_tags"),
                    "dosage_tags": row.get("dosage_tags"),
                    "crowd_tags": row.get("crowd_tags"),
                    "scenario_tags": row.get("scenario_tags"),
                    "complaint_tags": row.get("complaint_tags"),
                    "is_repurchase": safe_int(row.get("is_repurchase")),
                    "is_followup": safe_int(row.get("is_followup")),
                    "followup_days": safe_int(row.get("followup_days")),
                    "followup_text": row.get("followup_text"),
                    "member_level": row.get("member_level"),
                    "product_spec": row.get("product_spec"),
                    "image_count": safe_int(row.get("image_count")),
                    "like_count": safe_int(row.get("like_count")),
                    "reply_count": safe_int(row.get("reply_count")),
                    "data_sources": [f"0512_{sheet}"],
                },
            )
            graph.add_edge("ConsumerReview", rid, "REVIEWS_PRODUCT", "Product", pid, {"source": f"0512_{sheet}"})
            for flavor in split_items(row.get("flavor_tags")):
                graph.add_node("Flavor", flavor, {"data_sources": [f"0512_{sheet}"]})
                graph.add_edge("ConsumerReview", rid, "MENTIONS_FLAVOR", "Flavor", flavor, {"source": f"0512_{sheet}"})
            for effect in split_items(row.get("effect_tags")):
                graph.add_node("Effect", effect, {"data_sources": [f"0512_{sheet}"]})
                graph.add_edge("ConsumerReview", rid, "MENTIONS_EFFECT", "Effect", effect, {"source": f"0512_{sheet}"})
            crowd = row.get("crowd_tags")
            scenario = row.get("scenario_tags")
            effect = row.get("effect_tags")
            if clean_text(crowd) or clean_text(scenario) or clean_text(effect):
                segment = consumer_segment_key(crowd, scenario, effect)
                graph.add_node(
                    "ConsumerSegment",
                    segment,
                    {
                        "segment_key": segment,
                        "segment_label": " / ".join(part for part in [clean_text(crowd), clean_text(scenario), clean_text(effect)] if part),
                        "crowd_tags": crowd,
                        "scenario_tags": scenario,
                        "effect_tags": effect,
                        "data_sources": [f"0512_{sheet}"],
                    },
                )
                graph.add_edge("ConsumerReview", rid, "BELONGS_TO_CONSUMER_SEGMENT", "ConsumerSegment", segment, {"source": f"0512_{sheet}"})


def build_consumer_personas(graph: GraphBuild, data_root: Path) -> None:
    build_consumer_products(graph, data_root)
    profile_edges = build_consumer_profiles(graph, data_root)
    top_edges = build_consumer_segments(graph, data_root)
    segment_by_product: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in top_edges:
        segment_by_product[edge["product_id"]].append(edge)
    for edge in profile_edges:
        for top in segment_by_product.get(edge["product_id"], []):
            graph.add_edge(
                "ConsumerProfile",
                edge["profile_id"],
                "MATCHES_CONSUMER_SEGMENT",
                "ConsumerSegment",
                top["segment_key"],
                {"top_product_rank": top["rank"], "source": "0512_consumer_segment_top_product"},
            )
    build_consumer_reviews(graph, data_root)


def build_kb7_compliance(graph: GraphBuild, kb_root: Path) -> None:
    kb7_root = kb_root / "KB7_食品标准合规库"
    split_configs = [
        (kb7_root / "01_药食同源目录.xlsx", "药食同源目录", "directory"),
        (kb7_root / "02_GB2760添加剂规则.xlsx", "GB2760添加剂规则", "gb2760"),
        (kb7_root / "03_GB7718标签规则.xlsx", "GB7718标签规则", "gb7718"),
        (kb7_root / "04_普通食品宣传边界.xlsx", "普通食品宣传边界", "promotion"),
        (kb7_root / "05_禁用慎用表述.xlsx", "禁用慎用表述", "risk_expression"),
    ]
    used_split = False
    for path, sheet, kind in split_configs:
        if not path.exists():
            continue
        used_split = True
        if kind == "directory":
            _import_kb7_directory_rows(graph, read_rows(path, sheet), source_tag="KB7_分拆_药食同源目录")
        elif kind == "gb2760":
            _import_kb7_gb2760_rows(graph, read_rows(path, sheet), source_tag="KB7_分拆_GB2760")
        elif kind == "gb7718":
            _import_kb7_gb7718_rows(graph, read_rows(path, sheet), source_tag="KB7_分拆_GB7718")
        elif kind == "promotion":
            _import_kb7_promotion_rows(graph, read_rows(path, sheet), source_tag="KB7_分拆_宣传边界")
        elif kind == "risk_expression":
            _import_kb7_risk_expression_rows(graph, read_rows(path, sheet), source_tag="KB7_分拆_禁用慎用表述")

    if used_split:
        return

    path = kb7_root / "食品标准合规.xlsx"
    _import_kb7_directory_rows(graph, read_rows(path, "药食同源目录"), source_tag="KB7_药食同源目录", herb_field="原料名称")
    _import_kb7_gb2760_rows(graph, read_rows(path, "GB2760添加剂规则"), source_tag="KB7")
    _import_kb7_gb7718_rows(graph, read_rows(path, "GB7718标签规则"), source_tag="KB7")
    _import_kb7_promotion_rows(graph, read_rows(path, "普通食品宣传边界"), source_tag="KB7")
    _import_kb7_risk_expression_rows(graph, read_rows(path, "禁用慎用表述"), source_tag="KB7_禁用慎用表述", merged=True)


def _import_kb7_directory_rows(
    graph: GraphBuild,
    rows: list[dict[str, Any]],
    source_tag: str,
    herb_field: str = "原料名",
) -> None:
    for row in rows:
        herb_name = row.get(herb_field) or row.get("原料名称") or row.get("原料名")
        herb = graph.add_node(
            "Herb",
            herb_name,
            {
                "food_homology": "是",
                "directory_source": row.get("目录来源"),
                "announcement_year": row.get("公告年份"),
                "edible_part": row.get("可食用部位") or row.get("可食部位/部位"),
                "food_use_limit": row.get("使用限制"),
                "food_safety_note": row.get("安全限量/备注"),
                "data_sources": [source_tag],
            },
        )
        rule_id = stable_id("CR", "药食同源目录", herb_name, row.get("目录来源"), source_tag)
        graph.add_node(
            "ComplianceRule",
            rule_id,
            {
                "rule_id": rule_id,
                "rule_type": "药食同源目录",
                "rule_name": herb_name,
                "directory_source": row.get("目录来源"),
                "announcement_year": row.get("公告年份"),
                "applicable_scope": row.get("使用限制"),
                "rule_content": row.get("安全限量/备注"),
                "source_file": row.get("证据文件") or row.get("来源文件"),
                "data_sources": [source_tag],
            },
        )
        if herb:
            graph.add_edge("Herb", herb, "LISTED_IN_COMPLIANCE_RULE", "ComplianceRule", rule_id, {"source": source_tag})


def _import_kb7_gb2760_rows(graph: GraphBuild, rows: list[dict[str, Any]], source_tag: str) -> None:
    for row in rows:
        name = clean_text(row.get("规则对象")) or clean_text(row.get("添加剂/规则"))
        if not name:
            continue
        rule_id = stable_id("CR", "GB2760", name, source_tag, json.dumps(row, ensure_ascii=False, sort_keys=True))
        graph.add_node(
            "ComplianceRule",
            rule_id,
            {
                "rule_id": rule_id,
                "rule_type": "GB2760添加剂规则",
                "rule_name": name,
                "function_category": row.get("功能类别"),
                "applicable_scope": row.get("适用范围") or row.get("适用食品/食品分类"),
                "max_usage": row.get("最大使用量/残留量"),
                "rule_content": row.get("规则内容") or row.get("合规检查逻辑"),
                "agent_check_point": row.get("Agent检查点") or row.get("合规检查逻辑"),
                "source_file": row.get("证据文件") or row.get("来源文件"),
                "data_sources": [source_tag],
            },
        )


def _import_kb7_gb7718_rows(graph: GraphBuild, rows: list[dict[str, Any]], source_tag: str) -> None:
    for row in rows:
        name = clean_text(row.get("标签项目"))
        if not name:
            continue
        rule_id = stable_id("CR", "GB7718", name, source_tag, json.dumps(row, ensure_ascii=False, sort_keys=True))
        graph.add_node(
            "ComplianceRule",
            rule_id,
            {
                "rule_id": rule_id,
                "rule_type": "GB7718标签规则",
                "rule_name": name,
                "applicable_scope": row.get("适用说明") or row.get("是否强制"),
                "rule_content": row.get("规则内容") or row.get("标示规则"),
                "agent_check_point": row.get("Agent检查点"),
                "source_file": row.get("证据文件") or row.get("来源文件"),
                "data_sources": [source_tag],
            },
        )


def _import_kb7_promotion_rows(graph: GraphBuild, rows: list[dict[str, Any]], source_tag: str) -> None:
    for row in rows:
        name = clean_text(row.get("边界类型"))
        if not name:
            continue
        rule_id = stable_id("CR", "普通食品宣传边界", name, source_tag, json.dumps(row, ensure_ascii=False, sort_keys=True))
        graph.add_node(
            "ComplianceRule",
            rule_id,
            {
                "rule_id": rule_id,
                "rule_type": "普通食品宣传边界",
                "rule_name": name,
                "risk_level": row.get("风险等级"),
                "applicable_scope": row.get("允许/禁止") or row.get("依据"),
                "rule_content": row.get("规则内容"),
                "agent_check_point": row.get("Agent判断逻辑"),
                "source_file": row.get("依据") or row.get("依据文件"),
                "data_sources": [source_tag],
            },
        )


def _import_kb7_risk_expression_rows(
    graph: GraphBuild,
    rows: list[dict[str, Any]],
    source_tag: str,
    merged: bool = False,
) -> None:
    for row in rows:
        expression = graph.add_node(
            "RiskExpression",
            row.get("表述"),
            {
                "expression": row.get("表述"),
                "category": row.get("类别"),
                "risk_level": row.get("风险等级"),
                "risk_reason": row.get("风险说明") or row.get("风险原因"),
                "suggested_expression": row.get("建议替代表述"),
                "source_file": row.get("依据") or row.get("依据文件"),
                "data_sources": [source_tag],
            },
        )
        rule_id = stable_id("CR", "禁用慎用表述", row.get("表述"), row.get("风险等级"), source_tag)
        graph.add_node(
            "ComplianceRule",
            rule_id,
            {
                "rule_id": rule_id,
                "rule_type": "禁用慎用表述",
                "rule_name": row.get("表述") or row.get("风险等级"),
                "risk_level": row.get("风险等级"),
                "rule_content": row.get("风险说明") or row.get("风险原因"),
                "suggested_expression": row.get("建议替代表述"),
                "source_file": row.get("依据") or row.get("依据文件"),
                "data_sources": [source_tag],
            },
        )
        if expression:
            graph.add_edge("RiskExpression", expression, "DERIVED_FROM_RULE", "ComplianceRule", rule_id, {"source": source_tag})


def build_kb8_constitution(graph: GraphBuild, kb_root: Path) -> None:
    kb8_root = kb_root / "KB8_9种体质辨识与食养规则库"
    for row in read_rows(kb8_root / "03_九种体质.xlsx", "九种体质"):
        graph.add_node(
            "ConstitutionType",
            row.get("constitution_type"),
            {
                "constitution_id": row.get("constitution_id"),
                "constitution_type_name": row.get("constitution_type"),
                "constitution_category": row.get("constitution_category"),
                "main_feature": row.get("main_feature"),
                "body_feature": row.get("body_feature"),
                "common_manifestations": row.get("common_manifestations"),
                "psychological_feature": row.get("psychological_feature"),
                "disease_tendency": row.get("disease_tendency"),
                "environment_adaptability": row.get("environment_adaptability"),
                "source_standard": row.get("source_standard"),
                "source_page": row.get("source_page"),
                "agent_use": row.get("agent_use"),
                "data_sources": ["KB8_九种体质"],
            },
        )

    for row in read_rows(kb8_root / "01_体质问卷.xlsx", "体质问卷"):
        question = graph.add_node(
            "ConstitutionQuestion",
            row.get("question_id"),
            {
                "question_code": row.get("question_id"),
                "table_no": row.get("table_no"),
                "constitution_type_name": row.get("constitution_type"),
                "question_no": safe_int(row.get("question_no")),
                "question_text": row.get("question_text"),
                "reverse_scored": clean_text(row.get("reverse_scoring")) == "是",
                "applicable_group": row.get("applicable_population"),
                "score_1": row.get("score_1"),
                "score_2": row.get("score_2"),
                "score_3": row.get("score_3"),
                "score_4": row.get("score_4"),
                "score_5": row.get("score_5"),
                "source_standard": row.get("source_standard"),
                "source_page": row.get("source_page"),
                "notes": row.get("notes"),
                "data_sources": ["KB8_体质问卷"],
            },
        )
        constitution = graph.add_node("ConstitutionType", row.get("constitution_type"), {"data_sources": ["KB8_体质问卷"]})
        if question and constitution:
            graph.add_edge("ConstitutionQuestion", question, "ASSESSES_CONSTITUTION", "ConstitutionType", constitution, {"source": "KB8"})

    for row in read_rows(kb8_root / "02_评分规则.xlsx", "评分规则"):
        rule_id = clean_text(row.get("rule_id")) or stable_id("CR", "评分规则", row.get("rule_name"))
        graph.add_node(
            "ComplianceRule",
            rule_id,
            {
                "rule_id": rule_id,
                "rule_type": "体质评分规则",
                "rule_name": row.get("rule_name"),
                "target_constitution": row.get("target_constitution"),
                "condition": row.get("condition"),
                "result": row.get("result"),
                "formula_or_rule": row.get("formula_or_rule"),
                "source_standard": row.get("source_standard"),
                "source_page": row.get("source_page"),
                "agent_use": row.get("agent_use"),
                "data_sources": ["KB8_评分规则"],
            },
        )

    herb_names = graph.herb_names()
    for row in read_rows(kb8_root / "04_体质-食养方向.xlsx", "体质食养方向"):
        constitution = graph.add_node(
            "ConstitutionType",
            row.get("constitution_type"),
            {
                "diet_direction": row.get("diet_direction"),
                "food_homology_direction": row.get("food_homology_direction"),
                "suitable_ingredient_examples": row.get("suitable_ingredient_examples"),
                "product_form_suggestion": row.get("product_form_suggestion"),
                "scenario_suggestion": row.get("scenario_suggestion"),
                "risk_control": row.get("risk_control"),
                "evidence_basis": row.get("evidence_basis"),
                "notes": row.get("notes"),
                "data_sources": ["KB8_体质食养方向"],
            },
        )
        if constitution:
            for herb in extract_known_herbs(row.get("suitable_ingredient_examples"), herb_names):
                graph.add_edge("ConstitutionType", constitution, "RECOMMENDS_HERB", "Herb", herb, {"source": "KB8"})

    for row in read_rows(kb8_root / "05_体质慎用原料.xlsx", "体质慎用原料"):
        constitution = graph.add_node("ConstitutionType", row.get("constitution_type"), {"data_sources": ["KB8_体质慎用原料"]})
        if constitution:
            for herb in extract_known_herbs(row.get("caution_ingredient_examples"), herb_names):
                graph.add_edge(
                    "ConstitutionType",
                    constitution,
                    "CAUTIONS_HERB",
                    "Herb",
                    herb,
                    {
                        "caution_category": row.get("caution_category"),
                        "caution_reason": row.get("caution_reason"),
                        "risk_level": row.get("risk_level"),
                        "agent_action": row.get("agent_action"),
                        "notes": row.get("notes"),
                        "source": "KB8",
                    },
                )


def apply_regulatory_overrides(
    graph: GraphBuild,
    overrides_path: Path = DEFAULT_REGULATORY_OVERRIDES_PATH,
) -> None:
    if not overrides_path.exists():
        return
    payload = json.loads(overrides_path.read_text(encoding="utf-8"))
    for item in payload.get("herbs", []):
        herb_name = clean_text(item.get("herb_name"))
        if not herb_name:
            continue
        record = graph.nodes["Herb"].setdefault(herb_name, {"herb_name": herb_name})
        for key, value in compact_props(item.get("properties") or {}).items():
            if key == "herb_name":
                continue
            record[key] = value
        for rule in item.get("compliance_rules", []):
            rule_id = clean_text(rule.get("rule_id"))
            if not rule_id:
                continue
            graph.add_node(
                "ComplianceRule",
                rule_id,
                {
                    "rule_id": rule_id,
                    **(rule.get("properties") or {}),
                    "data_sources": ["ingredient_regulatory_overrides"],
                },
            )
            graph.add_edge(
                "Herb",
                herb_name,
                "LISTED_IN_COMPLIANCE_RULE",
                "ComplianceRule",
                rule_id,
                {"source": "ingredient_regulatory_overrides"},
            )


def build_graph(
    data_root: Path,
    regulatory_overrides_path: Path = DEFAULT_REGULATORY_OVERRIDES_PATH,
) -> GraphBuild:
    kb_root = data_root / KB_DIR_NAME
    graph = GraphBuild()
    build_kb1_to_kb3(graph, kb_root)
    build_kb4_replacements(graph, kb_root)
    build_kb4_rules_and_incompat(graph, kb_root)
    build_kb4_excluded_candidates(graph, kb_root)
    build_kb5_formulas(graph, kb_root)
    build_kb6_products(graph, kb_root)
    build_kb7_compliance(graph, kb_root)
    build_kb8_constitution(graph, kb_root)
    build_consumer_personas(graph, data_root)
    build_consumer_aware_substitutes(graph, data_root)
    build_meandqi_formulas(graph, data_root)
    apply_regulatory_overrides(graph, regulatory_overrides_path)
    return graph


def create_constraints(driver) -> None:
    with driver.session() as session:
        for label, key in NODE_KEYS.items():
            constraint_name = f"{label.lower()}_{key}_unique"
            session.run(f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{key} IS UNIQUE")


def backup_existing_graph(driver, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = backup_dir / f"neo4j_backup_before_0604_rebuild_{timestamp}.json"
    with driver.session() as session:
        nodes = [
            {
                "element_id": record["element_id"],
                "labels": record["labels"],
                "props": record["props"],
            }
            for record in session.run("MATCH (n) RETURN elementId(n) AS element_id, labels(n) AS labels, properties(n) AS props")
        ]
        relationships = [
            {
                "element_id": record["element_id"],
                "type": record["type"],
                "start": record["start"],
                "end": record["end"],
                "props": record["props"],
            }
            for record in session.run(
                """
MATCH ()-[r]->()
RETURN elementId(r) AS element_id, type(r) AS type,
       elementId(startNode(r)) AS start, elementId(endNode(r)) AS end,
       properties(r) AS props
"""
            )
        ]
    path.write_text(json.dumps({"nodes": nodes, "relationships": relationships}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def clear_graph(driver) -> None:
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")


def write_nodes(driver, graph: GraphBuild, batch_size: int = 500) -> Counter[str]:
    stats: Counter[str] = Counter()
    with driver.session() as session:
        for label, records in graph.nodes.items():
            key = NODE_KEYS[label]
            rows = [{"key": value, "props": props} for value, props in records.items()]
            query = f"UNWIND $rows AS row MERGE (n:{label} {{{key}: row.key}}) SET n += row.props"
            for start in range(0, len(rows), batch_size):
                session.run(query, {"rows": rows[start : start + batch_size]})
            stats[label] += len(rows)
    return stats


def write_edges(driver, graph: GraphBuild, batch_size: int = 500) -> Counter[str]:
    stats: Counter[str] = Counter()
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for (start_label, start, rel_type, end_label, end), props in graph.edges.items():
        grouped[(start_label, NODE_KEYS[start_label], rel_type, end_label, NODE_KEYS[end_label])].append(
            {"start": start, "end": end, "props": props}
        )
    with driver.session() as session:
        for (start_label, start_key, rel_type, end_label, end_key), rows in grouped.items():
            query = f"""
UNWIND $rows AS row
MATCH (a:{start_label} {{{start_key}: row.start}})
MATCH (b:{end_label} {{{end_key}: row.end}})
MERGE (a)-[r:{rel_type}]->(b)
SET r += row.props
"""
            for start in range(0, len(rows), batch_size):
                session.run(query, {"rows": rows[start : start + batch_size]})
            stats[rel_type] += len(rows)
    return stats


def run_import(args: argparse.Namespace) -> dict[str, Any]:
    graph = build_graph(args.data_root, args.regulatory_overrides_path)
    result: dict[str, Any] = {
        "dry_run": args.dry_run,
        "data_root": str(args.data_root),
        "compound_network_imported": False,
        "consumer_persona_imported": True,
        "planned": graph.stats(),
    }
    if args.dry_run:
        return result

    driver = GraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_username, args.neo4j_password))
    try:
        if args.clear and not args.skip_backup:
            result["backup_path"] = str(backup_existing_graph(driver, args.backup_dir))
        if args.clear:
            clear_graph(driver)
        create_constraints(driver)
        node_stats = write_nodes(driver, graph)
        edge_stats = write_edges(driver, graph)
        result["imported"] = {
            "nodes": dict(sorted(node_stats.items())),
            "relationships": dict(sorted(edge_stats.items())),
            "total_nodes": sum(node_stats.values()),
            "total_relationships": sum(edge_stats.values()),
        }
        return result
    finally:
        driver.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild the 0604 KB1-KB8 Neo4j graph without Compound nodes.")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument(
        "--regulatory-overrides-path",
        type=Path,
        default=DEFAULT_REGULATORY_OVERRIDES_PATH,
    )
    parser.add_argument("--dry-run", action="store_true", help="Only parse source files and print planned stats.")
    parser.add_argument("--clear", action="store_true", help="Clear the target Neo4j database before import.")
    parser.add_argument("--backup-dir", type=Path, default=Path("neo4j_backups"))
    parser.add_argument("--skip-backup", action="store_true", help="Skip JSON backup when using --clear.")
    parser.add_argument("--neo4j-uri", default=DEFAULT_NEO4J_URI)
    parser.add_argument("--neo4j-username", default=DEFAULT_NEO4J_USERNAME)
    parser.add_argument("--neo4j-password", default=DEFAULT_NEO4J_PASSWORD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_import(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
