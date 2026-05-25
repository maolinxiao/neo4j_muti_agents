"""Incrementally import the latest 0512/0524 agent-project data into Neo4j.

The script never clears existing graph data. It keeps the v3 graph modelling
rule: every node type has its own label and unique key.

Usage:
    python scripts/import_agent_project_data.py --dry-run
    python scripts/import_agent_project_data.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

BACKEND_VENDOR = Path(__file__).resolve().parents[1] / "backend" / "_vendor"
if BACKEND_VENDOR.exists():
    sys.path.insert(0, str(BACKEND_VENDOR))

from neo4j import GraphDatabase

from import_neo4j_kg import read_sheet_rows


DEFAULT_DATA_ROOT = Path(r"D:\工作\多智能体-宋\最新数据\药食同源agent项目")
URI = "neo4j://localhost:7687"
USER = "neo4j"
PASSWORD = "3217858658"


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
        if isinstance(value, (int, float, bool)) and value is not None:
            cleaned[key] = value
            continue
        text = clean_text(value)
        if text is not None:
            cleaned[key] = text
    return cleaned


def split_items(value: Any) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    for sep in ["；", ";", "，", ",", "/", "\n"]:
        text = text.replace(sep, "、")
    items: list[str] = []
    for item in text.split("、"):
        cleaned = clean_text(item)
        if cleaned and cleaned not in items:
            items.append(cleaned)
    return items


def read_sheet(path: Path, sheet_name: str, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        print(f"File not found, skip: {path}")
        return []
    rows = list(read_sheet_rows(path, sheet_name))
    return rows[:limit] if limit else rows


def write_batches(driver, query: str, rows: list[dict[str, Any]], dry_run: bool, batch_size: int = 500) -> int:
    if dry_run or not rows:
        return len(rows)
    with driver.session() as session:
        for start in range(0, len(rows), batch_size):
            session.run(query, {"rows": rows[start : start + batch_size]})
    return len(rows)


def create_constraints(driver, dry_run: bool) -> None:
    constraints = [
        "CREATE CONSTRAINT product_id_unique IF NOT EXISTS FOR (p:Product) REQUIRE p.product_id IS UNIQUE",
        "CREATE CONSTRAINT consumer_profile_unique IF NOT EXISTS FOR (c:ConsumerProfile) REQUIRE c.profile_id IS UNIQUE",
        "CREATE CONSTRAINT consumer_segment_unique IF NOT EXISTS FOR (c:ConsumerSegment) REQUIRE c.segment_key IS UNIQUE",
        "CREATE CONSTRAINT constitution_type_unique IF NOT EXISTS FOR (c:ConstitutionType) REQUIRE c.constitution_type_name IS UNIQUE",
        "CREATE CONSTRAINT constitution_question_unique IF NOT EXISTS FOR (c:ConstitutionQuestion) REQUIRE c.question_code IS UNIQUE",
    ]
    if dry_run:
        return
    with driver.session() as session:
        for query in constraints:
            session.run(query)


def segment_key(crowd: str | None, scenario: str | None, effect: str | None) -> str:
    raw = "|".join([crowd or "", scenario or "", effect or ""])
    return "CS_" + hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def normalize_product_id(row: dict[str, Any]) -> str | None:
    product_id = clean_text(row.get("product_id"))
    if product_id and not product_id.endswith("_"):
        return product_id
    source_no = safe_int(row.get("source_product_no"))
    platform = clean_text(row.get("platform") or row.get("source_platform")) or ""
    prefix = "TB" if "淘" in platform else "JD" if "京" in platform else "PR"
    if source_no is None:
        hash_basis = "|".join(
            clean_text(row.get(key)) or ""
            for key in ("product_name", "brand", "specification", "source_url")
        ).strip("|")
        if not hash_basis:
            return product_id
        digest = hashlib.md5(hash_basis.encode("utf-8")).hexdigest()[:8].upper()
        return f"{prefix}_{digest}"
    return f"{prefix}_{source_no:04d}"


def parse_formula_herbs(text: Any) -> list[dict[str, str | None]]:
    herbs: list[dict[str, str | None]] = []
    for chunk in re.split(r"[，,；;、]", clean_text(text) or ""):
        cleaned = clean_text(chunk)
        if not cleaned:
            continue
        normalized = re.sub(r"[（(].*?[）)]", "", cleaned).strip()
        match = re.match(r"(.+?)([0-9半一二三四五六七八九十百两钱克gG枚片各].*)$", normalized)
        herb_name = clean_text(match.group(1) if match else normalized)
        dosage = clean_text(match.group(2) if match else None)
        if herb_name and len(herb_name) <= 12:
            herbs.append({"herb_name": herb_name, "dosage": dosage})
    return herbs


def build_products(data_root: Path, limit: int | None) -> tuple[list[dict], list[dict]]:
    path = data_root / "0512-消费者_体质" / "消费者评价数据" / "药食同源消费者数据_评论标签化_人群分组.xlsx"
    products: list[dict] = []
    herb_edges: list[dict] = []
    for row in read_sheet(path, "1_产品", limit):
        product_id = normalize_product_id(row)
        if not product_id:
            continue
        products.append(
            {
                "product_id": product_id,
                "props": compact_props(
                    {
                        "product_id": product_id,
                        "source_product_no": safe_int(row.get("source_product_no")),
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
                        "source_url": row.get("jd_url"),
                        "packaging": row.get("packaging"),
                        "product_standard": row.get("product_standard"),
                        "food_production_standard": row.get("food_production_standard"),
                        "approval_no": row.get("approval_no"),
                        "specification": row.get("specification"),
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
                        "data_source": "0512_product_sheet",
                    }
                ),
            }
        )
        for herb_name in split_items(row.get("ingredients")):
            herb_edges.append({"product_id": product_id, "herb_name": herb_name})
    return products, herb_edges


def build_consumer_profiles(data_root: Path, limit: int | None) -> tuple[list[dict], list[dict], list[dict]]:
    path = data_root / "0512-消费者_体质" / "消费者评价数据" / "consumer_profile_table_商品对应消费者画像表.xlsx"
    profiles: list[dict] = []
    product_edges: list[dict] = []
    flavor_edges: list[dict] = []
    for row in read_sheet(path, "consumer_profile_table_full", limit):
        profile_id = clean_text(row.get("profile_id"))
        product_id = normalize_product_id(row)
        if not profile_id or not product_id:
            continue
        profiles.append(
            {
                "profile_id": profile_id,
                "props": compact_props(
                    {
                        "profile_id": profile_id,
                        "product_id": product_id,
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
                        "data_source": "0512_consumer_profile",
                    }
                ),
            }
        )
        product_edges.append(
            {
                "product_id": product_id,
                "profile_id": profile_id,
                "props": compact_props(
                    {
                        "review_count": safe_int(row.get("review_count")),
                        "positive_rate": safe_float(row.get("positive_rate")),
                        "source": "consumer_profile_table",
                    }
                ),
            }
        )
        for flavor_name in split_items(row.get("preferred_flavor")):
            flavor_edges.append({"profile_id": profile_id, "flavor_name": flavor_name, "rel_type": "PREFERS_FLAVOR"})
        for flavor_name in split_items(row.get("disliked_flavor")):
            flavor_edges.append({"profile_id": profile_id, "flavor_name": flavor_name, "rel_type": "DISLIKES_FLAVOR"})
    return profiles, product_edges, flavor_edges


def build_consumer_segments(data_root: Path, limit: int | None) -> tuple[list[dict], list[dict]]:
    path = data_root / "0512-消费者_体质" / "消费者评价数据" / "药食同源消费者数据_评论标签化_人群分组.xlsx"
    segments: list[dict] = []
    top_edges: list[dict] = []
    for row in read_sheet(path, "4_人群场景功效分组", limit):
        crowd = clean_text(row.get("crowd_tags"))
        scenario = clean_text(row.get("scenario_tags"))
        effect = clean_text(row.get("effect_tags"))
        key = segment_key(crowd, scenario, effect)
        segments.append(
            {
                "segment_key": key,
                "props": compact_props(
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
                        "data_source": "0512_consumer_segment",
                    }
                ),
            }
        )
        for rank, product_id in enumerate(split_items(row.get("top_product_ids")), start=1):
            top_edges.append({"segment_key": key, "product_id": product_id, "rank": rank})
    return segments, top_edges


def build_constitutions(data_root: Path, limit: int | None) -> tuple[list[dict], list[dict], list[dict]]:
    path = data_root / "0512-消费者_体质" / "中医体质症状" / "中医体质分类与判定题目.xlsx"
    type_props: dict[str, dict[str, Any]] = {}
    for row in read_sheet(path, "体质得分计算"):
        name = clean_text(row.get("体质类型"))
        if name:
            type_props[name] = compact_props(
                {
                    "constitution_type_name": name,
                    "item_count": safe_int(row.get("条目数")),
                    "judgement_rule": row.get("判定规则提示"),
                    "source": "GB/T 46939-2025",
                    "data_source": "constitution_score_sheet",
                }
            )
    questions: list[dict] = []
    edges: list[dict] = []
    for row in read_sheet(path, "体质题目清单", limit):
        constitution = clean_text(row.get("体质类型"))
        question_no = clean_text(row.get("题号"))
        if not constitution or not question_no:
            continue
        type_props.setdefault(
            constitution,
            compact_props(
                {
                    "constitution_type_name": constitution,
                    "source": "GB/T 46939-2025",
                    "data_source": "constitution_question_sheet",
                }
            ),
        )
        question_code = f"{clean_text(row.get('表号')) or constitution}-{question_no}"
        questions.append(
            {
                "question_code": question_code,
                "props": compact_props(
                    {
                        "question_code": question_code,
                        "table_no": row.get("表号"),
                        "constitution_type_name": constitution,
                        "question_no": safe_int(question_no),
                        "question_text": row.get("题目"),
                        "reverse_scored": clean_text(row.get("是否逆向计分")) == "是",
                        "applicable_group": row.get("适用人群"),
                        "score_1": row.get("1分"),
                        "score_2": row.get("2分"),
                        "score_3": row.get("3分"),
                        "score_4": row.get("4分"),
                        "score_5": row.get("5分"),
                        "source_page": row.get("来源页码"),
                        "data_source": "constitution_question_sheet",
                    }
                ),
            }
        )
        edges.append({"question_code": question_code, "constitution_type_name": constitution})
    types = [{"constitution_type_name": name, "props": props} for name, props in type_props.items()]
    return types, questions, edges


def build_formulas(data_root: Path, limit: int | None) -> tuple[list[dict], list[dict], dict[str, list[dict]]]:
    formulas: list[dict] = []
    in_edges: list[dict] = []
    role_edges: dict[str, list[dict]] = {"MONARCH_HERB": [], "MINISTER_HERB": [], "ASSISTANT_HERB": [], "GUIDE_HERB": []}
    role_columns = {"君药": "MONARCH_HERB", "臣药": "MINISTER_HERB", "佐药": "ASSISTANT_HERB", "使药": "GUIDE_HERB"}

    path = data_root / "0524" / "方剂" / "meandqi方剂数据_中文整理.xlsx"
    for row in read_sheet(path, "中文整理", limit):
        name = clean_text(row.get("方剂中文名"))
        if not name:
            continue
        formulas.append(
            {
                "formula_name": name,
                "props": compact_props(
                    {
                        "formula_name": name,
                        "source": row.get("来源/出处（中文提取）"),
                        "efficacy": row.get("应用方向（中文）"),
                        "category": row.get("方剂类别（中文）"),
                        "ingredients": row.get("组成药材（中文初译）"),
                        "monarch_herb": row.get("君药"),
                        "minister_herb": row.get("臣药"),
                        "assistant_herb": row.get("佐药"),
                        "guide_herb": row.get("使药"),
                        "summary": row.get("中文概要"),
                        "source_url": row.get("原网页"),
                        "data_source": "0524_meandqi",
                    }
                ),
            }
        )
        for role_name, rel_type in role_columns.items():
            for herb_name in split_items(row.get(role_name)):
                in_edges.append({"formula_name": name, "herb_name": herb_name, "role": role_name, "dosage": None})
                role_edges[rel_type].append({"formula_name": name, "herb_name": herb_name})

    path = data_root / "0524" / "方剂" / "TCMM_3000条.xlsx"
    for row in read_sheet(path, "方剂数据", limit):
        name = clean_text(row.get("名称"))
        if not name:
            continue
        formulas.append(
            {
                "formula_name": name,
                "props": compact_props(
                    {
                        "formula_name": name,
                        "tcmm_id": row.get("TCMM ID"),
                        "source": row.get("出处"),
                        "crowd": row.get("适应症"),
                        "ingredients": row.get("药方"),
                        "original_text": row.get("原始文本"),
                        "data_source": "0524_tcmm",
                    }
                ),
            }
        )
        for item in parse_formula_herbs(row.get("药方")):
            in_edges.append({"formula_name": name, "herb_name": item["herb_name"], "role": "角色未标注", "dosage": item["dosage"]})

    path = data_root / "0524" / "方剂" / "方剂学_伤寒论.xlsx"
    for row in read_sheet(path, "方剂总表", limit):
        name = clean_text(row.get("方剂名"))
        if not name:
            continue
        formulas.append(
            {
                "formula_name": name,
                "props": compact_props(
                    {
                        "formula_name": name,
                        "category": row.get("一级分类"),
                        "subcategory": row.get("二级分类"),
                        "efficacy": row.get("功用"),
                        "crowd": row.get("主治"),
                        "source": row.get("来源"),
                        "ingredients": row.get("组成"),
                        "notes": row.get("补充依据/备注"),
                        "data_source": "0524_formula_shanghan",
                    }
                ),
            }
        )
        for item in parse_formula_herbs(row.get("组成")):
            in_edges.append({"formula_name": name, "herb_name": item["herb_name"], "role": "角色未标注", "dosage": item["dosage"]})
    return formulas, in_edges, role_edges


def build_replacements(data_root: Path, limit: int | None) -> list[dict]:
    path = data_root / "0524" / "替换方案.xlsx"
    rows: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for sheet in ["Top10_药食同源替换非药食同源", "Top10_保健食品替换非药食同源"]:
        for row in read_sheet(path, sheet, limit):
            source = clean_text(row.get("原非药食同源药材"))
            target = clean_text(row.get("候选替代药材"))
            candidate_source = clean_text(row.get("候选替代来源")) or sheet
            if not source or not target:
                continue
            identity = (source, target, candidate_source)
            if identity in seen:
                continue
            seen.add(identity)
            rows.append(
                {
                    "source_herb": source,
                    "target_herb": target,
                    "candidate_source": candidate_source,
                    "props": compact_props(
                        {
                            "model": "replacement_0524",
                            "candidate_source": candidate_source,
                            "rank": safe_int(row.get("替换排名")),
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
                            "source_effect_level1": row.get("原药材effect_level1"),
                            "target_effect_level1": row.get("候选effect_level1"),
                            "source_effect_level2": row.get("原药材effect_level2"),
                            "target_effect_level2": row.get("候选effect_level2"),
                            "source_symptoms": row.get("原药材主治病症"),
                            "target_symptoms": row.get("候选主治病症"),
                            "usage_note": row.get("候选使用注意"),
                            "contraindication": row.get("候选contraindication"),
                            "recommendation_status": row.get("推荐状态"),
                            "source_type": "replacement_0524",
                        }
                    ),
                }
            )
    return rows


def import_all(data_root: Path, dry_run: bool, limit: int | None, uri: str, username: str, password: str) -> dict[str, Any]:
    driver = GraphDatabase.driver(uri, auth=(username, password))
    stats: Counter[str] = Counter()
    try:
        create_constraints(driver, dry_run)

        products, product_herb_edges = build_products(data_root, limit)
        stats["products"] = write_batches(driver, "UNWIND $rows AS row MERGE (p:Product {product_id: row.product_id}) SET p += row.props", products, dry_run)
        stats["product_uses_herb_edges"] = write_batches(
            driver,
            """
