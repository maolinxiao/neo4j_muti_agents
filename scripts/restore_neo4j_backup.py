"""Restore a Neo4j graph from JSON backup created by import_agent_kg_0604.py.

The backup format stores nodes with elementId, labels, props and relationships
with start/end elementId references. Restoration rebuilds nodes by business keys
and recreates relationships.

Examples:
    python scripts/restore_neo4j_backup.py --backup neo4j_backups/neo4j_backup_before_0604_rebuild_20260624_212411.json
    python scripts/restore_neo4j_backup.py --backup neo4j_backups/latest.json --yes
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

BACKEND_VENDOR = Path(__file__).resolve().parents[1] / "backend" / "_vendor"
if BACKEND_VENDOR.exists():
    sys.path.insert(0, str(BACKEND_VENDOR))

from neo4j import GraphDatabase

DEFAULT_NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
DEFAULT_NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
DEFAULT_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

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
    "Compound": "compound_name",
}


def primary_label(labels: list[str]) -> str | None:
    for label in labels:
        if label in NODE_KEYS:
            return label
    return labels[0] if labels else None


def load_backup(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "nodes" not in payload or "relationships" not in payload:
        raise ValueError(f"Invalid backup format: {path}")
    return payload


def clear_graph(driver) -> None:
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")


def restore_nodes(
    driver, nodes: list[dict[str, Any]], batch_size: int = 500
) -> tuple[Counter[str], dict[str, tuple[str, str]]]:
    stats: Counter[str] = Counter()
    grouped: dict[str, list[dict[str, Any]]] = {}
    id_map: dict[str, tuple[str, str]] = {}

    for node in nodes:
        labels = node.get("labels") or []
        label = primary_label(labels)
        if not label or label not in NODE_KEYS:
            continue
        key_field = NODE_KEYS[label]
        props = dict(node.get("props") or {})
        key_value = props.get(key_field)
        if not key_value:
            continue
        grouped.setdefault(label, []).append({"key": key_value, "props": props})
        id_map[node["element_id"]] = (label, str(key_value))

    with driver.session() as session:
        for label, rows in grouped.items():
            key_field = NODE_KEYS[label]
            query = f"UNWIND $rows AS row MERGE (n:{label} {{{key_field}: row.key}}) SET n += row.props"
            for start in range(0, len(rows), batch_size):
                session.run(query, {"rows": rows[start : start + batch_size]})
            stats[label] += len(rows)
    return stats, id_map


def restore_relationships(
    driver,
    relationships: list[dict[str, Any]],
    id_map: dict[str, tuple[str, str]],
    batch_size: int = 500,
) -> Counter[str]:
    stats: Counter[str] = Counter()
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = {}

    for rel in relationships:
        start = id_map.get(rel.get("start"))
        end = id_map.get(rel.get("end"))
        rel_type = rel.get("type")
        if not start or not end or not rel_type:
            continue
        start_label, start_key = start
        end_label, end_key = end
        if start_label not in NODE_KEYS or end_label not in NODE_KEYS:
            continue
        identity = (start_label, NODE_KEYS[start_label], rel_type, end_label, NODE_KEYS[end_label])
        grouped.setdefault(identity, []).append(
            {"start": start_key, "end": end_key, "props": rel.get("props") or {}}
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


def run_restore(args: argparse.Namespace) -> dict[str, Any]:
    backup_path = Path(args.backup)
    payload = load_backup(backup_path)
    driver = GraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_username, args.neo4j_password))
    try:
        if not args.skip_clear:
            clear_graph(driver)
        node_stats, id_map = restore_nodes(driver, payload["nodes"], batch_size=args.batch_size)
        rel_stats = restore_relationships(
            driver,
            payload["relationships"],
            id_map,
            batch_size=args.batch_size,
        )
        return {
            "backup": str(backup_path),
            "mapped_nodes": sum(node_stats.values()),
            "mapped_relationships": sum(rel_stats.values()),
            "nodes": dict(sorted(node_stats.items())),
            "relationships": dict(sorted(rel_stats.items())),
            "unmapped_nodes": len(payload["nodes"]) - sum(node_stats.values()),
            "unmapped_relationships": len(payload["relationships"]) - sum(rel_stats.values()),
        }
    finally:
        driver.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore Neo4j graph from JSON backup.")
    parser.add_argument("--backup", type=Path, required=True, help="Path to JSON backup file.")
    parser.add_argument("--neo4j-uri", default=DEFAULT_NEO4J_URI)
    parser.add_argument("--neo4j-username", default=DEFAULT_NEO4J_USERNAME)
    parser.add_argument("--neo4j-password", default=DEFAULT_NEO4J_PASSWORD)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--skip-clear", action="store_true", help="Do not clear graph before restore.")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.backup.exists():
        raise SystemExit(f"Backup not found: {args.backup}")
    if not args.yes and not args.skip_clear:
        answer = input(f"This will DELETE all nodes in {args.neo4j_uri} and restore from {args.backup}. Continue? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            raise SystemExit("Cancelled.")
    result = run_restore(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
