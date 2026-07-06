import hashlib
from collections import Counter

from app.repositories.neo4j_repository import Neo4jRepository
from app.repositories.postgres_repository import PostgresRepository
from app.services.qa_routing import get_qa_route_resolver


class GraphRetriever:
    def __init__(self, neo4j_repository: Neo4jRepository, postgres_repository: PostgresRepository) -> None:
        self.neo4j_repository = neo4j_repository
        self.postgres_repository = postgres_repository
        self.route_resolver = get_qa_route_resolver()

    def retrieve(self, question: str, entities: list[dict], scene: str, qa_route: str | None = None) -> tuple[str, dict, list[dict]]:
        template_key = self._normalize_scene(self.route_resolver.graph_scene_for(scene, qa_route))
        selected_entities = self.select_entities(question, entities, template_key, qa_route=qa_route)
        if template_key == "constitution_recommendation" and self.route_resolver.should_offer_constitution_panel(qa_route):
            graph = self._retrieve_constitution_scale_graph()
            graph = self._attach_question_node(question, graph, selected_entities)
            return template_key, self._finalize_graph(graph, selected_entities), selected_entities
        if template_key == "constitution_recommendation":
            graph = self._retrieve_recommendation_graph(question, template_key, qa_route=qa_route)
            graph = self._attach_question_node(question, graph, selected_entities)
            return template_key, self._finalize_graph(graph, selected_entities), selected_entities
        if template_key == "product_recommendation":
            graph = self._retrieve_recommendation_graph(question, template_key, qa_route=qa_route)
            graph = self._attach_question_node(question, graph, selected_entities)
            return template_key, self._finalize_graph(graph, selected_entities), selected_entities
        if selected_entities:
            graph = self._build_combined_graph(question, selected_entities, template_key)
            return template_key, graph, selected_entities

        template = self.postgres_repository.get_cypher_template_by_key(template_key)
        graph = self.neo4j_repository.retrieve_graph(template.cypher_query, {"keyword": question})
        return template.key, self._attach_question_node(question, graph, []), []

    def select_entities(self, question: str, entities: list[dict], scene: str, qa_route: str | None = None) -> list[dict]:
        if not entities:
            return []

        route_preferred_types = self.route_resolver.preferred_types_for(scene, qa_route)
        preferred_types = route_preferred_types or {
            "herb_efficacy": ["Herb", "Formula", "Effect", "EffectCategory", "Symptom", "Flavor", "NatureFlavor", "ConstitutionType", "ComplianceRule"],
            "formula_relation": ["Formula", "Herb", "Symptom", "Effect", "Flavor", "NatureFlavor", "Source", "ConstitutionType"],
            "formula_replacement": ["Formula", "Herb", "Effect", "Symptom", "Flavor", "NatureFlavor", "Taboo", "ConstitutionType", "ComplianceRule", "RiskExpression"],
            "constitution_recommendation": ["ConstitutionType", "ConsumerProfile", "ConsumerSegment", "Herb", "Symptom", "Product", "Flavor", "ComplianceRule", "ConsumerReview"],
            "product_recommendation": ["Product", "ConsumerProfile", "ConsumerSegment", "Herb", "Formula", "Effect", "Flavor", "ComplianceRule", "RiskExpression", "ConsumerReview"],
            "entity_explanation": ["Herb", "Formula", "Effect", "Symptom", "Flavor", "NatureFlavor", "Meridian", "ComplianceRule", "RiskExpression"],
        }.get(scene, ["Herb", "Formula", "Effect", "Symptom", "ComplianceRule"])
        rank_map = {entity_type: index for index, entity_type in enumerate(preferred_types)}

        contains_cjk = any("一" <= char <= "鿿" for char in question)
        threshold = 90 if contains_cjk else 70
        ranked = sorted(
            entities,
            key=lambda item: (
                rank_map.get(item.get("entity_type", ""), 99),
                -item.get("score", 0),
                -self._source_priority(item),
                -self._property_richness(item),
                len(item.get("name", "")),
            ),
        )

        selected: list[dict] = []
        seen_ids: set[str] = set()
        seen_names: set[tuple[str, str]] = set()
        for entity in ranked:
            if entity["id"] in seen_ids:
                continue
            identity = ((entity.get("name") or "").strip(), entity.get("entity_type", "Entity"))
            if identity in seen_names:
                continue
            if entity.get("score", 0) < threshold and len(selected) >= 1:
                continue
            selected.append(entity)
            seen_ids.add(entity["id"])
            seen_names.add(identity)
            if len(selected) >= 6:
                break

        if selected:
            return selected
        return ranked[:3]

    def _build_combined_graph(self, question: str, entities: list[dict], template_key: str) -> dict:
        graph = {"nodes": [], "edges": [], "focus_paths": [], "legend": {}, "metrics": {"nodeCount": 0, "edgeCount": 0}}
        for entity in entities:
            entity_graph = self.neo4j_repository.retrieve_graph_for_entity(entity, self._scene_for_entity(entity, template_key))
            graph = self._merge_graphs(graph, entity_graph)

        graph = self._attach_question_node(question, graph, entities)
        for entity in entities[:4]:
            graph = self._augment_entity_if_sparse(entity, graph, question)
        return self._finalize_graph(graph, entities)

    def _retrieve_recommendation_graph(self, question: str, scene: str, qa_route: str | None = None) -> dict:
        expand_terms = getattr(self.neo4j_repository, "_expand_recommendation_terms", None)
        terms = expand_terms(question, scene, qa_route=qa_route) if callable(expand_terms) else [question]
        if scene == "product_recommendation":
            query = """
CALL () {
    MATCH (p:Product)
    OPTIONAL MATCH (p)-[:USES_HERB|CLAIMS_EFFECT|HAS_FLAVOR|HAS_CONSUMER_PROFILE|TOP_PRODUCT]-(related)
    WITH
        p,
        collect(DISTINCT related) AS related_nodes,
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
            + CASE WHEN coalesce(p.primary_age_group, '') CONTAINS term THEN 5 ELSE 0 END
            + CASE WHEN coalesce(p.secondary_age_group, '') CONTAINS term THEN 4 ELSE 0 END
            + CASE WHEN coalesce(p.product_form_category, '') CONTAINS term THEN 4 ELSE 0 END
            + CASE WHEN coalesce(p.effect_category, '') CONTAINS term THEN 5 ELSE 0 END
            + CASE WHEN coalesce(p.scenario, '') CONTAINS term THEN 4 ELSE 0 END
            + CASE WHEN any(x IN coalesce(p.inferred_ingredients, []) WHERE x CONTAINS term) THEN 5 ELSE 0 END
            + CASE WHEN any(x IN related_nodes WHERE coalesce(x.herb_name, '') CONTAINS term) THEN 6 ELSE 0 END
            + CASE WHEN any(x IN related_nodes WHERE coalesce(x.effect_name, '') CONTAINS term) THEN 6 ELSE 0 END
            + CASE WHEN any(x IN related_nodes WHERE coalesce(x.flavor_name, '') CONTAINS term) THEN 4 ELSE 0 END
            + CASE WHEN any(x IN related_nodes WHERE coalesce(x.crowd_type, '') CONTAINS term) THEN 7 ELSE 0 END
            + CASE WHEN any(x IN related_nodes WHERE coalesce(x.core_need, '') CONTAINS term) THEN 6 ELSE 0 END
            + CASE WHEN any(x IN related_nodes WHERE coalesce(x.preferred_flavor, '') CONTAINS term) THEN 6 ELSE 0 END
            + CASE WHEN any(x IN related_nodes WHERE coalesce(x.disliked_flavor, '') CONTAINS term) THEN 5 ELSE 0 END
            + CASE WHEN any(x IN related_nodes WHERE coalesce(x.segment_label, '') CONTAINS term) THEN 6 ELSE 0 END
            + CASE WHEN any(x IN related_nodes WHERE coalesce(x.top_flavor_tags, '') CONTAINS term) THEN 5 ELSE 0 END
        ) AS score
    WHERE score > 0 OR $allow_fallback
    WITH p, score
    ORDER BY score DESC, coalesce(p.positive_rate, p.rating, 0) DESC, coalesce(p.review_count, p.sales, 0) DESC
    LIMIT 8
    OPTIONAL MATCH (p)-[r1:USES_HERB|CLAIMS_EFFECT|HAS_CONSUMER_PROFILE|TOP_PRODUCT]-(n1)
    OPTIONAL MATCH (n1)-[r2:PREFERS_FLAVOR|DISLIKES_FLAVOR|MATCHES_CONSUMER_SEGMENT|SEGMENT_PREFERS_FLAVOR|TOP_PRODUCT]-(n2)
    RETURN p AS n, r1 AS r, n1 AS m, r2, n2, score AS score

UNION ALL

    MATCH (cp:ConsumerProfile)
    WITH cp, [term IN $terms WHERE term <> ''] AS terms
    WITH
        cp,
        reduce(score = 0, term IN terms |
            score
            + CASE WHEN coalesce(cp.product_name, '') CONTAINS term THEN 8 ELSE 0 END
            + CASE WHEN coalesce(cp.brand, '') CONTAINS term THEN 4 ELSE 0 END
            + CASE WHEN coalesce(cp.crowd_type, '') CONTAINS term THEN 8 ELSE 0 END
            + CASE WHEN coalesce(cp.core_need, '') CONTAINS term THEN 7 ELSE 0 END
            + CASE WHEN coalesce(cp.preferred_dosage, '') CONTAINS term THEN 6 ELSE 0 END
            + CASE WHEN coalesce(cp.preferred_flavor, '') CONTAINS term THEN 8 ELSE 0 END
            + CASE WHEN coalesce(cp.disliked_flavor, '') CONTAINS term THEN 7 ELSE 0 END
            + CASE WHEN coalesce(cp.primary_age_group, '') CONTAINS term THEN 6 ELSE 0 END
            + CASE WHEN coalesce(cp.effect_category, '') CONTAINS term THEN 6 ELSE 0 END
        ) AS score
    WHERE score > 0 OR $allow_fallback
    WITH cp, score
    ORDER BY score DESC, coalesce(cp.positive_rate, 0) DESC, coalesce(cp.review_count, 0) DESC
    LIMIT 10
    OPTIONAL MATCH (cp)-[r1:PREFERS_FLAVOR|DISLIKES_FLAVOR|MATCHES_CONSUMER_SEGMENT|HAS_CONSUMER_PROFILE]-(n1)
    OPTIONAL MATCH (n1)-[r2:SEGMENT_PREFERS_FLAVOR|TOP_PRODUCT|PREFERS_FLAVOR|DISLIKES_FLAVOR]-(n2)
    RETURN cp AS n, r1 AS r, n1 AS m, r2, n2, score AS score

UNION ALL

    MATCH (cs:ConsumerSegment)
    WITH cs, [term IN $terms WHERE term <> ''] AS terms
    WITH
        cs,
        reduce(score = 0, term IN terms |
            score
            + CASE WHEN coalesce(cs.segment_label, '') CONTAINS term THEN 8 ELSE 0 END
            + CASE WHEN coalesce(cs.crowd_tags, '') CONTAINS term THEN 7 ELSE 0 END
            + CASE WHEN coalesce(cs.scenario_tags, '') CONTAINS term THEN 6 ELSE 0 END
            + CASE WHEN coalesce(cs.effect_tags, '') CONTAINS term THEN 6 ELSE 0 END
            + CASE WHEN coalesce(cs.top_flavor_tags, '') CONTAINS term THEN 8 ELSE 0 END
            + CASE WHEN coalesce(cs.top_dosage_tags, '') CONTAINS term THEN 6 ELSE 0 END
            + CASE WHEN coalesce(cs.top_complaint_tags, '') CONTAINS term THEN 6 ELSE 0 END
        ) AS score
    WHERE score > 0 OR $allow_fallback
    WITH cs, score
    ORDER BY score DESC, coalesce(cs.positive_rate, 0) DESC, coalesce(cs.review_count, 0) DESC
    LIMIT 10
    OPTIONAL MATCH (cs)-[r1:SEGMENT_PREFERS_FLAVOR|TOP_PRODUCT|MATCHES_CONSUMER_SEGMENT]-(n1)
    OPTIONAL MATCH (n1)-[r2:HAS_CONSUMER_PROFILE|PREFERS_FLAVOR|DISLIKES_FLAVOR|REVIEWS_PRODUCT]-(n2)
    RETURN cs AS n, r1 AS r, n1 AS m, r2, n2, score AS score

UNION ALL

    MATCH (rv:ConsumerReview)
    WITH rv, [term IN $terms WHERE term <> ''] AS terms
    WITH
        rv,
        reduce(score = 0, term IN terms |
            score
            + CASE WHEN coalesce(rv.flavor_tags, '') CONTAINS term THEN 7 ELSE 0 END
            + CASE WHEN coalesce(rv.effect_tags, '') CONTAINS term THEN 6 ELSE 0 END
            + CASE WHEN coalesce(rv.crowd_tags, '') CONTAINS term THEN 6 ELSE 0 END
            + CASE WHEN coalesce(rv.scenario_tags, '') CONTAINS term THEN 5 ELSE 0 END
            + CASE WHEN coalesce(rv.complaint_tags, '') CONTAINS term THEN 5 ELSE 0 END
            + CASE WHEN coalesce(rv.cleaned_text, '') CONTAINS term THEN 3 ELSE 0 END
        ) AS score
    WHERE score > 0
    WITH rv, score
    ORDER BY score DESC, coalesce(rv.quality_score, 0) DESC
    LIMIT 12
    OPTIONAL MATCH (rv)-[r1:REVIEWS_PRODUCT|MENTIONS_FLAVOR|MENTIONS_EFFECT|BELONGS_TO_CONSUMER_SEGMENT]-(n1)
    RETURN rv AS n, r1 AS r, n1 AS m, null AS r2, null AS n2, score AS score

UNION ALL

    MATCH (cr:ComplianceRule)
    WITH cr, [term IN $terms WHERE term <> ''] AS terms
    WITH
        cr,
        reduce(score = 0, term IN terms |
            score
            + CASE WHEN coalesce(cr.rule_name, '') CONTAINS term THEN 8 ELSE 0 END
            + CASE WHEN coalesce(cr.rule_type, '') CONTAINS term THEN 8 ELSE 0 END
            + CASE WHEN coalesce(cr.rule_content, '') CONTAINS term THEN 5 ELSE 0 END
            + CASE WHEN coalesce(cr.agent_check_point, '') CONTAINS term THEN 5 ELSE 0 END
        ) AS score
    WHERE score > 0 OR $include_compliance
    WITH cr, score
    ORDER BY score DESC, coalesce(cr.rule_type, ''), coalesce(cr.rule_name, '')
    LIMIT 12
    OPTIONAL MATCH (cr)-[r1]-(n1)
    RETURN cr AS n, r1 AS r, n1 AS m, null AS r2, null AS n2, score AS score

UNION ALL

    MATCH (re:RiskExpression)
    WITH re, [term IN $terms WHERE term <> ''] AS terms
    WITH
        re,
        reduce(score = 0, term IN terms |
            score
            + CASE WHEN re.expression CONTAINS term THEN 9 ELSE 0 END
            + CASE WHEN coalesce(re.risk_reason, '') CONTAINS term THEN 5 ELSE 0 END
            + CASE WHEN coalesce(re.suggested_expression, '') CONTAINS term THEN 4 ELSE 0 END
        ) AS score
    WHERE score > 0 OR $include_compliance
    WITH re, score
    ORDER BY score DESC, coalesce(re.risk_level, ''), re.expression
    LIMIT 8
    OPTIONAL MATCH (re)-[r1]-(n1)
    RETURN re AS n, r1 AS r, n1 AS m, null AS r2, null AS n2, score AS score
}
RETURN n, r, m, r2, n2
ORDER BY score DESC
LIMIT 260
"""
            return self.neo4j_repository.retrieve_graph(
                query,
                {"terms": terms, "allow_fallback": True, "include_compliance": True, "entity_id": None},
            )

        query = """
CALL () {
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
    LIMIT 60

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

UNION ALL

    MATCH (cp:ConsumerProfile)
    WITH cp, [term IN $terms WHERE term <> ''] AS terms
    WITH
        cp,
        reduce(score = 0, term IN terms |
            score
            + CASE WHEN coalesce(cp.crowd_type, '') CONTAINS term THEN 8 ELSE 0 END
            + CASE WHEN coalesce(cp.core_need, '') CONTAINS term THEN 7 ELSE 0 END
            + CASE WHEN coalesce(cp.preferred_flavor, '') CONTAINS term THEN 7 ELSE 0 END
            + CASE WHEN coalesce(cp.disliked_flavor, '') CONTAINS term THEN 7 ELSE 0 END
            + CASE WHEN coalesce(cp.primary_age_group, '') CONTAINS term THEN 7 ELSE 0 END
            + CASE WHEN coalesce(cp.product_form_category, '') CONTAINS term THEN 5 ELSE 0 END
        ) AS score
    WHERE score > 0
    WITH cp, score
    ORDER BY score DESC, coalesce(cp.positive_rate, 0) DESC, coalesce(cp.review_count, 0) DESC
    LIMIT 10
    OPTIONAL MATCH (cp)-[r1:PREFERS_FLAVOR|DISLIKES_FLAVOR|MATCHES_CONSUMER_SEGMENT|HAS_CONSUMER_PROFILE]-(n1)
    OPTIONAL MATCH (n1)-[r2:SEGMENT_PREFERS_FLAVOR|TOP_PRODUCT]-(n2)
    RETURN cp AS n, r1 AS r, n1 AS m, r2 AS r2, n2 AS n2, score AS score

UNION ALL

    MATCH (cs:ConsumerSegment)
    WITH cs, [term IN $terms WHERE term <> ''] AS terms
    WITH
        cs,
        reduce(score = 0, term IN terms |
            score
            + CASE WHEN coalesce(cs.segment_label, '') CONTAINS term THEN 8 ELSE 0 END
            + CASE WHEN coalesce(cs.crowd_tags, '') CONTAINS term THEN 7 ELSE 0 END
            + CASE WHEN coalesce(cs.scenario_tags, '') CONTAINS term THEN 6 ELSE 0 END
            + CASE WHEN coalesce(cs.effect_tags, '') CONTAINS term THEN 6 ELSE 0 END
            + CASE WHEN coalesce(cs.top_flavor_tags, '') CONTAINS term THEN 7 ELSE 0 END
            + CASE WHEN coalesce(cs.top_complaint_tags, '') CONTAINS term THEN 6 ELSE 0 END
        ) AS score
    WHERE score > 0
    WITH cs, score
    ORDER BY score DESC, coalesce(cs.positive_rate, 0) DESC, coalesce(cs.review_count, 0) DESC
    LIMIT 10
    OPTIONAL MATCH (cs)-[r1:SEGMENT_PREFERS_FLAVOR|TOP_PRODUCT|MATCHES_CONSUMER_SEGMENT]-(n1)
    RETURN cs AS n, r1 AS r, n1 AS m, null AS r2, null AS n2, score AS score

UNION ALL

    MATCH (rv:ConsumerReview)
    WITH rv, [term IN $terms WHERE term <> ''] AS terms
    WITH
        rv,
        reduce(score = 0, term IN terms |
            score
            + CASE WHEN coalesce(rv.flavor_tags, '') CONTAINS term THEN 6 ELSE 0 END
            + CASE WHEN coalesce(rv.crowd_tags, '') CONTAINS term THEN 6 ELSE 0 END
            + CASE WHEN coalesce(rv.scenario_tags, '') CONTAINS term THEN 5 ELSE 0 END
            + CASE WHEN coalesce(rv.complaint_tags, '') CONTAINS term THEN 5 ELSE 0 END
        ) AS score
    WHERE score > 0
    WITH rv, score
    ORDER BY score DESC, coalesce(rv.quality_score, 0) DESC
    LIMIT 8
    OPTIONAL MATCH (rv)-[r1:REVIEWS_PRODUCT|MENTIONS_FLAVOR|MENTIONS_EFFECT|BELONGS_TO_CONSUMER_SEGMENT]-(n1)
    RETURN rv AS n, r1 AS r, n1 AS m, null AS r2, null AS n2, score AS score
}
RETURN n, r, m, r2, n2
ORDER BY score DESC
LIMIT 260
"""
        allow_fallback = any(
            token in (question or "")
            for token in ["\u4f53\u8d28", "\u91cf\u8868", "\u95ee\u5377", "\u6d4b\u8bd5", "\u6d4b\u8bc4"]
        )
        return self.neo4j_repository.retrieve_graph(query, {"terms": terms, "allow_fallback": allow_fallback, "entity_id": None})

    def _retrieve_constitution_scale_graph(self) -> dict:
        query = """
MATCH (cq:ConstitutionQuestion)-[r:ASSESSES_CONSTITUTION]->(ct:ConstitutionType)
RETURN cq AS n, r AS r, ct AS m, null AS r2, null AS n2
ORDER BY ct.constitution_type_name, cq.question_no
LIMIT 200
"""
        nodes: dict[str, dict] = {}
        edges: dict[str, dict] = {}
        label_counter: Counter[str] = Counter()
        edge_counter: Counter[str] = Counter()

        with self.neo4j_repository.driver.session() as session:
            for record in session.run(query):
                self.neo4j_repository._collect_node(nodes, label_counter, record.get("n"))
                self.neo4j_repository._collect_node(nodes, label_counter, record.get("m"))
                self.neo4j_repository._collect_edge(edges, edge_counter, record.get("r"))

        node_list = sorted(
            nodes.values(),
            key=lambda node: (
                self._node_priority(node.get("type", "Entity")),
                str(node.get("label", "")),
            ),
        )
        edge_list = sorted(
            edges.values(),
            key=lambda edge: (
                self._edge_priority(edge.get("type", "")),
                str(edge.get("source", "")),
                str(edge.get("target", "")),
            ),
        )
        return {
            "nodes": node_list,
            "edges": edge_list,
            "focus_paths": self._build_focus_paths(node_list, edge_list),
            "legend": {"nodeTypes": dict(label_counter), "edgeTypes": dict(edge_counter)},
            "metrics": {"nodeCount": len(node_list), "edgeCount": len(edge_list)},
        }

    def _scene_for_entity(self, entity: dict, template_key: str) -> str:
        entity_type = entity.get("entity_type", "")
        if template_key == "herb_efficacy" and entity_type == "Herb":
            return template_key
        if template_key in ("formula_relation", "formula_replacement") and entity_type == "Formula":
            return "formula_relation"
        if template_key == "constitution_recommendation" and entity_type in {"ConstitutionType", "ConstitutionQuestion"}:
            return "entity_explanation"
        if template_key == "product_recommendation" and entity_type in {"Product", "ConsumerProfile", "ConsumerSegment", "ConsumerReview", "Herb", "Effect", "Flavor", "ComplianceRule", "RiskExpression"}:
            return "entity_explanation"
        return "entity_explanation"

    def _attach_question_node(self, question: str, graph: dict, entities: list[dict]) -> dict:
        question_id = f"question:{hashlib.md5(question.encode('utf-8')).hexdigest()[:12]}"
        node_map = {node["id"]: node for node in graph.get("nodes", [])}
        edge_map = {edge["id"]: edge for edge in graph.get("edges", [])}
        node_map[question_id] = {
            "id": question_id,
            "label": question[:36] + ("..." if len(question) > 36 else ""),
            "type": "Question",
            "props": {"question": question},
            "score": 1.0,
        }
        for entity in entities:
            if entity["id"] not in node_map:
                node_map[entity["id"]] = {
                    "id": entity["id"],
                    "label": entity.get("name") or entity["id"],
                    "type": entity.get("entity_type", "Entity"),
                    "props": entity.get("props", {}),
                    "score": entity.get("score", 1.0),
                }
            edge_id = f"{question_id}->{entity['id']}"
            edge_map[edge_id] = {
                "id": edge_id,
                "source": question_id,
                "target": entity["id"],
                "type": "MENTIONS",
                "props": {"source": "question"},
                "score": entity.get("score", 1.0),
            }
        graph["nodes"] = list(node_map.values())
        graph["edges"] = list(edge_map.values())
        return graph

    def _augment_entity_if_sparse(self, entity: dict, graph: dict, question: str) -> dict:
        entity_id = entity["id"]
        relation_edges = [
            edge
            for edge in graph.get("edges", [])
            if edge["type"] != "MENTIONS" and (edge["source"] == entity_id or edge["target"] == entity_id)
        ]
        if relation_edges:
            return graph

        if any(token in question for token in ["成分", "成份", "化合物"]):
            self._add_note_node(graph, entity_id, "compound_note", "0604 新图谱以 KB1-KB8 为准，不包含 Compound/成分网络")
        if any(token in question for token in ["方剂", "方子", "方"]) and not self._has_related_type(graph, entity_id, "Formula"):
            self._add_note_node(graph, entity_id, "formula_note", "当前知识图谱未找到该实体的直接方剂关系")

        return graph

    def _add_note_node(self, graph: dict, entity_id: str, field: str, text: str) -> None:
        node_map = {node["id"]: node for node in graph.get("nodes", [])}
        edge_map = {edge["id"]: edge for edge in graph.get("edges", [])}
        node_id = f"{entity_id}:{field}"
        node_map[node_id] = {
            "id": node_id,
            "label": text,
            "type": "EvidenceNote",
            "props": {"field": field, "value": text},
            "score": 0.65,
        }
        edge_map[f"{entity_id}->{field}"] = {
            "id": f"{entity_id}->{field}",
            "source": entity_id,
            "target": node_id,
            "type": "LACKS_DIRECT_EVIDENCE",
            "props": {"source": "entity_props"},
            "score": 0.65,
        }
        graph["nodes"] = list(node_map.values())
        graph["edges"] = list(edge_map.values())

    def _finalize_graph(self, graph: dict, entities: list[dict]) -> dict:
        node_map = {node["id"]: node for node in graph.get("nodes", [])}
        edge_map = {edge["id"]: edge for edge in graph.get("edges", [])}
        edges = self._limit_edges(list(edge_map.values()))

        required_ids: set[str] = set()
        for edge in edges:
            required_ids.add(edge["source"])
            required_ids.add(edge["target"])
        for entity in entities[:6]:
            required_ids.add(entity["id"])

        ordered_nodes = sorted(
            node_map.values(),
            key=lambda node: (
                0 if node["type"] == "Question" else 1,
                self._node_priority(node["type"]),
                node["label"],
            ),
        )

        nodes: list[dict] = []
        for node in ordered_nodes:
            if node["id"] not in required_ids and len(nodes) >= 36:
                continue
            nodes.append(node)
            if len(nodes) >= 48:
                break

        valid_ids = {node["id"] for node in nodes}
        edges = [edge for edge in edges if edge["source"] in valid_ids and edge["target"] in valid_ids]

        graph["nodes"] = nodes
        graph["edges"] = edges
        graph["focus_paths"] = self._build_focus_paths(nodes, edges)
        graph["legend"] = {
            "nodeTypes": self._counter(nodes, "type"),
            "edgeTypes": self._counter(edges, "type"),
        }
        graph["metrics"] = {"nodeCount": len(nodes), "edgeCount": len(edges)}
        return graph

    def _build_focus_paths(self, nodes: list[dict], edges: list[dict]) -> list[dict]:
        question_nodes = [node for node in nodes if node["type"] == "Question"]
        if not question_nodes:
            return []
        question_id = question_nodes[0]["id"]
        mention_edges = [edge for edge in edges if edge["source"] == question_id][:4]
        relation_edges = [edge for edge in edges if edge["type"] not in {"MENTIONS"}][:4]
        focus_paths = [
            {
                "node_ids": [edge["source"], edge["target"]],
                "edge_ids": [edge["id"]],
                "reason": "问题命中了该实体，系统基于该实体继续向外检索知识图谱证据",
            }
            for edge in mention_edges
        ]
        focus_paths.extend(
            {
                "node_ids": [edge["source"], edge["target"]],
                "edge_ids": [edge["id"]],
                "reason": "这是当前问题命中的图谱关系证据",
            }
            for edge in relation_edges
        )
        return focus_paths[:8]

    def _merge_graphs(self, left: dict, right: dict) -> dict:
        node_map = {node["id"]: node for node in left.get("nodes", [])}
        edge_map = {edge["id"]: edge for edge in left.get("edges", [])}
        for node in right.get("nodes", []):
            node_map.setdefault(node["id"], node)
        for edge in right.get("edges", []):
            edge_map.setdefault(edge["id"], edge)
        return {
            "nodes": list(node_map.values()),
            "edges": list(edge_map.values()),
            "focus_paths": left.get("focus_paths", []) + right.get("focus_paths", []),
            "legend": {},
            "metrics": {"nodeCount": len(node_map), "edgeCount": len(edge_map)},
        }

    def _limit_edges(self, edges: list[dict]) -> list[dict]:
        sorted_edges = sorted(
            edges,
            key=lambda edge: (
                0 if edge["type"] == "MENTIONS" else 1,
                self._edge_priority(edge["type"]),
                edge["type"],
            ),
        )
        quotas = {
            "MENTIONS": 8,
            "INCOMPATIBLE_WITH": 10,
            "HAS_EFFECT": 14,
            "CAN_REPLACE": 10,
            "CLAIMS_EFFECT": 10,
            "HAS_CONSUMER_PROFILE": 10,
            "PREFERS_FLAVOR": 10,
            "DISLIKES_FLAVOR": 10,
            "SEGMENT_PREFERS_FLAVOR": 10,
            "MATCHES_CONSUMER_SEGMENT": 10,
            "TOP_PRODUCT": 8,
            "REVIEWS_PRODUCT": 8,
            "MENTIONS_FLAVOR": 10,
            "MENTIONS_EFFECT": 10,
            "BELONGS_TO_CONSUMER_SEGMENT": 10,
            "USES_HERB": 12,
            "TREATS": 10,
            "TARGETS_SYMPTOM": 10,
            "HAS_FLAVOR": 8,
            "HAS_NATURE_FLAVOR": 8,
            "ENTERS_MERIDIAN": 8,
            "HAS_TABOO": 6,
            "IN_FORMULA": 10,
            "ASSESSES_CONSTITUTION": 12,
            "RECOMMENDS_HERB": 12,
            "CAUTIONS_HERB": 12,
            "LISTED_IN_COMPLIANCE_RULE": 8,
            "DERIVED_FROM_RULE": 8,
            "LACKS_DIRECT_EVIDENCE": 8,
        }
        selected: list[dict] = []
        counts: Counter[str] = Counter()
        for edge in sorted_edges:
            limit = quotas.get(edge["type"], 8)
            if counts[edge["type"]] >= limit:
                continue
            selected.append(edge)
            counts[edge["type"]] += 1
            if len(selected) >= 80:
                break
        return selected

    def _counter(self, items: list[dict], key: str) -> dict:
        output: dict[str, int] = {}
        for item in items:
            value = item.get(key, "Unknown")
            output[value] = output.get(value, 0) + 1
        return output

    def _has_related_type(self, graph: dict, entity_id: str, target_type: str) -> bool:
        node_types = {node["id"]: node.get("type", "Entity") for node in graph.get("nodes", [])}
        for edge in graph.get("edges", []):
            if edge["source"] == entity_id and node_types.get(edge["target"]) == target_type:
                return True
            if edge["target"] == entity_id and node_types.get(edge["source"]) == target_type:
                return True
        return False

    def _normalize_scene(self, scene: str) -> str:
        if scene in {
            "herb_efficacy",
            "formula_relation",
            "formula_replacement",
            "constitution_recommendation",
            "product_recommendation",
            "entity_explanation",
        }:
            return scene
        return "entity_explanation"

    def _source_priority(self, entity: dict) -> int:
        return 0

    def _property_richness(self, entity: dict) -> int:
        return len(entity.get("props", {}))

    def _node_priority(self, node_type: str) -> int:
        order = {
            "Question": -1,
            "Herb": 0,
            "Formula": 1,
            "Product": 2,
            "ConsumerProfile": 3,
            "ConsumerSegment": 4,
            "ConstitutionType": 5,
            "ConstitutionQuestion": 6,
            "ComplianceRule": 7,
            "RiskExpression": 8,
            "Effect": 9,
            "EffectCategory": 10,
            "Flavor": 11,
            "ConsumerReview": 12,
            "NatureFlavor": 13,
            "Meridian": 14,
            "Symptom": 15,
            "Taboo": 16,
            "Source": 17,
            "Compound": 30,
            "Attribute": 20,
            "EvidenceNote": 21,
            "Entity": 40,
        }
        return order.get(node_type, 16)

    def _edge_priority(self, edge_type: str) -> int:
        order = {
            "INCOMPATIBLE_WITH": 0,
            "HAS_EFFECT": 1,
            "CAN_REPLACE": 2,
            "CLAIMS_EFFECT": 2,
            "HAS_CONSUMER_PROFILE": 2,
            "PREFERS_FLAVOR": 2,
            "DISLIKES_FLAVOR": 2,
            "SEGMENT_PREFERS_FLAVOR": 2,
            "IN_FORMULA": 3,
            "MONARCH_HERB": 3,
            "MINISTER_HERB": 3,
            "ASSISTANT_HERB": 3,
            "GUIDE_HERB": 3,
            "USES_HERB": 3,
            "TREATS": 4,
            "TARGETS_SYMPTOM": 4,
            "HAS_FLAVOR": 5,
            "HAS_NATURE_FLAVOR": 5,
            "ENTERS_MERIDIAN": 6,
            "HAS_TABOO": 7,
            "ASSESSES_CONSTITUTION": 7,
            "RECOMMENDS_HERB": 7,
            "CAUTIONS_HERB": 7,
            "MATCHES_CONSUMER_SEGMENT": 7,
            "TOP_PRODUCT": 7,
            "REVIEWS_PRODUCT": 8,
            "MENTIONS_FLAVOR": 8,
            "MENTIONS_EFFECT": 8,
            "BELONGS_TO_CONSUMER_SEGMENT": 8,
            "BELONGS_TO_EFFECT_CATEGORY": 8,
            "FROM_SOURCE": 9,
            "LISTED_IN_COMPLIANCE_RULE": 9,
            "DERIVED_FROM_RULE": 9,
            "LACKS_DIRECT_EVIDENCE": 20,
        }
        return order.get(edge_type, 10)

    def _stringify(self, value: str | list[str]) -> str:
        if isinstance(value, list):
            return "、".join(str(item) for item in value[:8])
        return str(value)