UNWIND $rows AS row
MERGE (p:Product {product_id: row.product_id})
MERGE (h:Herb {herb_name: row.herb_name})
ON CREATE SET h.food_homology = '待核验'
MERGE (p)-[r:USES_HERB]->(h)
SET r.source = 'consumer_product_ingredients'
""",
            product_herb_edges,
            dry_run,
        )

        profiles, profile_edges, flavor_edges = build_consumer_profiles(data_root, limit)
        stats["consumer_profiles"] = write_batches(driver, "UNWIND $rows AS row MERGE (cp:ConsumerProfile {profile_id: row.profile_id}) SET cp += row.props", profiles, dry_run)
        stats["product_profile_edges"] = write_batches(
            driver,
            """
UNWIND $rows AS row
MERGE (p:Product {product_id: row.product_id})
MERGE (cp:ConsumerProfile {profile_id: row.profile_id})
MERGE (p)-[r:HAS_CONSUMER_PROFILE]->(cp)
SET r += row.props
""",
            profile_edges,
            dry_run,
        )
        for rel_type in ["PREFERS_FLAVOR", "DISLIKES_FLAVOR"]:
            rows = [row for row in flavor_edges if row["rel_type"] == rel_type]
            stats[f"profile_{rel_type.lower()}_edges"] = write_batches(
                driver,
                f"""
