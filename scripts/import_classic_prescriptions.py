import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

BACKEND_VENDOR = Path(__file__).resolve().parents[1] / "backend" / "_vendor"
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if BACKEND_VENDOR.exists():
    sys.path.insert(0, str(BACKEND_VENDOR))
if BACKEND_DIR.exists():
    sys.path.insert(0, str(BACKEND_DIR))

from import_neo4j_kg import clean_text, slugify, read_sheet_rows


def prescription_key(name: str) -> str:
    return f"prescription:{slugify(name)}"


def split_herbs(text: str) -> list[str]:
    if not text:
        return []
    parts = re.split(r"[、，,；;·\s]+", text)
    return [p.strip() for p in parts if p.strip()]


ROLE_COLUMNS = [
    ("monarch_herb", "君药"),
    ("minister_herb", "臣药"),
    ("assistant_herb", "佐药"),
    ("guide_herb", "使药"),
]


def build_prescriptions(xlsx_path: str) -> list[dict[str, Any]]:
    rows = list(read_sheet_rows(Path(xlsx_path)))
    prescriptions = []
    for row in rows:
        name = clean_text(row.get("prescription_name"))
        if not name:
            continue
        herb_roles: list[dict[str, str]] = []
        for col, role in ROLE_COLUMNS:
            raw = clean_text(row.get(col))
            if not raw:
                continue
            for herb_name in split_herbs(raw):
                herb_roles.append({"herb_name": herb_name, "role": role})
        all_ingredients = split_herbs(clean_text(row.get("ingredients")) or "")
        prescriptions.append({
            "key": prescription_key(name),
            "name": name,
            "prescription_id": clean_text(row.get("id")),
            "source": clean_text(row.get("source")),
            "efficacy": clean_text(row.get("efficacy")),
            "ratio": clean_text(row.get("ratio")),
            "crowd": clean_text(row.get("crowd")),
            "taboo": clean_text(row.get("taboo")),
            "herb_roles": herb_roles,
            "all_ingredients": all_ingredients,
        })
    return prescriptions


def import_to_neo4j(prescriptions: list[dict[str, Any]], uri: str, username: str, password: str, batch_size: int = 100) -> dict[str, int]:
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(uri, auth=(username, password))
    stats = {"prescriptions": 0, "herb_roles_matched": 0, "herb_roles_created": 0, "herb_roles_skipped": 0}

    try:
        with driver.session() as session:
            session.run(
                "CREATE CONSTRAINT prescription_key IF NOT EXISTS "
                "FOR (n:ClassicPrescription) REQUIRE n.key IS UNIQUE"
            )

            for p in prescriptions:
                session.run(
                    """
UNWIND $rows AS row
MERGE (n:Entity {key: row.key})
SET n:ClassicPrescription
SET n += row.props
""",
                    {"rows": [{"key": p["key"], "props": {
                        "name": p["name"],
                        "prescription_id": p["prescription_id"],
                        "source": p["source"],
                        "efficacy": p["efficacy"],
                        "ratio": p["ratio"],
                        "crowd": p["crowd"],
                        "taboo": p["taboo"],
                        "ingredients": p["all_ingredients"],
                    }}]},
                )
                stats["prescriptions"] += 1

                for hr in p["herb_roles"]:
                    herb_name = hr["herb_name"]
                    role = hr["role"]
                    herb_key_val = f"herb:{slugify(herb_name)}"

                    result = session.run(
                        """
MATCH (h:Entity {key: $herb_key})
RETURN labels(h) AS labels, h.name AS name LIMIT 1
""",
                        {"herb_key": herb_key_val},
                    )
                    existing = result.single()

                    if existing is None:
                        session.run(
                            """
MERGE (h:Entity {key: $herb_key})
SET h:Herb
SET h.name = coalesce(h.name, $name)
""",
                            {"herb_key": herb_key_val, "name": herb_name},
                        )
                        stats["herb_roles_created"] += 1
                    else:
                        stats["herb_roles_matched"] += 1

                    session.run(
                        """
MATCH (p:Entity {key: $pres_key})
MATCH (h:Entity {key: $herb_key})
MERGE (p)-[r:CONTAINS_HERB]->(h)
SET r.role = $role
""",
                        {"pres_key": p["key"], "herb_key": herb_key_val, "role": role},
                    )

        return stats
    finally:
        driver.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import 100 classic prescriptions into Neo4j knowledge graph.")
    parser.add_argument("--xlsx", type=str, default=r"D:\工作\多智能体-宋\100经典名方-处理过.xlsx")
    parser.add_argument("--neo4j-uri", default="neo4j://localhost:7687")
    parser.add_argument("--neo4j-username", default="neo4j")
    parser.add_argument("--neo4j-password", default="3217858658")
    args = parser.parse_args()

    print("Reading prescriptions from Excel...")
    prescriptions = build_prescriptions(args.xlsx)
    print(f"  Total prescriptions: {len(prescriptions)}")

    total_herb_roles = sum(len(p["herb_roles"]) for p in prescriptions)
    print(f"  Total herb-role entries: {total_herb_roles}")

    print("\nImporting to Neo4j...")
    stats = import_to_neo4j(prescriptions, args.neo4j_uri, args.neo4j_username, args.neo4j_password)
    print(f"\nImport complete:")
    print(f"  Prescriptions created: {stats['prescriptions']}")
    print(f"  Herbs matched (existed): {stats['herb_roles_matched']}")
    print(f"  Herbs created (new): {stats['herb_roles_created']}")
    print(f"  Herb roles skipped: {stats['herb_roles_skipped']}")
    print(json.dumps({"stats": stats}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
