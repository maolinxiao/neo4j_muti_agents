import json
import re
from collections import Counter
from typing import Any

from neo4j import GraphDatabase

from app.core.config import settings


class Neo4jRepository:
    def __init__(self) -> None:
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )

    def close(self) -> None:
        self.driver.close()

    def health_check(self) -> bool:
        with self.driver.session() as session:
            return bool(session.run("RETURN 1 AS ok").single())

    def label_counts(self) -> list[dict[str, Any]]:
        query = """
MATCH (n)
UNWIND labels(n) AS label
RETURN label, count(*) AS total
ORDER BY total DESC
LIMIT 20
"""
        with self.driver.session() as session:
            records = session.run(query)
            return [{"label": record["label"], "total": record["total"]} for record in records]

    def graph_metrics(self) -> dict[str, Any]:
        query = """
CALL () {
    MATCH (h:Herb)
    RETURN
        count(h) AS herb_count,
        count(CASE WHEN h.food_homology = '是' THEN 1 END) AS food_homology_count
}
CALL () {
    MATCH (c:Compound)
    RETURN count(c) AS compound_count
}
CALL () {
    MATCH (e:Effect)
    RETURN count(e) AS effect_count
}
CALL () {
    MATCH (ec:EffectCategory)
    RETURN count(ec) AS effect_category_count
}
CALL () {
    MATCH (f:Formula)
    RETURN count(f) AS formula_count
}
CALL () {
    MATCH (p:Product)
    RETURN count(p) AS product_count
}
CALL () {
    MATCH (cp:ConsumerProfile)
    RETURN count(cp) AS consumer_profile_count
}
CALL () {
    MATCH (ct:ConstitutionType)
    RETURN count(ct) AS constitution_type_count
}
CALL () {
    MATCH ()-[r:CAN_REPLACE]->()
    RETURN count(r) AS replacement_edge_count
}
RETURN herb_count, food_homology_count, compound_count, effect_count, effect_category_count, formula_count,
       product_count, consumer_profile_count, constitution_type_count, replacement_edge_count
"""
        with self.driver.session() as session:
            record = session.run(query).single()
            return dict(record) if record else {}

    def search_entities(self, keyword: str, limit: int = 10) -> list[dict[str, Any]]:
        normalized = self._normalize_keyword(keyword)
        raw = keyword.strip()
        query = """
MATCH (h:Herb)
WHERE h.herb_name CONTAINS $raw
RETURN h.herb_name AS id, h.herb_name AS name, 'Herb' AS entity_type, properties(h) AS props,
       CASE WHEN h.herb_name = $raw THEN 130 WHEN h.herb_name CONTAINS $raw THEN 90 ELSE 50 END AS score,
       [] AS aliases
UNION ALL
MATCH (c:Compound)
WHERE coalesce(c.compound_name, '') CONTAINS $raw
   OR c.canonical_smiles CONTAINS $raw
RETURN c.canonical_smiles AS id, coalesce(c.compound_name, c.canonical_smiles) AS name, 'Compound' AS entity_type, properties(c) AS props,
       CASE WHEN c.compound_name = $raw THEN 130 WHEN coalesce(c.compound_name, '') CONTAINS $raw THEN 90 ELSE 50 END AS score,
       [] AS aliases
UNION ALL
MATCH (e:Effect)
WHERE e.effect_name CONTAINS $raw
RETURN e.effect_name AS id, e.effect_name AS name, 'Effect' AS entity_type, properties(e) AS props,
       CASE WHEN e.effect_name = $raw THEN 130 WHEN e.effect_name CONTAINS $raw THEN 90 ELSE 50 END AS score,
       [] AS aliases
UNION ALL
MATCH (f:Flavor)
WHERE f.flavor_name CONTAINS $raw
RETURN f.flavor_name AS id, f.flavor_name AS name, 'Flavor' AS entity_type, properties(f) AS props,
       CASE WHEN f.flavor_name = $raw THEN 130 WHEN f.flavor_name CONTAINS $raw THEN 90 ELSE 50 END AS score,
       [] AS aliases
UNION ALL
MATCH (f:Formula)
WHERE f.formula_name CONTAINS $raw
   OR coalesce(f.efficacy, '') CONTAINS $raw
RETURN f.formula_name AS id, f.formula_name AS name, 'Formula' AS entity_type, properties(f) AS props,
       CASE WHEN f.formula_name = $raw THEN 130 WHEN f.formula_name CONTAINS $raw THEN 90 ELSE 50 END AS score,
       [] AS aliases
UNION ALL
MATCH (s:Symptom)
WHERE s.symptom_name CONTAINS $raw
RETURN s.symptom_name AS id, s.symptom_name AS name, 'Symptom' AS entity_type, properties(s) AS props,
       CASE WHEN s.symptom_name = $raw THEN 130 WHEN s.symptom_name CONTAINS $raw THEN 90 ELSE 50 END AS score,
       [] AS aliases
UNION ALL
MATCH (t:Taboo)
WHERE t.taboo_name CONTAINS $raw
RETURN t.taboo_name AS id, t.taboo_name AS name, 'Taboo' AS entity_type, properties(t) AS props,
       CASE WHEN t.taboo_name = $raw THEN 130 WHEN t.taboo_name CONTAINS $raw THEN 90 ELSE 50 END AS score,
       [] AS aliases
UNION ALL
MATCH (s:Source)
WHERE s.source_name CONTAINS $raw
RETURN s.source_name AS id, s.source_name AS name, 'Source' AS entity_type, properties(s) AS props,
       CASE WHEN s.source_name = $raw THEN 130 WHEN s.source_name CONTAINS $raw THEN 90 ELSE 50 END AS score,
       [] AS aliases
UNION ALL
MATCH (n:NatureFlavor)
WHERE n.nature_flavor_name CONTAINS $raw
RETURN n.nature_flavor_name AS id, n.nature_flavor_name AS name, 'NatureFlavor' AS entity_type, properties(n) AS props,
       CASE WHEN n.nature_flavor_name = $raw THEN 130 WHEN n.nature_flavor_name CONTAINS $raw THEN 90 ELSE 50 END AS score,
       [] AS aliases
UNION ALL
MATCH (m:Meridian)
WHERE m.meridian_name CONTAINS $raw
RETURN m.meridian_name AS id, m.meridian_name AS name, 'Meridian' AS entity_type, properties(m) AS props,
       CASE WHEN m.meridian_name = $raw THEN 130 WHEN m.meridian_name CONTAINS $raw THEN 90 ELSE 50 END AS score,
       [] AS aliases
UNION ALL
MATCH (ec:EffectCategory)
WHERE ec.effect_category_name CONTAINS $raw
RETURN ec.effect_category_name AS id, ec.effect_category_name AS name, 'EffectCategory' AS entity_type, properties(ec) AS props,
       CASE WHEN ec.effect_category_name = $raw THEN 130 WHEN ec.effect_category_name CONTAINS $raw THEN 90 ELSE 50 END AS score,
       [] AS aliases
UNION ALL
MATCH (p:Product)
WHERE coalesce(p.product_name, '') CONTAINS $raw
   OR coalesce(p.brand, '') CONTAINS $raw
   OR coalesce(p.claimed_effect, '') CONTAINS $raw
   OR coalesce(p.dosage_form, '') CONTAINS $raw
RETURN p.product_id AS id, coalesce(p.product_name, p.product_id) AS name, 'Product' AS entity_type, properties(p) AS props,
       CASE WHEN p.product_name = $raw THEN 130 WHEN coalesce(p.product_name, '') CONTAINS $raw THEN 90 ELSE 70 END AS score,
       [] AS aliases
UNION ALL
MATCH (cp:ConsumerProfile)
WHERE coalesce(cp.product_name, '') CONTAINS $raw
   OR coalesce(cp.crowd_type, '') CONTAINS $raw
   OR coalesce(cp.core_need, '') CONTAINS $raw
   OR coalesce(cp.agent_strategy, '') CONTAINS $raw
RETURN cp.profile_id AS id, coalesce(cp.product_name, cp.profile_id) AS name, 'ConsumerProfile' AS entity_type, properties(cp) AS props,
       CASE WHEN cp.profile_id = $raw THEN 130 WHEN coalesce(cp.product_name, '') CONTAINS $raw THEN 95 ELSE 80 END AS score,
       [] AS aliases
UNION ALL
MATCH (cs:ConsumerSegment)
WHERE coalesce(cs.crowd_tags, '') CONTAINS $raw
   OR coalesce(cs.scenario_tags, '') CONTAINS $raw
   OR coalesce(cs.effect_tags, '') CONTAINS $raw
RETURN cs.segment_key AS id, coalesce(cs.segment_label, cs.segment_key) AS name, 'ConsumerSegment' AS entity_type, properties(cs) AS props,
       CASE WHEN cs.segment_label = $raw THEN 130 ELSE 85 END AS score,
       [] AS aliases
UNION ALL
MATCH (ct:ConstitutionType)
WHERE ct.constitution_type_name CONTAINS $raw
RETURN ct.constitution_type_name AS id, ct.constitution_type_name AS name, 'ConstitutionType' AS entity_type, properties(ct) AS props,
       CASE WHEN ct.constitution_type_name = $raw THEN 130 WHEN ct.constitution_type_name CONTAINS $raw THEN 95 ELSE 80 END AS score,
       [] AS aliases
UNION ALL
MATCH (cq:ConstitutionQuestion)
WHERE coalesce(cq.question_text, '') CONTAINS $raw
RETURN cq.question_code AS id, coalesce(cq.question_text, cq.question_code) AS name, 'ConstitutionQuestion' AS entity_type, properties(cq) AS props,
       75 AS score,
       [] AS aliases
ORDER BY
    score DESC,
    CASE entity_type
        WHEN 'Herb' THEN 0
        WHEN 'Formula' THEN 1
        WHEN 'Product' THEN 2
        WHEN 'ConsumerProfile' THEN 3
        WHEN 'ConsumerSegment' THEN 4
        WHEN 'ConstitutionType' THEN 5
        WHEN 'Effect' THEN 6
        WHEN 'EffectCategory' THEN 7
        WHEN 'Compound' THEN 8
        WHEN 'Symptom' THEN 9
        WHEN 'Flavor' THEN 10
        WHEN 'NatureFlavor' THEN 11
        WHEN 'Meridian' THEN 12
        WHEN 'Taboo' THEN 13
        WHEN 'Source' THEN 14
        ELSE 20
    END ASC
LIMIT $limit
"""
        with self.driver.session() as session:
            rows = session.run(
                query,
                {"raw": raw, "compact_upper": normalized, "limit": limit},
            )
            return [dict(record) for record in rows]

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        query = """
CALL {
    MATCH (h:Herb {herb_name: $entity_id})
    RETURN h.herb_name AS id, 'Herb' AS entity_type, properties(h) AS props
}
UNION ALL
CALL {
    MATCH (c:Compound {canonical_smiles: $entity_id})
    RETURN c.canonical_smiles AS id, 'Compound' AS entity_type, properties(c) AS props
}
UNION ALL
CALL {
    MATCH (c:Compound {compound_name: $entity_id})
    RETURN c.canonical_smiles AS id, 'Compound' AS entity_type, properties(c) AS props
}
UNION ALL
CALL {
    MATCH (e:Effect {effect_name: $entity_id})
    RETURN e.effect_name AS id, 'Effect' AS entity_type, properties(e) AS props
}
UNION ALL
CALL {
    MATCH (f:Flavor {flavor_name: $entity_id})
    RETURN f.flavor_name AS id, 'Flavor' AS entity_type, properties(f) AS props
}
UNION ALL
CALL {
    MATCH (f:Formula {formula_name: $entity_id})
    RETURN f.formula_name AS id, 'Formula' AS entity_type, properties(f) AS props
}
UNION ALL
CALL {
    MATCH (s:Symptom {symptom_name: $entity_id})
    RETURN s.symptom_name AS id, 'Symptom' AS entity_type, properties(s) AS props
}
UNION ALL
CALL {
    MATCH (t:Taboo {taboo_name: $entity_id})
    RETURN t.taboo_name AS id, 'Taboo' AS entity_type, properties(t) AS props
}
UNION ALL
CALL {
    MATCH (s:Source {source_name: $entity_id})
    RETURN s.source_name AS id, 'Source' AS entity_type, properties(s) AS props
}
UNION ALL
CALL {
    MATCH (n:NatureFlavor {nature_flavor_name: $entity_id})
    RETURN n.nature_flavor_name AS id, 'NatureFlavor' AS entity_type, properties(n) AS props
}
UNION ALL
CALL {
    MATCH (m:Meridian {meridian_name: $entity_id})
    RETURN m.meridian_name AS id, 'Meridian' AS entity_type, properties(m) AS props
}
UNION ALL
CALL {
    MATCH (ec:EffectCategory {effect_category_name: $entity_id})
    RETURN ec.effect_category_name AS id, 'EffectCategory' AS entity_type, properties(ec) AS props
}
UNION ALL
CALL {
    MATCH (p:Product {product_id: $entity_id})
    RETURN p.product_id AS id, 'Product' AS entity_type, properties(p) AS props
}
UNION ALL
CALL {
    MATCH (cp:ConsumerProfile {profile_id: $entity_id})
    RETURN cp.profile_id AS id, 'ConsumerProfile' AS entity_type, properties(cp) AS props
}
UNION ALL
CALL {
    MATCH (cs:ConsumerSegment {segment_key: $entity_id})
    RETURN cs.segment_key AS id, 'ConsumerSegment' AS entity_type, properties(cs) AS props
}
UNION ALL
CALL {
    MATCH (ct:ConstitutionType {constitution_type_name: $entity_id})
    RETURN ct.constitution_type_name AS id, 'ConstitutionType' AS entity_type, properties(ct) AS props
}
UNION ALL
CALL {
    MATCH (cq:ConstitutionQuestion {question_code: $entity_id})
    RETURN cq.question_code AS id, 'ConstitutionQuestion' AS entity_type, properties(cq) AS props
}
RETURN id, entity_type, props, [] AS aliases
LIMIT 1
"""
        with self.driver.session() as session:
            record = session.run(query, {"entity_id": entity_id}).single()
            if record is None:
                return None
            item = dict(record)
            props = item.get("props", {})
            item["name"] = (
                props.get("compound_name")
                or props.get("herb_name")
                or props.get("effect_name")
                or props.get("formula_name")
                or props.get("product_name")
                or props.get("segment_label")
                or props.get("constitution_type_name")
                or props.get("question_text")
                or item["id"]
            )
            return item

    def search_food_homology_herbs(self, keyword: str, limit: int = 20) -> list[dict[str, Any]]:
        raw = keyword.strip()
        query = """
MATCH (h:Herb)
WHERE h.food_homology = '是'
WITH h, coalesce(toString(h.herb_name), '') AS name
WITH
    h,
    name,
    CASE
        WHEN name = $raw THEN 130
        WHEN name CONTAINS $raw THEN 90
        ELSE 50
    END AS score
WHERE score > 0
RETURN
    h.herb_name AS id,
    name AS name,
    'Herb' AS entity_type,
    properties(h) AS props,
    [] AS aliases,
    score
ORDER BY score DESC, name ASC
LIMIT $limit
"""
        with self.driver.session() as session:
            rows = session.run(query, {"raw": raw, "limit": limit})
            return [dict(record) for record in rows]

    def get_herb_by_name(self, herb_name: str) -> dict[str, Any] | None:
        query = """
MATCH (h:Herb)
WHERE h.herb_name = $name
RETURN
    h.herb_name AS id,
    h.herb_name AS name,
    'Herb' AS entity_type,
    properties(h) AS props,
    [] AS aliases
LIMIT 1
"""
        with self.driver.session() as session:
            record = session.run(query, {"name": herb_name.strip()}).single()
            return dict(record) if record else None

    def find_candidate_herbs_for_brief(self, search_terms: list[str], limit: int = 18) -> list[dict[str, Any]]:
        query = """
MATCH (h:Herb)
WHERE h.food_homology = '是'
OPTIONAL MATCH (h)-[:HAS_EFFECT]->(effect:Effect)
OPTIONAL MATCH (h)-[:TREATS]->(symptom:Symptom)
OPTIONAL MATCH (h)-[:HAS_NATURE_FLAVOR]->(nf:NatureFlavor)
OPTIONAL MATCH (h)-[:ENTERS_MERIDIAN]->(m:Meridian)
WITH h,
     collect(DISTINCT toString(effect.effect_name)) AS effects,
     collect(DISTINCT toString(symptom.symptom_name)) AS symptoms,
     collect(DISTINCT toString(nf.nature_flavor_name)) AS nature_flavors,
     collect(DISTINCT toString(m.meridian_name)) AS meridians
WITH
    h,
    effects,
    symptoms,
    nature_flavors,
    meridians,
    toLower(coalesce(toString(h.herb_name), '')) AS name,
    [term IN $terms | toLower(term)] AS lowered_terms
WITH
    h,
    effects,
    symptoms,
    nature_flavors,
    meridians,
    reduce(score = 0, term IN lowered_terms |
        score +
        CASE
            WHEN term = '' THEN 0
            WHEN name CONTAINS term THEN 5
            WHEN any(eff IN effects WHERE toLower(eff) CONTAINS term) THEN 6
            WHEN any(sym IN symptoms WHERE toLower(sym) CONTAINS term) THEN 4
            WHEN any(nf IN nature_flavors WHERE toLower(nf) CONTAINS term) THEN 3
            WHEN any(m IN meridians WHERE toLower(m) CONTAINS term) THEN 3
            ELSE 0
        END
    ) AS score
WHERE score > 0
RETURN
    h.herb_name AS id,
    h.herb_name AS name,
    'Herb' AS entity_type,
    properties(h) AS props,
    [] AS aliases,
    effects AS tags,
    nature_flavors,
    meridians,
    score
ORDER BY score DESC, name ASC
LIMIT $limit
"""
        fallback_query = """
MATCH (h:Herb)
WHERE h.food_homology = '是'
OPTIONAL MATCH (h)-[:HAS_EFFECT]->(effect:Effect)
WITH h, collect(DISTINCT toString(effect.effect_name)) AS tags
OPTIONAL MATCH (h)-[:CAN_REPLACE]->(target:Herb)
WITH h, tags, count(target) AS replacement_count
RETURN
    h.herb_name AS id,
    h.herb_name AS name,
    'Herb' AS entity_type,
    properties(h) AS props,
    [] AS aliases,
    tags,
    size(tags) + replacement_count AS score
ORDER BY replacement_count DESC, size(tags) DESC, name ASC
LIMIT $limit
"""
        with self.driver.session() as session:
            rows = session.run(query, {"terms": search_terms, "limit": limit})
            results = [dict(record) for record in rows]
            if results:
                return results
            rows = session.run(fallback_query, {"limit": limit})
            return [dict(record) for record in rows]

    def get_replacement_candidates(self, herb_name: str, limit: int = 5) -> list[dict[str, Any]]:
        query = """
MATCH (h:Herb {herb_name: $herb_name})-[r:CAN_REPLACE]->(target:Herb)
RETURN
    target.herb_name AS id,
    target.herb_name AS name,
    properties(target) AS props,
    r.model AS model,
    r.rank AS rank,
    r.final_score AS score,
    r.flavor_acceptance AS flavor_acceptance,
    r.effect_similarity AS effect_similarity,
    r.embedding_similarity AS embedding_similarity,
    r.structure_similarity AS structure_similarity,
    r.formula_context_similarity AS formula_context_similarity,
    r.source_type AS source_type
ORDER BY r.rank ASC, r.final_score DESC
LIMIT $limit
"""
        with self.driver.session() as session:
            rows = session.run(query, {"herb_name": herb_name, "limit": limit})
            results = []
            for record in rows:
                item = dict(record)
                item["baseline_candidates"] = []
                results.append(item)
            return results

    def retrieve_rnd_graph(self, herb_names: list[str], focus_relation: str | None = None) -> dict[str, Any]:
        query = """
MATCH (h:Herb)
WHERE h.herb_name IN $herb_names
OPTIONAL MATCH (h)-[r1]-(n1)
OPTIONAL MATCH (n1)-[r2]-(n2)
RETURN h AS n, r1 AS r, n1 AS m, r2, n2
LIMIT 180
"""
        graph = self.retrieve_graph(query, {"herb_names": herb_names, "entity_id": herb_names[0] if herb_names else None})
        if focus_relation:
            graph["focus_paths"] = [
                path for path in graph.get("focus_paths", []) if any(focus_relation == edge["type"] for edge in graph.get("edges", []))
            ] or graph.get("focus_paths", [])
        return graph

    def retrieve_graph_for_entity(self, entity: dict[str, Any], scene: str) -> dict[str, Any]:
        entity_id = entity["id"]
        entity_type = entity.get("entity_type") or "Herb"
        queries = {
            "herb_efficacy": """
MATCH (h:Herb {herb_name: $entity_id})
OPTIONAL MATCH (h)-[r1]-(n1)
OPTIONAL MATCH (n1)-[r2]-(n2)
RETURN h AS n, r1 AS r, n1 AS m, r2, n2
LIMIT 140
""",
            "formula_relation": """
MATCH (f:Formula {formula_name: $entity_id})
OPTIONAL MATCH (f)-[r1]-(n1)
OPTIONAL MATCH (n1)-[r2]-(n2)
RETURN f AS n, r1 AS r, n1 AS m, r2, n2
LIMIT 140
""",
            "entity_explanation": """
MATCH (n)
WHERE (n:Herb AND n.herb_name = $entity_id)
   OR (n:Compound AND n.canonical_smiles = $entity_id)
   OR (n:Compound AND n.compound_name = $entity_id)
   OR (n:Effect AND n.effect_name = $entity_id)
   OR (n:Flavor AND n.flavor_name = $entity_id)
   OR (n:Formula AND n.formula_name = $entity_id)
   OR (n:Symptom AND n.symptom_name = $entity_id)
   OR (n:Taboo AND n.taboo_name = $entity_id)
   OR (n:Source AND n.source_name = $entity_id)
   OR (n:NatureFlavor AND n.nature_flavor_name = $entity_id)
   OR (n:Meridian AND n.meridian_name = $entity_id)
   OR (n:EffectCategory AND n.effect_category_name = $entity_id)
   OR (n:Product AND n.product_id = $entity_id)
   OR (n:ConsumerProfile AND n.profile_id = $entity_id)
   OR (n:ConsumerSegment AND n.segment_key = $entity_id)
   OR (n:ConstitutionType AND n.constitution_type_name = $entity_id)
   OR (n:ConstitutionQuestion AND n.question_code = $entity_id)
OPTIONAL MATCH (n)-[r1]-(n1)
OPTIONAL MATCH (n1)-[r2]-(n2)
RETURN n, r1 AS r, n1 AS m, r2, n2
LIMIT 140
""",
        }
        if scene == "herb_efficacy" and entity_type != "Herb":
            scene = "entity_explanation"
        if scene == "formula_relation" and entity_type != "Formula":
            scene = "entity_explanation"
        return self.retrieve_graph(queries.get(scene, queries["entity_explanation"]), {"entity_id": entity_id})

    def retrieve_recommendation_graph(self, question: str, scene: str) -> dict[str, Any]:
        terms = self._expand_recommendation_terms(question, scene)
        if scene == "product_recommendation":
            query = """
MATCH (p:Product)
OPTIONAL MATCH (p)-[:HAS_CONSUMER_PROFILE]->(profile:ConsumerProfile)
WITH
    p,
    profile,
    [term IN $terms WHERE term <> ''] AS terms
WITH
    p,
    reduce(score = 0, term IN terms |
        score
        + CASE WHEN coalesce(p.product_name, '') CONTAINS term THEN 8 ELSE 0 END
        + CASE WHEN coalesce(p.brand, '') CONTAINS term THEN 4 ELSE 0 END
        + CASE WHEN coalesce(p.claimed_effect, '') CONTAINS term THEN 7 ELSE 0 END
        + CASE WHEN coalesce(p.dosage_form, '') CONTAINS term THEN 5 ELSE 0 END
        + CASE WHEN coalesce(p.ingredients, '') CONTAINS term THEN 4 ELSE 0 END
        + CASE WHEN coalesce(profile.crowd_type, '') CONTAINS term THEN 8 ELSE 0 END
        + CASE WHEN coalesce(profile.core_need, '') CONTAINS term THEN 8 ELSE 0 END
        + CASE WHEN coalesce(profile.preferred_flavor, '') CONTAINS term THEN 5 ELSE 0 END
        + CASE WHEN coalesce(profile.disliked_flavor, '') CONTAINS term THEN 5 ELSE 0 END
        + CASE WHEN coalesce(profile.price_sensitivity, '') CONTAINS term THEN 3 ELSE 0 END
    ) AS score
WHERE score > 0 OR $allow_fallback
WITH p, score
ORDER BY score DESC, coalesce(p.positive_rate, p.rating, 0) DESC, coalesce(p.review_count, p.sales, 0) DESC
LIMIT 8
OPTIONAL MATCH (p)-[r1]-(n1)
OPTIONAL MATCH (n1)-[r2]-(n2)
RETURN p AS n, r1 AS r, n1 AS m, r2, n2
LIMIT 220
"""
            return self.retrieve_graph(query, {"terms": terms, "allow_fallback": True, "entity_id": None})

        query = """
CALL {
    MATCH (ct:ConstitutionType)
    OPTIONAL MATCH (cq:ConstitutionQuestion)-[acr:ASSESSES_CONSTITUTION]->(ct)
    WITH ct, cq, acr, [term IN $terms WHERE term <> ''] AS terms
    WITH
        ct,
        cq,
        acr,
        reduce(score = 0, term IN terms |
            score
            + CASE WHEN ct.constitution_type_name CONTAINS term THEN 10 ELSE 0 END
            + CASE WHEN coalesce(cq.question_text, '') CONTAINS term THEN 4 ELSE 0 END
        ) AS score
    WHERE score > 0 OR $allow_fallback
    RETURN ct AS n, acr AS r, cq AS m, null AS r2, null AS n2, score AS score
    ORDER BY score DESC
    LIMIT 40

UNION ALL

    MATCH (f:Formula)
    WITH f, [term IN $terms WHERE term <> ''] AS terms
    WITH
        f,
        reduce(score = 0, term IN terms |
            score
            + CASE WHEN coalesce(f.formula_name, '') CONTAINS term THEN 10 ELSE 0 END
            + CASE WHEN coalesce(f.efficacy, '') CONTAINS term THEN 8 ELSE 0 END
            + CASE WHEN coalesce(f.crowd, '') CONTAINS term THEN 7 ELSE 0 END
            + CASE WHEN coalesce(f.ingredients, '') CONTAINS term THEN 4 ELSE 0 END
        ) AS score
    WHERE score > 0
    WITH f, score
    ORDER BY score DESC
    LIMIT 8
    OPTIONAL MATCH (f)-[r1]-(n1)
    OPTIONAL MATCH (n1)-[r2]-(n2)
    RETURN f AS n, r1 AS r, n1 AS m, r2 AS r2, n2 AS n2, score AS score

UNION ALL

    MATCH (h:Herb)
    OPTIONAL MATCH (h)-[:HAS_EFFECT]->(e:Effect)
    OPTIONAL MATCH (h)-[:TREATS]->(s:Symptom)
    WITH h, collect(DISTINCT e.effect_name) AS effects, collect(DISTINCT s.symptom_name) AS symptoms, [term IN $terms WHERE term <> ''] AS terms
    WITH
        h,
        reduce(score = 0, term IN terms |
            score
            + CASE WHEN h.herb_name CONTAINS term THEN 10 ELSE 0 END
            + CASE WHEN any(effect IN effects WHERE effect CONTAINS term) THEN 7 ELSE 0 END
            + CASE WHEN any(symptom IN symptoms WHERE symptom CONTAINS term) THEN 5 ELSE 0 END
        ) AS score
    WHERE score > 0 AND h.food_homology = '是'
    WITH h, score
    ORDER BY score DESC
    LIMIT 8
    OPTIONAL MATCH (h)-[r1]-(n1)
    RETURN h AS n, r1 AS r, n1 AS m, null AS r2, null AS n2, score AS score
}
RETURN n, r, m, r2, n2
LIMIT 260
"""
        return self.retrieve_graph(query, {"terms": terms, "allow_fallback": "体质" in question, "entity_id": None})

    def retrieve_graph(self, cypher_query: str, params: dict[str, Any]) -> dict[str, Any]:
        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[str, dict[str, Any]] = {}
        label_counter: Counter[str] = Counter()
        edge_counter: Counter[str] = Counter()

        with self.driver.session() as session:
            for record in session.run(cypher_query, params):
                self._collect_node(nodes, label_counter, record.get("n"))
                self._collect_node(nodes, label_counter, record.get("m"))
                self._collect_node(nodes, label_counter, record.get("n2"))
                self._collect_edge(edges, edge_counter, record.get("r"))
                self._collect_edge(edges, edge_counter, record.get("r2"))

        primary_id = params.get("entity_id")
        sorted_edges = sorted(
            edges.values(),
            key=lambda edge: (
                0 if edge["source"] == primary_id or edge["target"] == primary_id else 1,
                self._edge_priority(edge["type"]),
                edge["type"],
            ),
        )
        edge_list = self._select_balanced_edges(sorted_edges, settings.max_graph_edges)

        selected_node_ids = {primary_id} if primary_id else set()
        for edge in edge_list:
            selected_node_ids.add(edge["source"])
            selected_node_ids.add(edge["target"])

        degree_counter: Counter[str] = Counter()
        for edge in edge_list:
            degree_counter[edge["source"]] += 1
            degree_counter[edge["target"]] += 1

        sorted_nodes = sorted(
            nodes.values(),
            key=lambda node: (
                0 if node["id"] == primary_id else 1,
                self._node_priority(node["type"]),
                -degree_counter.get(node["id"], 0),
                node["label"],
            ),
        )
        node_map = {node["id"]: node for node in sorted_nodes}
        node_list = []
        added_ids: set[str] = set()
        if primary_id and primary_id in node_map:
            node_list.append(node_map[primary_id])
            added_ids.add(primary_id)
        for edge in edge_list:
            for node_id in (edge["source"], edge["target"]):
                if node_id in node_map and node_id not in added_ids and len(node_list) < settings.max_graph_nodes:
                    node_list.append(node_map[node_id])
                    added_ids.add(node_id)
        for node in sorted_nodes:
            if node["id"] in added_ids:
                continue
            if len(node_list) >= settings.max_graph_nodes:
                break
            node_list.append(node)
            added_ids.add(node["id"])

        valid_ids = {node["id"] for node in node_list}
        edge_list = [
            edge
            for edge in edge_list
            if edge["source"] in valid_ids and edge["target"] in valid_ids
        ]

        return {
            "nodes": node_list,
            "edges": edge_list,
            "focus_paths": self._build_focus_paths(node_list, edge_list),
            "legend": {"nodeTypes": dict(label_counter), "edgeTypes": dict(edge_counter)},
            "metrics": {"nodeCount": len(node_list), "edgeCount": len(edge_list)},
        }

    def _collect_node(self, bucket: dict[str, dict[str, Any]], counter: Counter[str], node: Any) -> None:
        if node is None:
            return
        node_id = self._node_id(node)
        node_type = self._primary_label(list(node.labels))
        counter[node_type] += 1
        if node_id not in bucket:
            bucket[node_id] = {
                "id": node_id,
                "label": self._node_label(node, list(node.labels)),
                "type": node_type,
                "props": dict(node),
                "score": 1.0,
            }

    def _node_id(self, node: Any) -> str:
        labels = list(node.labels)
        if "Herb" in labels:
            return node.get("herb_name") or str(node.id)
        if "Compound" in labels:
            return node.get("canonical_smiles") or str(node.id)
        if "Effect" in labels:
            return node.get("effect_name") or str(node.id)
        if "Flavor" in labels:
            return node.get("flavor_name") or str(node.id)
        if "Formula" in labels:
            return node.get("formula_name") or str(node.id)
        if "Symptom" in labels:
            return node.get("symptom_name") or str(node.id)
        if "Taboo" in labels:
            return node.get("taboo_name") or str(node.id)
        if "Source" in labels:
            return node.get("source_name") or str(node.id)
        if "NatureFlavor" in labels:
            return node.get("nature_flavor_name") or str(node.id)
        if "Meridian" in labels:
            return node.get("meridian_name") or str(node.id)
        if "EffectCategory" in labels:
            return node.get("effect_category_name") or str(node.id)
        if "Product" in labels:
            return node.get("product_id") or str(node.id)
        if "ConsumerProfile" in labels:
            return node.get("profile_id") or str(node.id)
        if "ConsumerSegment" in labels:
            return node.get("segment_key") or str(node.id)
        if "ConstitutionType" in labels:
            return node.get("constitution_type_name") or str(node.id)
        if "ConstitutionQuestion" in labels:
            return node.get("question_code") or str(node.id)
        return str(node.id)

    def _node_label(self, node: Any, labels: list[str]) -> str:
        if "Herb" in labels:
            return node.get("herb_name") or str(node.id)
        if "Compound" in labels:
            return node.get("compound_name") or node.get("canonical_smiles") or str(node.id)
        if "Effect" in labels:
            return node.get("effect_name") or str(node.id)
        if "Flavor" in labels:
            return node.get("flavor_name") or str(node.id)
        if "Formula" in labels:
            return node.get("formula_name") or str(node.id)
        if "Symptom" in labels:
            return node.get("symptom_name") or str(node.id)
        if "Taboo" in labels:
            return node.get("taboo_name") or str(node.id)
        if "Source" in labels:
            return node.get("source_name") or str(node.id)
        if "NatureFlavor" in labels:
            return node.get("nature_flavor_name") or str(node.id)
        if "Meridian" in labels:
            return node.get("meridian_name") or str(node.id)
        if "EffectCategory" in labels:
            return node.get("effect_category_name") or str(node.id)
        if "Product" in labels:
            return node.get("product_name") or node.get("product_id") or str(node.id)
        if "ConsumerProfile" in labels:
            return node.get("product_name") or node.get("profile_id") or str(node.id)
        if "ConsumerSegment" in labels:
            return node.get("segment_label") or node.get("segment_key") or str(node.id)
        if "ConstitutionType" in labels:
            return node.get("constitution_type_name") or str(node.id)
        if "ConstitutionQuestion" in labels:
            return node.get("question_text") or node.get("question_code") or str(node.id)
        return str(node.id)

    def _collect_edge(self, bucket: dict[str, dict[str, Any]], counter: Counter[str], edge: Any) -> None:
        if edge is None:
            return
        edge_id = str(edge.id)
        counter[edge.type] += 1
        if edge_id not in bucket:
            bucket[edge_id] = {
                "id": edge_id,
                "source": self._node_id(edge.start_node),
                "target": self._node_id(edge.end_node),
                "type": edge.type,
                "props": dict(edge),
                "score": 1.0,
            }

    def _build_focus_paths(self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not nodes or not edges:
            return []
        return [
            {
                "node_ids": [edges[0]["source"], edges[0]["target"]],
                "edge_ids": [edges[0]["id"]],
                "reason": "系统优先展示最先命中的证据关系",
            }
        ]

    def _expand_recommendation_terms(self, question: str, scene: str) -> list[str]:
        compact = re.sub(r"\s+", "", question or "")
        cleaned = re.sub(r"[？?，,。；;：:、（）()\[\]【】/\\\n\r\t]+", " ", question or "")
        raw_terms = [term.strip() for term in cleaned.split() if term.strip()]
        terms: list[str] = []

        def add(value: str | None) -> None:
            text = (value or "").strip()
            if text and len(text) > 1 and text not in terms:
                terms.append(text)

        for term in raw_terms:
            add(term)

        constitution_map = {
            "平和质": ["平和质", "日常养生", "调和"],
            "气虚质": ["气虚质", "气虚", "补气", "益气", "疲乏", "倦怠", "乏力"],
            "阳虚质": ["阳虚质", "阳虚", "温阳", "畏寒", "怕冷"],
            "阴虚质": ["阴虚质", "阴虚", "滋阴", "内热", "口干"],
            "痰湿质": ["痰湿质", "痰湿", "健脾", "祛湿", "肥胖"],
            "湿热质": ["湿热质", "湿热", "清热", "利湿"],
            "血瘀质": ["血瘀质", "血瘀", "活血", "化瘀"],
            "气郁质": ["气郁质", "气郁", "疏肝", "解郁"],
            "特禀质": ["特禀质", "过敏", "敏感", "咳嗽"],
        }
        if scene == "constitution_recommendation":
            for constitution, extra_terms in constitution_map.items():
                if constitution in compact or constitution.replace("质", "") in compact:
                    for term in extra_terms:
                        add(term)
            if "疲乏" in compact or "乏力" in compact:
                for term in ["气虚", "补气", "益气", "疲乏", "乏力"]:
                    add(term)
            if "怕冷" in compact or "畏寒" in compact:
                for term in ["阳虚", "温阳", "畏寒", "怕冷"]:
                    add(term)

        product_term_map = {
            "老人": ["老人", "中老年", "长辈"],
            "长辈": ["老人", "中老年", "长辈"],
            "送礼": ["送礼", "礼盒", "包装"],
            "宝妈": ["宝妈", "女性"],
            "学生": ["学生", "青少年"],
            "怕苦": ["苦", "低苦味", "好喝", "甜"],
            "好喝": ["好喝", "甜", "清香"],
            "便携": ["便携", "支装", "茶包", "袋泡"],
            "口服液": ["口服液", "即饮"],
            "睡眠": ["睡眠", "睡眠改善"],
            "免疫": ["免疫", "元气"],
            "补气": ["补气", "滋补", "元气"],
        }
        if scene == "product_recommendation":
            for hint, extra_terms in product_term_map.items():
                if hint in compact:
                    for term in extra_terms:
                        add(term)

        for size in range(min(5, len(compact)), 1, -1):
            for index in range(0, len(compact) - size + 1):
                piece = compact[index : index + size]
                if piece not in {"推荐", "哪些", "哪个", "产品", "成药", "体质", "药食"}:
                    add(piece)
        return terms[:30]

    def _normalize_keyword(self, keyword: str) -> str:
        compact = keyword.strip().replace(" ", "").replace("-", "_")
        return compact.upper()

    def _primary_label(self, labels: list[str]) -> str:
        priority = [
            "Herb", "Compound", "Effect", "Flavor", "Formula",
            "Symptom", "Taboo", "Source", "NatureFlavor", "Meridian",
            "EffectCategory",
            "Product", "ConsumerProfile", "ConsumerSegment",
            "ConstitutionType", "ConstitutionQuestion",
        ]
        for label in priority:
            if label in labels:
                return label
        return labels[0] if labels else "Entity"

    def _node_priority(self, node_type: str) -> int:
        order = {
            "Herb": 0,
            "Formula": 1,
            "Product": 2,
            "ConsumerProfile": 3,
            "ConsumerSegment": 4,
            "ConstitutionType": 5,
            "ConstitutionQuestion": 6,
            "Effect": 7,
            "EffectCategory": 8,
            "Compound": 9,
            "Flavor": 10,
            "NatureFlavor": 11,
            "Meridian": 12,
            "Symptom": 13,
            "Taboo": 14,
            "Source": 15,
            "Attribute": 20,
            "EvidenceNote": 21,
            "Entity": 30,
        }
        return order.get(node_type, 15)

    def _edge_priority(self, edge_type: str) -> int:
        order = {
            "CONTAINS": 0,
            "HAS_EFFECT": 1,
            "HAS_COMPOUND_EFFECT": 1,
            "CAN_REPLACE": 2,
            "HAS_CONSUMER_PROFILE": 2,
            "MATCHES_CONSUMER_SEGMENT": 2,
            "TOP_PRODUCT": 2,
            "IN_FORMULA": 3,
            "MONARCH_HERB": 3,
            "MINISTER_HERB": 3,
            "ASSISTANT_HERB": 3,
            "GUIDE_HERB": 3,
            "USES_HERB": 3,
            "TREATS": 4,
            "TARGETS_SYMPTOM": 4,
            "HAS_FLAVOR": 5,
            "PREFERS_FLAVOR": 5,
            "DISLIKES_FLAVOR": 5,
            "PRODUCES_FLAVOR": 5,
            "HAS_NATURE_FLAVOR": 5,
            "ENTERS_MERIDIAN": 6,
            "HAS_TABOO": 7,
            "ASSESSES_CONSTITUTION": 7,
            "BELONGS_TO_EFFECT_CATEGORY": 8,
            "FROM_SOURCE": 9,
            "LACKS_DIRECT_EVIDENCE": 20,
        }
        return order.get(edge_type, 10)

    def _select_balanced_edges(self, sorted_edges: list[dict[str, Any]], max_edges: int) -> list[dict[str, Any]]:
        quotas = {
            "CONTAINS": 16,
            "HAS_EFFECT": 14,
            "HAS_CONSUMER_PROFILE": 10,
            "MATCHES_CONSUMER_SEGMENT": 10,
            "TOP_PRODUCT": 10,
            "USES_HERB": 12,
            "TREATS": 12,
            "HAS_FLAVOR": 10,
            "PREFERS_FLAVOR": 8,
            "DISLIKES_FLAVOR": 8,
            "BELONGS_TO_EFFECT_CATEGORY": 4,
            "ENTERS_MERIDIAN": 8,
            "HAS_NATURE_FLAVOR": 8,
            "HAS_TABOO": 6,
            "ASSESSES_CONSTITUTION": 12,
        }
        selected: list[dict[str, Any]] = []
        counts: Counter[str] = Counter()
        for edge in sorted_edges:
            limit = quotas.get(edge["type"], 8)
            if counts[edge["type"]] >= limit:
                continue
            selected.append(edge)
            counts[edge["type"]] += 1
            if len(selected) >= max_edges:
                return selected
        for edge in sorted_edges:
            if edge in selected:
                continue
            selected.append(edge)
            if len(selected) >= max_edges:
                break
        return selected
