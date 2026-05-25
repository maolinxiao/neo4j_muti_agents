"""Import the latest v3 knowledge graph (0508汇总) into Neo4j.

Usage:
    python scripts/import_neo4j_graph_v3.py
"""

from neo4j import GraphDatabase
import pandas as pd
import os
import sys

URI = "neo4j://localhost:7687"
USER = "neo4j"
PASSWORD = "3217858658"

CSV_DIR = r"D:\工作\多智能体-宋\最新数据\0508汇总\neo4j_graph_v3"
CONSUMER_SUBSTITUTE_CSV = r"D:\工作\多智能体-宋\最新数据\0508汇总\consumer_aware_substitute_results.csv"

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))


def run_query(query, params=None):
    with driver.session() as session:
        session.run(query, params or {})


def read_csv(name):
    path = os.path.join(CSV_DIR, name)
    if not os.path.exists(path):
        print(f"File not found, skip: {name}")
        return pd.DataFrame()
    return pd.read_csv(path)


def safe_value(x):
    if pd.isna(x):
        return None
    return x


def safe_float(x):
    if pd.isna(x):
        return None
    try:
        return float(x)
    except Exception:
        return None


# =========================
# Clear old graph
# =========================

print("Clearing old graph...")
run_query("MATCH (n) DETACH DELETE n")
print("Old graph cleared.")

# =========================
# Create constraints
# =========================

print("Creating constraints...")
constraints = [
    "CREATE CONSTRAINT herb_name_unique IF NOT EXISTS FOR (h:Herb) REQUIRE h.herb_name IS UNIQUE",
    "CREATE CONSTRAINT compound_smiles_unique IF NOT EXISTS FOR (c:Compound) REQUIRE c.canonical_smiles IS UNIQUE",
    "CREATE CONSTRAINT effect_name_unique IF NOT EXISTS FOR (e:Effect) REQUIRE e.effect_name IS UNIQUE",
    "CREATE CONSTRAINT flavor_name_unique IF NOT EXISTS FOR (f:Flavor) REQUIRE f.flavor_name IS UNIQUE",
    "CREATE CONSTRAINT formula_name_unique IF NOT EXISTS FOR (f:Formula) REQUIRE f.formula_name IS UNIQUE",
    "CREATE CONSTRAINT effect_category_unique IF NOT EXISTS FOR (e:EffectCategory) REQUIRE e.effect_category_name IS UNIQUE",
    "CREATE CONSTRAINT symptom_unique IF NOT EXISTS FOR (s:Symptom) REQUIRE s.symptom_name IS UNIQUE",
    "CREATE CONSTRAINT taboo_unique IF NOT EXISTS FOR (t:Taboo) REQUIRE t.taboo_name IS UNIQUE",
    "CREATE CONSTRAINT source_unique IF NOT EXISTS FOR (s:Source) REQUIRE s.source_name IS UNIQUE",
    "CREATE CONSTRAINT nature_flavor_unique IF NOT EXISTS FOR (n:NatureFlavor) REQUIRE n.nature_flavor_name IS UNIQUE",
    "CREATE CONSTRAINT meridian_unique IF NOT EXISTS FOR (m:Meridian) REQUIRE m.meridian_name IS UNIQUE",
]

for q in constraints:
    run_query(q)
print("Constraints created.")


# =========================
# Node import
# =========================

print("Importing Herb nodes...")
herb = read_csv("herb_nodes.csv")
for _, row in herb.iterrows():
    run_query(
        """
        MERGE (h:Herb {herb_name:$herb_name})
        SET h.food_homology=$food_homology
        """,
        {
            "herb_name": row["herb_name"],
            "food_homology": safe_value(row.get("food_homology"))
        }
    )
print(f"  Imported {len(herb)} Herb nodes.")


print("Importing Compound nodes...")
compound = read_csv("compound_nodes.csv")
compound = compound.dropna(subset=["canonical_smiles"])
for _, row in compound.iterrows():
    run_query(
        """
        MERGE (c:Compound {canonical_smiles:$canonical_smiles})
        SET c.compound_name=$compound_name,
            c.pubchem_cid=$pubchem_cid,
            c.mw=$mw,
            c.logp=$logp,
            c.tpsa=$tpsa,
            c.ob=$ob,
            c.dl=$dl,
            c.ecfp_bits=$ecfp_bits
        """,
        {
            "canonical_smiles": row["canonical_smiles"],
            "compound_name": safe_value(row.get("compound_name")),
            "pubchem_cid": None if pd.isna(row.get("pubchem_cid")) else str(row.get("pubchem_cid")),
            "mw": safe_float(row.get("mw")),
            "logp": safe_float(row.get("logp")),
            "tpsa": safe_float(row.get("tpsa")),
            "ob": safe_float(row.get("ob")),
            "dl": safe_float(row.get("dl")),
            "ecfp_bits": safe_value(row.get("ecfp_bits"))
        }
    )
