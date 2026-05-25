from difflib import SequenceMatcher
from datetime import datetime, timezone
import json as json_module
import logging
import re
from pathlib import Path
from time import perf_counter
from typing import Generator

from app.repositories.postgres_repository import PostgresRepository
from app.services.entity_resolver import EntityResolver
from app.services.graph_retriever import GraphRetriever
from app.services.minimax_client import MiniMaxClient
from app.services.qa_answer_templates import (
    compose_constraints_block,
    context_answer_rules,
    enforce_conclusion_structure,
    outline_for_question_type,
)
from app.services.question_classifier import QuestionClassifier


logger = logging.getLogger(__name__)

ROLE_DISPLAY = {
    "monarch": "君药",
    "minister": "臣药",
    "assistant": "佐药",
    "guide": "使药",
    "MONARCH_HERB": "君药",
    "MINISTER_HERB": "臣药",
    "ASSISTANT_HERB": "佐药",
    "GUIDE_HERB": "使药",
}

ROLE_PROP_FIELDS = {
    "君药": "monarch_herb",
    "臣药": "minister_herb",
    "佐药": "assistant_herb",
    "使药": "guide_herb",
}


class QAOrchestrator:
    def __init__(
        self,
        postgres_repository: PostgresRepository,
        entity_resolver: EntityResolver,
        graph_retriever: GraphRetriever,
        minimax_client: MiniMaxClient,
    ) -> None:
        self.postgres_repository = postgres_repository
        self.entity_resolver = entity_resolver
        self.graph_retriever = graph_retriever
        self.minimax_client = minimax_client
        self.classifier = QuestionClassifier()

    def ask(self, session_id: str, question: str) -> dict:
        session = self.postgres_repository.get_chat_session(session_id)
        if session is None:
            raise ValueError("Session not found")

        self.postgres_repository.create_message(session_id, "user", question)
        session.last_question = question
        session.title = session.title or question[:40]

        question_type = self.classifier.classify(question)
        started = perf_counter()
        entities = self.entity_resolver.resolve(question, preferred_types=self._preferred_types(question_type))
        if self._should_use_llm_analysis(question, entities):
            question_analysis, analysis_ms = self.minimax_client.analyze_question(question, entities)
        else:
            question_analysis = self.minimax_client.local_analyze_question(question)
            analysis_ms = 0
        question_type = self._refine_question_type(question_type, question_analysis)
        entities = self.entity_resolver.resolve_terms(
            self._build_search_terms(question, question_analysis, entities),
            preferred_types=self._preferred_types(question_type),
        )
        template_key, graph, selected_entities = self.graph_retriever.retrieve(question, entities, question_type)
        retrieval_ms = int((perf_counter() - started) * 1000)

        context = self._build_llm_context(
            question, question_type, entities, selected_entities, graph, question_analysis,
            chat_history=self._recent_chat_history(session_id),
        )
        prompt = self.postgres_repository.get_prompt_template_by_key("qa_default")
        system_prompt = self._compose_system_prompt(
            prompt.system_prompt if prompt is not None else self._default_system_prompt(),
            question_type,
        )
        llm_payload, answer_llm_ms = self.minimax_client.generate_answer(context, system_prompt)
        llm_ms = analysis_ms + answer_llm_ms

        answer_payload = self._normalize_answer_payload(llm_payload, selected_entities)
        answer_payload = self._backfill_answer_payload(answer_payload, selected_entities, graph)
        answer_payload = self._finalize_answer_payload(answer_payload, question_type)
        if answer_payload.get("_fallback") or not self._has_substantive_evidence(graph):
            local_error = llm_payload.get("cautions", "") if answer_payload.get("_fallback") else ""
            answer_payload = self._build_local_answer(question, question_type, selected_entities, graph, local_error)
            llm_ms = 0
        elif answer_payload.get("evidence_summary"):
            rewritten_conclusion, rewrite_llm_ms = self.minimax_client.rewrite_answer(
                question=question,
                question_type=question_type,
                draft_conclusion=answer_payload.get("conclusion", ""),
                evidence_summary=answer_payload.get("evidence_summary", ""),
                selected_entities=selected_entities,
                graph_metrics=graph.get("metrics", {}),
            )
            answer_payload["conclusion"] = rewritten_conclusion
            answer_payload = self._finalize_answer_payload(answer_payload, question_type)
            llm_ms += rewrite_llm_ms

        answer_payload, extracted_think = self._separate_answer_thinking(answer_payload)
        think_content = self._merge_text_blocks(llm_payload.get("_think_content", ""), extracted_think)

        snapshot = self.postgres_repository.create_graph_snapshot(session_id, question, graph)
        trace_summary = (
            f"识别到 {len(entities)} 个候选实体，纳入回答的实体 {len(selected_entities)} 个，"
            f"问题解析类型 {question_type}，使用模板 {template_key}，返回 {graph['metrics']['nodeCount']} 个节点和 {graph['metrics']['edgeCount']} 条边。"
        )

        self.postgres_repository.create_message(
            session_id,
            "assistant",
            answer_payload.get("conclusion", ""),
            extra_payload={
                "evidence_summary": answer_payload.get("evidence_summary", ""),
                "cautions": answer_payload.get("cautions", ""),
                "related_entities": answer_payload.get("related_entities", []),
                "follow_up_questions": answer_payload.get("follow_up_questions", []),
                "graph_snapshot_id": snapshot.id,
                "answer_mode": "llm_grounded" if llm_ms > 0 else "graph_fallback",
                "question_analysis": question_analysis,
                "think_content": think_content,
            },
        )
        self.postgres_repository.create_trace(
            session_id=session_id,
            question=question,
            question_type=question_type,
            entities=selected_entities or entities,
            cypher_template_key=template_key,
            trace_summary=trace_summary,
            retrieval_ms=retrieval_ms,
            llm_ms=llm_ms,
            graph_snapshot_id=snapshot.id,
            reasoning_payload={
                "reasoning_details": llm_payload.get("_reasoning_details"),
                "think_content": think_content,
                "question_analysis": question_analysis,
            },
        )
        self.postgres_repository.session.commit()
        return {
            "session_id": session_id,
            "answer": answer_payload.get("conclusion", ""),
            "evidence_summary": answer_payload.get("evidence_summary", ""),
            "related_entities": answer_payload.get("related_entities", []),
            "graph_snapshot_id": snapshot.id,
            "trace_summary": trace_summary,
            "cautions": answer_payload.get("cautions", ""),
            "follow_up_questions": answer_payload.get("follow_up_questions", []),
            "answer_mode": "llm_grounded" if llm_ms > 0 else "graph_fallback",
        }

    def ask_stream(self, session_id: str, question: str) -> Generator[str, None, None]:
        """Stream Q&A response as SSE events. User message is already persisted by the route."""
        try:
            # Phase 1: Fast preprocessing
            question_type = self.classifier.classify(question)
            started = perf_counter()
            entities = self.entity_resolver.resolve(question, preferred_types=self._preferred_types(question_type))
            if self._should_use_llm_analysis(question, entities):
                question_analysis, analysis_ms = self.minimax_client.analyze_question(question, entities)
            else:
                question_analysis = self.minimax_client.local_analyze_question(question)
                analysis_ms = 0
            question_type = self._refine_question_type(question_type, question_analysis)
            entities = self.entity_resolver.resolve_terms(
                self._build_search_terms(question, question_analysis, entities),
                preferred_types=self._preferred_types(question_type),
            )
            template_key, graph, selected_entities = self.graph_retriever.retrieve(question, entities, question_type)

            context = self._build_llm_context(
                question, question_type, entities, selected_entities, graph, question_analysis,
                chat_history=self._recent_chat_history(session_id),
            )
            prompt = self.postgres_repository.get_prompt_template_by_key("qa_default")
            system_prompt = self._compose_system_prompt(
                prompt.system_prompt if prompt is not None else self._default_system_prompt(),
                question_type,
            )

            # Phase 2: Stream LLM conclusion (with separated think blocks)
            full_conclusion = ""
            full_think = ""
            emitted_answer = False
            answer_buffer = ""
            buffering_json_answer: bool | None = None
            for chunk in self.minimax_client.generate_answer_stream(context, system_prompt):
                event_type = chunk["event"]
                text = chunk["text"]
                if event_type == "think":
                    full_think += text
                    yield self._sse("think", {"text": text})
                else:
                    full_conclusion += text
                    if buffering_json_answer is None:
                        answer_buffer += text
                        stripped = answer_buffer.lstrip()
                        if not stripped:
                            continue
                        buffering_json_answer = self._looks_like_json_answer(stripped)
                        if buffering_json_answer:
                            continue
                        emitted_answer = True
                        yield self._sse("token", {"text": answer_buffer})
                        answer_buffer = ""
                    elif buffering_json_answer:
                        answer_buffer += text
                    else:
                        emitted_answer = True
                        yield self._sse("token", {"text": text})

            if answer_buffer and not buffering_json_answer:
                emitted_answer = True
                yield self._sse("token", {"text": answer_buffer})

            # Phase 3: Build evidence and persist
            streamed_payload = self._parse_streamed_answer(full_conclusion)
            has_streamed_conclusion = bool(streamed_payload.get("conclusion", "").strip())
            if has_streamed_conclusion:
                answer_payload = self._normalize_answer_payload(streamed_payload, selected_entities)
                answer_payload = self._backfill_answer_payload(answer_payload, selected_entities, graph)
                answer_payload = self._finalize_answer_payload(answer_payload, question_type)
            else:
                answer_payload = self._build_local_answer(question, question_type, selected_entities, graph, "")
            answer_payload, extracted_think = self._separate_answer_thinking(answer_payload)
            full_think = self._merge_text_blocks(full_think, extracted_think)
            answer_mode = "llm_grounded" if has_streamed_conclusion else "graph_fallback"
            if not emitted_answer and answer_payload.get("conclusion", "").strip():
                yield self._sse("token", {"text": answer_payload["conclusion"]})

            snapshot = self.postgres_repository.create_graph_snapshot(session_id, question, graph)

            self.postgres_repository.create_message(
                session_id,
                "assistant",
                answer_payload.get("conclusion", ""),
                extra_payload={
                    "evidence_summary": answer_payload.get("evidence_summary", ""),
                    "cautions": answer_payload.get("cautions", ""),
                    "related_entities": answer_payload.get("related_entities", []),
                    "follow_up_questions": answer_payload.get("follow_up_questions", []),
                    "graph_snapshot_id": snapshot.id,
                    "answer_mode": answer_mode,
                    "question_analysis": question_analysis,
                    "think_content": full_think.strip(),
                },
            )

            retrieval_ms = int((perf_counter() - started) * 1000)
            trace_summary = (
                f"识别到 {len(entities)} 个候选实体，纳入回答的实体 {len(selected_entities)} 个，"
                f"问题解析类型 {question_type}，使用模板 {template_key}，返回 {graph['metrics']['nodeCount']} 个节点和 {graph['metrics']['edgeCount']} 条边。"
            )
            self.postgres_repository.create_trace(
                session_id=session_id,
                question=question,
                question_type=question_type,
                entities=selected_entities or entities,
                cypher_template_key=template_key,
                trace_summary=trace_summary,
                retrieval_ms=retrieval_ms,
                llm_ms=0,
                graph_snapshot_id=snapshot.id,
                reasoning_payload={
                    "question_analysis": question_analysis,
                },
            )
            self.postgres_repository.session.commit()

            yield self._sse("evidence", {
                "evidence_summary": answer_payload.get("evidence_summary", ""),
                "related_entities": answer_payload.get("related_entities", []),
                "cautions": answer_payload.get("cautions", ""),
                "follow_up_questions": answer_payload.get("follow_up_questions", []),
                "answer_mode": answer_mode,
            })

            yield self._sse("graph", {
                "nodes": graph.get("nodes", []),
                "edges": graph.get("edges", []),
                "focus_paths": graph.get("focus_paths", []),
                "legend": graph.get("legend", {}),
                "metrics": graph.get("metrics", {}),
            })

            yield self._sse("done", {"session_id": session_id})

        except Exception as exc:
            logger.exception("Knowledge QA stream failed for session_id=%s", session_id)
            self.postgres_repository.create_message(
                session_id,
                "assistant",
                "系统处理请求时遇到错误，请稍后重试。",
                extra_payload={
                    "evidence_summary": "",
                    "cautions": f"处理出错：{exc}",
                    "related_entities": [],
                    "follow_up_questions": [],
                    "answer_mode": "error",
                },
            )
            try:
                self.postgres_repository.session.commit()
            except Exception:
                pass
            yield self._sse("error", {"message": str(exc)})

    @staticmethod
    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"

    def _parse_streamed_answer(self, raw_text: str) -> dict:
        """Normalize streamed model text into the same payload shape as non-stream answers."""
        cleaned = self.minimax_client._remove_think_blocks(raw_text or "")
        if not cleaned.strip():
            return {}
        if self._looks_like_json_answer(cleaned):
            parsed = self.minimax_client._parse_json_text(cleaned)
            return parsed
        return {"conclusion": cleaned.strip()}

    @staticmethod
    def _looks_like_json_answer(text: str) -> bool:
        stripped = (text or "").lstrip()
        return (
            stripped.startswith("{")
            or stripped.startswith("```")
            or stripped.startswith('"conclusion"')
            or '"evidence_summary"' in stripped[:160]
            or '"related_entities"' in stripped[:200]
        )

    def _preferred_types(self, question_type: str) -> list[str]:
        mapping = {
            "herb_efficacy": ["Herb", "Formula", "Compound", "Effect", "Symptom", "NatureFlavor", "Meridian"],
            "formula_relation": ["Formula", "Herb", "Compound", "Symptom"],
            "formula_replacement": ["Formula", "Herb", "Compound", "Symptom", "Taboo"],
            "constitution_recommendation": ["ConstitutionType", "ConstitutionQuestion", "Formula", "Herb", "Symptom", "Product"],
            "product_recommendation": ["Product", "ConsumerProfile", "ConsumerSegment", "Herb", "Flavor", "Effect", "Formula"],
            "entity_explanation": ["Herb", "Compound", "Formula", "Effect", "Symptom", "Flavor", "NatureFlavor", "Meridian"],
        }
        return mapping.get(question_type, ["Herb", "Formula", "Compound", "Effect", "Symptom"])

    def _build_llm_context(
        self,
        question: str,
        question_type: str,
        entities: list[dict],
        selected_entities: list[dict],
        graph: dict,
        question_analysis: dict,
        chat_history: list[dict[str, str]] | None = None,
    ) -> dict:
        node_lookup = {node["id"]: node for node in graph.get("nodes", [])}
        edge_summaries = []
        for edge in graph.get("edges", [])[:50]:
            source = node_lookup.get(edge["source"], {"label": edge["source"], "type": "Entity"})
            target = node_lookup.get(edge["target"], {"label": edge["target"], "type": "Entity"})
            summary = {
                "source_id": edge["source"],
                "source_label": source["label"],
                "source_type": source.get("type", "Entity"),
                "relation": edge["type"],
                "target_id": edge["target"],
                "target_label": target["label"],
                "target_type": target.get("type", "Entity"),
            }
            edge_props = edge.get("props", {})
            if edge["type"] == "CAN_REPLACE" and edge_props:
                summary["replacement_score"] = edge_props.get("final_score") or edge_props.get("score")
                summary["rank"] = edge_props.get("rank")
                summary["effect_similarity"] = edge_props.get("effect_similarity")
                summary["flavor_acceptance"] = edge_props.get("flavor_acceptance")
                summary["source_type"] = edge_props.get("source_type")
                summary["candidate_source"] = edge_props.get("candidate_source")
                summary["professional_score"] = edge_props.get("professional_score")
                summary["safety_score"] = edge_props.get("safety_score")
                summary["recommendation_status"] = edge_props.get("recommendation_status")
                summary["contraindication"] = edge_props.get("contraindication")
            elif edge["type"] in {"HAS_CONSUMER_PROFILE", "MATCHES_CONSUMER_SEGMENT", "TOP_PRODUCT"} and edge_props:
                summary["positive_rate"] = edge_props.get("positive_rate")
                summary["review_count"] = edge_props.get("review_count")
                summary["rank"] = edge_props.get("rank")
            elif edge["type"] in {"PREFERS_FLAVOR", "DISLIKES_FLAVOR"} and edge_props:
                summary["source"] = edge_props.get("source")
            edge_summaries.append(summary)

        entity_profiles = []
        for entity in selected_entities[:6]:
            props = entity.get("props", {})
            etype = entity.get("entity_type", "Entity")
            if etype == "Formula":
                ep = {
                    "formula_name": props.get("formula_name"),
                    "source": props.get("source"),
                    "efficacy": props.get("efficacy"),
                    "ratio": props.get("ratio"),
                    "crowd": props.get("crowd"),
                    "taboo": props.get("taboo"),
                    "ingredients": props.get("ingredients"),
                    "monarch_herb": props.get("monarch_herb"),
                    "minister_herb": props.get("minister_herb"),
                    "assistant_herb": props.get("assistant_herb"),
                    "guide_herb": props.get("guide_herb"),
                }
            elif etype == "Herb":
                ep = {
                    "herb_name": props.get("herb_name"),
                    "food_homology": props.get("food_homology"),
                }
            elif etype == "Compound":
                ep = {
                    "compound_name": props.get("compound_name"),
                    "canonical_smiles": props.get("canonical_smiles"),
                    "mw": props.get("mw"),
                    "logp": props.get("logp"),
                    "ob": props.get("ob"),
                    "dl": props.get("dl"),
                }
            elif etype == "Product":
                ep = {
                    "product_id": props.get("product_id"),
                    "product_name": props.get("product_name"),
                    "brand": props.get("brand"),
                    "dosage_form": props.get("dosage_form"),
                    "claimed_effect": props.get("claimed_effect"),
                    "ingredients": props.get("ingredients"),
                    "price": props.get("price"),
                    "sales": props.get("sales"),
                    "rating": props.get("rating"),
                    "positive_rate": props.get("positive_rate"),
                    "review_count": props.get("review_count"),
                    "approval_no": props.get("approval_no"),
                    "specification": props.get("specification"),
                }
            elif etype == "ConsumerProfile":
                ep = {
                    "profile_id": props.get("profile_id"),
                    "product_name": props.get("product_name"),
                    "crowd_type": props.get("crowd_type"),
                    "core_need": props.get("core_need"),
                    "preferred_dosage": props.get("preferred_dosage"),
                    "preferred_flavor": props.get("preferred_flavor"),
                    "disliked_flavor": props.get("disliked_flavor"),
                    "price_sensitivity": props.get("price_sensitivity"),
                    "concern_points": props.get("concern_points"),
                    "agent_strategy": props.get("agent_strategy"),
                    "review_count": props.get("review_count"),
                    "positive_rate": props.get("positive_rate"),
                }
            elif etype == "ConsumerSegment":
                ep = {
                    "segment_key": props.get("segment_key"),
                    "segment_label": props.get("segment_label"),
                    "crowd_tags": props.get("crowd_tags"),
                    "scenario_tags": props.get("scenario_tags"),
                    "effect_tags": props.get("effect_tags"),
                    "review_count": props.get("review_count"),
                    "positive_rate": props.get("positive_rate"),
                    "top_flavor_tags": props.get("top_flavor_tags"),
                    "top_dosage_tags": props.get("top_dosage_tags"),
                    "top_complaint_tags": props.get("top_complaint_tags"),
                }
            elif etype == "ConstitutionType":
                ep = {
                    "constitution_type_name": props.get("constitution_type_name"),
                    "item_count": props.get("item_count"),
                    "judgement_rule": props.get("judgement_rule"),
                    "source": props.get("source"),
                }
            elif etype == "ConstitutionQuestion":
                ep = {
                    "question_code": props.get("question_code"),
                    "constitution_type_name": props.get("constitution_type_name"),
                    "question_no": props.get("question_no"),
                    "question_text": props.get("question_text"),
                    "reverse_scored": props.get("reverse_scored"),
                    "applicable_group": props.get("applicable_group"),
                    "source_page": props.get("source_page"),
                }
            else:
                ep = {}
            entity_profiles.append(
                {
                    "id": entity["id"],
                    "name": entity.get("name") or entity["id"],
                    "entity_type": etype,
                    "score": entity.get("score", 0),
                    "properties": ep,
                }
            )

        return {
            "question": question,
            "question_type": question_type,
            "question_analysis": question_analysis,
            "chat_history": chat_history or [],
            "resolved_entities": [
                {
                    "id": entity["id"],
                    "name": entity.get("name") or entity["id"],
                    "entity_type": entity.get("entity_type", "Entity"),
                    "score": entity.get("score", 0),
                }
                for entity in entities[:12]
            ],
            "selected_entities": entity_profiles,
            "graph_metrics": graph.get("metrics", {}),
            "evidence_nodes": graph.get("nodes", [])[:40],
            "evidence_edges": edge_summaries,
            "focus_paths": graph.get("focus_paths", [])[:8],
            "formula_details": self._build_formula_details(selected_entities, graph),
            "recommendation_context": self._build_recommendation_context(graph),
            "answer_outline": outline_for_question_type(question_type),
            "answer_rules": context_answer_rules(question_type),
        }

    def _build_recommendation_context(self, graph: dict) -> dict:
        products: list[dict] = []
        consumer_profiles: list[dict] = []
        consumer_segments: list[dict] = []
        constitution_types: list[dict] = []
        constitution_questions: list[dict] = []
        replacements: list[dict] = []

        node_lookup = {node["id"]: node for node in graph.get("nodes", [])}
        for node in graph.get("nodes", []):
            props = node.get("props", {}) or {}
            node_type = node.get("type")
            if node_type == "Product":
                products.append(
                    {
                        "product_id": props.get("product_id") or node["id"],
                        "product_name": props.get("product_name") or node.get("label"),
                        "brand": props.get("brand"),
                        "dosage_form": props.get("dosage_form"),
                        "claimed_effect": props.get("claimed_effect"),
                        "ingredients": props.get("ingredients"),
                        "price": props.get("price"),
                        "sales": props.get("sales"),
                        "rating": props.get("rating"),
                        "positive_rate": props.get("positive_rate"),
                        "review_count": props.get("review_count"),
                        "approval_no": props.get("approval_no"),
                        "specification": props.get("specification"),
                    }
                )
            elif node_type == "ConsumerProfile":
                consumer_profiles.append(
                    {
                        "profile_id": props.get("profile_id") or node["id"],
                        "product_name": props.get("product_name") or node.get("label"),
                        "crowd_type": props.get("crowd_type"),
                        "core_need": props.get("core_need"),
                        "preferred_dosage": props.get("preferred_dosage"),
                        "preferred_flavor": props.get("preferred_flavor"),
                        "disliked_flavor": props.get("disliked_flavor"),
                        "price_sensitivity": props.get("price_sensitivity"),
                        "concern_points": props.get("concern_points"),
                        "agent_strategy": props.get("agent_strategy"),
                        "positive_rate": props.get("positive_rate"),
                        "review_count": props.get("review_count"),
                    }
                )
            elif node_type == "ConsumerSegment":
                consumer_segments.append(
                    {
                        "segment_label": props.get("segment_label") or node.get("label"),
                        "crowd_tags": props.get("crowd_tags"),
                        "scenario_tags": props.get("scenario_tags"),
                        "effect_tags": props.get("effect_tags"),
                        "review_count": props.get("review_count"),
                        "positive_rate": props.get("positive_rate"),
                        "top_product_ids": props.get("top_product_ids"),
                        "top_flavor_tags": props.get("top_flavor_tags"),
                        "top_dosage_tags": props.get("top_dosage_tags"),
                        "top_complaint_tags": props.get("top_complaint_tags"),
                    }
                )
            elif node_type == "ConstitutionType":
                constitution_types.append(
                    {
                        "constitution_type_name": props.get("constitution_type_name") or node.get("label"),
                        "item_count": props.get("item_count"),
                        "judgement_rule": props.get("judgement_rule"),
                        "source": props.get("source"),
                    }
                )
            elif node_type == "ConstitutionQuestion":
                constitution_questions.append(
                    {
                        "question_code": props.get("question_code") or node["id"],
                        "constitution_type_name": props.get("constitution_type_name"),
                        "question_no": props.get("question_no"),
                        "question_text": props.get("question_text") or node.get("label"),
                        "reverse_scored": props.get("reverse_scored"),
                    }
                )

        for edge in graph.get("edges", []):
            if edge.get("type") != "CAN_REPLACE":
                continue
            props = edge.get("props", {}) or {}
            source = node_lookup.get(edge.get("source"), {})
            target = node_lookup.get(edge.get("target"), {})
            replacements.append(
                {
                    "source_herb": source.get("label") or edge.get("source"),
                    "target_herb": target.get("label") or edge.get("target"),
                    "model": props.get("model"),
                    "candidate_source": props.get("candidate_source") or props.get("source_type"),
                    "rank": props.get("rank"),
                    "final_score": props.get("final_score") or props.get("score"),
                    "professional_score": props.get("professional_score"),
                    "effect_similarity": props.get("effect_similarity"),
                    "flavor_acceptance": props.get("flavor_acceptance"),
                    "safety_score": props.get("safety_score"),
                    "recommendation_status": props.get("recommendation_status"),
                    "contraindication": props.get("contraindication"),
                }
            )

        return {
            "products": products[:8],
            "consumer_profiles": consumer_profiles[:8],
            "consumer_segments": consumer_segments[:8],
            "constitution_types": constitution_types[:6],
            "constitution_questions": constitution_questions[:12],
            "replacement_options": replacements[:12],
        }

    def _build_local_answer(
        self,
        question: str,
        question_type: str,
        selected_entities: list[dict],
        graph: dict,
        llm_error: str,
    ) -> dict:
        if not selected_entities:
            return {
                "conclusion": (
                    "【核心结论】\n"
                    "当前没有在知识图谱中稳定识别出与问题对应的实体，因此暂时无法给出可靠回答。\n\n"
                    "【注意事项】\n"
                    "建议把问题改成更明确的实体名、症状名或方剂名。\n\n"
                    "【总结建议】\n"
                    "本次未形成足够稳定的图谱证据链，系统不会补充图谱外结论。请补充明确的药材、方剂或症状名称后再查询。"
                ),
                "evidence_summary": "这次检索没有形成足够稳定的图谱命中结果。",
                "cautions": llm_error or "建议把问题改成更明确的实体名、症状名、方剂名。",
                "related_entities": [],
                "follow_up_questions": ["请直接输入一个药材名或症状名", "请把问题拆成更短的几个实体词"],
            }

        names = [entity.get("name") or entity["id"] for entity in selected_entities[:6]]
        node_lookup = {node["id"]: node for node in graph.get("nodes", [])}
        related_groups = {
            "Formula": [],
            "Compound": [],
            "Effect": [],
            "Herb": [],
            "Symptom": [],
            "Taboo": [],
            "Product": [],
            "ConsumerProfile": [],
            "ConsumerSegment": [],
            "ConstitutionType": [],
            "ConstitutionQuestion": [],
        }
        for node in graph.get("nodes", []):
            node_type = node.get("type", "Entity")
            if node_type in related_groups and node["id"] not in {entity["id"] for entity in selected_entities}:
                if node["label"] not in related_groups[node_type]:
                    related_groups[node_type].append(node["label"])

        conclusion_parts = [f"【核心结论】\n本次问题命中了多个图谱实体：{'、'.join(names)}。"]
        if question_type == "formula_replacement":
            conclusion_parts.append("系统已按方剂药材替换问题进行联合检索，提取了药材的 CAN_REPLACE 替代关系及综合评分。")
        elif question_type == "constitution_recommendation":
            conclusion_parts.append("系统已按体质辅助推荐问题进行联合检索，提取了体质量表、药食同源药材和方剂证据。")
        elif question_type == "product_recommendation":
            conclusion_parts.append("系统已按消费者/成药产品推荐问题进行联合检索，提取了产品、消费者画像和人群场景聚合证据。")
        elif question_type == "formula_relation":
            conclusion_parts.append("系统已按方剂相关问题进行联合检索，并尝试从这些实体向外扩展方剂和药材证据。")
        else:
            conclusion_parts.append("系统已基于这些实体的图谱邻居和属性证据进行联合检索。")

        formula_detail_lines = self._build_formula_detail_lines(selected_entities, graph)
        if formula_detail_lines:
            conclusion_parts.append(f"【方剂组成与剂量】\n{chr(10).join(formula_detail_lines)}")

        evidence_parts: list[str] = []
        if related_groups["Formula"]:
            evidence_parts.append(f"当前命中的相关方剂包括：{self._join_names(related_groups['Formula'])}。")
        else:
            evidence_parts.append("当前图谱中没有检索到与这些命中实体直接连通的方剂证据。")

        if related_groups["Product"]:
            evidence_parts.append(f"当前命中的相关产品包括：{self._join_names(related_groups['Product'])}。")
        if related_groups["ConsumerProfile"]:
            evidence_parts.append(f"当前命中的消费者画像包括：{self._join_names(related_groups['ConsumerProfile'])}。")
        if related_groups["ConsumerSegment"]:
            evidence_parts.append(f"当前命中的消费者分组包括：{self._join_names(related_groups['ConsumerSegment'])}。")
        if related_groups["ConstitutionType"]:
            evidence_parts.append(f"当前命中的体质类型包括：{self._join_names(related_groups['ConstitutionType'])}。")
        if related_groups["Compound"]:
            evidence_parts.append(f"当前命中的相关化合物包括：{self._join_names(related_groups['Compound'][:12])}。")
        if related_groups["Effect"]:
            evidence_parts.append(f"当前命中的相关功效包括：{self._join_names(related_groups['Effect'][:12])}。")
        if related_groups["Herb"]:
            evidence_parts.append(f"当前命中的相关药材包括：{self._join_names(related_groups['Herb'])}。")
        if related_groups["Symptom"]:
            evidence_parts.append(f"当前命中的相关症状包括：{self._join_names(related_groups['Symptom'][:12])}。")
        evidence_text = "\n".join(evidence_parts)
        conclusion_parts.append(f"【图谱依据】\n{evidence_text}")

        evidence_lines = [
            f"本次纳入回答的实体共有 {len(selected_entities)} 个：{'、'.join(names)}。",
            f"证据子图返回 {graph['metrics']['nodeCount']} 个节点、{graph['metrics']['edgeCount']} 条边。",
        ]

        cautions = llm_error or "当前回答已退回到本地图谱证据总结模式。"
        cautions += "\n系统不会在知识图谱缺少直接证据时自行补充疾病、证候或方剂结论。"
        if not related_groups["Formula"] and any(token in question for token in ["方剂", "方子", "方"]):
            cautions += "\n知识图谱目前没有给出这些命中实体到方剂的直接连接证据。"
        conclusion_parts.append(f"【注意事项】\n{cautions}")
        conclusion_parts.append("【总结建议】\n以上内容仅基于当前知识图谱命中的节点、关系和属性生成。如果涉及实际用药，请结合专业医师辨证；如果需要更精确的方剂剂量，请继续追问具体方剂名称。")

        related_entities = [
            {
                "id": entity["id"],
                "name": entity.get("name") or entity["id"],
                "entity_type": entity.get("entity_type", "Entity"),
            }
            for entity in selected_entities[:12]
        ]
        for edge in graph.get("edges", [])[:12]:
            for node_id in [edge["source"], edge["target"]]:
                node = node_lookup.get(node_id)
                if node is None or node["type"] in {"Question", "Attribute", "EvidenceNote"}:
                    continue
                item = {"id": node["id"], "name": node["label"], "entity_type": node.get("type", "Entity")}
                if item not in related_entities:
                    related_entities.append(item)

        return {
            "conclusion": "\n".join(conclusion_parts),
            "evidence_summary": "\n".join(evidence_lines),
            "cautions": cautions,
            "related_entities": related_entities[:20],
            "follow_up_questions": self._build_follow_ups(selected_entities),
        }

    def _build_formula_detail_lines(self, selected_entities: list[dict], graph: dict) -> list[str]:
        formula_details = self._build_formula_details(selected_entities, graph)
        formula_lines: list[str] = []
        for detail in formula_details:
            role_lines: list[str] = []
            for role_label in ["君药", "臣药", "佐药", "使药", "角色未标注"]:
                herbs = detail.get("roles", {}).get(role_label, [])
                if not herbs:
                    continue
                herb_items = [
                    f"{item['name']}：{item.get('dosage') or '图谱未提供剂量'}"
                    for item in herbs
                ]
                role_lines.append(f"{role_label}：" + "；".join(herb_items))

            detail_parts = [detail["formula_name"]]
            if detail.get("source"):
                detail_parts.append(f"出处：{detail['source']}")
            if detail.get("efficacy"):
                detail_parts.append(f"功效：{detail['efficacy']}")
            if detail.get("crowd"):
                detail_parts.append(f"适用/主治：{detail['crowd']}")
            detail_parts.append("组成明细：" + ("；".join(role_lines) if role_lines else "图谱未提供药材剂量明细"))
            if detail.get("taboo"):
                detail_parts.append(f"禁忌：{detail['taboo']}")
            formula_lines.append("\n".join(detail_parts))
        return formula_lines[:6]

    def _build_formula_details(self, selected_entities: list[dict], graph: dict) -> list[dict]:
        node_lookup = {node["id"]: node for node in graph.get("nodes", [])}
        formula_ids: set[str] = set()

        for entity in selected_entities:
            if entity.get("entity_type") == "Formula":
                formula_ids.add(entity["id"])
        for node in graph.get("nodes", []):
            if node.get("type") == "Formula":
                formula_ids.add(node["id"])

        details: list[dict] = []
        for formula_id in formula_ids:
            node = node_lookup.get(formula_id)
            formula_name = formula_id
            props = {}
            if node is not None:
                formula_name = node.get("label") or formula_id
                props = node.get("props", {}) or {}

            role_map = self._formula_role_map(formula_id, props, graph, node_lookup)
            dosage_map = self._formula_dosage_map(formula_id, props, graph, node_lookup)
            ingredient_names = self._formula_ingredient_names(props, role_map, dosage_map)
            roles: dict[str, list[dict[str, str]]] = {role: [] for role in ["君药", "臣药", "佐药", "使药", "角色未标注"]}
            for role_label in ["君药", "臣药", "佐药", "使药", "角色未标注"]:
                names = role_map.get(role_label, [])
                if role_label == "角色未标注":
                    names = [name for name in ingredient_names if not self._role_for_herb(name, role_map)]
                if not names:
                    continue
                roles[role_label] = [
                    {
                        "name": name,
                        "role": role_label,
                        "dosage": dosage_map.get(name) or "图谱未提供剂量",
                    }
                    for name in names
                ]
            details.append(
                {
                    "formula_name": formula_name,
                    "source": props.get("source") or "",
                    "efficacy": props.get("efficacy") or "",
                    "crowd": props.get("crowd") or "",
                    "taboo": props.get("taboo") or "",
                    "ratio": props.get("ratio") or "",
                    "ingredients": ingredient_names,
                    "roles": {role: herbs for role, herbs in roles.items() if herbs},
                }
            )

        return details[:6]

    def _formula_role_map(
        self,
        formula_id: str,
        props: dict,
        graph: dict,
        node_lookup: dict[str, dict],
    ) -> dict[str, list[str]]:
        role_map: dict[str, list[str]] = {role: [] for role in ["君药", "臣药", "佐药", "使药"]}

        for role_label, field in ROLE_PROP_FIELDS.items():
            for name in self._split_herb_names(props.get(field)):
                self._append_unique(role_map[role_label], name)

        for edge in graph.get("edges", []):
            role_label = None
            herb_name = None
            if edge.get("source") == formula_id and edge.get("type") in ROLE_DISPLAY:
                role_label = ROLE_DISPLAY.get(edge.get("type"))
                herb = node_lookup.get(edge.get("target"), {})
                herb_name = herb.get("label") or edge.get("target")
            elif edge.get("type") == "IN_FORMULA" and edge.get("target") == formula_id:
                role_label = ROLE_DISPLAY.get((edge.get("props") or {}).get("role", ""))
                herb = node_lookup.get(edge.get("source"), {})
                herb_name = herb.get("label") or edge.get("source")

            if role_label and herb_name:
                self._append_unique(role_map[role_label], herb_name)

        return role_map

    def _formula_dosage_map(
        self,
        formula_id: str,
        props: dict,
        graph: dict,
        node_lookup: dict[str, dict],
    ) -> dict[str, str]:
        dosage_map = self._parse_ratio_dosages(props.get("ratio"))
        for edge in graph.get("edges", []):
            if edge.get("type") != "IN_FORMULA" or edge.get("target") != formula_id:
                continue
            herb = node_lookup.get(edge.get("source"), {})
            herb_name = herb.get("label") or edge.get("source")
            edge_props = edge.get("props", {}) or {}
            dosage = edge_props.get("dosage")
            if dosage:
                dosage_map[herb_name] = str(dosage)
        return dosage_map

    def _formula_ingredient_names(
        self,
        props: dict,
        role_map: dict[str, list[str]],
        dosage_map: dict[str, str],
    ) -> list[str]:
        names: list[str] = []
        for name in self._split_herb_names(props.get("ingredients")):
            self._append_unique(names, name)
        for role_names in role_map.values():
            for name in role_names:
                self._append_unique(names, name)
        for name in dosage_map:
            self._append_unique(names, name)
        return names

    @staticmethod
    def _role_for_herb(herb_name: str, role_map: dict[str, list[str]]) -> str | None:
        for role_label, names in role_map.items():
            if herb_name in names:
                return role_label
        return None

    @staticmethod
    def _split_herb_names(value) -> list[str]:
        if not value:
            return []
        if isinstance(value, list):
            raw_items = value
        else:
            raw_items = re.split(r"[、,，;；/\\s]+", str(value))
        return [item.strip() for item in raw_items if item and str(item).strip()]

    @staticmethod
    def _parse_ratio_dosages(value) -> dict[str, str]:
        text = str(value or "").strip()
        if not text:
            return {}
        dosage_map: dict[str, str] = {}
        pattern = re.compile(r"([一-鿿]+)\s*([0-9]+(?:\.[0-9]+)?\s*(?:g|克|枚|片|钱|两))", re.I)
        for herb_name, dosage in pattern.findall(text):
            dosage_map[herb_name.strip()] = re.sub(r"\s+", "", dosage.strip())
        return dosage_map

    @staticmethod
    def _append_unique(items: list[str], value: str) -> None:
        cleaned = (value or "").strip()
        if cleaned and cleaned not in items:
            items.append(cleaned)

    def _build_follow_ups(self, selected_entities: list[dict]) -> list[str]:
        names = [entity.get("name") or entity["id"] for entity in selected_entities[:3]]
        if not names:
            return ["这个问题还可以拆成哪些更明确的实体？", "知识图谱里有没有更接近的药材名或症状名？"]
        joined = "、".join(names)
        return [
            f"{joined} 在知识图谱里还关联了哪些方剂或症状？",
            f"{joined} 的上下游证据链分别是什么？",
            f"如果只看 {names[0]}，还能展开出哪些成分或功效？",
        ]

    def _default_system_prompt(self) -> str:
        return (
            "你是药食同源知识问答助手。"
            "你只能基于提供的 Neo4j 知识图谱证据和实体属性回答，不能编造不存在的关系。"
            "如果问题里有多个实体、多个症状或多个子问题，必须整体回答，不能只抓住其中一个。"
            "如果某类证据缺失，要明确指出缺失的是方剂、成分还是功效证据。"
            "如果图谱没有给出直接证据，不要自行补充可能的疾病、证候、疗法或方剂。"
            "conclusion 必须写成用户可直接阅读的结构化答案，使用【核心结论】【图谱依据】【方剂组成与剂量】【注意事项】【总结建议】等小标题。"
            "【图谱依据】必须把图谱获得的方剂、药材、功效、症状、禁忌、证据边界分点展示，不能只给笼统回答。"
            "如果用户询问药方、方剂、开什么药或方剂替换，且图谱提供组成或剂量，必须列出药材和剂量；缺少剂量时明确写“图谱未提供剂量”。"
            "如果用户询问体质推荐或消费者/成药推荐，必须基于体质量表、产品、消费者画像和聚合分组证据，不得编造诊断或评论原文。"
            "conclusion 不要写成三元组或证据条目列表，不要直接复述 evidence_summary。"
            "evidence_summary 应该简短，只保留支撑答案的关键证据，不要与 conclusion 大段重复。"
            "cautions 只能写图谱证据缺失说明或使用范围提醒，不能引入图谱外医学常识。"
            "不要在 conclusion 中输出 <think>、</think> 或任何内部推理标签。"
            "请严格输出 JSON，对象字段必须包含 conclusion, evidence_summary, cautions, related_entities, follow_up_questions。"
            "其中 related_entities 和 follow_up_questions 必须是数组。"
        )

    def _has_substantive_evidence(self, graph: dict) -> bool:
        return any(
            edge["type"] not in {"MENTIONS", "LACKS_DIRECT_EVIDENCE"}
            for edge in graph.get("edges", [])
        )

    def _refine_question_type(self, current_question_type: str, question_analysis: dict) -> str:
        llm_question_type = question_analysis.get("question_type")
        recommendation_types = {"constitution_recommendation", "product_recommendation"}
        if current_question_type in recommendation_types and llm_question_type not in recommendation_types:
            return current_question_type
        if current_question_type == "formula_replacement" and llm_question_type == "entity_explanation":
            return current_question_type
        if llm_question_type in {
            "herb_efficacy",
            "formula_relation",
            "formula_replacement",
            "constitution_recommendation",
            "product_recommendation",
            "entity_explanation",
        }:
            return llm_question_type
        return current_question_type

    def _compose_system_prompt(self, base_prompt: str, question_type: str = "entity_explanation") -> str:
        markdown_rules = self._load_answer_rules_markdown()
        return (
            f"{base_prompt}\n"
            f"{markdown_rules}\n"
            f"{compose_constraints_block(question_type)}"
        )

    def _load_answer_rules_markdown(self) -> str:
        path = Path(__file__).resolve().parents[1] / "prompts" / "knowledge_qa_answer_rules.md"
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def _separate_answer_thinking(self, answer_payload: dict) -> tuple[dict, str]:
        payload = dict(answer_payload)
        extracted_blocks: list[str] = []
        for field in ["conclusion", "evidence_summary", "cautions"]:
            value = payload.get(field)
            if not isinstance(value, str) or "<think" not in value.lower():
                continue
            visible, think = self._extract_think_blocks(value)
            payload[field] = visible
            if think:
                extracted_blocks.append(think)
        return payload, self._merge_text_blocks(*extracted_blocks)

    @staticmethod
    def _extract_think_blocks(text: str) -> tuple[str, str]:
        think_blocks = re.findall(r"<think\b[^>]*>([\s\S]*?)(?:</think>|$)", text, flags=re.I)
        visible = re.sub(r"<think\b[^>]*>[\s\S]*?(?:</think>|$)", "", text, flags=re.I).strip()
        return visible, "\n\n".join(block.strip() for block in think_blocks if block.strip())

    @staticmethod
    def _merge_text_blocks(*blocks: str | None) -> str:
        merged: list[str] = []
        for block in blocks:
            cleaned = (block or "").strip()
            if cleaned and cleaned not in merged:
                merged.append(cleaned)
        return "\n\n".join(merged)

    def _should_use_llm_analysis(self, question: str, entities: list[dict]) -> bool:
        if not entities:
            return True
        broad_hints = ["相关", "哪些", "推荐", "适合", "有没有", "药食同源", "最好", "怎么选"]
        disease_hints = ["高血压", "糖尿病", "失眠", "症状", "病"]
        if any(token in question for token in broad_hints) and any(token in question for token in disease_hints):
            return True
        if len(entities) >= 6:
            return True
        return False

    def _finalize_answer_payload(self, payload: dict, question_type: str) -> dict:
        result = dict(payload)
        conclusion = result.get("conclusion", "")
        if isinstance(conclusion, str) and conclusion.strip():
            result["conclusion"] = enforce_conclusion_structure(conclusion, question_type)
        evidence = result.get("evidence_summary", "")
        if isinstance(evidence, str) and isinstance(conclusion, str):
            result["evidence_summary"] = self._dedupe_evidence_summary(evidence, result["conclusion"])
        cautions = result.get("cautions", "")
        if isinstance(cautions, str) and isinstance(conclusion, str):
            result["cautions"] = self._dedupe_evidence_summary(cautions, result["conclusion"])
        return result

    @staticmethod
    def _dedupe_evidence_summary(summary: str, conclusion: str) -> str:
        cleaned = (summary or "").strip()
        if not cleaned:
            return cleaned
        conclusion_compact = (conclusion or "").replace("\n", "").replace(" ", "")
        summary_compact = cleaned.replace("\n", "").replace(" ", "")
        if summary_compact and summary_compact in conclusion_compact:
            return ""
        return cleaned

    def _normalize_answer_payload(self, payload: dict, selected_entities: list[dict]) -> dict:
        for field in ["conclusion", "evidence_summary", "cautions"]:
            payload[field] = self._normalize_text_field(payload.get(field, ""))
        follow_ups = payload.get("follow_up_questions", [])
        if isinstance(follow_ups, str):
            payload["follow_up_questions"] = [follow_ups]
        elif isinstance(follow_ups, list):
            payload["follow_up_questions"] = [self._normalize_text_field(item) for item in follow_ups if self._normalize_text_field(item)]
        else:
            payload["follow_up_questions"] = []

        related_entities = payload.get("related_entities", [])
        normalized_related: list[dict] = []
        entity_lookup = {
            item["id"]: {
                "id": item["id"],
                "name": item.get("name") or item["id"],
                "entity_type": item.get("entity_type", "Entity"),
            }
            for item in selected_entities
        }
        for item in related_entities:
            if isinstance(item, dict):
                normalized_related.append(
                    {
                        "id": item.get("id") or item.get("name") or item.get("entity_type") or "unknown",
                        "name": item.get("name") or item.get("id") or "未知实体",
                        "entity_type": item.get("entity_type", "Entity"),
                    }
                )
            elif isinstance(item, str):
                matched = next((value for value in entity_lookup.values() if value["name"] == item or value["id"] == item), None)
                if matched:
                    normalized_related.append(matched)
                else:
                    normalized_related.append({"id": item, "name": item, "entity_type": "Entity"})
        payload["related_entities"] = normalized_related
        return payload

    @staticmethod
    def _normalize_text_field(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return "\n".join(str(item) for item in value if item is not None)
        if isinstance(value, dict):
            return json_module.dumps(value, ensure_ascii=False)
        return str(value)

    def _backfill_answer_payload(self, payload: dict, selected_entities: list[dict], graph: dict) -> dict:
        if not payload.get("evidence_summary"):
            payload["evidence_summary"] = self._build_missing_evidence_summary(selected_entities, graph)
        if not payload.get("related_entities"):
            payload["related_entities"] = self._build_missing_related_entities(selected_entities, graph)
        if not payload.get("follow_up_questions"):
            payload["follow_up_questions"] = self._build_follow_ups(selected_entities)
        return payload

    def _build_missing_evidence_summary(self, selected_entities: list[dict], graph: dict) -> str:
        names = [entity.get("name") or entity["id"] for entity in selected_entities[:6]]
        metrics = graph.get("metrics", {})
        node_count = metrics.get("nodeCount", len(graph.get("nodes", [])))
        edge_count = metrics.get("edgeCount", len(graph.get("edges", [])))
        evidence_lines: list[str] = []
        if names:
            evidence_lines.append(
                f"本次回答纳入了 {len(selected_entities)} 个核心实体：{self._join_names(names)}。"
            )
        if node_count or edge_count:
            evidence_lines.append(f"证据子图共返回 {node_count} 个节点、{edge_count} 条边。")
        if evidence_lines:
            return "\n".join(evidence_lines)
        if graph.get("nodes") or graph.get("edges"):
            return "已检索到相关证据子图，可点击「查看更多详情」查看节点、关系。"
        return ""

    def _build_missing_related_entities(self, selected_entities: list[dict], graph: dict) -> list[dict]:
        related_entities = [
            {
                "id": entity["id"],
                "name": entity.get("name") or entity["id"],
                "entity_type": entity.get("entity_type", "Entity"),
            }
            for entity in selected_entities[:12]
        ]
        node_lookup = {node["id"]: node for node in graph.get("nodes", [])}
        for edge in graph.get("edges", [])[:12]:
            for node_id in [edge["source"], edge["target"]]:
                node = node_lookup.get(node_id)
                if node is None or node["type"] in {"Question", "Attribute", "EvidenceNote"}:
                    continue
                item = {"id": node["id"], "name": node["label"], "entity_type": node.get("type", "Entity")}
                if item not in related_entities:
                    related_entities.append(item)
        return related_entities[:20]

    def _should_rewrite_conclusion(self, conclusion: str, evidence_summary: str) -> bool:
        if not conclusion or not evidence_summary:
            return False
        normalized_conclusion = self._normalize_text_for_similarity(conclusion)
        normalized_evidence = self._normalize_text_for_similarity(evidence_summary)
        if not normalized_conclusion or not normalized_evidence:
            return False
        if normalized_evidence in normalized_conclusion:
            return True
        similarity = SequenceMatcher(None, normalized_conclusion, normalized_evidence).ratio()
        token_overlap = self._token_overlap_ratio(conclusion, evidence_summary)
        return similarity >= 0.72 or token_overlap >= 0.68

    def _normalize_text_for_similarity(self, text: str) -> str:
        return re.sub(r"[^0-9A-Za-z一-鿿]+", "", text).lower()

    def _token_overlap_ratio(self, text_a: str, text_b: str) -> float:
        tokens_a = set(re.findall(r"[A-Za-z0-9_:-]+|[一-鿿]{2,}", text_a))
        tokens_b = set(re.findall(r"[A-Za-z0-9_:-]+|[一-鿿]{2,}", text_b))
        if not tokens_a or not tokens_b:
            return 0.0
        return len(tokens_a & tokens_b) / max(1, min(len(tokens_a), len(tokens_b)))

    def _build_search_terms(self, question: str, question_analysis: dict, initial_entities: list[dict]) -> list[str]:
        search_terms: list[str] = [question]
        for entity in initial_entities[:6]:
            for term in [entity.get("name"), entity.get("id")]:
                if term and term not in search_terms:
                    search_terms.append(term)
        synonym_map = {
            "高血压": ["高血压", "Hypertension"],
            "糖尿病": ["糖尿病", "Diabetes"],
            "失眠": ["失眠", "Insomnia"],
            "头痛": ["头痛", "Headache"],
            "咳嗽": ["咳嗽", "Cough"],
        }
        for chinese, terms in synonym_map.items():
            if chinese in question:
                for term in terms:
                    if term not in search_terms:
                        search_terms.append(term)
        for term in question_analysis.get("search_terms", []) or []:
            if term and term not in search_terms:
                search_terms.append(term)
        return search_terms[:12]

    def _recent_chat_history(self, session_id: str) -> list[dict[str, str]]:
        """Return the last 6 messages (3 Q&A pairs) as a list of {role, content} dicts."""
        messages = self.postgres_repository.list_messages(session_id)
        recent = messages[-6:] if len(messages) > 6 else messages
        return [{"role": msg.role, "content": (msg.content or "")[:300]} for msg in recent]

    def _join_names(self, names: list[str]) -> str:
        deduped: list[str] = []
        for name in names:
            if name not in deduped:
                deduped.append(name)
        return "、".join(deduped[:12])

    def _stringify(self, value) -> str:
        if isinstance(value, list):
            return "、".join(str(item) for item in value[:12])
        if isinstance(value, dict):
            return "；".join(f"{key}：{val}" for key, val in list(value.items())[:12])
        return str(value)