UNWIND $rows AS row
MERGE (cp:ConsumerProfile {{profile_id: row.profile_id}})
MERGE (f:Flavor {{flavor_name: row.flavor_name}})
MERGE (cp)-[r:{rel_type}]->(f)
SET r.source = 'consumer_profile_table'
""",
                rows,
                dry_run,
            )

        segments, top_edges = build_consumer_segments(data_root, limit)
        stats["consumer_segments"] = write_batches(driver, "UNWIND $rows AS row MERGE (cs:ConsumerSegment {segment_key: row.segment_key}) SET cs += row.props", segments, dry_run)
        stats["segment_top_product_edges"] = write_batches(
            driver,
            """
UNWIND $rows AS row
MERGE (cs:ConsumerSegment {segment_key: row.segment_key})
MERGE (p:Product {product_id: row.product_id})
MERGE (cs)-[r:TOP_PRODUCT]->(p)
SET r.rank = row.rank, r.source = 'consumer_segment_sheet'
""",
            top_edges,
            dry_run,
        )
        segment_by_product: dict[str, list[dict]] = {}
        for edge in top_edges:
            segment_by_product.setdefault(edge["product_id"], []).append(edge)
        profile_segment_edges = [
            {"profile_id": edge["profile_id"], "segment_key": top["segment_key"], "rank": top["rank"]}
            for edge in profile_edges
            for top in segment_by_product.get(edge["product_id"], [])
        ]
        stats["profile_segment_edges"] = write_batches(
            driver,
            """
