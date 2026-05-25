import hashlib
from collections import Counter

from app.repositories.neo4j_repository import Neo4jRepository
from app.repositories.postgres_repository import PostgresRepository


class GraphRetriever:
    def __init__(self, neo4j_repository: Neo4jRepository, postgres_repository: PostgresRepository) -> None:
        self.neo4j_repository = neo4j_repository
        self.postgres_repository = postgres_repository

    def retrieve(self, question: str, entities: list[dict], scene: str) -> tuple[str, dict, list[dict]]:
        template_key = self._normalize_scene(scene)
        selected_entities = self.select_entities(question, entities, template_key)
        if template_key in {"constitution_recommendation", "product_recommendation"}:
            graph = self.neo4j_repository.retrieve_recommendation_graph(question, template_key)
            selected_entities = self._dedupe_entities(
                selected_entities + self._entities_from_recommendation_graph(graph, template_key)
            )[:6]
            for entity in selected_entities[:4]:
                entity_graph = self.neo4j_repository.retrieve_graph_for_entity(entity, self._scene_for_entity(entity, template_key))
                graph = self._merge_graphs(graph, entity_graph)
            graph = self._attach_question_node(question, graph, selected_entities)
            return template_key, self._finalize_graph(graph, selected_entities), selected_entities

        if selected_entities:
            graph = self._build_combined_graph(question, selected_entities, template_key)
            return template_key, graph, selected_entities

        template = self.postgres_repository.get_cypher_template_by_key(template_key)
        graph = self.neo4j_repository.retrieve_graph(template.cypher_query, {"keyword": question})
        return template.key, self._attach_question_node(question, graph, []), []

    def select_entities(self, question: str, entities: list[dict], scene: str) -> list[dict]:
        if not entities:
            return []

        preferred_types = {
            "herb_efficacy": ["Herb", "Formula", "Compound", "Effect", "Symptom"],
            "formula_relation": ["Formula", "Herb", "Compound", "Symptom"],
            "formula_replacement": ["Formula", "Herb", "Compound", "Symptom", "Taboo"],
            "constitution_recommendation": ["ConstitutionType", "ConstitutionQuestion", "Formula", "Herb", "Symptom", "Product"],
            "product_recommendation": ["Product", "ConsumerProfile", "ConsumerSegment", "Herb", "Flavor", "Effect", "Formula"],
            "entity_explanation": ["Herb", "Compound", "Formula", "Effect", "Symptom", "Flavor", "NatureFlavor", "Meridian"],
        }.get(scene, ["Herb", "Formula", "Compound", "Effect", "Symptom"])
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

    def _scene_for_entity(self, entity: dict, template_key: str) -> str:
        entity_type = entity.get("entity_type", "")
        if template_key == "herb_efficacy" and entity_type == "Herb":
            return template_key
        if template_key in ("formula_relation", "formula_replacement") and entity_type == "Formula":
            return "formula_relation"
        if template_key in {"constitution_recommendation", "product_recommendation"}:
            return "entity_explanation"
        return "entity_explanation"

    def _entities_from_recommendation_graph(self, graph: dict, template_key: str) -> list[dict]:
        preferred_types = (
            ["Product", "ConsumerProfile", "ConsumerSegment", "Formula", "Herb"]
            if template_key == "product_recommendation"
            else ["ConstitutionType", "Formula", "Herb", "Symptom", "Product"]
        )
        rank_map = {node_type: index for index, node_type in enumerate(preferred_types)}
        nodes = [
            node
            for node in graph.get("nodes", [])
            if node.get("type") in rank_map
        ]
        nodes = sorted(
            nodes,
            key=lambda node: (
                rank_map.get(node.get("type"), 99),
                -float(node.get("score", 0) or 0),
                node.get("label", ""),
            ),
        )
        entities: list[dict] = []
        seen_names: set[tuple[str, str]] = set()
        for node in nodes:
            identity = ((node.get("label") or "").strip(), node.get("type", "Entity"))
            if identity in seen_names:
                continue
            seen_names.add(identity)
            entities.append(
                {
                    "id": node["id"],
                    "name": node.get("label") or node["id"],
                    "entity_type": node.get("type", "Entity"),
                    "props": node.get("props", {}),
                    "score": node.get("score", 1.0),
                    "aliases": [],
                }
            )
            if len(entities) >= 6:
                break
        return entities

    def _dedupe_entities(self, entities: list[dict]) -> list[dict]:
        output: list[dict] = []
        seen_ids: set[str] = set()
        seen_names: set[tuple[str, str]] = set()
        for entity in entities:
            entity_id = entity.get("id")
            identity = ((entity.get("name") or "").strip(), entity.get("entity_type", "Entity"))
            if entity_id in seen_ids or identity in seen_names:
                continue
            output.append(entity)
            if entity_id:
                seen_ids.add(entity_id)
            seen_names.add(identity)
        return output

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

        if any(token in question for token in ["成分", "成份", "化合物"]) and not self._has_related_type(graph, entity_id, "Compound"):
            self._add_note_node(graph, entity_id, "compound_note", "当前知识图谱未找到该实体的直接成分/化合物关系")
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
            "CONTAINS": 16,
            "HAS_EFFECT": 14,
            "HAS_COMPOUND_EFFECT": 12,
            "CAN_REPLACE": 10,
            "HAS_CONSUMER_PROFILE": 10,
            "MATCHES_CONSUMER_SEGMENT": 10,
            "TOP_PRODUCT": 10,
            "USES_HERB": 12,
            "PREFERS_FLAVOR": 8,
            "DISLIKES_FLAVOR": 8,
            "ASSESSES_CONSTITUTION": 12,
            "TREATS": 10,
            "TARGETS_SYMPTOM": 10,
            "HAS_FLAVOR": 8,
            "PRODUCES_FLAVOR": 8,
            "HAS_NATURE_FLAVOR": 8,
            "ENTERS_MERIDIAN": 8,
            "HAS_TABOO": 6,
            "IN_FORMULA": 10,
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
            "Compound": 7,
            "Effect": 8,
            "EffectCategory": 9,
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
            "USES_HERB": 3,
            "IN_FORMULA": 3,
            "MONARCH_HERB": 3,
            "MINISTER_HERB": 3,
            "ASSISTANT_HERB": 3,
            "GUIDE_HERB": 3,
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
        return order.get(edge_type, 9)

    def _stringify(self, value: str | list[str]) -> str:
        if isinstance(value, list):
            return "、".join(str(item) for item in value[:8])
        return str(value)
