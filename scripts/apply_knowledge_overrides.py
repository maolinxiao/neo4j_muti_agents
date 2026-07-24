"""Apply curated regulatory knowledge overrides without clearing Neo4j."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from neo4j import GraphDatabase


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from import_agent_kg_0604 import (  # noqa: E402
    DEFAULT_REGULATORY_OVERRIDES_PATH,
    GraphBuild,
    apply_regulatory_overrides,
    create_constraints,
    write_edges,
    write_nodes,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply machine-readable regulatory knowledge overrides incrementally."
    )
    parser.add_argument(
        "--overrides-path",
        type=Path,
        default=DEFAULT_REGULATORY_OVERRIDES_PATH,
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--neo4j-uri", default=settings.neo4j_uri)
    parser.add_argument("--neo4j-username", default=settings.neo4j_username)
    parser.add_argument("--neo4j-password", default=settings.neo4j_password)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    graph = GraphBuild()
    apply_regulatory_overrides(graph, args.overrides_path)
    result = {
        "dry_run": args.dry_run,
        "overrides_path": str(args.overrides_path),
        "planned": graph.stats(),
    }
    if not args.dry_run:
        driver = GraphDatabase.driver(
            args.neo4j_uri,
            auth=(args.neo4j_username, args.neo4j_password),
        )
        try:
            create_constraints(driver)
            result["nodes"] = dict(write_nodes(driver, graph))
            result["relationships"] = dict(write_edges(driver, graph))
        finally:
            driver.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