print(f"  Imported {len(compound)} Compound nodes.")


print("Importing Effect nodes...")
effect = read_csv("effect_nodes.csv")
for _, row in effect.iterrows():
    run_query(
        """
        MERGE (e:Effect {effect_name:$effect_name})
        """,
        {"effect_name": row["effect_name"]}
    )
print(f"  Imported {len(effect)} Effect nodes.")


print("Importing Flavor nodes...")
flavor = read_csv("flavor_nodes.csv")
for _, row in flavor.iterrows():
    run_query(
        """
        MERGE (f:Flavor {flavor_name:$flavor_name})
        """,
        {"flavor_name": row["flavor_name"]}
    )
print(f"  Imported {len(flavor)} Flavor nodes.")


print("Importing Formula nodes...")
formula = read_csv("formula_nodes.csv")
for _, row in formula.iterrows():
    run_query(
        """
        MERGE (f:Formula {formula_name:$formula_name})
        SET f.source=$source,
            f.efficacy=$efficacy,
            f.monarch_herb=$monarch_herb,
            f.minister_herb=$minister_herb,
            f.assistant_herb=$assistant_herb,
            f.guide_herb=$guide_herb,
            f.ingredients=$ingredients,
            f.ratio=$ratio,
            f.crowd=$crowd,
            f.taboo=$taboo
        """,
        {
            "formula_name": row["prescription_name"] if "prescription_name" in row else row.get("formula_name"),
            "source": safe_value(row.get("source")),
            "efficacy": safe_value(row.get("efficacy")),
            "monarch_herb": safe_value(row.get("monarch_herb")),
            "minister_herb": safe_value(row.get("minister_herb")),
            "assistant_herb": safe_value(row.get("assistant_herb")),
            "guide_herb": safe_value(row.get("guide_herb")),
            "ingredients": safe_value(row.get("ingredients")),
            "ratio": safe_value(row.get("ratio")),
            "crowd": safe_value(row.get("crowd")),
            "taboo": safe_value(row.get("taboo")),
        }
    )
print(f"  Imported {len(formula)} Formula nodes.")


def import_simple_node(file, label, key):
    df = read_csv(file)
    print(f"Importing {label} nodes ({len(df)} rows)...")
    for _, row in df.iterrows():
        run_query(
            f"""
            MERGE (n:{label} {{{key}:$name}})
            """,
            {"name": row[key]}
        )


import_simple_node("effect_category_nodes.csv", "EffectCategory", "effect_category_name")
import_simple_node("symptom_nodes.csv", "Symptom", "symptom_name")
import_simple_node("taboo_nodes.csv", "Taboo", "taboo_name")
import_simple_node("source_nodes.csv", "Source", "source_name")
import_simple_node("nature_flavor_nodes.csv", "NatureFlavor", "nature_flavor_name")
import_simple_node("meridian_nodes.csv", "Meridian", "meridian_name")


# =========================
# Basic relationship import
# =========================

mol_map = compound[["compound_name", "canonical_smiles"]].drop_duplicates()


print("Importing Herb -> Compound (CONTAINS)...")
edge = read_csv("herb_compound_edges.csv")
edge = edge.merge(mol_map, on="compound_name", how="left")
edge = edge.dropna(subset=["canonical_smiles"])
for _, row in edge.iterrows():
    run_query(
        """
        MATCH (h:Herb {herb_name:$herb_name})
        MATCH (c:Compound {canonical_smiles:$canonical_smiles})
        MERGE (h)-[r:CONTAINS]->(c)
        SET r.ob=$ob,
            r.dl=$dl
        """,
        {
            "herb_name": row["herb_name"],
            "canonical_smiles": row["canonical_smiles"],
            "ob": safe_float(row.get("ob")),
            "dl": safe_float(row.get("dl")),
        }
    )
print(f"  Imported {len(edge)} Herb->Compound edges.")