UNWIND $rows AS row
MERGE (cp:ConsumerProfile {profile_id: row.profile_id})
MERGE (cs:ConsumerSegment {segment_key: row.segment_key})
MERGE (cp)-[r:MATCHES_CONSUMER_SEGMENT]->(cs)
SET r.top_product_rank = row.rank, r.source = 'consumer_segment_top_product'
""",
            profile_segment_edges,
            dry_run,
        )

        types, questions, constitution_edges = build_constitutions(data_root, limit)
        stats["constitution_types"] = write_batches(driver, "UNWIND $rows AS row MERGE (ct:ConstitutionType {constitution_type_name: row.constitution_type_name}) SET ct += row.props", types, dry_run)
        stats["constitution_questions"] = write_batches(driver, "UNWIND $rows AS row MERGE (cq:ConstitutionQuestion {question_code: row.question_code}) SET cq += row.props", questions, dry_run)
        stats["constitution_question_edges"] = write_batches(
            driver,
            """
UNWIND $rows AS row
MERGE (cq:ConstitutionQuestion {question_code: row.question_code})
MERGE (ct:ConstitutionType {constitution_type_name: row.constitution_type_name})
MERGE (cq)-[r:ASSESSES_CONSTITUTION]->(ct)
SET r.source = 'GB/T 46939-2025'
""",
            constitution_edges,
            dry_run,
        )

        formulas, formula_edges, role_edges = build_formulas(data_root, limit)
        stats["formulas"] = write_batches(driver, "UNWIND $rows AS row MERGE (f:Formula {formula_name: row.formula_name}) SET f += row.props", formulas, dry_run)
        stats["formula_in_formula_edges"] = write_batches(
            driver,
            """
