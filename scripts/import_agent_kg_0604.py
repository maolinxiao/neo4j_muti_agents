# -*- coding: utf-8 -*-
"""Rebuild the 2026-06-04 agent knowledge graph in Neo4j.

The 0604 graph uses KB1-KB8 as the source of truth, plus the current 0512
consumer/persona workbooks under the same data root. It intentionally does not
import the old Compound / ingredient network.

可复用的解析/写入内核自 2026-10-12 起位于 `backend/app/services/kg_import_core.py`
（管理端「数据导入」功能共用同一套实现）。本脚本只保留 CLI、JSON 备份与清库等
破坏性操作，并把内核的全部公开名字再导出，原有 `from import_agent_kg_0604 import ...`
的调用点不受影响。

Examples:
    python scripts/import_agent_kg_0604.py --dry-run
    python scripts/import_agent_kg_0604.py --clear
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_VENDOR = Path(__file__).resolve().parents[1] / "backend" / "_vendor"
if BACKEND_VENDOR.exists():
    sys.path.insert(0, str(BACKEND_VENDOR))

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from neo4j import GraphDatabase  # noqa: E402

from app.services import kg_import_core as _core  # noqa: E402

# 再导出内核的全部公开名字（GraphBuild / build_kb* / create_constraints / write_* / NODE_KEYS ...）
globals().update({name: value for name, value in vars(_core).items() if not name.startswith("_")})

DEFAULT_DATA_ROOT = Path(r"D:\工作\多智能体-宋\最新数据\6-4\药食同源agent项目")
DEFAULT_NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
DEFAULT_NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
DEFAULT_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")


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