print("Importing Herb -> Effect (HAS_EFFECT)...")
edge = read_csv("herb_effect_edges.csv")
for _, row in edge.iterrows():
    run_query(
        """
        MATCH (h:Herb {herb_name:$herb_name})
        MATCH (e:Effect {effect_name:$effect_name})
        MERGE (h)-[:HAS_EFFECT]->(e)
        """,
        {
            "herb_name": row["herb_name"],
            "effect_name": row["effect_name"]
        }
    )
print(f"  Imported {len(edge)} Herb->Effect edges.")


print("Importing Herb -> Flavor (HAS_FLAVOR)...")
edge = read_csv("herb_flavor_edges.csv")
for _, row in edge.iterrows():
    run_query(
        """
        MATCH (h:Herb {herb_name:$herb_name})
        MATCH (f:Flavor {flavor_name:$flavor_name})
        MERGE (h)-[r:HAS_FLAVOR]->(f)
        SET r.intensity=$intensity
        """,
        {
            "herb_name": row["herb_name"],
            "flavor_name": row["flavor_name"],
            "intensity": safe_float(row.get("intensity"))
        }
    )
print(f"  Imported {len(edge)} Herb->Flavor edges.")


print("Importing Compound -> Effect (HAS_COMPOUND_EFFECT)...")
edge = read_csv("compound_effect_edges.csv")
edge = edge.merge(mol_map, on="compound_name", how="left")
edge = edge.dropna(subset=["canonical_smiles"])
for _, row in edge.iterrows():
    run_query(
        """
        MATCH (c:Compound {canonical_smiles:$canonical_smiles})
        MATCH (e:Effect {effect_name:$effect_name})
        MERGE (c)-[:HAS_COMPOUND_EFFECT]->(e)
        """,
        {
            "canonical_smiles": row["canonical_smiles"],
            "effect_name": row["effect_name"]
        }
    )
print(f"  Imported {len(edge)} Compound->Effect edges.")


print("Importing Compound -> Flavor (PRODUCES_FLAVOR)...")
edge = read_csv("compound_flavor_edges.csv")
edge = edge.merge(mol_map, on="compound_name", how="left")
edge = edge.dropna(subset=["canonical_smiles"])
for _, row in edge.iterrows():
    run_query(
        """
        MATCH (c:Compound {canonical_smiles:$canonical_smiles})
        MATCH (f:Flavor {flavor_name:$flavor_name})
        MERGE (c)-[r:PRODUCES_FLAVOR]->(f)
        SET r.intensity=$intensity
        """,
        {
            "canonical_smiles": row["canonical_smiles"],
            "flavor_name": row["flavor_name"],
            "intensity": safe_float(row.get("intensity"))
        }
    )
print(f"  Imported {len(edge)} Compound->Flavor edges.")


print("Importing Herb -> Formula (IN_FORMULA)...")
edge = read_csv("herb_formula_edges.csv")
for _, row in edge.iterrows():
    formula_name = row["prescription_name"] if "prescription_name" in row else row.get("formula_name")
    run_query(
        """
        MATCH (h:Herb {herb_name:$herb_name})
        MATCH (f:Formula {formula_name:$formula_name})
        MERGE (h)-[r:IN_FORMULA]->(f)
        SET r.role=$role,
            r.dosage=$dosage
        """,
        {
            "herb_name": row["herb_name"],
            "formula_name": formula_name,
            "role": safe_value(row.get("role")),
            "dosage": safe_value(row.get("dosage"))
        }
    )
print(f"  Imported {len(edge)} Herb->Formula edges.")


# =========================
# v3 new relationships
# =========================

def import_herb_relation(file, target_label, target_key, rel_type):
    df = read_csv(file)
    print(f"Importing Herb -[{rel_type}]-> {target_label} ({len(df)} rows)...")
    for _, row in df.iterrows():
        run_query(
            f"""
            MATCH (h:Herb {{herb_name:$herb_name}})
            MATCH (t:{target_label} {{{target_key}:$target_name}})
            MERGE (h)-[:{rel_type}]->(t)
            """,
            {
                "herb_name": row["herb_name"],
                "target_name": row[target_key]
            }
        )


import_herb_relation("herb_effect_category_edges.csv", "EffectCategory", "effect_category_name", "BELONGS_TO_EFFECT_CATEGORY")
import_herb_relation("herb_symptom_edges.csv", "Symptom", "symptom_name", "TREATS")
import_herb_relation("herb_taboo_edges.csv", "Taboo", "taboo_name", "HAS_TABOO")
import_herb_relation("herb_nature_flavor_edges.csv", "NatureFlavor", "nature_flavor_name", "HAS_NATURE_FLAVOR")
import_herb_relation("herb_meridian_edges.csv", "Meridian", "meridian_name", "ENTERS_MERIDIAN")