UNWIND $rows AS row
MERGE (h:Herb {herb_name: row.herb_name})
ON CREATE SET h.food_homology = '待核验'
MERGE (f:Formula {formula_name: row.formula_name})
MERGE (h)-[r:IN_FORMULA]->(f)
SET r.role = row.role, r.dosage = row.dosage, r.source = '0524_formula_import'
""",
            formula_edges,
            dry_run,
        )
        for rel_type, rows in role_edges.items():
            stats[f"formula_{rel_type.lower()}_edges"] = write_batches(
                driver,
                f"""
UNWIND $rows AS row
MERGE (f:Formula {{formula_name: row.formula_name}})
MERGE (h:Herb {{herb_name: row.herb_name}})
ON CREATE SET h.food_homology = '待核验'
MERGE (f)-[r:{rel_type}]->(h)
SET r.source = '0524_formula_import'
""",
                rows,
                dry_run,
            )

        replacements = build_replacements(data_root, limit)
        stats["replacement_edges"] = write_batches(
            driver,
            """
UNWIND $rows AS row
MERGE (h:Herb {herb_name: row.source_herb})
ON CREATE SET h.food_homology = '否'
MERGE (t:Herb {herb_name: row.target_herb})
ON CREATE SET t.food_homology = CASE WHEN row.candidate_source CONTAINS '药食同源' THEN '是' ELSE '待核验' END
MERGE (h)-[r:CAN_REPLACE {model: 'replacement_0524', candidate_source: row.candidate_source}]->(t)
SET r += row.props
""",
            replacements,
            dry_run,
        )
        return {"dry_run": dry_run, "stats": dict(stats)}
    finally:
        driver.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Incrementally import the latest agent project data into Neo4j.")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows per sheet for quick checks.")
    parser.add_argument("--neo4j-uri", default=URI)
    parser.add_argument("--neo4j-username", default=USER)
    parser.add_argument("--neo4j-password", default=PASSWORD)
    args = parser.parse_args()
    result = import_all(args.data_root, args.dry_run, args.limit, args.neo4j_uri, args.neo4j_username, args.neo4j_password)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