def import_formula_relation(file, target_label, target_key, rel_type):
    df = read_csv(file)
    print(f"Importing Formula -[{rel_type}]-> {target_label} ({len(df)} rows)...")
    for _, row in df.iterrows():
        run_query(
            f"""
            MATCH (f:Formula {{formula_name:$formula_name}})
            MATCH (t:{target_label} {{{target_key}:$target_name}})
            MERGE (f)-[:{rel_type}]->(t)
            """,
            {
                "formula_name": row["formula_name"],
                "target_name": row[target_key]
            }
        )


import_formula_relation("formula_source_edges.csv", "Source", "source_name", "FROM_SOURCE")
import_formula_relation("formula_effect_edges.csv", "Effect", "effect_name", "HAS_EFFECT")
import_formula_relation("formula_symptom_edges.csv", "Symptom", "symptom_name", "TARGETS_SYMPTOM")
import_formula_relation("formula_taboo_edges.csv", "Taboo", "taboo_name", "HAS_TABOO")


print("Importing Formula -> Herb (MONARCH/MINISTER/ASSISTANT/GUIDE_HERB)...")
edge = read_csv("formula_role_edges.csv")
allowed_roles = {"MONARCH_HERB", "MINISTER_HERB", "ASSISTANT_HERB", "GUIDE_HERB"}
for _, row in edge.iterrows():
    rel_type = row["relation_type"]
    if rel_type not in allowed_roles:
        continue
    run_query(
        f"""
        MATCH (f:Formula {{formula_name:$formula_name}})
        MATCH (h:Herb {{herb_name:$herb_name}})
        MERGE (f)-[:{rel_type}]->(h)
        """,
        {
            "formula_name": row["formula_name"],
            "herb_name": row["herb_name"]
        }
    )
print(f"  Imported {len(edge)} Formula->Herb role edges.")


# =========================
# Consumer-aware substitute results
# =========================

print("Importing consumer-aware substitute results (CAN_REPLACE)...")
if os.path.exists(CONSUMER_SUBSTITUTE_CSV):
    sub_df = pd.read_csv(CONSUMER_SUBSTITUTE_CSV)
    count = 0
    for _, row in sub_df.iterrows():
        source_herb = safe_value(row.get("source_herb"))
        target_herb = safe_value(row.get("candidate_food_homology_herb"))
        if not source_herb or not target_herb:
            continue
        run_query(
            """
            MATCH (h:Herb {herb_name:$source_herb})
            MATCH (t:Herb {herb_name:$target_herb})
            MERGE (h)-[r:CAN_REPLACE]->(t)
            SET r.model='consumer_aware',
                r.rank=$rank,
                r.final_score=$final_score,
                r.flavor_acceptance=$flavor_acceptance,
                r.effect_similarity=$effect_similarity,
                r.embedding_similarity=$embedding_similarity,
                r.structure_similarity=$structure_similarity,
                r.formula_context_similarity=$formula_context_similarity,
                r.source_type='consumer_aware'
            """,
            {
                "source_herb": source_herb,
                "target_herb": target_herb,
                "rank": int(row.get("rank", 0)),
                "final_score": safe_float(row.get("final_score")),
                "flavor_acceptance": safe_float(row.get("flavor_acceptance")),
                "effect_similarity": safe_float(row.get("effect_similarity")),
                "embedding_similarity": safe_float(row.get("embedding_similarity")),
                "structure_similarity": safe_float(row.get("structure_similarity")),
                "formula_context_similarity": safe_float(row.get("formula_context_similarity")),
            }
        )
        count += 1
    print(f"  Imported {count} CAN_REPLACE edges.")
else:
    print(f"  Consumer substitute file not found: {CONSUMER_SUBSTITUTE_CSV}")


# =========================
# Statistics
# =========================

print("\nNode statistics:")
with driver.session() as session:
    result = session.run(
        """
        MATCH (n)
        RETURN labels(n)[0] AS label, count(n) AS count
        ORDER BY count DESC
        """
    )
    for r in result:
        print(f"  {r['label']}: {r['count']}")

print("\nRelationship statistics:")
with driver.session() as session:
    result = session.run(
        """
        MATCH ()-[r]->()
        RETURN type(r) AS relation, count(r) AS count
        ORDER BY count DESC
        """
    )
    for r in result:
        print(f"  {r['relation']}: {r['count']}")

print("\nNeo4j v3 knowledge graph import complete!")
driver.close()
