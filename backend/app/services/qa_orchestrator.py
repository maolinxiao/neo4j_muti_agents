from difflib import SequenceMatcher
import json as json_module
import logging
import re
from pathlib import Path
from time import perf_counter
from typing import Generator

from app.db.models import AppUser
from app.repositories.postgres_repository import PostgresRepository
from app.services.entity_resolver import EntityResolver
from app.services.graph_retriever import GraphRetriever
from app.services.deepseek_client import DeepSeekClient
from app.services.qa_answer_templates import (
    compose_constraints_block,
    context_answer_rules,
    enforce_conclusion_structure,
    outline_for_question_type,
)
from app.services.qa_routing import QARoute, get_qa_route_resolver
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

FLAVOR_PREFERENCE_FOLLOW_UP = (
    "你更偏好的口味是什么（例如低甜、微酸、草本清香或无明显药味），"
    "以及是否需要避开苦味、涩感或药味？"
)
FLAVOR_FOLLOW_UP_SUBJECT_KEYWORDS = ("风味", "口味", "口感", "低甜", "微酸", "草本", "药味", "苦味", "涩感", "甜度", "香气")
FLAVOR_FOLLOW_UP_PREFERENCE_KEYWORDS = ("偏好", "喜欢", "不喜欢", "避开", "更偏", "能否接受", "是否接受", "低甜", "微酸")


class QAOrchestrator:
    def __init__(
        self,
        postgres_repository: PostgresRepository,
        entity_resolver: EntityResolver,
        graph_retriever: GraphRetriever,
        llm_client: DeepSeekClient,
    ) -> None:
        self.postgres_repository = postgres_repository
        self.entity_resolver = entity_resolver
        self.graph_retriever = graph_retriever
        self.llm_client = llm_client
        self.classifier = QuestionClassifier()
        self.route_resolver = get_qa_route_resolver()

    def ask(self, session_id: str, question: str, current_user: AppUser | dict | None = None) -> dict:
        session = self.postgres_repository.get_chat_session(session_id)
        if session is None:
            raise ValueError("Session not found")

        self.postgres_repository.create_message(session_id, "user", question)
        session.last_question = question
        session.title = session.title or question[:40]

        qa_route = self.classifier.classify_route(question)
        question_type = qa_route.question_type
        constitution_profile = self._relevant_constitution_profile(question, current_user, qa_route)
        need_constitution_panel = self._should_offer_constitution_panel(
            question, question_type, constitution_profile, qa_route.task_key
        )
        if need_constitution_panel:
            constitution_assessment_payload = self._build_constitution_assessment_payload(constitution_profile)
            answer_payload = self._build_constitution_panel_answer(question, constitution_assessment_payload)
            think_content = self._build_constitution_panel_think(constitution_assessment_payload)
            graph = self._empty_graph()
            snapshot = self.postgres_repository.create_graph_snapshot(session_id, question, graph)
            missing_slots = self._missing_core_questions(
                question, question_type, graph, constitution_profile=constitution_profile, qa_route=qa_route.task_key
            )
            trace_summary = "用户需要体质辨识，已直接返回体质辨识面板和标准量表入口。"
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
                    "answer_mode": "graph_fallback",
                    "question_analysis": self.llm_client.local_analyze_question(question),
                    "think_content": think_content,
                    "qa_route": qa_route.to_context(),
                    "process_summary": think_content,
                    "missing_slots": missing_slots,
                    "constitution_assessment": constitution_assessment_payload,
                },
            )
            self.postgres_repository.create_trace(
                session_id=session_id,
                question=question,
                question_type=question_type,
                entities=[],
                cypher_template_key="constitution_panel",
                trace_summary=trace_summary,
                retrieval_ms=0,
                llm_ms=0,
                graph_snapshot_id=snapshot.id,
                reasoning_payload={
                    "retrieval_summary": think_content,
                    "question_analysis": self.llm_client.local_analyze_question(question),
                    "qa_route": qa_route.to_context(),
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
                "answer_mode": "graph_fallback",
                "qa_route": qa_route.to_context(),
                "process_summary": think_content,
                "missing_slots": missing_slots,
                "constitution_assessment": constitution_assessment_payload,
            }
        started = perf_counter()
        initial_product_development = qa_route.task_key == "product_development"
        skip_broad_entity_resolution = self._should_skip_broad_entity_resolution(qa_route.task_key)
        if initial_product_development:
            entities = self.entity_resolver.resolve_product_core_ingredients(
                question,
                preferred_types=self._preferred_types(question_type, qa_route.task_key),
            )
        elif skip_broad_entity_resolution:
            entities = []
        else:
            entities = self.entity_resolver.resolve(
                question,
                preferred_types=self._preferred_types(question_type, qa_route.task_key),
            )
        if self._should_use_llm_analysis(question, entities, question_type):
            question_analysis, analysis_ms = self.llm_client.analyze_question(question, entities)
        else:
            question_analysis = self.llm_client.local_analyze_question(question)
            analysis_ms = 0
        question_type = self._refine_question_type(question_type, question_analysis)
        qa_route = self._resolve_refined_route(question, question_type)
        question_type = qa_route.question_type
        question_analysis = {**question_analysis, "qa_route": qa_route.task_key, "audience": qa_route.audience}
        if qa_route.task_key == "product_development":
            if not initial_product_development:
                entities = self.entity_resolver.resolve_product_core_ingredients(
                    question,
                    preferred_types=self._preferred_types(question_type, qa_route.task_key),
                )
        elif skip_broad_entity_resolution or self._should_skip_broad_entity_resolution(qa_route.task_key):
            entities = []
        else:
            entities = self.entity_resolver.resolve_terms(
                self._build_search_terms(question, question_analysis, entities),
                preferred_types=self._preferred_types(question_type, qa_route.task_key),
            )
        template_key, graph, selected_entities = self.graph_retriever.retrieve(
            question, entities, question_type, qa_route=qa_route.task_key
        )
        retrieval_ms = int((perf_counter() - started) * 1000)

        constitution_profile = self._relevant_constitution_profile(question, current_user, qa_route)
        need_constitution_panel = self._should_offer_constitution_panel(
            question, question_type, constitution_profile, qa_route.task_key
        )
        constitution_assessment_payload = (
            self._build_constitution_assessment_payload(constitution_profile)
            if need_constitution_panel
            else None
        )
        llm_payload: dict = {}
        retrieval_summary = self._build_retrieval_summary(
            question, question_type, template_key, selected_entities, graph, constitution_profile, qa_route=qa_route.task_key
        )
        if self._should_use_constitution_scale_answer(question, question_type, graph):
            answer_payload = self._build_constitution_scale_answer(question, graph, constitution_profile)
            llm_ms = 0
            think_content = self._compose_user_facing_think(
                retrieval_summary,
                self._build_constitution_scale_think(graph),
            )
        elif qa_route.task_key == "product_development":
            answer_payload = self._build_local_answer(
                question,
                question_type,
                selected_entities,
                graph,
                "",
                constitution_profile=constitution_profile,
                qa_route=qa_route.task_key,
            )
            llm_ms = 0
            think_content = retrieval_summary
        else:
            context = self._build_llm_context(
                question, question_type, entities, selected_entities, graph, question_analysis,
                chat_history=self._recent_chat_history(session_id),
                constitution_profile=constitution_profile,
                qa_route=qa_route,
            )
            prompt = self.postgres_repository.get_prompt_template_by_key("qa_default")
            system_prompt = self._compose_system_prompt(
                prompt.system_prompt if prompt is not None else self._default_system_prompt(),
                question_type,
                qa_route.task_key,
            )
            llm_payload, answer_llm_ms = self.llm_client.generate_answer(context, system_prompt)
            llm_ms = analysis_ms + answer_llm_ms

            answer_payload = self._normalize_answer_payload(llm_payload, selected_entities)
            answer_payload = self._backfill_answer_payload(
                answer_payload,
                selected_entities,
                graph,
                question=question,
                question_type=question_type,
                constitution_profile=constitution_profile,
                qa_route=qa_route.task_key,
            )
            answer_payload = self._finalize_answer_payload(
                answer_payload,
                question_type,
                qa_route.task_key,
                graph=graph,
            )
            if answer_payload.get("_fallback") or not self._has_substantive_evidence(graph):
                local_error = llm_payload.get("cautions", "") if answer_payload.get("_fallback") else ""
                answer_payload = self._build_local_answer(
                    question,
                    question_type,
                    selected_entities,
                    graph,
                    local_error,
                    constitution_profile=constitution_profile,
                    qa_route=qa_route.task_key,
                )
                llm_ms = 0
            elif answer_payload.get("evidence_summary"):
                rewritten_conclusion, rewrite_llm_ms = self.llm_client.rewrite_answer(
                    question=question,
                    question_type=question_type,
                    draft_conclusion=answer_payload.get("conclusion", ""),
                    evidence_summary=answer_payload.get("evidence_summary", ""),
                    selected_entities=selected_entities,
                    graph_metrics=graph.get("metrics", {}),
                )
                answer_payload["conclusion"] = rewritten_conclusion
                answer_payload = self._finalize_answer_payload(
                    answer_payload,
                    question_type,
                    qa_route.task_key,
                    graph=graph,
                )
                llm_ms += rewrite_llm_ms
                if answer_payload.get("_fallback"):
                    answer_payload = self._build_local_answer(
                        question,
                        question_type,
                        selected_entities,
                        graph,
                        "",
                        constitution_profile=constitution_profile,
                        qa_route=qa_route.task_key,
                    )
                    llm_ms = 0

            answer_payload, extracted_think = self._separate_answer_thinking(answer_payload)
            think_content = self._compose_user_facing_think(
                retrieval_summary,
                llm_payload.get("_think_content", ""),
                extracted_think,
            )

        answer_mode = (
            "graph_grounded"
            if qa_route.task_key == "product_development"
            else "llm_grounded"
            if llm_ms > 0
            else "graph_fallback"
        )
        snapshot = self.postgres_repository.create_graph_snapshot(session_id, question, graph)
        missing_slots = self._missing_core_questions(
            question, question_type, graph, constitution_profile=constitution_profile, qa_route=qa_route.task_key
        )
        trace_summary = (
            f"识别到 {len(entities)} 个候选实体，纳入回答的实体 {len(selected_entities)} 个，"
            f"问题解析类型 {question_type}，业务路由 {qa_route.task_key}，使用模板 {template_key}，"
            f"返回 {graph['metrics']['nodeCount']} 个节点和 {graph['metrics']['edgeCount']} 条边。"
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
                "answer_mode": answer_mode,
                "question_analysis": question_analysis,
                "think_content": think_content,
                "qa_route": qa_route.to_context(),
                "process_summary": retrieval_summary,
                "missing_slots": missing_slots,
                "constitution_assessment": constitution_assessment_payload or answer_payload.get("constitution_assessment"),
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
                "retrieval_summary": think_content,
                "question_analysis": question_analysis,
                "qa_route": qa_route.to_context(),
                "missing_slots": missing_slots,
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
            "answer_mode": answer_mode,
            "qa_route": qa_route.to_context(),
            "process_summary": retrieval_summary,
            "missing_slots": missing_slots,
            "constitution_assessment": constitution_assessment_payload or answer_payload.get("constitution_assessment"),
        }

    def ask_stream(self, session_id: str, question: str, current_user: AppUser | dict | None = None) -> Generator[str, None, None]:
        """Stream Q&A response as SSE events. User message is already persisted by the route."""
        try:
            # Phase 1: Fast preprocessing
            qa_route = self.classifier.classify_route(question)
            question_type = qa_route.question_type
            constitution_profile = self._relevant_constitution_profile(question, current_user, qa_route)
            need_constitution_panel = self._should_offer_constitution_panel(
                question, question_type, constitution_profile, qa_route.task_key
            )
            if need_constitution_panel:
                constitution_assessment_payload = self._build_constitution_assessment_payload(constitution_profile)
                answer_payload = self._build_constitution_panel_answer(question, constitution_assessment_payload)
                full_think = self._build_constitution_panel_think(constitution_assessment_payload)
                yield self._sse("think", {"text": full_think})
                if answer_payload.get("conclusion", "").strip():
                    yield self._sse("token", {"text": answer_payload["conclusion"]})
                graph = self._empty_graph()
                snapshot = self.postgres_repository.create_graph_snapshot(session_id, question, graph)
                missing_slots = self._missing_core_questions(
                    question, question_type, graph, constitution_profile=constitution_profile, qa_route=qa_route.task_key
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
                        "answer_mode": "graph_fallback",
                        "question_analysis": self.llm_client.local_analyze_question(question),
                        "think_content": full_think,
                        "qa_route": qa_route.to_context(),
                        "process_summary": full_think,
                        "missing_slots": missing_slots,
                        "constitution_assessment": constitution_assessment_payload,
                    },
                )
                self.postgres_repository.create_trace(
                    session_id=session_id,
                    question=question,
                    question_type=question_type,
                    entities=[],
                    cypher_template_key="constitution_panel",
                    trace_summary="用户需要体质辨识，流式返回体质辨识面板。",
                    retrieval_ms=0,
                    llm_ms=0,
                    graph_snapshot_id=snapshot.id,
                    reasoning_payload={
                        "retrieval_summary": full_think,
                        "question_analysis": self.llm_client.local_analyze_question(question),
                        "qa_route": qa_route.to_context(),
                        "missing_slots": missing_slots,
                    },
                )
                self.postgres_repository.session.commit()
                yield self._sse("evidence", {
                    "evidence_summary": answer_payload.get("evidence_summary", ""),
                    "related_entities": answer_payload.get("related_entities", []),
                    "cautions": answer_payload.get("cautions", ""),
                    "follow_up_questions": answer_payload.get("follow_up_questions", []),
                    "answer_mode": "graph_fallback",
                    "qa_route": qa_route.to_context(),
                    "process_summary": full_think,
                    "missing_slots": missing_slots,
                    "constitution_assessment": constitution_assessment_payload,
                })
                yield self._sse("graph", graph)
                yield self._sse("done", {"session_id": session_id})
                return
            started = perf_counter()
            yield self._sse(
                "think",
                {"text": f"▌ 阶段 1/5：完成任务分流（{qa_route.task_key}）\n"},
            )
            skip_broad_entity_resolution = self._should_skip_broad_entity_resolution(qa_route.task_key)
            initial_product_development = qa_route.task_key == "product_development"
            if initial_product_development:
                yield self._sse(
                    "think",
                    {"text": "▌ 阶段 2/5：识别核心原料并准备精确图谱检索…\n"},
                )
                entities = self.entity_resolver.resolve_product_core_ingredients(
                    question,
                    preferred_types=self._preferred_types(question_type, qa_route.task_key),
                )
            elif skip_broad_entity_resolution:
                yield self._sse(
                    "think",
                    {"text": "▌ 阶段 2/5：按高风险人群、症状和风味偏好整理检索词，跳过泛实体扫描…\n"},
                )
                entities = []
            else:
                yield self._sse(
                    "think",
                    {"text": "▌ 阶段 2/5：解析候选实体并准备图谱检索…\n"},
                )
                entities = self.entity_resolver.resolve(
                    question,
                    preferred_types=self._preferred_types(question_type, qa_route.task_key),
                )
            if self._should_use_llm_analysis(question, entities, question_type):
                yield self._sse(
                    "think",
                    {"text": "▌ 阶段 3/5：分析需求约束，识别核心实体、追问方向与检索词…\n"},
                )
                question_analysis, analysis_ms = self.llm_client.analyze_question(question, entities)
                yield self._sse(
                    "think",
                    {"text": f"  · 问题分析完成（{analysis_ms} ms）\n"},
                )
            else:
                yield self._sse(
                    "think",
                    {"text": "▌ 阶段 3/5：按业务规则整理需求约束与检索重点…\n"},
                )
                question_analysis = self.llm_client.local_analyze_question(question)
                analysis_ms = 0
            question_type = self._refine_question_type(question_type, question_analysis)
            qa_route = self._resolve_refined_route(question, question_type)
            question_type = qa_route.question_type
            question_analysis = {**question_analysis, "qa_route": qa_route.task_key, "audience": qa_route.audience}
            if qa_route.task_key == "product_development":
                if not initial_product_development:
                    entities = self.entity_resolver.resolve_product_core_ingredients(
                        question,
                        preferred_types=self._preferred_types(question_type, qa_route.task_key),
                    )
            elif skip_broad_entity_resolution or self._should_skip_broad_entity_resolution(qa_route.task_key):
                entities = []
            else:
                entities = self.entity_resolver.resolve_terms(
                    self._build_search_terms(question, question_analysis, entities),
                    preferred_types=self._preferred_types(question_type, qa_route.task_key),
                )
            yield self._sse(
                "think",
                {
                    "text": (
                        f"▌ 阶段 4/5：调用知识图谱检索（{len(entities)} 个候选实体）…\n"
                    )
                },
            )
            graph_started = perf_counter()
            template_key, graph, selected_entities = self.graph_retriever.retrieve(
                question, entities, question_type, qa_route=qa_route.task_key
            )
            graph_ms = int((perf_counter() - graph_started) * 1000)
            retrieval_summary = self._build_retrieval_summary(
                question, question_type, template_key, selected_entities, graph, constitution_profile, qa_route=qa_route.task_key
            )
            retrieval_ms = int((perf_counter() - started) * 1000)
            pre_graph_ms = max(retrieval_ms - graph_ms, 0)
            yield self._sse(
                "think",
                {
                    "text": (
                        f"  · 图谱查询完成（{graph_ms} ms；前置解析 {pre_graph_ms} ms），"
                        f"{'开始生成图谱证据回答' if qa_route.task_key == 'product_development' else '开始让大模型生成回答'}…\n\n"
                    )
                },
            )
            yield self._sse("think", {"text": retrieval_summary})
            yield self._sse(
                "think",
                {"text": "\n\n▌ 阶段 5/5：校验回答结构并生成正文，内容将在下方持续输出…\n"},
            )

            constitution_profile = self._relevant_constitution_profile(question, current_user, qa_route)
            need_constitution_panel = self._should_offer_constitution_panel(
                question, question_type, constitution_profile, qa_route.task_key
            )
            constitution_assessment_payload = (
                self._build_constitution_assessment_payload(constitution_profile)
                if need_constitution_panel
                else None
            )
            if self._should_use_constitution_scale_answer(question, question_type, graph):
                answer_payload = self._build_constitution_scale_answer(question, graph, constitution_profile)
                scale_think_append = self._format_think_append(
                    retrieval_summary,
                    self._build_constitution_scale_think(graph),
                )
                full_think = self._merge_text_blocks(retrieval_summary, scale_think_append)
                if scale_think_append:
                    yield self._sse("think", {"text": f"\n\n{scale_think_append}"})
                emitted_answer = False
                if answer_payload.get("conclusion", "").strip():
                    emitted_answer = True
                    yield self._sse("token", {"text": answer_payload["conclusion"]})
                answer_mode = "graph_fallback"
            elif qa_route.task_key == "product_development":
                answer_payload = self._build_local_answer(
                    question,
                    question_type,
                    selected_entities,
                    graph,
                    "",
                    constitution_profile=constitution_profile,
                    qa_route=qa_route.task_key,
                )
                full_think = retrieval_summary
                emitted_answer = False
                for answer_chunk in self._direct_answer_chunks(
                    answer_payload.get("conclusion", "")
                ):
                    emitted_answer = True
                    yield self._sse("token", {"text": answer_chunk})
                answer_mode = "graph_grounded"
            else:
                context = self._build_llm_context(
                    question, question_type, entities, selected_entities, graph, question_analysis,
                    chat_history=self._recent_chat_history(session_id),
                    constitution_profile=constitution_profile,
                    qa_route=qa_route,
                )
                prompt = self.postgres_repository.get_prompt_template_by_key("qa_default")
                system_prompt = self._compose_stream_system_prompt(
                    prompt.system_prompt if prompt is not None else self._default_system_prompt(),
                    question_type,
                    qa_route.task_key,
                )

                # Phase 2: Stream LLM conclusion (with separated think blocks)
                stream_started = perf_counter()
                full_conclusion = ""
                full_think = retrieval_summary
                emitted_answer = False
                answer_buffer = ""
                buffering_json_answer: bool | None = None
                for chunk in self.llm_client.generate_answer_stream(context, system_prompt):
                    event_type = chunk["event"]
                    text = chunk["text"]
                    if event_type == "think":
                        text = self._strip_stream_think_tags(text)
                        if not self._looks_like_user_facing_answer(text):
                            continue
                    else:
                        text = self._strip_stream_think_tags(text)
                    text = self._professionalize_gap_language(text)
                    if not text:
                        continue
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
                stream_ms = int((perf_counter() - stream_started) * 1000)
                logger.info(
                    "QA stream produced conclusion_chars=%s think_chars=%s stream_ms=%s",
                    len(full_conclusion),
                    len(full_think),
                    stream_ms,
                )

                # Phase 3: Build evidence and persist
                streamed_payload = self._parse_streamed_answer(full_conclusion)
                has_streamed_conclusion = bool(streamed_payload.get("conclusion", "").strip())
                reset_streamed_answer = False
                if has_streamed_conclusion:
                    answer_payload = self._normalize_answer_payload(streamed_payload, selected_entities)
                    answer_payload = self._backfill_answer_payload(
                        answer_payload,
                        selected_entities,
                        graph,
                        question=question,
                        question_type=question_type,
                        constitution_profile=constitution_profile,
                        qa_route=qa_route.task_key,
                    )
                    answer_payload = self._finalize_answer_payload(
                        answer_payload,
                        question_type,
                        qa_route.task_key,
                        graph=graph,
                    )
                    if answer_payload.get("_fallback"):
                        reset_streamed_answer = emitted_answer
                        answer_payload = self._build_local_answer(
                            question,
                            question_type,
                            selected_entities,
                            graph,
                            "",
                            constitution_profile=constitution_profile,
                            qa_route=qa_route.task_key,
                        )
                        has_streamed_conclusion = False
                else:
                    answer_payload = self._build_local_answer(
                        question,
                        question_type,
                        selected_entities,
                        graph,
                        "",
                        constitution_profile=constitution_profile,
                        qa_route=qa_route.task_key,
                    )
                answer_payload, _extracted_think = self._separate_answer_thinking(answer_payload)
                answer_mode = "llm_grounded" if has_streamed_conclusion else "graph_fallback"
                final_conclusion = answer_payload.get("conclusion", "").strip()
                language_reset_needed = emitted_answer and self._contains_system_gap_language(full_conclusion)
                if (reset_streamed_answer or language_reset_needed) and final_conclusion:
                    yield self._sse("answer_reset", {})
                    emitted_answer = True
                    yield self._sse("token", {"text": final_conclusion})
                elif not emitted_answer and final_conclusion:
                    emitted_answer = True
                    yield self._sse("token", {"text": final_conclusion})
            snapshot = self.postgres_repository.create_graph_snapshot(session_id, question, graph)
            missing_slots = self._missing_core_questions(
                question, question_type, graph, constitution_profile=constitution_profile, qa_route=qa_route.task_key
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
                    "answer_mode": answer_mode,
                    "question_analysis": question_analysis,
                    "think_content": full_think.strip(),
                    "qa_route": qa_route.to_context(),
                    "process_summary": retrieval_summary,
                    "missing_slots": missing_slots,
                    "constitution_assessment": constitution_assessment_payload or answer_payload.get("constitution_assessment"),
                },
            )

            retrieval_ms = int((perf_counter() - started) * 1000)
            trace_summary = (
                f"识别到 {len(entities)} 个候选实体，纳入回答的实体 {len(selected_entities)} 个，"
                f"问题解析类型 {question_type}，业务路由 {qa_route.task_key}，使用模板 {template_key}，"
                f"返回 {graph['metrics']['nodeCount']} 个节点和 {graph['metrics']['edgeCount']} 条边。"
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
                    "retrieval_summary": full_think.strip(),
                    "question_analysis": question_analysis,
                    "qa_route": qa_route.to_context(),
                    "missing_slots": missing_slots,
                },
            )
            self.postgres_repository.session.commit()

            yield self._sse("evidence", {
                "evidence_summary": answer_payload.get("evidence_summary", ""),
                "related_entities": answer_payload.get("related_entities", []),
                "cautions": answer_payload.get("cautions", ""),
                "follow_up_questions": answer_payload.get("follow_up_questions", []),
                "answer_mode": answer_mode,
                "qa_route": qa_route.to_context(),
                "process_summary": retrieval_summary,
                "missing_slots": missing_slots,
                "constitution_assessment": constitution_assessment_payload or answer_payload.get("constitution_assessment"),
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

    @staticmethod
    def _direct_answer_chunks(conclusion: str) -> Generator[str, None, None]:
        for chunk in re.split(r"(?=【[^】]+】)", conclusion or ""):
            if chunk:
                yield chunk

    def _parse_streamed_answer(self, raw_text: str) -> dict:
        """Normalize streamed model text into the same payload shape as non-stream answers."""
        source = raw_text or ""
        cleaned = self.llm_client._remove_think_blocks(source)
        if not cleaned.strip():
            rescued = self._extract_user_facing_answer_from_think(source)
            return {"conclusion": rescued} if rescued else {}
        if self._looks_like_json_answer(cleaned):
            parsed = self.llm_client._parse_json_text(cleaned)
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

    @staticmethod
    def _strip_stream_think_tags(text: str) -> str:
        return re.sub(r"</?think\b[^>]*>", "", text or "", flags=re.I)

    @staticmethod
    def _looks_like_user_facing_answer(text: str) -> bool:
        return QAOrchestrator._answer_marker_index(text) >= 0

    @staticmethod
    def _answer_marker_index(text: str) -> int:
        stripped = text or ""
        if not stripped.strip():
            return -1
        answer_markers = (
            "【核心结论】",
            "【判断依据】",
            "【推荐理由】",
            "【原方依据】",
            "【替代依据】",
            "【知识依据】",
            "【任务路由】",
        )
        positions = [stripped.find(marker) for marker in answer_markers if stripped.find(marker) >= 0]
        return min(positions) if positions else -1

    def _extract_user_facing_answer_from_think(self, text: str) -> str:
        for block in re.findall(r"<think\b[^>]*>([\s\S]*?)(?:</think>|$)", text or "", flags=re.I):
            cleaned = self._strip_stream_think_tags(block).strip()
            marker_index = self._answer_marker_index(cleaned)
            if marker_index >= 0:
                return cleaned[marker_index:].strip()
        marker_index = self._answer_marker_index(text or "")
        if marker_index >= 0:
            return self._strip_stream_think_tags((text or "")[marker_index:]).strip()
        return ""

    def _preferred_types(self, question_type: str, qa_route: str | None = None) -> list[str]:
        route_types = self.route_resolver.preferred_types_for(question_type, qa_route)
        if route_types:
            return route_types
        mapping = {
            "herb_efficacy": ["Herb", "Formula", "Effect", "EffectCategory", "Symptom", "Flavor", "NatureFlavor", "Meridian", "ConstitutionType", "ComplianceRule"],
            "formula_relation": ["Formula", "Herb", "Effect", "Symptom", "Flavor", "NatureFlavor", "Source", "Taboo", "ConstitutionType"],
            "formula_replacement": ["Formula", "Herb", "Effect", "Symptom", "Flavor", "NatureFlavor", "Taboo", "ConstitutionType", "ComplianceRule", "RiskExpression"],
            "constitution_recommendation": ["ConstitutionType", "ConstitutionQuestion", "Herb", "Symptom", "Product", "ComplianceRule"],
            "product_recommendation": ["Product", "Herb", "Flavor", "Effect", "Formula", "ComplianceRule", "RiskExpression"],
            "entity_explanation": ["Herb", "Formula", "Effect", "Symptom", "Flavor", "NatureFlavor", "Meridian", "ComplianceRule", "RiskExpression"],
        }
        return mapping.get(question_type, ["Herb", "Formula", "Effect", "Symptom", "ComplianceRule"])

    def _build_llm_context(
        self,
        question: str,
        question_type: str,
        entities: list[dict],
        selected_entities: list[dict],
        graph: dict,
        question_analysis: dict,
        chat_history: list[dict[str, str]] | None = None,
        constitution_profile: dict | None = None,
        qa_route: QARoute | None = None,
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
                summary["replacement_score"] = edge_props.get("final_score") or edge_props.get("score") or edge_props.get("consumer_final_score")
                summary["rank"] = edge_props.get("rank")
                summary["effect_similarity"] = edge_props.get("effect_similarity") or edge_props.get("effect_level1_similarity")
                summary["flavor_acceptance"] = edge_props.get("flavor_acceptance")
                summary["source_type"] = edge_props.get("source_type")
                summary["candidate_source"] = edge_props.get("candidate_source")
                summary["professional_score"] = edge_props.get("professional_score")
                summary["safety_score"] = edge_props.get("safety_score")
                summary["recommendation_status"] = edge_props.get("recommendation_status")
                summary["exclusion_reason"] = edge_props.get("exclusion_reason")
                summary["contraindication"] = edge_props.get("contraindication")
                summary["embedding_similarity"] = edge_props.get("embedding_similarity")
                summary["structure_similarity"] = edge_props.get("structure_similarity")
                summary["formula_context_similarity"] = edge_props.get("formula_context_similarity")
            elif edge["type"] == "INCOMPATIBLE_WITH" and edge_props:
                summary["rule_type"] = edge_props.get("rule_type")
                summary["description"] = edge_props.get("description")
                summary["source"] = edge_props.get("source")
            elif edge["type"] in {"CLAIMS_EFFECT", "USES_HERB", "HAS_FLAVOR", "LISTED_IN_COMPLIANCE_RULE", "DERIVED_FROM_RULE"} and edge_props:
                summary["source"] = edge_props.get("source")
                summary["match_source"] = edge_props.get("match_source")
            elif edge["type"] in {"RECOMMENDS_HERB", "CAUTIONS_HERB"} and edge_props:
                summary["risk_level"] = edge_props.get("risk_level")
                summary["caution_reason"] = edge_props.get("caution_reason")
                summary["agent_action"] = edge_props.get("agent_action")
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
                    "directory_source": props.get("directory_source"),
                    "regulatory_categories": props.get("regulatory_categories"),
                    "ordinary_food_status": props.get("ordinary_food_status"),
                    "ordinary_food_conditions": props.get("ordinary_food_conditions"),
                    "ordinary_food_growth_year_limit": props.get("ordinary_food_growth_year_limit"),
                    "ordinary_food_daily_limit_g": props.get("ordinary_food_daily_limit_g"),
                    "health_food_status": props.get("health_food_status"),
                    "health_food_growth_year_limit": props.get("health_food_growth_year_limit"),
                    "health_food_daily_range_g": props.get("health_food_daily_range_g"),
                    "health_food_allowed_functions": props.get("health_food_allowed_functions"),
                    "health_food_filing_compound_policy": props.get("health_food_filing_compound_policy"),
                    "regulatory_summary": props.get("regulatory_summary"),
                    "regulatory_source_urls": props.get("regulatory_source_urls"),
                    "effect_level1": props.get("effect_level1"),
                    "effect_level2": props.get("effect_level2"),
                    "efficacy": props.get("efficacy"),
                    "symptom_text": props.get("symptom_text"),
                    "nature": props.get("nature"),
                    "flavor": props.get("flavor"),
                    "meridian": props.get("meridian"),
                    "contraindication": props.get("contraindication"),
                    "usage_precautions": props.get("usage_precautions"),
                    "overall_flavor_acceptance": props.get("overall_flavor_acceptance"),
                    "bitter_risk": props.get("bitter_risk"),
                    "astringent_risk": props.get("astringent_risk"),
                    "sweet_contribution": props.get("sweet_contribution"),
                    "sour_contribution": props.get("sour_contribution"),
                    "herbal_medicine_risk": props.get("herbal_medicine_risk"),
                    "aroma_description": props.get("aroma_description"),
                    "aftertaste_risk": props.get("aftertaste_risk"),
                }
            elif etype == "Product":
                ep = {
                    "product_id": props.get("product_id"),
                    "product_name": props.get("product_name"),
                    "brand": props.get("brand"),
                    "dosage_form": props.get("dosage_form"),
                    "claimed_effect": props.get("claimed_effect"),
                    "ingredients": props.get("ingredients"),
                    "inferred_ingredients": props.get("inferred_ingredients"),
                    "ingredient_match_source": props.get("ingredient_match_source"),
                    "selling_points": props.get("selling_points"),
                    "comments": props.get("comments"),
                    "scenario": props.get("scenario"),
                    "price": props.get("price"),
                    "sales": props.get("sales"),
                    "rating": props.get("rating"),
                    "positive_rate": props.get("positive_rate"),
                    "review_count": props.get("review_count"),
                    "approval_no": props.get("approval_no"),
                    "specification": props.get("specification"),
                }
            elif etype == "ConstitutionType":
                ep = {
                    "constitution_type_name": props.get("constitution_type_name"),
                    "constitution_category": props.get("constitution_category"),
                    "main_feature": props.get("main_feature"),
                    "body_feature": props.get("body_feature"),
                    "common_manifestations": props.get("common_manifestations"),
                    "diet_direction": props.get("diet_direction"),
                    "food_homology_direction": props.get("food_homology_direction"),
                    "suitable_ingredient_examples": props.get("suitable_ingredient_examples"),
                    "product_form_suggestion": props.get("product_form_suggestion"),
                    "scenario_suggestion": props.get("scenario_suggestion"),
                    "risk_control": props.get("risk_control"),
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
            elif etype == "ComplianceRule":
                ep = {
                    "rule_id": props.get("rule_id"),
                    "rule_type": props.get("rule_type"),
                    "rule_name": props.get("rule_name"),
                    "applicable_scope": props.get("applicable_scope"),
                    "rule_content": props.get("rule_content"),
                    "agent_check_point": props.get("agent_check_point"),
                    "source_file": props.get("source_file"),
                    "source_url": props.get("source_url"),
                    "effective_date": props.get("effective_date"),
                }
            elif etype == "RiskExpression":
                ep = {
                    "expression": props.get("expression"),
                    "risk_level": props.get("risk_level"),
                    "risk_reason": props.get("risk_reason"),
                    "suggested_expression": props.get("suggested_expression"),
                    "source_file": props.get("source_file"),
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

        route_key = qa_route.task_key if qa_route else ""
        return {
            "question": question,
            "question_type": question_type,
            "qa_route": route_key,
            "qa_route_context": qa_route.to_context() if qa_route else {},
            "reasoning_steps": self.route_resolver.reasoning_steps_for(route_key or None),
            "required_kbs": qa_route.required_kbs if qa_route else [],
            "missing_slots": self._missing_core_questions(
                question,
                question_type,
                graph,
                constitution_profile=constitution_profile,
                qa_route=route_key or None,
            ),
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
            "formula_provenance_context": self._build_formula_provenance_context(graph),
            "recommendation_context": self._build_recommendation_context(graph),
            "flavor_population_context": self._build_flavor_population_context(
                graph,
                selected_entities,
                constitution_profile=constitution_profile,
            ),
            "user_constitution_profile": constitution_profile or {},
            "answer_outline": outline_for_question_type(question_type, route_key or None),
            "answer_style_policy": {
                "mode": "expert_judgement_first",
                "markdown": "正文只使用【】小标题、标准编号列表和 - 无序列表；禁止 **/*** 伪标题。",
                "score_display": "不展示0.xxx原始小数或内部字段名；产品研发/替代问题可展示换算后的整数百分制，并另列高/中/低、证据性质和评分依据。",
                "evidence_style": "先整合判断，再把待验证项改写成核验、小试或专业复核建议；不使用系统视角措辞。",
                "risk_boundary": "儿童、孕妇、慢病、过敏、正在用药等高风险个人问题先给图谱支持的辅助方向和取舍；不输出家庭完整处方或儿童剂量，安全提醒后置；药食同源合法候选、谨慎候选、非药食同源/禁忌排除线索必须分层表达。",
            },
            "answer_rules": context_answer_rules(question_type, route_key or None),
        }

    def _build_recommendation_context(self, graph: dict) -> dict:
        products: list[dict] = []
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
                        "inferred_ingredients": props.get("inferred_ingredients"),
                        "ingredient_match_source": props.get("ingredient_match_source"),
                        "price": props.get("price"),
                        "sales": props.get("sales"),
                        "rating": props.get("rating"),
                        "positive_rate": props.get("positive_rate"),
                        "review_count": props.get("review_count"),
                        "approval_no": props.get("approval_no"),
                        "specification": props.get("specification"),
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
                        "score_1": props.get("score_1"),
                        "score_2": props.get("score_2"),
                        "score_3": props.get("score_3"),
                        "score_4": props.get("score_4"),
                        "score_5": props.get("score_5"),
                        "table_no": props.get("table_no"),
                        "source_page": props.get("source_page"),
                        "applicable_group": props.get("applicable_group"),
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
            "constitution_types": constitution_types[:6],
            "constitution_questions": constitution_questions[:30],
            "replacement_options": replacements[:12],
        }

    def _build_formula_provenance_context(self, graph: dict) -> dict:
        node_lookup = {str(node.get("id")): node for node in graph.get("nodes", [])}
        formula_ingredients: dict[str, list[str]] = {}
        formula_roles: dict[str, list[dict]] = {}
        replacements: list[dict] = []

        def append_unique(bucket: dict[str, list], key: str, value: object) -> None:
            if value in (None, "", {}):
                return
            bucket.setdefault(key, [])
            if value not in bucket[key]:
                bucket[key].append(value)

        for edge in graph.get("edges", []):
            source = node_lookup.get(str(edge.get("source")), {})
            target = node_lookup.get(str(edge.get("target")), {})
            edge_type = edge.get("type")
            if edge_type == "IN_FORMULA":
                if source.get("type") == "Herb" and target.get("type") == "Formula":
                    append_unique(formula_ingredients, str(target.get("id")), source.get("label"))
                elif source.get("type") == "Formula" and target.get("type") == "Herb":
                    append_unique(formula_ingredients, str(source.get("id")), target.get("label"))
            elif edge_type in {"MONARCH_HERB", "MINISTER_HERB", "ASSISTANT_HERB", "GUIDE_HERB"}:
                if source.get("type") == "Formula" and target.get("type") == "Herb":
                    append_unique(
                        formula_roles,
                        str(source.get("id")),
                        {
                            "herb_name": target.get("label"),
                            "role": ROLE_DISPLAY.get(edge_type, edge_type),
                        },
                    )
            elif edge_type == "CAN_REPLACE":
                props = edge.get("props", {}) or {}
                kb4_score = (
                    props.get("final_score")
                    if props.get("final_score") is not None
                    else props.get("score")
                    if props.get("score") is not None
                    else props.get("consumer_final_score")
                )
                composite_score = self._replacement_composite_confidence(props)
                replacements.append(
                    {
                        "source_herb": source.get("label") or edge.get("source"),
                        "target_herb": target.get("label") or edge.get("target"),
                        "rank": props.get("rank"),
                        "recommendation_status": props.get("recommendation_status"),
                        "kb4_original_score_100": self._score_to_100(kb4_score),
                        "consumer_aware_score_100": self._score_to_100(props.get("consumer_final_score")),
                        "system_composite_confidence_100": composite_score,
                        "confidence_level": self._confidence_level(composite_score),
                        "professional_score_100": self._score_to_100(props.get("professional_score")),
                        "effect_similarity_100": self._score_to_100(
                            props.get("effect_similarity")
                            if props.get("effect_similarity") is not None
                            else props.get("effect_level2_similarity")
                            if props.get("effect_level2_similarity") is not None
                            else props.get("effect_level1_similarity")
                        ),
                        "flavor_acceptance_100": self._score_to_100(props.get("flavor_acceptance")),
                        "safety_score_100": self._score_to_100(props.get("safety_score")),
                        "formula_context_score_100": self._score_to_100(props.get("formula_context_similarity")),
                        "source_type": props.get("source_type"),
                        "candidate_source": props.get("candidate_source"),
                        "contraindication": props.get("contraindication"),
                        "evidence_type": "KB4图谱直接评分＋系统综合评估",
                    }
                )

        prototypes: list[dict] = []
        for node in graph.get("nodes", []):
            if node.get("type") != "Formula":
                continue
            props = node.get("props", {}) or {}
            rank = props.get("prototype_rank")
            if rank is None:
                continue
            formula_id = str(node.get("id"))
            sources = [
                str(item)
                for item in (props.get("prototype_sources") or [])
                if str(item).strip()
            ]
            if not sources and props.get("source"):
                sources = [str(props.get("source"))]
            ingredients = formula_ingredients.get(formula_id, [])
            property_ingredients = self._split_herb_names(props.get("ingredients"))
            if len(property_ingredients) > len(ingredients):
                ingredients = property_ingredients
            match_score = self._score_to_100(props.get("prototype_match_score"), already_percent=True)
            prototypes.append(
                {
                    "rank": int(rank),
                    "formula_name": props.get("formula_name") or node.get("label"),
                    "sources": sources,
                    "ingredients": ingredients,
                    "roles": formula_roles.get(formula_id, []),
                    "efficacy": props.get("efficacy"),
                    "crowd": props.get("crowd"),
                    "taboo": props.get("taboo"),
                    "match_type": props.get("prototype_match_type"),
                    "evidence_type": props.get("prototype_evidence_type") or "系统推导",
                    "prototype_match_score_100": match_score,
                    "confidence_level": self._confidence_level(match_score),
                    "match_reasons": props.get("prototype_match_reasons") or [],
                }
            )

        prototypes.sort(key=lambda item: (item["rank"], -float(item.get("prototype_match_score_100") or 0)))
        replacements.sort(
            key=lambda item: (
                str(item.get("source_herb") or ""),
                int(item.get("rank") or 999),
                -float(item.get("kb4_original_score_100") or 0),
            )
        )
        return {
            "formula_prototypes": prototypes[:3],
            "replacement_options": replacements[:18],
            "adjustment_actions": ["保留", "替换", "新增", "删除"],
            "display_policy": (
                "名方直接关联与系统相似匹配必须分开标识；最终配方逐味标注保留、替换、新增、删除。"
                "KB4原始分按100分制展示，系统综合可信度另列，均不得表述为临床有效率。"
            ),
        }

    def _format_formula_provenance_lines(self, provenance_context: dict) -> list[str]:
        prototypes = provenance_context.get("formula_prototypes") or []
        if not prototypes:
            return [
                "建议在定稿前补充核对可直接关联的经典方剂；当前草案只保留功效、风味与合规研发逻辑，不标注未经核实的名方来源。"
            ]
        primary = prototypes[0]
        source_text = self._join_names(primary.get("sources") or []) or "出处需在定稿前进一步核对"
        ingredient_text = self._join_names(primary.get("ingredients") or []) or "原方组成需进一步核对"
        reason_text = self._join_names(primary.get("match_reasons") or []) or "按核心原料与目标需求综合匹配"
        score = primary.get("prototype_match_score_100")
        score_text = (
            f"{score}/100（{primary.get('confidence_level') or '待核验'}）"
            if score is not None
            else "待核验"
        )
        evidence_type = primary.get("evidence_type") or "系统推导"
        relation_text = (
            "核心原料与原方存在直接图谱关系"
            if primary.get("match_type") == "direct_core_herb"
            else "依据功效、人群和风味相似性自动筛选"
        )
        return [
            f"- 参考原型：{primary.get('formula_name')}；出处：{source_text}。",
            f"- 证据性质：{evidence_type}；{relation_text}。最终产品是研发改方，不等同于原方。",
            f"- 原型组成：{ingredient_text}。",
            f"- 原型匹配度：{score_text}；依据：{reason_text}。该分值表示研发匹配程度，不是临床有效率。",
        ]

    def _build_formula_adjustment_lines(
        self,
        provenance_context: dict,
        final_ingredient_names: list[str],
    ) -> list[str]:
        prototypes = provenance_context.get("formula_prototypes") or []
        if not prototypes:
            return [
                f"- 新增：{name}；作为当前研发草案原料，需继续核验功效、风味、合规和人群适配。"
                for name in list(dict.fromkeys(final_ingredient_names))
            ] or ["- 待补充最终配方原料后，再逐味标注保留、替换、新增和删除。"]

        original_names = list(dict.fromkeys(prototypes[0].get("ingredients") or []))
        final_names = list(dict.fromkeys(name for name in final_ingredient_names if name))
        replacements = provenance_context.get("replacement_options") or []
        options_by_source: dict[str, list[dict]] = {}
        for item in replacements:
            source_name = str(item.get("source_herb") or "")
            if source_name:
                options_by_source.setdefault(source_name, []).append(item)

        kept_names: list[str] = []
        deleted_names: list[str] = []
        added_names: list[str] = []
        replacement_lines: list[str] = []
        used_replacement_targets: set[str] = set()
        for original_name in original_names:
            if original_name in final_names:
                kept_names.append(original_name)
                continue
            chosen = next(
                (
                    item
                    for item in options_by_source.get(original_name, [])
                    if item.get("target_herb") in final_names
                ),
                None,
            )
            if chosen:
                target_name = str(chosen.get("target_herb"))
                used_replacement_targets.add(target_name)
                kb4_score = chosen.get("kb4_original_score_100")
                confidence = chosen.get("system_composite_confidence_100")
                replacement_lines.append(
                    f"{original_name} → {target_name}；"
                    f"KB4原始分{kb4_score if kb4_score is not None else '待核验'}/100，"
                    f"系统综合可信度{confidence if confidence is not None else '待核验'}/100"
                    f"（{chosen.get('confidence_level') or '待核验'}）。"
                )
                continue
            deleted_names.append(original_name)

        for final_name in final_names:
            if final_name in original_names or final_name in used_replacement_targets:
                continue
            added_names.append(final_name)

        lines = [
            f"1. 保留：{self._join_names(kept_names) if kept_names else '无'}；延续参考原型中的核心配伍位置。",
            (
                "2. 替换：" + " ".join(replacement_lines)
                if replacement_lines
                else "2. 替换：当前定稿草案未采用直接替换；功能相近但缺少 CAN_REPLACE 关系的调整按“删除＋新增”处理。"
            ),
            f"3. 新增：{self._join_names(added_names) if added_names else '无'}；用于补足目标风味、剂型或人群适配，需通过小试验证。",
            f"4. 删除：{self._join_names(deleted_names) if deleted_names else '无'}；当前产品草案暂不纳入，避免照搬原方全部药味和复杂度。",
        ]
        core_name = final_names[0] if final_names else ""
        core_options = options_by_source.get(core_name, [])[:3]
        if core_options:
            lines.append("- 备选替代方案：")
            for item in core_options:
                kb4_score = item.get("kb4_original_score_100")
                confidence = item.get("system_composite_confidence_100")
                lines.append(
                    f"- {core_name} → {item.get('target_herb')}："
                    f"KB4原始分{kb4_score if kb4_score is not None else '待核验'}/100；"
                    f"系统综合可信度{confidence if confidence is not None else '待核验'}/100"
                    f"（{item.get('confidence_level') or '待核验'}）；"
                    "仅作为备选，不代表当前方案已替换核心原料。"
                )
        return lines

    @staticmethod
    def _score_to_100(value: object, *, already_percent: bool = False) -> int | None:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return None
        if not already_percent and score <= 1:
            score *= 100
        return int(round(min(max(score, 0), 100)))

    @classmethod
    def _replacement_composite_confidence(cls, props: dict) -> int | None:
        raw_score = (
            props.get("final_score")
            if props.get("final_score") is not None
            else props.get("score")
            if props.get("score") is not None
            else props.get("consumer_final_score")
        )
        weighted_values = [
            (raw_score, 0.55),
            (props.get("safety_score"), 0.15),
            (props.get("flavor_acceptance"), 0.15),
            (props.get("formula_context_similarity"), 0.15),
        ]
        numerator = 0.0
        denominator = 0.0
        for value, weight in weighted_values:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if numeric > 1:
                numeric /= 100
            numerator += min(max(numeric, 0), 1) * weight
            denominator += weight
        if denominator == 0:
            return None
        return int(round((numerator / denominator) * 100))

    @staticmethod
    def _confidence_level(score: int | None) -> str:
        if score is None:
            return "待核验"
        if score >= 75:
            return "高"
        if score >= 55:
            return "中"
        return "低"

    def _build_flavor_population_context(
        self,
        graph: dict,
        selected_entities: list[dict],
        constitution_profile: dict | None = None,
    ) -> dict:
        node_lookup = {node["id"]: node for node in graph.get("nodes", [])}
        selected_ids = {entity["id"] for entity in selected_entities[:8]}
        connected_flavors: dict[str, list[str]] = {}
        connected_nature_flavors: dict[str, list[str]] = {}
        constitution_recommendations: dict[str, dict[str, list[str]]] = {}
        formula_ingredients: dict[str, list[str]] = {}
        replacement_checks: list[dict] = []

        def append_unique(bucket: dict[str, list[str]], key: str, value: str | None) -> None:
            cleaned = (value or "").strip()
            if not cleaned:
                return
            bucket.setdefault(key, [])
            if cleaned not in bucket[key]:
                bucket[key].append(cleaned)

        for edge in graph.get("edges", []):
            source = node_lookup.get(edge.get("source"), {})
            target = node_lookup.get(edge.get("target"), {})
            edge_type = edge.get("type")
            if edge_type == "HAS_FLAVOR":
                if source.get("type") == "Herb" and target.get("type") == "Flavor":
                    append_unique(connected_flavors, source["id"], target.get("label"))
                elif target.get("type") == "Herb" and source.get("type") == "Flavor":
                    append_unique(connected_flavors, target["id"], source.get("label"))
            elif edge_type == "HAS_NATURE_FLAVOR":
                if source.get("type") == "Herb" and target.get("type") == "NatureFlavor":
                    append_unique(connected_nature_flavors, source["id"], target.get("label"))
                elif target.get("type") == "Herb" and source.get("type") == "NatureFlavor":
                    append_unique(connected_nature_flavors, target["id"], source.get("label"))
            elif edge_type in {"IN_FORMULA", "MONARCH_HERB", "MINISTER_HERB", "ASSISTANT_HERB", "GUIDE_HERB"}:
                if source.get("type") == "Herb" and target.get("type") == "Formula":
                    append_unique(formula_ingredients, target["id"], source.get("label"))
                elif source.get("type") == "Formula" and target.get("type") == "Herb":
                    append_unique(formula_ingredients, source["id"], target.get("label"))
            elif edge_type in {"RECOMMENDS_HERB", "CAUTIONS_HERB"}:
                if source.get("type") == "ConstitutionType" and target.get("type") == "Herb":
                    item = constitution_recommendations.setdefault(
                        source["id"],
                        {"constitution_type": source.get("label") or source["id"], "recommended_herbs": [], "caution_herbs": []},
                    )
                    field = "recommended_herbs" if edge_type == "RECOMMENDS_HERB" else "caution_herbs"
                    herb_name = target.get("label") or target.get("id")
                    if herb_name and herb_name not in item[field]:
                        item[field].append(herb_name)
            elif edge_type == "CAN_REPLACE":
                props = edge.get("props", {}) or {}
                replacement_checks.append(
                    {
                        "source_herb": source.get("label") or edge.get("source"),
                        "target_herb": target.get("label") or edge.get("target"),
                        "final_score": props.get("final_score") or props.get("score") or props.get("consumer_final_score"),
                        "professional_score": props.get("professional_score"),
                        "flavor_acceptance": props.get("flavor_acceptance"),
                        "flavor_similarity": props.get("flavor_similarity"),
                        "safety_score": props.get("safety_score"),
                        "recommendation_status": props.get("recommendation_status"),
                        "exclusion_reason": props.get("exclusion_reason"),
                        "contraindication": props.get("contraindication"),
                        "source_type": props.get("source_type"),
                        "embedding_similarity": props.get("embedding_similarity"),
                        "structure_similarity": props.get("structure_similarity"),
                    }
                )
            elif edge_type == "INCOMPATIBLE_WITH":
                props = edge.get("props", {}) or {}
                replacement_checks.append(
                    {
                        "source_herb": source.get("label") or edge.get("source"),
                        "target_herb": target.get("label") or edge.get("target"),
                        "incompatibility": True,
                        "rule_type": props.get("rule_type"),
                        "description": props.get("description"),
                    }
                )

        herbs: list[dict] = []
        formulas: list[dict] = []
        constitution_types: list[dict] = []
        products: list[dict] = []
        consumer_profiles: list[dict] = []
        consumer_segments: list[dict] = []
        consumer_reviews: list[dict] = []
        for node in graph.get("nodes", []):
            props = node.get("props", {}) or {}
            node_type = node.get("type")
            if node_type == "Herb":
                herbs.append(
                    {
                        "herb_name": props.get("herb_name") or node.get("label"),
                        "is_selected": node["id"] in selected_ids,
                        "food_homology": props.get("food_homology") or props.get("is_food_homology"),
                        "nature": props.get("nature"),
                        "flavor": props.get("flavor"),
                        "kb3_flavors": connected_flavors.get(node["id"], []),
                        "nature_flavors": connected_nature_flavors.get(node["id"], []),
                        "bitter_risk": props.get("bitter_risk"),
                        "astringent_risk": props.get("astringent_risk"),
                        "herbal_medicine_risk": props.get("herbal_medicine_risk"),
                        "aftertaste_risk": props.get("aftertaste_risk"),
                        "sweet_contribution": props.get("sweet_contribution"),
                        "sour_contribution": props.get("sour_contribution"),
                        "aroma_description": props.get("aroma_description"),
                        "overall_flavor_acceptance": props.get("overall_flavor_acceptance"),
                        "contraindication": props.get("contraindication"),
                        "usage_precautions": props.get("usage_precautions") or props.get("usage_note"),
                    }
                )
            elif node_type == "Formula":
                formulas.append(
                    {
                        "formula_name": props.get("formula_name") or node.get("label"),
                        "crowd": props.get("crowd"),
                        "taboo": props.get("taboo"),
                        "efficacy": props.get("efficacy"),
                        "ingredients": formula_ingredients.get(node["id"], []) or self._split_herb_names(props.get("ingredients")),
                    }
                )
            elif node_type == "ConstitutionType":
                constitution_types.append(
                    {
                        "constitution_type_name": props.get("constitution_type_name") or node.get("label"),
                        "diet_direction": props.get("diet_direction"),
                        "food_homology_direction": props.get("food_homology_direction"),
                        "suitable_ingredient_examples": props.get("suitable_ingredient_examples"),
                        "risk_control": props.get("risk_control"),
                        "product_form_suggestion": props.get("product_form_suggestion"),
                        "scenario_suggestion": props.get("scenario_suggestion"),
                        **constitution_recommendations.get(node["id"], {}),
                    }
                )
            elif node_type == "Product":
                products.append(
                    {
                        "product_name": props.get("product_name") or node.get("label"),
                        "brand": props.get("brand"),
                        "dosage_form": props.get("dosage_form"),
                        "scenario": props.get("scenario"),
                        "ingredients": props.get("ingredients") or props.get("inferred_ingredients"),
                        "claimed_effect": props.get("claimed_effect"),
                    }
                )
            elif node_type == "ConsumerProfile":
                consumer_profiles.append(
                    {
                        "profile_id": props.get("profile_id") or node.get("id"),
                        "product_name": props.get("product_name") or node.get("label"),
                        "crowd_type": props.get("crowd_type"),
                        "core_need": props.get("core_need"),
                        "preferred_flavor": props.get("preferred_flavor"),
                        "disliked_flavor": props.get("disliked_flavor"),
                        "preferred_dosage": props.get("preferred_dosage"),
                        "primary_age_group": props.get("primary_age_group"),
                        "product_form_category": props.get("product_form_category"),
                        "top_flavor_tags_count": props.get("top_flavor_tags_count"),
                        "top_complaint_tags_count": props.get("top_complaint_tags_count"),
                        "positive_rate": props.get("positive_rate"),
                        "review_count": props.get("review_count"),
                    }
                )
            elif node_type == "ConsumerSegment":
                consumer_segments.append(
                    {
                        "segment_key": props.get("segment_key") or node.get("id"),
                        "segment_label": props.get("segment_label") or node.get("label"),
                        "crowd_tags": props.get("crowd_tags"),
                        "scenario_tags": props.get("scenario_tags"),
                        "effect_tags": props.get("effect_tags"),
                        "top_flavor_tags": props.get("top_flavor_tags"),
                        "top_dosage_tags": props.get("top_dosage_tags"),
                        "top_complaint_tags": props.get("top_complaint_tags"),
                        "positive_rate": props.get("positive_rate"),
                        "review_count": props.get("review_count"),
                    }
                )
            elif node_type == "ConsumerReview":
                consumer_reviews.append(
                    {
                        "review_id": props.get("review_id") or node.get("id"),
                        "flavor_tags": props.get("flavor_tags"),
                        "effect_tags": props.get("effect_tags"),
                        "crowd_tags": props.get("crowd_tags"),
                        "scenario_tags": props.get("scenario_tags"),
                        "complaint_tags": props.get("complaint_tags"),
                        "sentiment": props.get("sentiment"),
                        "quality_score": props.get("quality_score"),
                        "cleaned_text": props.get("cleaned_text") or node.get("label"),
                    }
                )

        flavor_gap = not any(
            [
                connected_flavors,
                consumer_profiles,
                consumer_segments,
                any(review.get("flavor_tags") for review in consumer_reviews),
                any(
                    herb.get("overall_flavor_acceptance") is not None
                    or herb.get("bitter_risk") is not None
                    or herb.get("aroma_description")
                    or herb.get("flavor")
                    for herb in herbs
                ),
            ]
        )
        population_gap = not any(
            [
                constitution_profile,
                constitution_types,
                consumer_profiles,
                consumer_segments,
                any(formula.get("crowd") for formula in formulas),
                any(product.get("scenario") for product in products),
            ]
        )
        return {
            "herb_flavor_profiles": herbs[:16],
            "formula_population_profiles": formulas[:8],
            "constitution_profiles": constitution_types[:8],
            "product_population_profiles": products[:8],
            "consumer_profiles": consumer_profiles[:8],
            "consumer_segments": consumer_segments[:8],
            "consumer_reviews": consumer_reviews[:8],
            "replacement_flavor_population_checks": replacement_checks[:16],
            "user_constitution_profile": constitution_profile or {},
            "evidence_gaps": {
                "flavor": "缺少 KB3 风味评价或风味关系证据" if flavor_gap else "",
                "population": "缺少目标人群、体质档案或方剂/产品人群画像" if population_gap else "",
            },
        }

    def _should_use_constitution_scale_answer(self, question: str, question_type: str, graph: dict) -> bool:
        if question_type != "constitution_recommendation":
            return False
        if not self._is_constitution_scale_request(question):
            return False
        return self._has_constitution_scale_data(graph)

    @staticmethod
    def _is_constitution_scale_request(question: str) -> bool:
        compact = re.sub(r"\s+", "", question or "")
        required_tokens = ("\u4f53\u8d28",)
        optional_tokens = (
            "\u91cf\u8868",
            "\u95ee\u5377",
            "\u6d4b\u8bd5",
            "\u6d4b\u8bc4",
            "\u5224\u5b9a",
            "\u8bc6\u522b",
            "\u786e\u5b9a",
        )
        return any(token in compact for token in required_tokens) and any(token in compact for token in optional_tokens)

    @staticmethod
    def _has_constitution_scale_data(graph: dict) -> bool:
        node_types = {node.get("type") for node in graph.get("nodes", [])}
        return "ConstitutionType" in node_types and "ConstitutionQuestion" in node_types

    def _build_retrieval_summary(
        self,
        question: str,
        question_type: str,
        template_key: str,
        selected_entities: list[dict],
        graph: dict,
        constitution_profile: dict | None = None,
        qa_route: str | None = None,
    ) -> str:
        """Build a user-facing process summary without exposing prompt metadata."""
        route = self.route_resolver.by_key(qa_route)
        route_label = self._route_label(question, question_type, qa_route)
        kb_route = self._kb_route(question, question_type, qa_route)
        reasoning_steps = self.route_resolver.reasoning_steps_for(qa_route)
        core_entities = [
            f"{entity.get('name') or entity.get('id')}（{entity.get('entity_type', 'Entity')}）"
            for entity in selected_entities[:4]
        ]
        evidence_gaps = self._evidence_gap_notes(question, question_type, graph)
        missing_questions = self._missing_core_questions(
            question,
            question_type,
            graph,
            constitution_profile=constitution_profile,
            qa_route=qa_route,
        )
        data_gaps = self.route_resolver.data_gap_notes()

        lines = [
            f"1. 任务分流：按“{route_label}”处理；输出边界是{route.output_boundary if route else '基于图谱证据作答'}。",
        ]
        if reasoning_steps:
            lines.append(f"2. 核心信息检查：{'；'.join(reasoning_steps[:2])}。")
        else:
            lines.append("2. 核心信息检查：先核对用户已给出的约束，再识别仍缺失的关键信息。")

        if missing_questions:
            compact_missing = [item.rstrip("？?") for item in missing_questions[:3]]
            lines.append(f"   仍缺少：{self._join_names(compact_missing)}。")
        elif constitution_profile and constitution_profile.get("primary_constitution"):
            lines.append(
                f"   已读取体质档案：主导体质为 {constitution_profile.get('primary_constitution')}。"
            )

        lines.append(f"3. KB 路由：{kb_route}。")
        if route and route.required_kbs:
            lines.append(f"   本路由优先核对 {'、'.join(route.required_kbs)}。")
        if core_entities:
            lines.append(
                f"   当前核心线索：{self._join_names(core_entities)}。"
            )
        else:
            lines.append("   建议补充明确的药材、方剂或产品名称；回答将先给出有限判断并集中追问。")

        risk_notes: list[str] = []
        if evidence_gaps:
            risk_notes.extend(evidence_gaps[:2])
        if route and route.evidence_requirements:
            risk_notes.append(f"需覆盖：{'、'.join(route.evidence_requirements[:4])}")
        if data_gaps and question_type == "product_recommendation" and route and route.audience == "enterprise":
            risk_notes.append("工艺、电子鼻和行业报告建议在下一阶段开展专项验证")
        if risk_notes:
            lines.append(f"4. 风险/合规边界：{self._join_names(risk_notes)}。")
        else:
            lines.append("4. 风险/合规边界：当前未发现必须先阻断回答的高风险缺口。")

        lines.append(f"5. 回答与追问：{self._analysis_focus(question_type, qa_route)}")
        if missing_questions:
            lines.append(f"   下一步将追问：{self._join_names(missing_questions[:3])}。")
        return self._sanitize_think_content(*lines)

    @staticmethod
    def _analysis_focus(question_type: str, qa_route: str | None = None) -> str:
        route_focus = {
            "product_development": "先做核心原料合规闸门，再交付产品定位、配方草案、分人群适配、风味剂型与研发验证。",
            "formula_foodification": "先保留 KB5 原方依据，再逐味替代、复核风味与食品化边界。",
            "herb_replacement": "先给替代排序与不能完全替代点，并同步检查配伍禁忌。",
            "flavor_form_factor": "先判断好不好喝、适合什么剂型，再谈工艺验证指标。",
            "market_analysis": "先总结竞品格局与差评痛点，再给差异化方向。",
            "compliance_review": "先给合规风险等级与禁用/慎用表述，再列需补充核验信息。",
            "constitution_assessment": "先给量表入口与评分规则，未完成问卷前不下体质诊断。",
            "personalized_food_recommendation": "先确认体质/风险/诉求/口味，再给温和食养方向。",
            "personal_product_fit": "先输出适合/谨慎/不建议及原因，再给替代方向。",
            "personal_product_recommendation": "先按人群与口味筛选成品，再说明风险边界。",
            "risk_boundary": "先给可考虑/谨慎/不建议的辅助方向，再写就医或专业咨询边界。",
        }
        if qa_route and qa_route in route_focus:
            return route_focus[qa_route]
        mapping = {
            "constitution_recommendation": "我会把体质量表和食养边界分开看，避免把测评工具直接说成诊断。",
            "product_recommendation": "我会把产品、风味和合规证据分开判断，避免推荐理由和风险边界混在一起。",
            "formula_replacement": "我会先保留原方依据，再看单味替代评分、风味接受度和目标人群，避免把动态替代说成已经预生成的新方。",
            "formula_relation": "我会优先核对原方组成、来源、主治线索、风味和适用人群，剂量缺失时直接标出来。",
            "herb_efficacy": "我会把功效、症状、性味归经、风味、人群和禁忌拆开看，避免把相邻关系扩大成治疗承诺。",
        }
        return mapping.get(question_type, "我会把命中的实体关系当作支撑证据，同时保留没有直接证据的部分。")

    def _route_label(self, question: str, question_type: str, qa_route: str | None = None) -> str:
        route = self.route_resolver.by_key(qa_route)
        if route and route.route_label:
            return route.route_label
        compact = re.sub(r"\s+", "", question or "")
        personal_hints = ("我", "体质", "孕妇", "儿童", "老人", "慢病", "过敏", "适合我", "能不能吃")
        if question_type == "constitution_recommendation":
            return "个人端：体质辨识、食养推荐或风险边界"
        if question_type == "formula_replacement":
            return "企业端：名方/方剂药食同源化或单味药替代"
        if question_type == "product_recommendation":
            if any(token in compact for token in personal_hints):
                return "个人端：产品适配、风味接受度或风险边界"
            return "企业端：产品研发、风味剂型、市场或合规判断"
        if question_type == "formula_relation":
            return "通用/企业端：方剂知识检索与原方依据整理"
        if question_type == "herb_efficacy":
            return "通用：原料功效、合法性与禁忌证据整理"
        return "通用：实体解释与图谱证据整理"

    def _kb_route(self, question: str, question_type: str, qa_route: str | None = None) -> str:
        route = self.route_resolver.by_key(qa_route)
        if route and route.kb_route:
            return route.kb_route
        compact = re.sub(r"\s+", "", question or "")
        if question_type == "constitution_recommendation":
            return "KB8 体质规则为主，结合 KB1、KB2、KB3、KB7 做食养与风险过滤"
        if question_type == "formula_replacement":
            return "KB5 读取原方，KB1 做合法性判断，KB4 动态单味替代，KB2/KB3 复核功效与风味，KB7 做合规边界"
        if question_type == "product_recommendation":
            if any(token in compact for token in ("好喝", "口味", "风味", "剂型", "工艺")):
                return "KB3 风味评价、KB6 产品市场、KB7 合规边界，必要时结合 KB1/KB2"
            if any(token in compact for token in ("合规", "宣传", "标签", "GB2760", "GB7718")):
                return "KB7 食品标准合规为主，结合 KB1 原料合法性和 KB6 产品信息"
            return "KB6 产品市场为主，结合 KB1、KB2、KB3、KB7 做原料、功效、风味和合规复核"
        if question_type == "formula_relation":
            return "KB5 方剂知识库为主，结合 KB1、KB2、KB7 检查原料、功效和边界"
        if question_type == "herb_efficacy":
            return "KB1 原料合法性、KB2 功效病症性味归经、KB3 风味和 KB7 合规边界"
        return "按命中实体在 KB1-KB8 中扩展相邻证据"

    @staticmethod
    def _evidence_gap_notes(question: str, question_type: str, graph: dict) -> list[str]:
        node_types = {node.get("type") for node in graph.get("nodes", [])}
        edge_types = {edge.get("type") for edge in graph.get("edges", [])}
        gaps: list[str] = []
        if question_type in {"formula_relation", "formula_replacement"} and "Formula" not in node_types:
            gaps.append("建议补充核对 KB5 原方名称、组成和出处")
        if question_type == "formula_replacement" and "CAN_REPLACE" not in edge_types:
            gaps.append("建议补充核对 KB4 单味替代评分")
        if question_type in {"formula_replacement", "herb_efficacy", "constitution_recommendation"} and any(
            token in (question or "") for token in ("替代", "替换", "组成", "配伍", "改造", "食品化")
        ) and "INCOMPATIBLE_WITH" not in edge_types:
            gaps.append("组合多种药材前建议人工复核十八反、十九畏及其他配伍安全")
        if question_type in {"herb_efficacy", "formula_relation", "formula_replacement", "product_recommendation"}:
            has_flavor_evidence = "Flavor" in node_types or "HAS_FLAVOR" in edge_types or any(
                (node.get("props") or {}).get(field) is not None
                for node in graph.get("nodes", [])
                for field in (
                    "flavor",
                    "overall_flavor_acceptance",
                    "bitter_risk",
                    "astringent_risk",
                    "herbal_medicine_risk",
                    "aroma_description",
                )
            )
            if not has_flavor_evidence:
                gaps.append("建议开展 KB3 风味评价与感官小试")
        if question_type in {"formula_relation", "formula_replacement", "product_recommendation"}:
            has_population_evidence = "ConstitutionType" in node_types or any(
                (node.get("props") or {}).get(field)
                for node in graph.get("nodes", [])
                for field in ("crowd", "scenario", "applicable_group", "diet_direction", "risk_control")
            )
            if not has_population_evidence:
                gaps.append("建议补充目标人群试食与体质分层验证")
        if question_type == "constitution_recommendation" and "ConstitutionType" not in node_types:
            gaps.append("建议先完成 KB8 体质量表或确认已知体质")
        if question_type == "product_recommendation" and "Product" not in node_types:
            gaps.append("建议补充 KB6 竞品、剂型和市场定位核验")
        if any(token in (question or "") for token in ["合规", "宣传", "标签", "孕妇", "儿童", "禁忌"]) and "ComplianceRule" not in node_types:
            gaps.append("定稿前建议专项核验 KB7 合规、标签和宣传规则")
        if "LACKS_DIRECT_EVIDENCE" in edge_types:
            gaps.append("建议对关键结论补充专项来源与人工复核")
        return gaps[:4]

    def _missing_core_questions(
        self,
        question: str,
        question_type: str,
        graph: dict | None = None,
        constitution_profile: dict | None = None,
        qa_route: str | None = None,
    ) -> list[str]:
        compact = re.sub(r"\s+", "", question or "")
        graph = graph or {}
        node_types = {node.get("type") for node in graph.get("nodes", [])}
        edge_types = {edge.get("type") for edge in graph.get("edges", [])}
        questions: list[str] = []

        def add(value: str) -> None:
            cleaned = value.strip()
            if cleaned and cleaned not in questions:
                questions.append(cleaned)

        for item in self.route_resolver.missing_slot_questions(
            question,
            qa_route,
            constitution_profile=constitution_profile,
        ):
            add(item)

        route = self.route_resolver.by_key(qa_route)
        audience = self.route_resolver.detect_audience(question, qa_route)
        is_personal = audience == "personal" or question_type == "constitution_recommendation"
        is_enterprise = audience == "enterprise"

        personal_hints = ("我", "适合我", "能不能吃", "能吃吗", "体质", "孕妇", "儿童", "老人", "慢病", "过敏", "哺乳")
        product_hints = ("产品", "配料", "保健品", "固体饮料", "代餐粉", "茶包", "口服液", "冲剂", "剂型", "好喝", "风味")
        formula_hints = ("方剂", "方子", "名方", "汤", "丸", "散", "四君子汤", "葛根汤")
        replacement_hints = ("替代", "替换", "代替", "换成", "改造", "药食同源化", "食品化")
        taste_hints = ("好喝", "风味", "口味", "苦", "涩", "药味", "香气", "怕苦")
        dosage_form_hints = ("饮品", "固体饮料", "代餐粉", "茶包", "软糖", "口服液", "冲剂", "片剂", "胶囊", "剂型")
        crowd_hints = ("人群", "儿童", "老人", "女性", "男性", "孕妇", "熬夜", "上班族", "学生", "慢病", "过敏")
        target_hints = ("护肝", "助眠", "抗疲劳", "润肺", "止咳", "化痰", "祛湿", "健脾", "补气", "滋补", "控糖", "降脂")
        risk_hints = ("孕妇", "儿童", "老人", "慢病", "过敏", "哺乳", "高血压", "糖尿病", "肝病", "肾病", "正在用药")
        compliance_hints = ("合规", "宣传", "标签", "GB2760", "GB7718", "普通食品", "禁用", "慎用", "上市")
        has_formula_word = any(token in compact for token in formula_hints)
        has_replacement_word = any(token in compact for token in replacement_hints)
        is_single_herb_replacement = has_replacement_word and not has_formula_word and not any(
            token in compact for token in ("整方", "方剂", "方子", "食品化", "药食同源化", "改造")
        )

        if is_personal:
            if constitution_profile is None and "ConstitutionType" not in node_types and not any(token in compact for token in ("平和质", "气虚质", "阳虚质", "阴虚质", "痰湿质", "湿热质", "血瘀质", "气郁质", "特禀质")):
                add("你是否已知自己的体质，还是需要先做九种体质量表？")
            if any(token in compact for token in product_hints) and "Product" not in node_types:
                add("请补充产品名称、配料表或主要原料，我才能判断是否适合你。")
            if not any(token in compact for token in risk_hints):
                add("是否有孕期、哺乳期、儿童、慢病、过敏或正在用药等风险情况？")
            if not any(token in compact for token in target_hints):
                add("你主要想改善疲劳、睡眠、咳嗽、湿气、怕冷、上火，还是其他具体场景？")
            if not any(token in compact for token in taste_hints):
                add("你更偏好甜、酸、草本香哪种方向？是否需要避开苦味、涩感或药味？")

        if question_type == "formula_replacement":
            if has_formula_word and "Formula" not in node_types:
                add("请补充原方名称或组成，便于核对 KB5 原方依据。")
            if has_replacement_word and "CAN_REPLACE" not in edge_types:
                if is_single_herb_replacement:
                    add("候选替代是否必须药食同源，并优先低苦味、低成本或某个剂型适配？")
                else:
                    add("你是只替换某一味药，还是需要整方药食同源化重组？")
            if not is_single_herb_replacement and not any(token in compact for token in dosage_form_hints):
                add("目标剂型想做饮品、固体饮料、代餐粉、茶包，还是其他形式？")
            if not is_single_herb_replacement and not any(token in compact for token in crowd_hints):
                add("目标人群是谁，例如熬夜、脾胃虚弱、女性、老人或普通大众？")

        elif question_type == "product_recommendation":
            if "Product" not in node_types and any(token in compact for token in product_hints):
                add("请补充产品名、配料表、剂型或竞品名称。")
            if is_enterprise and not any(token in compact for token in target_hints):
                add("这款产品的目标功效或消费场景是什么？")
            if is_enterprise and not any(token in compact for token in dosage_form_hints):
                add("希望优先评估哪种剂型：饮品、固体饮料、代餐粉、茶包还是软糖？")
            if is_enterprise and not any(token in compact for token in taste_hints):
                add("有没有口味、甜度、苦涩感、成本或竞品差异化约束？")
            if any(token in compact for token in compliance_hints) and "ComplianceRule" not in node_types:
                add("请补充食品类别、宣传语、标签场景或目标市场。")

        elif question_type == "formula_relation":
            if "Formula" not in node_types:
                add("请补充更准确的方剂名或原方组成。")
            if not any(token in compact for token in ("剂量", "用量", "配比", "组成")):
                add("是否需要重点查看组成剂量、君臣佐使、主治功效，还是禁忌边界？")

        elif question_type == "herb_efficacy":
            if "Herb" not in node_types:
                add("请补充明确的原料或药材名称。")
            if any(token in compact for token in compliance_hints) and "ComplianceRule" not in node_types:
                add("你想核对的是原料合法性、宣传边界，还是标签/添加剂规则？")
            if is_personal and not any(token in compact for token in risk_hints):
                add("是否属于孕妇、儿童、慢病、过敏或正在用药人群？")

        if not questions and not node_types:
            add("请补充一个明确的药材、方剂、产品、体质或症状名称。")
        return questions[:4]

    @staticmethod
    def _user_id_from_context(current_user: AppUser | dict | None) -> str | None:
        if current_user is None:
            return None
        if isinstance(current_user, dict):
            return current_user.get("id")
        return current_user.__dict__.get("id")

    def _get_constitution_profile(self, current_user: AppUser | dict | None) -> dict | None:
        user_id = self._user_id_from_context(current_user)
        if not user_id:
            return None
        profile = self.postgres_repository.get_constitution_profile(user_id)
        if profile is None:
            return None
        return {
            "id": profile.id,
            "user_id": profile.user_id,
            "primary_constitution": profile.primary_constitution,
            "secondary_constitutions": list(profile.secondary_constitutions or []),
            "source": profile.source,
            "scores": profile.scores or {},
            "notes": profile.notes,
            "last_assessment_id": profile.last_assessment_id,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        }

    def _relevant_constitution_profile(
        self,
        question: str,
        current_user: AppUser | dict | None,
        qa_route: QARoute,
    ) -> dict | None:
        if qa_route.audience != "personal":
            return None

        compact = re.sub(r"\s+", "", question or "")
        third_party_pattern = re.compile(
            r"(?:我家|家里|给|送给).{0,10}(?:老人|老年人|父母|爸爸|妈妈|孩子|儿童|青少年|孕妇|朋友)"
        )
        if third_party_pattern.search(compact):
            return None
        if not any(token in compact for token in ["我", "本人", "自己"]):
            return None
        return self._get_constitution_profile(current_user)

    def _build_constitution_assessment_payload(self, constitution_profile: dict | None) -> dict:
        neo4j_repository = self.graph_retriever.neo4j_repository
        return {
            "mode": "existing_profile" if constitution_profile else "need_user_choice",
            "types": neo4j_repository.list_constitution_types(),
            "questions": neo4j_repository.list_constitution_questions(),
            "score_options": [
                {"value": 1, "label": "从不"},
                {"value": 2, "label": "很少"},
                {"value": 3, "label": "有时"},
                {"value": 4, "label": "经常"},
                {"value": 5, "label": "总是"},
            ],
            "existing_profile": constitution_profile,
        }

    def _should_offer_constitution_panel(
        self,
        question: str,
        question_type: str,
        constitution_profile: dict | None,
        qa_route: str | None = None,
    ) -> bool:
        compact = re.sub(r"\s+", "", question or "")
        if self.route_resolver.should_offer_constitution_panel(qa_route):
            return True
        direct_test_tokens = (
            "我是什么体质",
            "不确定自己的体质",
            "帮我做体质测试",
            "帮我测试体质",
            "帮我测体质",
            "请给我测体质",
            "给我测体质",
            "我要测体质",
            "我想测体质",
            "我想重新测体质",
            "重新测体质",
            "重新测一下体质",
            "重新测评",
            "重新测试",
            "再测一次体质",
            "再测体质",
            "开始体质测试",
            "体质量表",
            "体质问卷",
            "标准量表测评",
            "量表测评",
            "体质辨识",
            "重新辨识体质",
        )
        if question_type == "constitution_recommendation" and any(token in compact for token in direct_test_tokens):
            return True
        if question_type == "constitution_recommendation" and constitution_profile and any(token in compact for token in ("重新测评", "重新测试", "再测一次体质")):
            return True
        return False

    def _build_constitution_panel_answer(self, question: str, payload: dict) -> dict:
        constitution_types = payload.get("types", [])
        constitution_questions = payload.get("questions", [])
        existing_profile = payload.get("existing_profile") or {}
        has_profile = bool(existing_profile)
        if has_profile:
            primary_constitution = existing_profile.get("primary_constitution") or "已保存体质"
            core_conclusion = (
                f"你当前已有体质档案：{primary_constitution}。如果想重新确认，可以在下方直接改选体质，"
                "也可以重新完成标准量表测评；保存后会更新后续知识问答使用的体质档案。"
            )
            next_step = (
                "你可以直接选择新的已知体质，也可以从第 1 题开始重新作答。"
                "量表提交后，系统会用新的结果覆盖当前体质档案。"
            )
            evidence_action = "已带入现有体质档案，并准备重新测评入口"
        else:
            core_conclusion = "现在还不能直接判断你的体质，需要先选择已知体质或完成标准量表测评。"
            next_step = "你可以先手动选择已知体质，也可以从第 1 题开始逐题作答；保存后，后续知识问答会自动带入该体质档案。"
            evidence_action = "下一步需要用户选择已知体质或完成量表作答"
        return {
            "conclusion": "\n\n".join(
                [
                    f"【核心结论】\n{core_conclusion}",
                    "【判断依据】\n体质辨识需要结合 KB8 的九种体质规则和量表题目逐项作答，不能仅凭一句主诉直接下结论。",
                    f"【食养或产品适配建议】\n{next_step}",
                    "【风险与禁忌】\n体质辨识用于食养和产品适配辅助判断，不替代临床诊断。",
                    "【证据边界】\n在没有量表结果或已知体质前，系统不会把体质推荐扩展成确定结论。",
                    "【追问建议】\n完成体质选择或测试后，再继续询问“适合吃什么”“这个产品适不适合我”等问题会更准确。",
                ]
            ),
            "evidence_summary": (
                "图谱检索与证据整理摘要："
                f"命中 {len(constitution_types)} 个体质类型、{len(constitution_questions)} 道体质量表题；"
                f"{evidence_action}，再进入个性化食养、产品适配和风险边界判断。"
            ),
            "cautions": "体质辨识结果仅作食养与产品适配辅助判断，不替代临床诊断。",
            "related_entities": [
                {
                    "id": item.get("constitution_type_name") or f"constitution:{index}",
                    "name": item.get("constitution_type_name") or f"体质{index + 1}",
                    "entity_type": "ConstitutionType",
                }
                for index, item in enumerate(constitution_types[:9])
            ],
            "follow_up_questions": [
                "你想先手动选择已知体质，还是开始标准量表测试？",
                "完成体质保存后，我可以继续帮你判断适合的原料、产品和风险边界。",
            ],
        }

    @staticmethod
    def _empty_graph() -> dict:
        return {
            "nodes": [],
            "edges": [],
            "focus_paths": [],
            "legend": {},
            "metrics": {
                "nodeCount": 0,
                "edgeCount": 0,
            },
        }

    @staticmethod
    def _build_constitution_panel_think(payload: dict) -> str:
        type_count = len(payload.get("types", []))
        question_count = len(payload.get("questions", []))
        existing_profile = payload.get("existing_profile") or {}
        if existing_profile:
            profile_text = f"当前已有体质档案：{existing_profile.get('primary_constitution') or '已保存体质'}，但用户表达了重新测评或确认体质的需求。"
        else:
            profile_text = "当前还没有可用于个性化判断的体质档案。"
        return (
            "我先判断这是一个需要体质辨识的问题。"
            f" {profile_text}"
            f" 当前已准备 {type_count} 个体质类型选项和 {question_count} 道标准量表题，"
            "下一步更适合让用户直接选择已知体质或进入测试，而不是先输出武断结论。"
        )

    def _build_constitution_scale_think(self, graph: dict) -> str:
        recommendation_context = self._build_recommendation_context(graph)
        type_count = len(recommendation_context.get("constitution_types", []))
        question_count = len(recommendation_context.get("constitution_questions", []))
        return (
            f"\u5df2\u547d\u4e2d\u4f53\u8d28\u91cf\u8868\u56fe\u8c31\u8bc1\u636e\uff0c"
            f"\u5305\u542b {type_count} \u4e2a\u4f53\u8d28\u7c7b\u578b\u548c {question_count} \u9053\u91cf\u8868\u9898\u3002"
            "\u4e0b\u9762\u76f4\u63a5\u6574\u7406\u6807\u51c6\u91cf\u8868\u3001\u8bc4\u5206\u65b9\u5f0f\u548c\u5224\u5b9a\u89c4\u5219\u3002"
        )

    def _build_constitution_scale_answer(
        self,
        question: str,
        graph: dict,
        constitution_profile: dict | None = None,
        llm_error: str = "",
    ) -> dict:
        recommendation_context = self._build_recommendation_context(graph)
        constitution_types = recommendation_context.get("constitution_types", [])
        constitution_questions = recommendation_context.get("constitution_questions", [])

        grouped_questions: dict[str, list[dict]] = {}
        for item in constitution_questions:
            constitution_name = item.get("constitution_type_name") or "\u672a\u6807\u6ce8\u4f53\u8d28"
            grouped_questions.setdefault(constitution_name, []).append(item)

        for items in grouped_questions.values():
            items.sort(key=lambda item: (str(item.get("question_code") or ""), int(item.get("question_no") or 0)))

        score_template = next(
            (
                item
                for item in constitution_questions
                if any(item.get(f"score_{index}") for index in range(1, 6))
            ),
            {},
        )
        score_lines = [
            f"{index}\u5206\uff1a{score_template.get(f'score_{index}')}"
            for index in range(1, 6)
            if score_template.get(f"score_{index}")
        ]
        if not score_lines:
            score_lines = [
                "1分：从不",
                "2分：很少",
                "3分：有时",
                "4分：经常",
                "5分：总是",
            ]

        rule_lines = []
        for item in constitution_types:
            name = item.get("constitution_type_name") or "\u672a\u6807\u6ce8\u4f53\u8d28"
            question_total = len(grouped_questions.get(name, []))
            rule = item.get("judgement_rule") or "\u56fe\u8c31\u672a\u63d0\u4f9b\u5224\u5b9a\u89c4\u5219"
            source = item.get("source") or "\u56fe\u8c31\u672a\u63d0\u4f9b\u6765\u6e90"
            rule_lines.append(f"- {name}：{question_total}题；判定规则：{rule}；来源：{source}")

        source_labels = sorted(
            {
                (item.get("source") or "").strip()
                for item in constitution_types
                if (item.get("source") or "").strip()
            }
        )
        source_text = "\u3001".join(source_labels) if source_labels else "\u56fe\u8c31\u5185\u7f6e\u4f53\u8d28\u91cf\u8868\u6570\u636e"

        conclusion = "\n\n".join(
            [
                "【核心结论】\n"
                + (
                    f"你当前已保存的体质档案是“{constitution_profile['primary_constitution']}”，"
                    "如果想重新确认，可以直接在下方使用标准量表重新测评。"
                    if constitution_profile
                    else "知识图谱中已收录标准体质量表，你可以直接在下方逐题完成测评；系统会在提交后自动整理主体质和兼夹体质。"
                ),
                "【判断依据】\n"
                f"\u91cf\u8868\u6765\u6e90\uff1a{source_text}\n"
                "\u8bc4\u5206\u65b9\u5f0f\uff1a\n"
                + "\n".join(f"- {line}" for line in score_lines)
                + "\n- \u6807\u6ce8\u201c\u53cd\u5411\u8ba1\u5206\u201d\u7684\u9898\u76ee\u9700\u8981\u6309\u76f8\u53cd\u65b9\u5411\u6298\u7b97\u3002\n"
                + "\u4f53\u8d28\u5224\u5b9a\u89c4\u5219\uff1a\n"
                + "\n".join(rule_lines),
                "【食养或产品适配建议】\n"
                "请直接在下方组件中选择已知体质或逐题作答；保存后，后续知识问答会自动带入你的体质档案。",
                "【风险与禁忌】\n"
                "\u8fd9\u4efd\u91cf\u8868\u53ea\u80fd\u7528\u4f5c\u8f85\u52a9\u8fa8\u8bc6\uff0c\u4e0d\u7b49\u540c\u4e8e\u4e34\u5e8a\u8bca\u65ad\u3002"
                "\u5982\u679c\u4f60\u6709\u660e\u663e\u4e0d\u9002\u6216\u60f3\u7ed3\u5408\u7528\u836f\uff0c\u4ecd\u9700\u7ed3\u5408\u4e13\u4e1a\u533b\u5e08\u8fa8\u8bc1\u3002",
                "【证据边界】\n"
                "\u672c\u6b21\u56de\u7b54\u57fa\u4e8e\u56fe\u8c31\u4e2d\u7684\u4f53\u8d28\u7c7b\u578b\u3001\u91cf\u8868\u9898\u76ee\u548c\u5224\u5b9a\u89c4\u5219\u6574\u7406\uff1b"
                "\u672a\u5728\u4f60\u5c1a\u672a\u4f5c\u7b54\u524d\u81ea\u884c\u5224\u5b9a\u6700\u7ec8\u4f53\u8d28\u3002",
                "【追问建议】\n"
                "\u4f60\u53ef\u4ee5\u76f4\u63a5\u6309\u9898\u53f7\u56de\u6211 1\u20135 \u5206\uff0c"
                "\u6216\u8005\u8ba9\u6211\u6309\u987a\u5e8f\u4e00\u9898\u9898\u5e26\u4f60\u6d4b\u5b8c\u3002",
            ]
        ).strip()

        related_entities = [
            {
                "id": item.get("constitution_type_name") or f"constitution:{index}",
                "name": item.get("constitution_type_name") or f"\u4f53\u8d28{index + 1}",
                "entity_type": "ConstitutionType",
            }
            for index, item in enumerate(constitution_types[:9])
        ]

        return {
            "conclusion": conclusion,
            "evidence_summary": (
                "图谱检索与证据整理摘要："
                f"\u547d\u4e2d {len(constitution_types)} \u4e2a\u4f53\u8d28\u7c7b\u578b\u548c "
                f"{len(constitution_questions)} \u9053\u4f53\u8d28\u91cf\u8868\u9898\uff0c"
                "\u7cfb\u7edf\u5c06\u7528\u6807\u51c6\u91cf\u8868\u89c4\u5219\u8fdb\u884c\u8bc4\u5206\u548c\u4f53\u8d28\u5206\u7c7b\u3002"
            ),
            "cautions": llm_error or "\u8fd9\u662f\u57fa\u4e8e\u56fe\u8c31\u91cf\u8868\u7684\u8f85\u52a9\u8fa8\u8bc6\u7ed3\u679c\uff0c\u4e0d\u4ee3\u66ff\u4e34\u5e8a\u8bca\u65ad\u3002",
            "related_entities": related_entities,
            "follow_up_questions": [
                "\u6211\u53ef\u4ee5\u6309 1\u20135 \u5206\u9010\u9898\u5e26\u4f60\u505a\u5b8c\u8fd9\u4efd\u4f53\u8d28\u91cf\u8868\u5417\uff1f",
                "\u4f60\u60f3\u5148\u770b\u4e5d\u79cd\u4f53\u8d28\u7684\u5224\u5b9a\u89c4\u5219\uff0c\u8fd8\u662f\u76f4\u63a5\u5f00\u59cb\u7b54\u9898\uff1f",
                "\u4f60\u628a\u6bcf\u9898\u5206\u6570\u53d1\u7ed9\u6211\u540e\uff0c\u6211\u53ef\u4ee5\u5e2e\u4f60\u6574\u7406\u6700\u53ef\u80fd\u7684\u4f53\u8d28\u503e\u5411\u3002",
            ],
            "constitution_assessment": self._build_constitution_assessment_payload(constitution_profile),
        }

    def _build_local_answer(
        self,
        question: str,
        question_type: str,
        selected_entities: list[dict],
        graph: dict,
        llm_error: str,
        constitution_profile: dict | None = None,
        qa_route: str | None = None,
    ) -> dict:
        if qa_route == "risk_boundary":
            return self._build_risk_boundary_local_answer(
                question,
                question_type,
                selected_entities,
                graph,
                llm_error,
                constitution_profile=constitution_profile,
                qa_route=qa_route,
            )

        if not selected_entities and question_type == "product_recommendation":
            preferred_types = (
                ["Formula"]
                if qa_route == "product_development"
                else ["Product", "ConsumerProfile", "ConsumerSegment", "ConsumerReview", "Flavor"]
            )
            selected_entities = self._selected_entities_from_graph(
                graph,
                preferred_types=preferred_types,
                limit=3 if qa_route == "product_development" else 8,
            )

        if not selected_entities:
            payload = {
                "conclusion": (
                    "【核心结论】\n"
                    "当前没有在知识图谱中稳定识别出与问题对应的实体，因此暂时无法给出可靠回答。\n\n"
                    "【证据边界】\n"
                    "本次未形成足够稳定的图谱证据链，因此不会补充图谱外结论。\n\n"
                    "【总结建议】\n"
                    "请补充明确的药材、方剂、产品、体质、人群或症状名称后再查询。"
                ),
                "evidence_summary": "图谱检索与证据整理摘要：这次检索没有形成足够稳定的图谱命中结果。",
                "cautions": llm_error or "建议把问题改成更明确的实体名、症状名、方剂名。",
                "related_entities": [],
                "follow_up_questions": self._build_follow_ups(
                    [],
                    question=question,
                    question_type=question_type,
                    graph=graph,
                    constitution_profile=constitution_profile,
                    qa_route=qa_route,
                ),
            }
            return self._finalize_answer_payload(payload, question_type, qa_route)

        names = [entity.get("name") or entity["id"] for entity in selected_entities[:6]]
        node_lookup = {node["id"]: node for node in graph.get("nodes", [])}
        related_groups = {
            "Formula": [],
            "Effect": [],
            "Herb": [],
            "Flavor": [],
            "NatureFlavor": [],
            "Symptom": [],
            "Taboo": [],
            "Product": [],
            "ConsumerProfile": [],
            "ConsumerSegment": [],
            "ConsumerReview": [],
            "ConstitutionType": [],
            "ConstitutionQuestion": [],
            "ComplianceRule": [],
            "RiskExpression": [],
        }
        for node in graph.get("nodes", []):
            node_type = node.get("type", "Entity")
            if node_type in related_groups and node["id"] not in {entity["id"] for entity in selected_entities}:
                if node["label"] not in related_groups[node_type]:
                    related_groups[node_type].append(node["label"])
        selected_groups = {key: [] for key in related_groups}
        for entity in selected_entities:
            entity_type = entity.get("entity_type", "Entity")
            entity_name = entity.get("name") or entity.get("id")
            if entity_type in selected_groups and entity_name:
                self._append_unique(selected_groups[entity_type], str(entity_name))
        product_candidates = selected_groups["Product"] + related_groups["Product"]
        herb_candidates = selected_groups["Herb"] + related_groups["Herb"]
        effect_candidates = selected_groups["Effect"] + related_groups["Effect"]

        formula_detail_lines = self._build_formula_detail_lines(selected_entities, graph)
        formula_provenance_context = self._build_formula_provenance_context(graph)
        flavor_population_context = self._build_flavor_population_context(
            graph,
            selected_entities,
            constitution_profile=constitution_profile,
        )
        if qa_route == "product_development":
            flavor_population_context = {
                **flavor_population_context,
                "herb_flavor_profiles": [
                    item
                    for item in flavor_population_context.get("herb_flavor_profiles", [])
                    if item.get("is_selected")
                ],
            }
        flavor_population_lines = self._format_flavor_population_lines(flavor_population_context)
        flavor_population_text = (
            "\n".join(flavor_population_lines)
            if flavor_population_lines
            else "建议补充剂型、口味偏好和目标人群/体质信息，并通过 KB3 感官小试进一步确认风味适配。"
        )

        evidence_parts: list[str] = []
        if related_groups["Formula"]:
            evidence_parts.append(f"当前命中的相关方剂包括：{self._join_names(related_groups['Formula'])}。")
        else:
            evidence_parts.append("建议在定稿前补充核对相关方剂的组成、剂量、出处与配伍依据。")

        if related_groups["Product"]:
            evidence_parts.append(f"当前命中的相关产品包括：{self._join_names(related_groups['Product'])}。")
        elif selected_groups["Product"]:
            evidence_parts.append(f"当前命中的产品候选包括：{self._join_names(selected_groups['Product'])}。")
        if related_groups["ConsumerProfile"] or related_groups["ConsumerSegment"]:
            consumer_names = related_groups["ConsumerProfile"] + related_groups["ConsumerSegment"]
            evidence_parts.append(f"当前命中的消费者画像/人群分组包括：{self._join_names(consumer_names[:12])}。")
        if related_groups["ConsumerReview"]:
            evidence_parts.append(f"当前命中的评论偏好证据包括：{self._join_names(related_groups['ConsumerReview'][:6])}。")
        if related_groups["ConstitutionType"]:
            evidence_parts.append(f"当前命中的体质类型包括：{self._join_names(related_groups['ConstitutionType'])}。")
        if related_groups["ComplianceRule"]:
            evidence_parts.append(f"当前命中的合规规则包括：{self._join_names(related_groups['ComplianceRule'][:12])}。")
        if related_groups["RiskExpression"]:
            evidence_parts.append(f"当前命中的禁用/慎用表述包括：{self._join_names(related_groups['RiskExpression'][:12])}。")
        if related_groups["Effect"]:
            evidence_parts.append(f"当前命中的相关功效包括：{self._join_names(related_groups['Effect'][:12])}。")
        if related_groups["Flavor"] or related_groups["NatureFlavor"]:
            flavor_names = related_groups["Flavor"] + related_groups["NatureFlavor"]
            evidence_parts.append(f"当前命中的风味/性味证据包括：{self._join_names(flavor_names[:12])}。")
        if related_groups["Herb"]:
            evidence_parts.append(f"当前命中的相关药材包括：{self._join_names(related_groups['Herb'])}。")
        if related_groups["Symptom"]:
            evidence_parts.append(f"当前命中的相关症状包括：{self._join_names(related_groups['Symptom'][:12])}。")
        evidence_text = "\n".join(evidence_parts)

        evidence_lines = [
            f"图谱检索与证据整理摘要：本次纳入回答的核心实体包括 {self._join_names(names)}。",
        ]
        if related_groups["Formula"]:
            evidence_lines.append(f"命中的方剂证据：{self._join_names(related_groups['Formula'][:8])}。")
        if related_groups["Product"]:
            evidence_lines.append(f"命中的产品证据：{self._join_names(related_groups['Product'][:8])}。")
        elif selected_groups["Product"]:
            evidence_lines.append(f"命中的产品候选：{self._join_names(selected_groups['Product'][:8])}。")
        if related_groups["ConsumerProfile"] or related_groups["ConsumerSegment"]:
            consumer_names = related_groups["ConsumerProfile"] + related_groups["ConsumerSegment"]
            evidence_lines.append(f"命中的消费者画像/人群分组证据：{self._join_names(consumer_names[:8])}。")
        if related_groups["ConsumerReview"]:
            evidence_lines.append(f"命中的评论偏好证据：{self._join_names(related_groups['ConsumerReview'][:4])}。")
        if related_groups["ConstitutionType"]:
            evidence_lines.append(f"命中的体质证据：{self._join_names(related_groups['ConstitutionType'][:8])}。")
        if related_groups["ComplianceRule"]:
            evidence_lines.append(f"命中的合规规则：{self._join_names(related_groups['ComplianceRule'][:8])}。")
        if related_groups["Flavor"] or related_groups["NatureFlavor"] or flavor_population_context["herb_flavor_profiles"]:
            evidence_lines.append("已整理 KB3 风味评价、性味/风味关系和药材风味属性，用于正文的风味与剂型判断。")
        if (
            constitution_profile
            or related_groups["ConstitutionType"]
            or related_groups["ConsumerProfile"]
            or related_groups["ConsumerSegment"]
            or any(item.get("crowd") for item in flavor_population_context["formula_population_profiles"])
        ):
            evidence_lines.append("已带入用户体质档案、消费者画像或图谱中的方剂/体质/产品人群画像，用于人群适配判断。")
        if not any([related_groups["Formula"], related_groups["Product"], related_groups["ConsumerProfile"], related_groups["ConsumerSegment"], related_groups["ConstitutionType"], related_groups["ComplianceRule"]]):
            evidence_lines.append("这次检索没有形成更强的扩展证据链，因此正文只保留保守判断。")

        if qa_route == "personal_product_recommendation" and not llm_error:
            cautions = (
                "送礼型成品产品仍需确认对方是否有慢病、过敏、正在用药或明确忌口；"
                "不要把产品卖点当成疾病治疗承诺。"
            )
        else:
            cautions = llm_error or "当前回答已退回到本地图谱证据总结模式。"
            cautions += "\n疾病、证候、方剂和监管结论应以专项来源与专业审核为准。"
        if not related_groups["Formula"] and any(token in question for token in ["方剂", "方子", "方"]):
            cautions += "\n知识图谱目前没有给出这些命中实体到方剂的直接连接证据。"

        route_label = self._route_label(question, question_type, qa_route)
        route_text = f"{route_label}；{self._kb_route(question, question_type, qa_route)}。"
        route = self.route_resolver.by_key(qa_route)
        product_development_candidate_ids: set[str] = set()
        if qa_route == "product_development":
            selected_herb_ids = {
                entity["id"]
                for entity in selected_entities
                if entity.get("entity_type") == "Herb"
            }
            incompatible_herbs: list[str] = []
            for edge in graph.get("edges", []):
                if edge.get("type") != "INCOMPATIBLE_WITH":
                    continue
                source = node_lookup.get(edge.get("source"), {})
                target = node_lookup.get(edge.get("target"), {})
                if source.get("id") in selected_herb_ids and target.get("type") == "Herb":
                    self._append_unique(incompatible_herbs, str(target.get("label") or target.get("id") or ""))
                elif target.get("id") in selected_herb_ids and source.get("type") == "Herb":
                    self._append_unique(incompatible_herbs, str(source.get("label") or source.get("id") or ""))

            selected_category_ids: set[str] = set()
            for edge in graph.get("edges", []):
                if edge.get("type") != "BELONGS_TO_EFFECT_CATEGORY":
                    continue
                source = node_lookup.get(edge.get("source"), {})
                target = node_lookup.get(edge.get("target"), {})
                if source.get("id") in selected_herb_ids and target.get("type") == "EffectCategory":
                    selected_category_ids.add(str(target.get("id")))
                elif target.get("id") in selected_herb_ids and source.get("type") == "EffectCategory":
                    selected_category_ids.add(str(source.get("id")))
            for edge in graph.get("edges", []):
                if edge.get("type") != "BELONGS_TO_EFFECT_CATEGORY":
                    continue
                source = node_lookup.get(edge.get("source"), {})
                target = node_lookup.get(edge.get("target"), {})
                herb_node = source if source.get("type") == "Herb" else target if target.get("type") == "Herb" else {}
                category_node = source if source.get("type") == "EffectCategory" else target if target.get("type") == "EffectCategory" else {}
                herb_props = herb_node.get("props", {}) or {}
                if (
                    category_node.get("id") in selected_category_ids
                    and herb_node.get("id") not in selected_herb_ids
                    and str(herb_props.get("food_homology") or "").strip() == "是"
                ):
                    product_development_candidate_ids.add(str(herb_node.get("id")))

            restricted_herbs: list[str] = []
            conditional_regulatory_notes: list[str] = []
            for node in graph.get("nodes", []):
                if node.get("type") != "Herb" or node.get("id") not in selected_herb_ids:
                    continue
                props = node.get("properties") or node.get("props") or {}
                homology_status = str(props.get("food_homology") or props.get("is_food_homology") or "").strip()
                directory_source = str(props.get("directory_source") or "").strip()
                ordinary_food_status = str(props.get("ordinary_food_status") or "").strip()
                health_food_status = str(props.get("health_food_status") or "").strip()
                regulatory_summary = str(props.get("regulatory_summary") or "").strip()
                if ordinary_food_status in {"可用", "条件可用"} or health_food_status:
                    self._append_unique(
                        conditional_regulatory_notes,
                        regulatory_summary
                        or str(props.get("ordinary_food_conditions") or health_food_status),
                    )
                elif homology_status == "否" or "非药食同源" in directory_source or "未匹配" in directory_source:
                    self._append_unique(restricted_herbs, str(node.get("label") or node.get("id") or ""))

            wants_sour = "酸" in question
            wants_sweet = any(token in question for token in ["甜", "甘"])
            flavor_candidate_nodes = []
            for node in graph.get("nodes", []):
                if node.get("type") != "Herb" or node.get("id") in selected_herb_ids:
                    continue
                props = node.get("properties") or node.get("props") or {}
                if str(props.get("food_homology") or "").strip() != "是":
                    continue
                sour_score = float(props.get("sour_contribution") or 0)
                sweet_score = float(props.get("sweet_contribution") or 0)
                if (wants_sour and sour_score >= 0.5) or (wants_sweet and sweet_score >= 0.7):
                    flavor_candidate_nodes.append(node)
                    product_development_candidate_ids.add(str(node.get("id")))
            flavor_candidate_nodes.sort(
                key=lambda node: (
                    -float((node.get("properties") or node.get("props") or {}).get("sour_contribution") or 0),
                    -float((node.get("properties") or node.get("props") or {}).get("sweet_contribution") or 0),
                    str(node.get("label") or ""),
                )
            )

            core_ingredients = [
                str(entity.get("name") or entity.get("id"))
                for entity in selected_entities
                if entity.get("entity_type") == "Herb"
            ]
            alternative_ingredients = [
                str(node.get("label") or node.get("id"))
                for node in graph.get("nodes", [])
                if node.get("id") in product_development_candidate_ids
            ][:5]
            core_name = core_ingredients[0] if core_ingredients else ""
            core_node = next(
                (
                    node
                    for node in graph.get("nodes", [])
                    if node.get("type") == "Herb" and node.get("id") in selected_herb_ids
                ),
                {},
            )
            core_props = core_node.get("properties") or core_node.get("props") or {}
            ordinary_conditions = str(core_props.get("ordinary_food_conditions") or "").strip()
            trial_doses: list[dict] = []
            formula_lines = [
                "- 计量口径：以下按干基原料、成人基础版单份粉体估算，默认1份/日；均为研发小试值，不是临床剂量或成品标签定稿量。",
            ]
            proposed_ingredient_names: list[str] = []
            if core_name:
                core_dose = self._product_trial_dose(core_name, core_props, role="君")
                trial_doses.append(core_dose)
                proposed_ingredient_names.append(core_name)
                formula_lines.append(
                    f"- {core_name}：君：作为配方核心；{self._format_product_trial_dose(core_dose)}；"
                    f"{ordinary_conditions or '具体品种、来源、加工规格和食品合规身份需在定稿前核验。'}"
                )
            else:
                primary_prototype = (formula_provenance_context.get("formula_prototypes") or [{}])[0]
                prototype_name = str(primary_prototype.get("formula_name") or "参考原型")
                prototype_ingredients = list(primary_prototype.get("ingredients") or [])
                formula_lines.append(
                    f"- 本次未指定核心原料，先以 {prototype_name} 的原方组成为借鉴范围；"
                    "原方不直接等同于食品配方，每味原料仍需分别通过 KB1/KB7 合规核验。"
                )
                development_roles = ("君", "臣", "佐", "使")
                for ingredient_name in prototype_ingredients:
                    ingredient_node = next(
                        (
                            node
                            for node in graph.get("nodes", [])
                            if node.get("type") == "Herb"
                            and str(node.get("label") or node.get("id") or "") == ingredient_name
                        ),
                        {},
                    )
                    ingredient_props = ingredient_node.get("properties") or ingredient_node.get("props") or {}
                    food_homology = str(ingredient_props.get("food_homology") or "").strip()
                    ordinary_status = str(ingredient_props.get("ordinary_food_status") or "").strip()
                    if food_homology != "是" and ordinary_status not in {"可用", "条件可用"}:
                        formula_lines.append(
                            f"- {ingredient_name}：待核验：保留为原方组成证据，"
                            "在食品原料身份与加工规格核验完成前不纳入本版定量草案。"
                        )
                        continue
                    role = development_roles[min(len(proposed_ingredient_names), len(development_roles) - 1)]
                    dose = self._product_trial_dose(ingredient_name, ingredient_props, role=role)
                    trial_doses.append(dose)
                    proposed_ingredient_names.append(ingredient_name)
                    formula_lines.append(
                        f"- {ingredient_name}：{role}（研发暂定）：承接 {prototype_name} 的组方逻辑；"
                        f"{self._format_product_trial_dose(dose)}。"
                    )
                if not proposed_ingredient_names:
                    formula_lines.append(
                        "- 定量草案：需先完成原方各味食品原料身份核验，再确定可进入饮品小试的原料与用量。"
                    )
            used_flavor_ids: set[str] = set()
            if wants_sour:
                sour_node = next(
                    (
                        node
                        for node in flavor_candidate_nodes
                        if float((node.get("properties") or node.get("props") or {}).get("sour_contribution") or 0)
                        >= 0.5
                    ),
                    None,
                )
                if sour_node:
                    used_flavor_ids.add(str(sour_node.get("id")))
                    proposed_ingredient_names.append(str(sour_node.get("label") or sour_node.get("id")))
                    sour_props = sour_node.get("properties") or sour_node.get("props") or {}
                    sour_dose = self._product_trial_dose(
                        str(sour_node.get("label") or sour_node.get("id")),
                        sour_props,
                        role="臣",
                    )
                    trial_doses.append(sour_dose)
                    formula_lines.append(
                        f"- {sour_node.get('label')}：臣：提供微酸主体并压低人参苦味、药味；"
                        f"{self._format_product_trial_dose(sour_dose)}。"
                    )
            if wants_sweet:
                sweet_preference = {
                    name: index
                    for index, name in enumerate(["大枣", "桑椹", "枸杞子", "桂圆", "龙眼肉"])
                }
                sweet_candidates = [
                    node
                    for node in flavor_candidate_nodes
                    if str(node.get("id")) not in used_flavor_ids
                    and float((node.get("properties") or node.get("props") or {}).get("sweet_contribution") or 0)
                    >= 0.7
                ]
                sweet_candidates.sort(
                    key=lambda node: (
                        sweet_preference.get(str(node.get("label") or node.get("id") or ""), 99),
                        float((node.get("properties") or node.get("props") or {}).get("sour_contribution") or 0),
                        -float((node.get("properties") or node.get("props") or {}).get("sweet_contribution") or 0),
                        str(node.get("label") or ""),
                    )
                )
                sweet_node = sweet_candidates[0] if sweet_candidates else None
                if sweet_node:
                    used_flavor_ids.add(str(sweet_node.get("id")))
                    proposed_ingredient_names.append(str(sweet_node.get("label") or sweet_node.get("id")))
                    sweet_props = sweet_node.get("properties") or sweet_node.get("props") or {}
                    sweet_dose = self._product_trial_dose(
                        str(sweet_node.get("label") or sweet_node.get("id")),
                        sweet_props,
                        role="佐",
                    )
                    trial_doses.append(sweet_dose)
                    formula_lines.append(
                        f"- {sweet_node.get('label')}：佐：补充自然甜感和圆润度；"
                        f"{self._format_product_trial_dose(sweet_dose)}；老年人版本优先控制添加糖总量。"
                    )
            if trial_doses:
                baseline_total = sum(float(item["baseline_g"]) for item in trial_doses)
                baseline_formula = " + ".join(
                    f"{item['name']} {self._format_gram_value(item['baseline_g'])}g"
                    for item in trial_doses
                )
                formula_lines.append(
                    f"- 单份基准配方：{baseline_formula}，合计约 {self._format_gram_value(baseline_total)}g/份；建议先按1份/日开展小试。"
                )
            formula_lines.extend(
                [
                    (
                        f"- 风味协同候选：{self._join_names(alternative_ingredients)}。候选通过药食同源与风味属性初筛，不代表可直接定稿，仍需复核体质、慢病用药、禁忌和工艺。"
                        if alternative_ingredients
                        else "- 风味协同候选：建议继续筛选同时满足合规、目标风味和人群适配的原料。"
                    ),
                    "- 小试设计：对通过合规复核的原料建立低、中、高梯度，验证酸甜比、苦味遮蔽、后味、稳定性和目标人群接受度。",
                ]
            )
            compliance_text = (
                f"合规初筛显示，{self._join_names(restricted_herbs[:4])} 的普通食品原料身份仍需专项核验。"
                "在完成具体品种、来源、加工规格和适用法规核验前，不得将其写入普通食品定稿配方，也不能据此推断唯一监管路径。"
                if restricted_herbs
                else (
                    "\n".join(conditional_regulatory_notes)
                    + "\n必须区分普通食品与保健食品路径；保健食品原料资格不能自动替代普通食品原料资格，复配产品也不能直接套用单方备案路径。"
                    if conditional_regulatory_notes
                    else (
                        f"可参考已命中的合规规则：{self._join_names(related_groups['ComplianceRule'][:8])}。"
                        if related_groups["ComplianceRule"]
                        else "建议继续核验 KB1/KB7 适用规则；当前配方仅作为待验证研发草案。"
                    )
                )
            )
            if incompatible_herbs:
                compliance_text += (
                    f"\n图谱配伍禁忌证据：{self._join_names(core_ingredients)}不应与"
                    f"{self._join_names(incompatible_herbs[:6])}作为协同原料使用；这些节点只进入风险排除，不进入配方候选。"
                )
            audience_lines: list[str] = []
            if "女性" in question:
                audience_lines.append("- 20-30 岁女性：可作为成人基础版的目标画像，但仍需按气虚、阴虚、湿热等体质倾向和孕哺状态继续分层。")
            if any(token in question for token in ["青少年", "儿童", "学生"]):
                audience_lines.append("- 青少年：不作为当前核心原料配方的默认适用人群，不输出成人用量；需先补充年龄边界和专项安全/合规证据。")
            if any(token in question for token in ["60岁", "老年", "老人", "中老年"]):
                audience_lines.append("- 60岁以上老年人：建议采用低糖、易冲调或小容量饮品形态；先核对高血压、糖代谢异常、睡眠情况、胃食管反流、过敏和正在用药，再确定核心原料梯度、糖度与单次饮用量。")
            if not audience_lines:
                audience_lines.append("- 目标人群：需按年龄、体质、慢病/用药和口味偏好分别判断，不能默认共用同一配方。")
            flavor_design_lines = [line for line in flavor_population_lines if line.startswith("风味证据")]
            flavor_design_text = (
                "\n".join(flavor_design_lines)
                if flavor_design_lines
                else "建议按低、中、高三个核心原料梯度开展苦味、药味、后味和整体接受度测试。"
            )
            if wants_sour or wants_sweet:
                flavor_design_text += (
                    "\n目标设为微酸偏甜：酸味用于缩短人参苦味和药味后味，甜味用于圆润口感；"
                    "老年人版本优先采用自然风味协同并控制添加糖，不以高甜掩盖苦味。"
                )
            provenance_lines = self._format_formula_provenance_lines(formula_provenance_context)
            adjustment_lines = self._build_formula_adjustment_lines(
                formula_provenance_context,
                proposed_ingredient_names,
            )
            elderly_target = any(token in question for token in ["60岁", "老年", "老人", "中老年"])
            primary_formula_name = str(
                (formula_provenance_context.get("formula_prototypes") or [{}])[0].get("formula_name")
                or ""
            )
            needs_process_detail = any(token in question for token in ["饮品", "饮料", "工艺", "炮制"])
            process_validation_text = (
                "1. 原料验收：逐味确认品种、来源、批次、食品合规身份、水分及污染物指标；原方组成证据与食品投料资格分开审核。\n"
                "2. 净制与炮制对照：分别记录净选、去核/切制、干燥和必要的炒制条件；涉及辅料炮制时单独核验辅料与食品路径，不把研发炮制样直接视为定稿原料。\n"
                "3. 水提小试：以料液比 1:8、1:10、1:12，温度 85、90、95℃，时间 30、45、60 分钟建立参数矩阵；比较一次提取与二次提取的风味、可溶性固形物和目标成分保留情况。\n"
                "4. 调配与稳定性：过滤后分别做原饮液、浓缩液和冲调粉方向；验证糖度、pH、沉淀、色泽、后味及加速稳定性，老年人版本优先低糖、小容量和易开启包装。\n"
                "5. 杀菌与灌装：依据最终 pH、包装和微生物挑战结果确定巴氏、热灌装或其他工艺，不预设未经验证的商业灭菌参数。\n"
                "6. 中等价位控制：优先使用常规食品级原料和水提工艺，按单份原料、能耗、包材、损耗与检测成本核算，再决定是否采用提取物或复杂炮制工艺。"
                if needs_process_detail
                else (
                    "1. 核验核心原料品种、来源、规格和食品合规身份。\n"
                    "2. 确定主功效与剂型后做配比梯度、感官、稳定性和相容性小试。\n"
                    "3. 按目标人群分别验证风味接受度、食用场景和风险排除条件。"
                )
            )
            conclusion_parts = [
                (
                    "【核心结论】\n可以形成一版面向60岁以上人群、微酸偏甜的人参复配研发草案，但必须先锁定产品监管路径和人参参龄。普通食品路径仅可使用符合公告条件的5年及以下人工种植人参；5年以上人参不能直接据此进入普通食品复配方。"
                    if elderly_target and core_name == "人参"
                    else (
                        f"【核心结论】\n可将数据库中的 {primary_formula_name} 作为首要借鉴方剂，研发一版面向60岁以上人群、中等价位的晚间舒缓饮品。方剂用于解释组方来源，最终食品配方仍需逐味通过合规、慢病用药、风味和工艺验证；普通食品宣传不得直接作疾病治疗或睡眠改善承诺。"
                        if elderly_target and primary_formula_name
                        else "【核心结论】\n当前问题应按产品研发处理，并先形成一个成人基础版，再按目标人群拆分；不同年龄与体质人群不能直接套用同一配方与用量。"
                    )
                ),
                (
                    "【产品定位】\n以指定核心原料为研发起点，围绕目标功效、体质适配和低苦低药味体验设计；以下为待验证研发草案。"
                    if core_name
                    else f"【产品定位】\n以 {primary_formula_name or 'KB5参考原型'} 为借鉴，定位为老年人晚间饮用、低糖易入口的中等价位饮品；围绕目标功效、人群、剂型、价格与工艺约束形成待验证草案，不把研发改方表述为原方复刻。"
                ),
                f"【名方溯源与借鉴】\n{chr(10).join(provenance_lines)}",
                f"【配方方案】\n{chr(10).join(formula_lines)}",
                f"【配方调整与替换依据】\n{chr(10).join(adjustment_lines)}",
                f"【体质与人群适配】\n{chr(10).join(audience_lines)}",
                "【功效逻辑】\n"
                + (
                    f"当前可用于配方取舍的功效线索包括：{self._join_names(effect_candidates[:8])}。"
                    if effect_candidates
                    else "当前图谱未形成足够稳定的目标功效链，需先明确主功效和消费场景。"
                ),
                f"【风味与剂型设计】\n{flavor_design_text}",
                f"【合规与风险边界】\n{compliance_text}",
                f"【研发验证】\n{process_validation_text}",
            ]
        elif question_type == "product_recommendation" and route and route.audience == "personal":
            conclusion_parts = [
                "【核心结论】\n"
                + (
                    f"当前可以围绕 {self._join_names(product_candidates[:4])} 做个人产品适配判断，但仍需要结合送礼对象的慢病、用药和口味偏好。"
                    if product_candidates
                    else "当前还缺少直接产品命中，建议补充产品名、配料表或主要原料后再判断是否适合你。"
                ),
                f"【判断依据】\n{route_text}",
                "【食养或产品适配建议】\n"
                + (
                    f"已命中产品/原料线索：{self._join_names((product_candidates + herb_candidates + effect_candidates)[:8])}。"
                    if product_candidates or herb_candidates or effect_candidates
                    else "图谱暂未形成稳定的产品成分链条，需要补充配料表。"
                ),
                f"【风险与禁忌】\n{cautions}",
                "【证据边界】\n以上只基于图谱命中的产品、原料、体质、风味和合规证据整理，不构成疾病诊断或治疗建议。",
            ]
        elif question_type == "product_recommendation":
            conclusion_parts = [
                "【核心结论】\n"
                + (
                    f"当前可以先围绕 {self._join_names(product_candidates[:4])} 做产品适配判断。"
                    if product_candidates
                    else "当前还缺少直接产品命中，建议补充产品名、剂型或目标场景后再做更具体判断。"
                ),
                f"【任务路由】\n{route_text}",
                "【推荐理由】\n"
                + (f"可参考的相关产品、原料或功效线索：{self._join_names((product_candidates + herb_candidates + effect_candidates)[:8])}。" if product_candidates or herb_candidates or effect_candidates else "建议补充产品配料、目标人群和使用场景后再确定推荐理由。"),
                "【研发或产品建议】\n"
                + (f"可优先查看相关产品：{self._join_names(product_candidates)}。" if product_candidates else "建议补充产品名、剂型或目标场景，再做产品化判断。"),
                "【风味与剂型判断】\n"
                + (f"可参考的风味相关线索：{self._join_names(product_candidates + herb_candidates[:6])}。\n{flavor_population_text}" if product_candidates or herb_candidates or flavor_population_lines else "建议通过感官小试和剂型适配试验进一步确认。"),
                "【合规边界】\n"
                + (f"可参考合规规则：{self._join_names(related_groups['ComplianceRule'][:8])}。" if related_groups["ComplianceRule"] else "定稿前需专项核验适用法规；普通食品宣传仍需避免治疗化表达。"),
                "【下一步验证】\n建议补充目标剂型、风味偏好、适用人群、成本区间和宣传卖点，再做感官评价、稳定性和合规文案验证。",
            ]
        elif question_type == "constitution_recommendation":
            conclusion_parts = [
                "【核心结论】\n"
                + (
                    f"当前可以围绕 {self._join_names(related_groups['ConstitutionType'][:3])} 这类体质线索做食养和风险边界判断。"
                    if related_groups["ConstitutionType"]
                    else "如果还没有完成体质选择或量表测评，当前只能先给保守的食养边界，不能直接确定体质。"
                ),
                f"【判断依据】\n{route_text}",
                "【食养或产品适配建议】\n"
                + (f"当前可参考的体质类型包括：{self._join_names(related_groups['ConstitutionType'])}。" if related_groups["ConstitutionType"] else "如果尚未完成体质问卷，不能直接判定体质；建议先补充量表作答或已知体质。"),
                f"【风险与禁忌】\n{cautions}",
                "【证据边界】\n以上只基于图谱命中的体质、原料、禁忌和食养规则整理，不构成疾病诊断。",
                "【追问建议】\n可以继续补充体质问卷得分、年龄、人群状态、过敏史和想改善的具体场景。",
            ]
        elif question_type == "formula_replacement":
            formula_lines = formula_detail_lines or ["建议补充原方名称、组成和剂量，便于核对 KB5 原方依据。"]
            conclusion_parts = [
                "【核心结论】\n当前回答会先保留原方依据，再给出可替代和不可替代的边界，不把动态替代说成现成成方。",
                f"【原方依据】\n{chr(10).join(formula_lines)}",
                f"【替代依据】\n{evidence_text}",
                "【保留与替代分流】\n药食同源原料应优先保留；非药食同源或高风险原料需要进入 KB4 单味替代评分，再结合 KB1 合法性复核。",
                "【动态替代对比】\n优先比较功效相近、风味接受度和安全性更稳妥的候选项；若缺少替代评分，则只保留原方依据和证据边界。",
                "【重组配方建议】\n当前只给出基于图谱证据的动态重组方向，不声称存在预生成方剂替代版本。",
                "【风味与剂型优化】\n替代后仍需结合 KB3 风味接受度和 KB6 剂型/产品证据，优先降低苦涩、药味和后味风险。",
                f"【风味与人群适配】\n{flavor_population_text}",
                "【合规边界】\n普通食品化表达不能承诺治疗疾病；涉及标签、添加剂和宣传时需继续调用 KB7。",
                f"【证据边界】\n{cautions}",
            ]
        else:
            conclusion_parts = [
                f"【核心结论】\n当前可先围绕 {self._join_names(names[:3])} 的已命中知识做保守回答，超出图谱直接证据的部分会明确留在边界里。"
            ]
            if formula_detail_lines:
                conclusion_parts.append(f"【方剂组成与剂量】\n{chr(10).join(formula_detail_lines)}")
            conclusion_parts.append(f"【知识依据】\n{evidence_text}")
            conclusion_parts.append(f"【风味与人群适配】\n{flavor_population_text}")
            conclusion_parts.append(f"【风险与禁忌】\n{cautions}")
            conclusion_parts.append("【证据边界】\n以上内容仅基于当前知识图谱命中的节点、关系和属性生成。")
            conclusion_parts.append("【总结建议】\n如果需要更精确的方剂剂量、替代路径、风味或合规判断，请继续补充具体方剂名称、目标人群和剂型。")

        related_entities = [
            {
                "id": entity["id"],
                "name": entity.get("name") or entity["id"],
                "entity_type": entity.get("entity_type", "Entity"),
            }
            for entity in selected_entities[:12]
        ]
        if qa_route == "product_development":
            for node in graph.get("nodes", []):
                if node.get("id") not in product_development_candidate_ids:
                    continue
                related_entities.append(
                    {"id": node["id"], "name": node["label"], "entity_type": node.get("type", "Herb")}
                )
        for edge in graph.get("edges", [])[:12]:
            for node_id in [edge["source"], edge["target"]]:
                node = node_lookup.get(node_id)
                if node is None or node["type"] in {"Question", "Attribute", "EvidenceNote"}:
                    continue
                if qa_route == "product_development" and node["type"] == "Herb" and node["id"] not in (
                    {
                        entity["id"]
                        for entity in selected_entities
                        if entity.get("entity_type") == "Herb"
                    }
                    | product_development_candidate_ids
                ):
                    continue
                item = {"id": node["id"], "name": node["label"], "entity_type": node.get("type", "Entity")}
                if item not in related_entities:
                    related_entities.append(item)

        payload = {
            "conclusion": "\n".join(conclusion_parts),
            "evidence_summary": "\n".join(evidence_lines),
            "cautions": cautions,
            "related_entities": related_entities[:20],
            "follow_up_questions": self._build_follow_ups(
                selected_entities,
                question=question,
                question_type=question_type,
                graph=graph,
                constitution_profile=constitution_profile,
                qa_route=qa_route,
            ),
        }
        return self._finalize_answer_payload(payload, question_type, qa_route)

    def _build_risk_boundary_local_answer(
        self,
        question: str,
        question_type: str,
        selected_entities: list[dict],
        graph: dict,
        llm_error: str,
        *,
        constitution_profile: dict | None = None,
        qa_route: str | None = None,
    ) -> dict:
        compact = re.sub(r"\s+", "", question or "")
        is_child = any(token in compact for token in ["儿童", "小孩", "孩子", "男童", "女童", "幼儿", "少儿"]) or bool(
            re.search(r"\d{1,2}岁", compact)
        )
        is_pregnancy = any(token in compact for token in ["孕妇", "孕期", "哺乳"])
        has_fever = any(token in compact for token in ["发热", "发烧", "高热", "体温"])
        has_cough_phlegm = any(token in compact for token in ["咳嗽", "多痰", "痰"])
        asks_formula = any(token in compact for token in ["药方", "方剂", "方子", "开药", "推荐"])

        risk_person = "儿童" if is_child else "孕妇/哺乳期人群" if is_pregnancy else "高风险人群"
        symptom_bits: list[str] = []
        if has_cough_phlegm:
            symptom_bits.append("咳嗽多痰")
        if has_fever:
            symptom_bits.append("发热")
        symptom_text = "、".join(symptom_bits) if symptom_bits else "症状信息尚不完整"

        node_groups: dict[str, list[str]] = {
            "Herb": [],
            "Formula": [],
            "Product": [],
            "Taboo": [],
            "ComplianceRule": [],
            "RiskExpression": [],
            "ConstitutionType": [],
            "Flavor": [],
            "ConsumerProfile": [],
            "ConsumerSegment": [],
        }
        herb_props_by_name: dict[str, dict] = {}
        for entity in selected_entities:
            node_type = entity.get("entity_type", "Entity")
            name = entity.get("name") or entity.get("id")
            if node_type in node_groups and name:
                self._append_unique(node_groups[node_type], str(name))
            if node_type == "Herb" and name:
                herb_props_by_name.setdefault(str(name), entity.get("props", {}) or {})
        for node in graph.get("nodes", []):
            node_type = node.get("type", "Entity")
            label = node.get("label") or node.get("id")
            if node_type in node_groups and label:
                self._append_unique(node_groups[node_type], str(label))
            if node_type == "Herb" and label:
                herb_props_by_name.setdefault(str(label), node.get("props", {}) or {})

        def _is_food_homology(props: dict) -> bool:
            food_value = str(props.get("is_food_homology") or props.get("food_homology") or "").strip()
            directory_source = str(props.get("directory_source") or "")
            return food_value == "是" or "药食同源目录" in directory_source

        def _risk_text(props: dict) -> str:
            return "；".join(
                str(props.get(key) or "")
                for key in [
                    "contraindication",
                    "usage_precautions",
                    "usage_note",
                    "pregnancy_taboo",
                    "food_use_limit",
                    "directory_source",
                ]
                if props.get(key)
            )

        def _has_symptom_relevance(props: dict) -> bool:
            text = "；".join(
                str(props.get(key) or "")
                for key in ["efficacy", "symptom_text", "effect_level1", "effect_level2", "flavor", "aroma_description"]
            )
            if has_cough_phlegm and any(token in text for token in ["咳", "痰", "肺", "咽", "润燥", "润肺", "化痰", "止咳", "平喘"]):
                return True
            if has_fever and any(token in text for token in ["清热", "凉", "热病", "肺热", "风热"]):
                return True
            return False

        def _number_prop(props: dict, key: str) -> float | None:
            try:
                value = props.get(key)
                if value in (None, ""):
                    return None
                return float(value)
            except (TypeError, ValueError):
                return None

        preferred_food_herbs: list[str] = []
        cautious_food_herbs: list[str] = []
        exclude_or_verify_herbs: list[str] = []
        for herb_name in node_groups["Herb"]:
            props = herb_props_by_name.get(herb_name, {})
            risk_text = _risk_text(props)
            nature = str(props.get("nature") or "")
            bitter_risk = _number_prop(props, "bitter_risk")
            herbal_risk = _number_prop(props, "herbal_medicine_risk")
            fever_heat_conflict = has_fever and any(token in nature for token in ["温", "热", "大热"])
            non_food_or_strong_risk = (
                not _is_food_homology(props)
                or "非药食同源" in risk_text
                or "禁用" in risk_text
                or "不宜" in risk_text
                or str(props.get("is_toxic") or "") == "是"
            )
            if non_food_or_strong_risk:
                self._append_unique(exclude_or_verify_herbs, herb_name)
                continue
            if not _has_symptom_relevance(props):
                self._append_unique(cautious_food_herbs, herb_name)
                continue
            has_mild_flavor = (bitter_risk is None or bitter_risk <= 0.35) and (herbal_risk is None or herbal_risk <= 0.5)
            if has_mild_flavor and not fever_heat_conflict and "慎用" not in risk_text:
                self._append_unique(preferred_food_herbs, herb_name)
            else:
                self._append_unique(cautious_food_herbs, herb_name)

        matched_items = (
            node_groups["Herb"]
            + node_groups["Product"]
            + node_groups["Formula"]
            + node_groups["ConstitutionType"]
        )
        evidence_target = self._join_names(matched_items[:8]) if matched_items else "本次没有稳定命中具体原料、方剂或产品"
        preferred_line = (
            f"可优先核验的药食同源方向：{self._join_names(preferred_food_herbs[:5])}。"
            if preferred_food_herbs
            else ""
        )
        cautious_line = (
            f"需谨慎、建议专业确认后再考虑的药食同源线索：{self._join_names(cautious_food_herbs[:6])}。"
            if cautious_food_herbs
            else ""
        )
        excluded_line = (
            f"仅作为排除或配伍核验线索，不作为家庭自用推荐：{self._join_names(exclude_or_verify_herbs[:6])}。"
            if exclude_or_verify_herbs
            else ""
        )
        flavor_context = (
            f"已看到的风味/人群线索包括：{self._join_names((node_groups['Flavor'] + node_groups['ConsumerProfile'] + node_groups['ConsumerSegment'])[:8])}。"
            if node_groups["Flavor"] or node_groups["ConsumerProfile"] or node_groups["ConsumerSegment"]
            else "还缺少孩子实际口味偏好、可接受剂型，以及针对该年龄段的风味接受证据。"
        )
        taboo_context = (
            f"需要重点避开的风险线索包括：{self._join_names((node_groups['Taboo'] + node_groups['RiskExpression'] + node_groups['ComplianceRule'])[:8])}。"
            if node_groups["Taboo"] or node_groups["RiskExpression"] or node_groups["ComplianceRule"]
            else "当前没有足够禁忌、用药史和配伍核验证据支持自行组合药方。"
        )

        if is_child and has_fever:
            core = (
                f"{risk_person}{symptom_text}时，可以先从图谱支持的药食同源辅助方向做筛选："
                "优先考虑风味温和、低苦味、偏清润或利咽化痰方向的原料/产品；传统成方和含非药食同源药材的方剂不作为家庭自用首选。"
            )
        elif is_pregnancy:
            core = (
                "孕期或哺乳期可以先按图谱筛出低风险、普通食品化、风味温和的食养方向；"
                "强功效原料、多味药方和禁忌不明产品不作为首选。"
            )
        else:
            core = (
                f"{risk_person}场景下可以先按图谱证据给出辅助食养或产品方向，但要把症状严重程度、基础病、过敏史和正在用药作为筛选条件。"
            )

        candidate_pieces = [piece for piece in [preferred_line, cautious_line] if piece]
        if node_groups["Product"]:
            candidate_pieces.append(f"产品线索可继续按配料、剂型和适用人群核验：{self._join_names(node_groups['Product'][:5])}。")
        if not candidate_pieces:
            candidate_pieces.append("建议先按药食同源合法性、症状相关性、风味接受度和人群风险完成方向性筛选。")
        candidate_line = " ".join(candidate_pieces)
        suggestion = (
            f"1. {candidate_line}\n"
            "2. 优先选择药食同源合法、风味接受度较高、苦味/药味风险较低的原料或产品方向；非药食同源药材只用于排除和风险核验。\n"
            "3. 对咳嗽多痰伴发热，可把候选方向限定在清润、利咽、化痰辅助和易接受剂型，不把传统中药成方直接作为家庭方案。\n"
            "4. 如果命中具体原料或产品，再按功效匹配、风味接受度、禁忌、合规边界和儿童人群适配做二次筛选。"
        )
        if asks_formula:
            suggestion += "\n5. 可以给药食同源辅助方向和候选原料，但不生成儿童剂量或可直接照用的完整家庭药方。"

        follow_ups = self._dedupe_follow_ups(
            [
                "症状持续多久、最高体温是多少，是否有喘憋、精神差、持续高热或夜间加重？",
                "是否已经就医或正在使用退烧药、止咳药、抗生素等药物，是否有过敏史或基础病？",
                FLAVOR_PREFERENCE_FOLLOW_UP,
            ],
            limit=4,
        )
        conclusion = (
            f"【核心结论】\n{core}\n\n"
            "【判断依据】\n"
            f"1. 当前问题同时包含{risk_person}、{symptom_text}和药方/推荐意图，业务上走个人端风险边界，但仍需要基于图谱先给辅助食养方向。\n"
            f"2. 本次图谱核心命中：{evidence_target}。这些证据可用于筛选候选方向、风味和禁忌，不应直接扩展成儿童剂量或处方。\n"
            f"3. 原料分层判断：{' '.join(piece for piece in [preferred_line, cautious_line, excluded_line] if piece) or '建议补充明确原料名称、配料表和风险信息后再分层。'}\n"
            "4. 发热伴咳嗽多痰需要区分寒热、病程、体温、精神状态、既往病史和用药情况，因此完整方剂和剂量需要留在专业判断之后。\n\n"
            f"【食养或产品适配建议】\n{suggestion}\n\n"
            f"【风味与人群适配】\n{flavor_context}\n\n"
            f"【证据边界】\n方剂组成、儿童剂量、病因诊断和正在用药信息不足时，只给辅助方向和筛选逻辑，不输出可直接照用的家庭药方。\n\n"
            f"【风险与禁忌】\n{taboo_context} {excluded_line} 若存在持续高热、喘憋、精神差、症状加重或正在用药，应先就医或咨询专业人员，再把食养作为辅助。\n\n"
            "【追问建议】\n"
            + "\n".join(f"{index + 1}. {question}" for index, question in enumerate(follow_ups))
        )

        related_entities = [
            {
                "id": entity["id"],
                "name": entity.get("name") or entity["id"],
                "entity_type": entity.get("entity_type", "Entity"),
            }
            for entity in selected_entities[:12]
        ]
        payload = {
            "conclusion": conclusion,
            "evidence_summary": (
                "图谱检索与证据整理摘要：已按个人端风险边界整理 KB1/KB2/KB3/KB5/KB7/KB8/CDB1，"
                f"重点核对特殊人群、症状、方剂/原料、风味、人群画像和合规风险。核心命中：{evidence_target}。"
            ),
            "cautions": llm_error or "儿童、孕妇、慢病、过敏或正在用药人群不适合直接套用通用药食同源方案。",
            "related_entities": related_entities,
            "follow_up_questions": follow_ups,
        }
        return self._finalize_answer_payload(payload, question_type, qa_route)

    @staticmethod
    def _selected_entities_from_graph(
        graph: dict,
        *,
        preferred_types: list[str],
        limit: int = 8,
    ) -> list[dict]:
        rank = {node_type: index for index, node_type in enumerate(preferred_types)}
        candidates = [
            node
            for node in graph.get("nodes", [])
            if node.get("type") in rank and node.get("id") and node.get("label")
        ]
        candidates.sort(key=lambda node: (rank.get(node.get("type"), 99), node.get("label", "")))
        selected: list[dict] = []
        seen: set[str] = set()
        for node in candidates:
            node_id = str(node.get("id"))
            if node_id in seen:
                continue
            selected.append(
                {
                    "id": node_id,
                    "name": node.get("label") or node_id,
                    "entity_type": node.get("type", "Entity"),
                    "props": node.get("props", {}) or {},
                    "score": node.get("score", 0),
                }
            )
            seen.add(node_id)
            if len(selected) >= limit:
                break
        return selected

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
                    f"{item['name']}：{item.get('dosage') or '剂量建议结合原方出处与专业规范进一步核定'}"
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
            detail_parts.append(
                "组成明细："
                + ("；".join(role_lines) if role_lines else "建议补充原方组成和剂量，便于进一步核定")
            )
            if detail.get("taboo"):
                detail_parts.append(f"禁忌：{detail['taboo']}")
            formula_lines.append("\n".join(detail_parts))
        return formula_lines[:6]

    def _format_flavor_population_lines(self, context: dict) -> list[str]:
        lines: list[str] = []
        herb_lines: list[str] = []
        for herb in context.get("herb_flavor_profiles", [])[:8]:
            name = herb.get("herb_name")
            if not name:
                continue
            flavor_bits: list[str] = []
            flavor_names = herb.get("kb3_flavors") or []
            nature_flavors = herb.get("nature_flavors") or []
            if herb.get("flavor"):
                flavor_bits.append(f"中医味：{herb['flavor']}")
            if flavor_names:
                flavor_bits.append(f"KB3 风味：{self._join_names(flavor_names[:4])}")
            if nature_flavors:
                flavor_bits.append(f"性味：{self._join_names(nature_flavors[:4])}")
            if herb.get("aroma_description"):
                flavor_bits.append(f"香气：{herb['aroma_description']}")
            risk_bits: list[str] = []
            for key, label in [
                ("overall_flavor_acceptance", "整体接受度"),
                ("bitter_risk", "苦味风险"),
                ("astringent_risk", "涩感风险"),
                ("herbal_medicine_risk", "药味风险"),
                ("aftertaste_risk", "后味风险"),
            ]:
                value = herb.get(key)
                if value is not None and value != "":
                    risk_bits.append(
                        self._qualitative_metric_text(
                            label,
                            value,
                            positive=key == "overall_flavor_acceptance",
                        )
                    )
            if flavor_bits or risk_bits:
                herb_lines.append(f"{name}（{'；'.join(flavor_bits + risk_bits)}）")
        if herb_lines:
            lines.append(f"风味证据：{self._join_names(herb_lines)}。")
        elif context.get("evidence_gaps", {}).get("flavor"):
            lines.append(context["evidence_gaps"]["flavor"] + "。")

        population_bits: list[str] = []
        profile = context.get("user_constitution_profile") or {}
        if profile.get("primary_constitution"):
            secondary = profile.get("secondary_constitutions") or []
            extra = f"，兼夹：{self._join_names(secondary)}" if secondary else ""
            population_bits.append(f"用户已保存体质：{profile['primary_constitution']}{extra}")
        for formula in context.get("formula_population_profiles", [])[:4]:
            if formula.get("crowd"):
                population_bits.append(f"{formula.get('formula_name')} 适用/主治人群：{formula['crowd']}")
            if formula.get("taboo"):
                population_bits.append(f"{formula.get('formula_name')} 禁忌：{formula['taboo']}")
        for item in context.get("constitution_profiles", [])[:4]:
            name = item.get("constitution_type_name")
            if not name:
                continue
            pieces = []
            if item.get("diet_direction"):
                pieces.append(f"食养方向：{item['diet_direction']}")
            if item.get("food_homology_direction"):
                pieces.append(f"药食同源方向：{item['food_homology_direction']}")
            if item.get("caution_herbs"):
                pieces.append(f"慎用原料：{self._join_names(item['caution_herbs'][:5])}")
            if pieces:
                population_bits.append(f"{name}（{'；'.join(pieces)}）")
        for product in context.get("product_population_profiles", [])[:4]:
            product_name = product.get("product_name")
            if product_name and product.get("scenario"):
                population_bits.append(f"{product_name} 场景：{product['scenario']}")
            if product_name and product.get("claimed_effect"):
                population_bits.append(f"{product_name} 功效/卖点：{product['claimed_effect']}")
        for profile in context.get("consumer_profiles", [])[:4]:
            pieces = []
            if profile.get("crowd_type"):
                pieces.append(f"人群：{profile['crowd_type']}")
            if profile.get("primary_age_group"):
                pieces.append(f"年龄段：{profile['primary_age_group']}")
            if profile.get("core_need"):
                pieces.append(f"核心需求：{profile['core_need']}")
            if profile.get("preferred_flavor"):
                pieces.append(f"偏好风味：{profile['preferred_flavor']}")
            if profile.get("disliked_flavor"):
                pieces.append(f"不喜欢：{profile['disliked_flavor']}")
            if pieces:
                name = profile.get("product_name") or profile.get("profile_id") or "消费者画像"
                population_bits.append(f"{name}（{'；'.join(pieces)}）")
        for segment in context.get("consumer_segments", [])[:4]:
            pieces = []
            if segment.get("top_flavor_tags"):
                pieces.append(f"高频风味：{segment['top_flavor_tags']}")
            if segment.get("top_dosage_tags"):
                pieces.append(f"剂型偏好：{segment['top_dosage_tags']}")
            if segment.get("top_complaint_tags"):
                pieces.append(f"常见不满：{segment['top_complaint_tags']}")
            if pieces:
                label = segment.get("segment_label") or segment.get("segment_key") or "人群分组"
                population_bits.append(f"{label}（{'；'.join(pieces)}）")
        if population_bits:
            lines.append(f"人群画像：{self._join_names(population_bits)}。")
        elif context.get("evidence_gaps", {}).get("population"):
            lines.append(context["evidence_gaps"]["population"] + "。")

        review_bits: list[str] = []
        for review in context.get("consumer_reviews", [])[:5]:
            pieces = []
            if review.get("flavor_tags"):
                pieces.append(f"风味标签：{review['flavor_tags']}")
            if review.get("complaint_tags"):
                pieces.append(f"不满点：{review['complaint_tags']}")
            if review.get("crowd_tags"):
                pieces.append(f"人群：{review['crowd_tags']}")
            if review.get("sentiment"):
                pieces.append(f"情感：{review['sentiment']}")
            if pieces:
                review_bits.append("；".join(pieces))
        if review_bits:
            lines.append(f"评论偏好证据：{self._join_names(review_bits)}。")

        replacement_bits: list[str] = []
        for item in context.get("replacement_flavor_population_checks", [])[:6]:
            source = item.get("source_herb")
            target = item.get("target_herb")
            if not source or not target:
                continue
            metrics = []
            for key, label in [
                ("final_score", "综合分"),
                ("professional_score", "专业分"),
                ("flavor_acceptance", "风味接受度"),
                ("flavor_similarity", "风味相似度"),
                ("safety_score", "安全分"),
            ]:
                value = item.get(key)
                if value is not None and value != "":
                    metrics.append(self._qualitative_metric_text(label, value, positive=True))
            if item.get("recommendation_status"):
                metrics.append(f"状态：{item['recommendation_status']}")
            replacement_bits.append(f"{source}->{target}（{'；'.join(metrics) if metrics else '图谱未给出完整评分'}）")
        if replacement_bits:
            lines.append(f"替代映射检查：{self._join_names(replacement_bits)}。")
        return lines

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
                        "dosage": dosage_map.get(name) or "剂量建议结合原方出处与专业规范进一步核定",
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

    @classmethod
    def _product_trial_dose(cls, herb_name: str, props: dict, *, role: str) -> dict:
        name = (herb_name or "原料").strip()
        if name == "人参":
            try:
                daily_limit = float(props.get("ordinary_food_daily_limit_g") or 3)
            except (TypeError, ValueError):
                daily_limit = 3.0
            return {
                "name": name,
                "baseline_g": 1.0,
                "gradient_g": [0.5, 1.0, min(1.5, daily_limit)],
                "daily_limit_g": daily_limit,
                "basis": "法规上限内的研发小试估算",
            }

        sour_score = cls._safe_float(props.get("sour_contribution"))
        astringent_risk = cls._safe_float(props.get("astringent_risk"))
        sweet_score = cls._safe_float(props.get("sweet_contribution"))
        if role == "臣" and sour_score >= 0.5:
            baseline = 1.5 if astringent_risk >= 0.6 else 2.0
            return {
                "name": name,
                "baseline_g": baseline,
                "gradient_g": [max(0.5, baseline - 0.5), baseline, baseline + 0.5],
                "daily_limit_g": None,
                "basis": "酸涩强度驱动的风味小试估算",
            }
        if role == "佐" and sweet_score >= 0.7:
            baseline = 3.0 if name in {"大枣", "桑椹", "桂圆", "龙眼肉"} else 2.5
            return {
                "name": name,
                "baseline_g": baseline,
                "gradient_g": [max(0.5, baseline - 1.0), baseline, baseline + 1.0],
                "daily_limit_g": None,
                "basis": "甜味与口感协同的小试估算",
            }
        return {
            "name": name,
            "baseline_g": 2.0,
            "gradient_g": [1.0, 2.0, 3.0],
            "daily_limit_g": None,
            "basis": "配方角色驱动的小试估算",
        }

    @classmethod
    def _format_product_trial_dose(cls, dose: dict) -> str:
        gradient = "/".join(cls._format_gram_value(value) for value in dose.get("gradient_g", []))
        text = (
            f"建议小试用量：{cls._format_gram_value(dose.get('baseline_g'))}g/份"
            f"（低/中/高梯度：{gradient}g/份，{dose.get('basis')}）"
        )
        daily_limit = dose.get("daily_limit_g")
        if daily_limit is not None:
            text += f"；每日总量不超过{cls._format_gram_value(daily_limit)}g"
        return text

    @staticmethod
    def _format_gram_value(value: object) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value or "")
        if number.is_integer():
            return str(int(number))
        return f"{number:.1f}".rstrip("0").rstrip(".")

    @staticmethod
    def _safe_float(value: object) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _append_unique(items: list[str], value: str) -> None:
        cleaned = (value or "").strip()
        if cleaned and cleaned not in items:
            items.append(cleaned)

    @classmethod
    def _qualitative_metric_text(cls, label: str, value: object, *, positive: bool = True) -> str:
        score = cls._coerce_score(value)
        if score is None:
            return f"{label}{value}"
        return f"{label}{cls._score_band(score, positive=positive)}"

    @staticmethod
    def _coerce_score(value: object) -> float | None:
        if value is None or value == "":
            return None
        try:
            score = float(str(value).strip())
        except (TypeError, ValueError):
            return None
        if score < 0:
            return None
        if score > 1 and score <= 100:
            score = score / 100
        if score > 1:
            return None
        return score

    @staticmethod
    def _score_band(score: float, *, positive: bool = True) -> str:
        if positive:
            if score >= 0.75:
                return "较高"
            if score >= 0.55:
                return "中等"
            return "偏低"
        if score >= 0.75:
            return "较高"
        if score >= 0.45:
            return "中等"
        return "较低"

    @classmethod
    def _sanitize_user_facing_answer_text(cls, text: str) -> str:
        cleaned = cls._professionalize_gap_language(str(text or ""))
        cleaned = re.sub(r"(?m)^(\s*)\*\s+", r"\1- ", cleaned)
        cleaned = re.sub(r"\*{2,3}([^*\n]+?)\*{2,3}\s*[：:]", r"\1：", cleaned)
        cleaned = re.sub(r"\*{2,3}([^*\n]+?)\*{2,3}", r"\1", cleaned)
        cleaned = re.sub(r"\*{2,3}", "", cleaned)
        cleaned = re.sub(r"(?m)([：:]\s*)(君|臣|佐|使)[。．.]\s*", r"\1\2：", cleaned)
        cleaned = re.sub(
            r"(?m)^(\s*[-*•]\s*)原料[：:]\s*(?=[^：:\n]{1,24}[：:]\s*[君臣佐使][：:])",
            r"\1",
            cleaned,
        )
        cleaned = re.sub(
            r"\b(final_score|professional_score|flavor_acceptance|consumer_final_score|overall_flavor_acceptance|safety_score)\b",
            "评分维度",
            cleaned,
            flags=re.I,
        )

        def replace_decimal(match: re.Match[str]) -> str:
            score = cls._coerce_score(match.group(2))
            if score is None:
                return match.group(0)
            return f"{match.group(1)}{cls._score_band(score, positive=True)}"

        cleaned = re.sub(
            r"(^|[^\d×])(0\.\d+|1\.0+)"
            r"(?![\d×/]|\s*(?:mg|g|kg|克|毫克|千克|ml|mL|毫升|%))",
            replace_decimal,
            cleaned,
        )
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    @staticmethod
    def _professionalize_gap_language(text: str) -> str:
        cleaned = str(text or "")
        replacements = [
            (
                "当前知识图谱未提供您指定的具体目标功效和剂型",
                "建议先明确具体目标功效和剂型",
            ),
            (
                "当前知识图谱未提供您指定的目标功效和剂型",
                "建议先明确目标功效和剂型",
            ),
            (
                "图谱未提供足够的 KB3 风味评价或目标人群/体质画像",
                "建议补充 KB3 感官小试、目标人群试食和体质分层验证",
            ),
            (
                "图谱未提供足够的风味或剂型直接证据",
                "建议通过感官小试和剂型适配试验进一步确认",
            ),
            (
                "图谱未提供可直接展开的 KB5 方剂组成或剂量",
                "建议补充原方名称、组成和剂量，便于核对 KB5 原方依据",
            ),
            (
                "图谱未提供药材剂量明细",
                "建议补充原方组成和剂量，便于进一步核定",
            ),
            (
                "图谱未提供剂量",
                "剂量建议结合原方出处与专业规范进一步核定",
            ),
            (
                "图谱未命中直接产品节点",
                "建议补充产品名、配料表、剂型和目标场景",
            ),
            (
                "当前图谱没有形成足够稳定的推荐理由链条",
                "建议补充产品配料、目标人群和使用场景后再确定推荐理由",
            ),
            (
                "当前知识库尚未支持直接按普通食品原料使用",
                "在完成品种、来源、加工规格和适用法规核验前，不建议直接按普通食品原料使用",
            ),
            (
                "当前知识库不支持直接按普通食品原料使用",
                "在完成品种、来源、加工规格和适用法规核验前，不建议直接按普通食品原料使用",
            ),
            (
                "当前知识库尚不支持直接给出完整方剂出处",
                "建议在定稿前补充核对原方出处",
            ),
        ]
        for source, target in replacements:
            cleaned = cleaned.replace(source, target)

        def replace_gap(match: re.Match[str]) -> str:
            topic = (match.group("topic") or "").strip()
            topic = re.sub(r"^(?:足够的|直接的|直接给出|直接|给出)", "", topic).strip()
            topic = re.sub(r"(?:节点|关系|证据)$", "", topic).strip()
            if not topic:
                return "建议在下一阶段补充专项核验"
            separator = " " if topic[:1].isascii() else ""
            return f"建议在下一阶段补充核验{separator}{topic}"

        cleaned = re.sub(
            r"(?:当前)?(?:知识)?图谱(?:中)?(?:尚未|未|没有)(?:提供|形成|命中|检索到)"
            r"(?P<topic>[^，。；！？\n]*)",
            replace_gap,
            cleaned,
        )
        cleaned = re.sub(
            r"(?:当前|现有)?知识库(?:中)?(?:尚未|尚不|未|不|没有)(?:提供|形成|支持|命中|检索到)"
            r"(?P<topic>[^，。；！？\n]*)",
            replace_gap,
            cleaned,
        )
        cleaned = re.sub(
            r"(?:当前)?未命中(?P<topic>[^，。；！？\n]*)",
            replace_gap,
            cleaned,
        )
        cleaned = re.sub(
            r"(?:当前)?没有检索到(?P<topic>[^，。；！？\n]*)",
            replace_gap,
            cleaned,
        )
        cleaned = re.sub(
            r"建议补充产品名、配料表、剂型和目标场景，建议补充产品名[^。！？\n]*",
            "建议补充产品名、配料表、剂型和目标场景后再判断",
            cleaned,
        )
        return cleaned

    @staticmethod
    def _contains_system_gap_language(text: str) -> bool:
        banned_phrases = (
            "图谱未提供",
            "知识图谱未提供",
            "图谱未命中",
            "未命中",
            "没有检索到",
            "知识库尚不支持",
            "知识库不支持",
            "知识库尚未提供",
            "知识库未提供",
            "现有知识库尚不支持",
        )
        return any(phrase in str(text or "") for phrase in banned_phrases)

    def _build_follow_ups(
        self,
        selected_entities: list[dict],
        question: str = "",
        question_type: str = "entity_explanation",
        graph: dict | None = None,
        constitution_profile: dict | None = None,
        qa_route: str | None = None,
    ) -> list[str]:
        follow_ups = self._missing_core_questions(
            question,
            question_type,
            graph or {},
            constitution_profile=constitution_profile,
            qa_route=qa_route,
        )
        names = [entity.get("name") or entity["id"] for entity in selected_entities[:3]]
        if not names:
            if len(follow_ups) >= 3:
                return self._dedupe_follow_ups(follow_ups)
            compact = re.sub(r"\s+", "", question or "")
            single_herb_replacement = question_type == "formula_replacement" and "方" not in compact and any(
                token in compact for token in ("替代", "替换", "代替", "换成")
            )
            if question_type == "constitution_recommendation":
                defaults = ["如果你已知体质，请直接告诉我体质类型；不知道的话可以先做九种体质量表。"]
            elif question_type == "product_recommendation":
                defaults = ["请补充目标人群、剂型、口味偏好、成本区间或竞品名称，我可以继续做产品化判断。"]
            elif question_type == "formula_replacement" and single_herb_replacement:
                defaults = ["你更希望候选偏功效相近、风味友好、安全合规，还是某种剂型适配？"]
            elif question_type == "formula_replacement":
                defaults = ["请补充目标剂型、人群、口味和成本约束，我可以继续做整方食品化重组。"]
            elif question_type == "formula_relation":
                defaults = ["你想优先查看组成剂量、君臣佐使、主治功效，还是禁忌边界？"]
            elif question_type == "herb_efficacy":
                defaults = ["你想重点看功效、禁忌、风味、归经，还是合规边界？"]
            else:
                defaults = ["请补充一个更明确的药材、方剂、产品、体质或症状名称。"]
            return self._dedupe_follow_ups(follow_ups + defaults)
        joined = "、".join(names)
        type_defaults = {
            "constitution_recommendation": [
                "你是否已经保存体质档案，还是需要先做体质量表？",
                f"围绕 {names[0]}，你更关心适合吃什么、不能吃什么，还是产品是否适配？",
            ],
            "product_recommendation": [
                "请补充目标人群、剂型、口味偏好和成本区间，我可以继续做产品化判断。",
                f"要不要继续看 {joined} 的风味风险、竞品差异化或合规宣传边界？",
            ],
            "formula_replacement": [
                "你希望保留原方功效优先，还是食品口感和普通食品合规优先？",
                "请补充目标剂型、人群和口味约束，我可以继续做逐味替代重组。",
            ],
            "formula_relation": [
                f"要不要继续展开 {joined} 的组成剂量、君臣佐使、主治功效或禁忌？",
            ],
            "herb_efficacy": [
                f"你想继续看 {joined} 的功效、禁忌、风味、归经，还是合规边界？",
            ],
        }
        defaults = type_defaults.get(
            question_type,
            [
                f"{joined} 在知识图谱里还关联了哪些方剂、症状、产品或合规规则？",
                f"如果只看 {names[0]}，你更想展开功效、风味、替代还是风险边界？",
            ],
        )
        return self._dedupe_follow_ups(follow_ups + defaults)

    @staticmethod
    def _dedupe_follow_ups(items: list[str], limit: int = 4) -> list[str]:
        deduped: list[str] = []
        for item in items:
            cleaned = re.sub(r"\s+", " ", (item or "").strip())
            if cleaned and cleaned not in deduped:
                deduped.append(cleaned)
            if len(deduped) >= limit:
                break
        return deduped

    def _append_follow_up_section(self, conclusion: str, follow_ups: list[str]) -> str:
        text = (conclusion or "").strip()
        if not text:
            return text
        questions = self._dedupe_follow_ups(follow_ups, limit=3)
        if not questions:
            return text
        if "【追问建议】" in text:
            section_text = self._follow_up_section_text(text)
            if self._has_flavor_follow_up(questions) and not self._has_flavor_follow_up([section_text]):
                next_index = self._next_follow_up_index(section_text)
                return f"{text.rstrip()}\n{next_index}. {FLAVOR_PREFERENCE_FOLLOW_UP}"
            return text
        body = "\n".join(f"{index + 1}. {question}" for index, question in enumerate(questions))
        return f"{text}\n\n【追问建议】\n{body}"

    def _default_system_prompt(self) -> str:
        return (
            "你是药食同源知识问答助手。"
            "你必须采用专家判断优先、证据支撑随后的回答方式，不能把图谱字段搬运成正文。"
            "你只能基于提供的 Neo4j 知识图谱证据、实体属性和用户明确输入回答，不能编造不存在的关系。"
            "如果问题里有多个实体、多个症状或多个子问题，必须整体回答，不能只抓住其中一个。"
            "0604 新图谱以 KB1-KB8 为准，不包含 Compound/成分网络。"
            "回答前必须区分企业端研发问题和个人端体质/食养/风险问题。"
            "分析摘要和正式回答都必须遵循流程图顺序：先任务分流，再检查核心信息是否缺失，再按 KB1-KB8 路由取证，最后给风险/合规边界和主动追问。"
            "企业端围绕产品研发、名方方剂药食同源化、单味药替代、风味剂型、市场和合规输出。"
            "个人端围绕体质辨识、食养方向、产品适配和禁忌风险输出；体质未知时优先给 KB8 体质辨识入口，不做疾病诊断，不替代医疗治疗。"
            "孕妇、儿童、慢病、过敏等高风险人群问题优先走风险边界，但仍要先基于图谱给出可考虑/不建议/需补充的辅助食养或产品方向。"
            "儿童咳嗽、多痰、发热、高热并索要药方时，核心结论先给图谱支持的辅助方向、候选原料类型和风味取舍；不要以“无法直接推荐任何药方/我不能推荐”作为第一句。"
            "个人高风险推荐必须区分药食同源合法候选、需专业确认的谨慎候选、非药食同源或禁忌排除线索，后两类不能写成可直接推荐。"
            "food_homology 只表示食药物质目录身份，不能覆盖新食品原料、保健食品原料和中药材路径；必须按实体的多轨监管属性与关联合规规则判断。"
            "涉及人参时，普通食品路径仅限5年及5年以下人工种植人参根及根茎且每日不超过3克；5年以上人参不得直接按普通食品放行。保健食品原料资格不能自动替代普通食品资格，复配草案不能直接套用单方备案路径。"
            "如果某类证据缺失，要明确指出缺失的是方剂、功效、风味、替代、体质、产品还是合规证据。"
            "疾病、证候、疗法或方剂缺乏专项依据时不要自行补充，统一转成下一步核验建议。"
            "conclusion 必须写成用户可直接阅读的结构化答案，使用随问题类型提供的【】小标题。"
            "正文中的业务依据必须解释为什么这样判断，不要重复图谱证据摘要和证据子图里的节点数、关系数、关系类型清单。"
            "正文禁止出现“知识图谱中检索到”“图谱提供了”“图谱未提供”“知识库尚不支持”“知识库未提供”“未命中”“没有检索到”等系统视角措辞；待验证项必须转成专业行动建议。"
            "正文 Markdown 只允许【】小标题、标准编号列表和 - 无序列表；禁止 **标题**、***标题*** 或多星号层级。"
            "正文不得裸露 final_score、professional_score、flavor_acceptance 等字段名或0.xxx原始小数；产品研发/替代问题可展示换算后的整数百分制，并另列高/中/低、证据性质和评分依据。"
            "【核心结论】必须直接回答用户问题，不能写成“本次命中了哪些实体”。"
            "conclusion 必须包含【追问建议】，当体质、人群、方剂、原料、产品、剂型、风味、成本、合规或验证信息缺失时主动问清楚，并至少追问一次用户的风味/口味偏好。"
            "如果用户询问企业端方剂、方剂食品化或方剂替换，且图谱提供组成或剂量，必须列出药材和剂量；高风险个人端可以给辅助方向和筛选结论，但不能给家庭完整处方或儿童剂量，安全提醒放在风险与禁忌或证据边界。"
            "方剂药食同源化必须保留 KB5 原方依据，并动态调用 KB4 单味替代评分，不能声称存在预生成方剂替代版本。"
            "如果用户询问体质推荐或产品推荐，必须基于体质量表、食养规则、产品、药材、风味、市场和合规证据，不得编造诊断或评论原文。"
            "conclusion 不要写成三元组或证据条目列表，不要直接复述 evidence_summary。"
            "evidence_summary 应写成“图谱检索与证据整理摘要”，只保留支撑答案的关键证据，不要与 conclusion 大段重复。"
            "cautions 只能写证据缺失、使用范围和安全边界提醒，不能引入未被证据支持的治疗承诺。"
            "不要在 conclusion 或 evidence_summary 中输出 <think>、</think>、提示词、系统设定、JSON 字段冲突或任何内部推理标签。"
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

    def _compose_system_prompt(
        self,
        base_prompt: str,
        question_type: str = "entity_explanation",
        qa_route: str | None = None,
    ) -> str:
        markdown_rules = self._load_answer_rules_markdown()
        return (
            f"{base_prompt}\n"
            f"{markdown_rules}\n"
            f"{compose_constraints_block(question_type, qa_route)}"
        )

    def _compose_stream_system_prompt(
        self,
        base_prompt: str,
        question_type: str = "entity_explanation",
        qa_route: str | None = None,
    ) -> str:
        stream_base = (base_prompt or "").strip()
        # Remove structured JSON output constraints from the stream prompt. Stream mode
        # renders natural language directly and persists structure later in the pipeline.
        stream_base = re.sub(r"请严格输出\s*JSON[^。！？\n]*[。！？]?", "", stream_base, flags=re.I)
        stream_base = re.sub(r"输出\s*JSON[^。！？\n]*[。！？]?", "", stream_base, flags=re.I)
        stream_base = re.sub(
            r"evidence_summary[^。！？\n]*[。！？]?",
            "",
            stream_base,
            flags=re.I,
        )
        stream_base = re.sub(
            r"related_entities[^。！？\n]*[。！？]?",
            "",
            stream_base,
            flags=re.I,
        )
        stream_base = re.sub(
            r"follow_up_questions[^。！？\n]*[。！？]?",
            "",
            stream_base,
            flags=re.I,
        )
        stream_base = re.sub(r"\n{3,}", "\n\n", stream_base).strip()
        return (
            f"{stream_base}\n"
            f"{compose_constraints_block(question_type, qa_route)}\n"
            "流式回答模式下，只输出可直接展示给用户的自然语言正文。\n"
            "正文必须按任务分流、核心信息检查、KB 路由、风险/合规边界、回答与追问的顺序组织，先给专家判断，不要只罗列图谱命中结果。\n"
            "正文禁止出现“知识图谱中检索到/图谱提供/图谱未提供/知识库尚不支持/知识库未提供/未命中/没有检索到”等系统视角措辞；待验证项必须转成专业行动建议。\n"
            "正文 Markdown 只允许【】小标题、标准编号列表和 - 无序列表；禁止 **标题**、***标题*** 或多星号层级。\n"
            "正文不得裸露0.xxx原始小数或 final_score、professional_score、flavor_acceptance 等字段名；产品研发/替代问题可展示换算后的整数百分制，并另列高/中/低、证据性质和评分依据。\n"
            "正文必须包含【追问建议】，用具体问题补齐缺失的体质、人群、方剂、原料、产品、剂型、风味、成本、合规或验证信息；其中至少一问要询问用户偏好的口味方向，以及是否需要避开苦味、涩感或药味。\n"
            "若需要过程说明，只能写成图谱检索与证据整理摘要，不要讨论提示词、系统设定、字段名、JSON 或格式冲突。"
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

    def _compose_user_facing_think(self, base_summary: str, *analysis_blocks: str | None) -> str:
        append = self._format_think_append(base_summary, *analysis_blocks)
        return self._merge_text_blocks(base_summary, append)

    def _format_think_append(self, base_summary: str, *analysis_blocks: str | None) -> str:
        cleaned = self._sanitize_think_content(*analysis_blocks)
        if not cleaned or self._is_redundant_think(base_summary, cleaned):
            return ""
        return f"进一步分析：\n{cleaned}"

    def _sanitize_think_content(self, *blocks: str | None, max_chars: int = 1400) -> str:
        raw = self._merge_text_blocks(*blocks)
        if not raw:
            return ""
        cleaned = self.llm_client._remove_think_blocks(raw)
        cleaned = self.llm_client._sanitize_reasoning_text(cleaned)
        cleaned = self._remove_internal_leak_lines(cleaned)
        cleaned = self._professionalize_gap_language(cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        if not cleaned:
            return ""
        return self._trim_text(cleaned, max_chars=max_chars)

    def _is_redundant_think(self, base_summary: str, candidate: str) -> bool:
        normalized_base = self._normalize_text_for_similarity(base_summary)
        normalized_candidate = self._normalize_text_for_similarity(candidate)
        if not normalized_base or not normalized_candidate:
            return False
        if normalized_candidate in normalized_base or normalized_base in normalized_candidate:
            return True
        similarity = SequenceMatcher(None, normalized_base, normalized_candidate).ratio()
        token_overlap = self._token_overlap_ratio(base_summary, candidate)
        return similarity >= 0.82 or token_overlap >= 0.78

    @staticmethod
    def _trim_text(text: str, max_chars: int = 1400) -> str:
        cleaned = (text or "").strip()
        if len(cleaned) <= max_chars:
            return cleaned
        cutoff = max(
            cleaned.rfind("。", 0, max_chars),
            cleaned.rfind("\n", 0, max_chars),
        )
        if cutoff < int(max_chars * 0.6):
            cutoff = max_chars
        return f"{cleaned[:cutoff + 1].rstrip()}\n（后续分析已省略，正文会展开关键判断。）"

    def _should_use_llm_analysis(self, question: str, entities: list[dict], question_type: str | None = None) -> bool:
        if question_type == "constitution_recommendation":
            return False
        if not entities:
            return True
        broad_hints = ["相关", "哪些", "推荐", "适合", "有没有", "药食同源", "最好", "怎么选"]
        disease_hints = ["高血压", "糖尿病", "失眠", "症状", "病"]
        if any(token in question for token in broad_hints) and any(token in question for token in disease_hints):
            return True
        if len(entities) >= 6:
            return True
        return False

    def _resolve_refined_route(self, question: str, refined_question_type: str) -> QARoute:
        explicit_route = self.route_resolver.resolve(question)
        if explicit_route.question_type == refined_question_type:
            return explicit_route
        return self.route_resolver.resolve(question, fallback_question_type=refined_question_type)

    @staticmethod
    def _should_skip_broad_entity_resolution(qa_route: str | None) -> bool:
        """Routes with their own recommendation queries should not scan the full graph for every n-gram."""
        return qa_route in {"risk_boundary"}

    def _finalize_answer_payload(
        self,
        payload: dict,
        question_type: str,
        qa_route: str | None = None,
        *,
        graph: dict | None = None,
    ) -> dict:
        result = dict(payload)
        follow_ups = result.get("follow_up_questions", [])
        if isinstance(follow_ups, str):
            result["follow_up_questions"] = self._dedupe_follow_ups([follow_ups])
        elif isinstance(follow_ups, list):
            result["follow_up_questions"] = self._dedupe_follow_ups(
                [self._normalize_text_field(item) for item in follow_ups]
            )
        else:
            result["follow_up_questions"] = []
        result["follow_up_questions"] = self._ensure_flavor_follow_up_questions(
            result["follow_up_questions"],
            question_type,
            qa_route,
        )
        conclusion = result.get("conclusion", "")
        if isinstance(conclusion, str) and conclusion.strip():
            structured_conclusion = enforce_conclusion_structure(
                self._remove_internal_leak_lines(conclusion),
                question_type,
                qa_route,
            )
            structured_conclusion = self._rebalance_risk_boundary_conclusion(
                structured_conclusion,
                qa_route,
            )
            structured_conclusion = self._append_follow_up_section(
                structured_conclusion,
                result["follow_up_questions"],
            )
            structured_conclusion = enforce_conclusion_structure(
                structured_conclusion,
                question_type,
                qa_route,
            )
            result["conclusion"] = self._sanitize_user_facing_answer_text(
                structured_conclusion
            )
        evidence = result.get("evidence_summary", "")
        if isinstance(evidence, str) and isinstance(conclusion, str):
            result["evidence_summary"] = self._dedupe_evidence_summary(
                self._sanitize_user_facing_answer_text(
                    self._remove_internal_leak_lines(evidence),
                ),
                result["conclusion"],
            )
        cautions = result.get("cautions", "")
        if isinstance(cautions, str) and isinstance(conclusion, str):
            result["cautions"] = self._sanitize_user_facing_answer_text(
                self._dedupe_evidence_summary(
                    self._remove_internal_leak_lines(cautions),
                    result["conclusion"],
                )
            )
        if qa_route == "product_development":
            route = self.route_resolver.by_key(qa_route)
            required_sections = route.answer_outline if route else []
            conclusion_text = result.get("conclusion", "")
            if any(f"【{title}】" not in conclusion_text for title in required_sections):
                result["_fallback"] = True
            grounding_errors = self._product_development_grounding_errors(
                conclusion_text,
                graph or {},
            )
            if grounding_errors:
                logger.warning(
                    "Product-development answer failed graph grounding: %s",
                    "; ".join(grounding_errors),
                )
                result["_fallback"] = True
        return result

    def _product_development_grounding_errors(self, conclusion: str, graph: dict) -> list[str]:
        if not graph:
            return []
        provenance = self._build_formula_provenance_context(graph)
        prototypes = provenance.get("formula_prototypes") or []
        if not prototypes:
            return ["missing formula prototype evidence"]

        primary = prototypes[0]
        formula_name = str(primary.get("formula_name") or "").strip()
        provenance_section = self._answer_section_body(conclusion, "名方溯源与借鉴")
        adjustment_section = self._answer_section_body(conclusion, "配方调整与替换依据")
        errors: list[str] = []

        if not formula_name or formula_name not in provenance_section:
            errors.append("primary formula name mismatch")
        sources = [str(item).strip() for item in (primary.get("sources") or []) if str(item).strip()]
        if sources and not any(source in provenance_section for source in sources):
            errors.append("formula source mismatch")
        evidence_type = str(primary.get("evidence_type") or "").strip()
        if evidence_type and evidence_type not in provenance_section:
            errors.append("formula evidence type missing")
        match_score = primary.get("prototype_match_score_100")
        if match_score is not None and f"{match_score}/100" not in provenance_section:
            errors.append("formula match score missing")

        for action in ("保留", "替换", "新增", "删除"):
            if action not in adjustment_section:
                errors.append(f"adjustment action missing: {action}")
        replacement_options = provenance.get("replacement_options") or []
        if replacement_options:
            if "KB4原始分" not in adjustment_section:
                errors.append("KB4 original score missing")
            if "系统综合可信度" not in adjustment_section:
                errors.append("composite confidence missing")

        allowed_pairs = {
            (
                str(item.get("source_herb") or "").strip(),
                str(item.get("target_herb") or "").strip(),
            )
            for item in replacement_options
            if item.get("source_herb") and item.get("target_herb")
        }
        for source_name, target_name in re.findall(
            r"([\u4e00-\u9fff]{1,12})\s*(?:→|->|⇒)\s*([\u4e00-\u9fff]{1,12})",
            conclusion or "",
        ):
            if (source_name, target_name) not in allowed_pairs:
                errors.append(f"unsupported replacement: {source_name}->{target_name}")

        for marker in ("名方原型", "参考原型"):
            start = 0
            while True:
                marker_index = (conclusion or "").find(marker, start)
                if marker_index < 0:
                    break
                window = conclusion[max(0, marker_index - 30): marker_index + len(marker) + 20]
                if formula_name and formula_name not in window:
                    errors.append(f"formula alias mismatch near {marker}")
                    break
                start = marker_index + len(marker)
        return list(dict.fromkeys(errors))

    @staticmethod
    def _answer_section_body(conclusion: str, title: str) -> str:
        marker = f"【{title}】"
        text = conclusion or ""
        start = text.find(marker)
        if start < 0:
            return ""
        body_start = start + len(marker)
        next_section = re.search(r"\n\s*【[^】]+】", text[body_start:])
        body_end = body_start + next_section.start() if next_section else len(text)
        return text[body_start:body_end].strip()

    @staticmethod
    def _rebalance_risk_boundary_conclusion(conclusion: str, qa_route: str | None = None) -> str:
        if qa_route != "risk_boundary" or "【核心结论】" not in (conclusion or ""):
            return conclusion
        text = conclusion or ""
        marker = "【核心结论】\n"
        start = text.find(marker)
        if start < 0:
            return text
        body_start = start + len(marker)
        next_section = re.search(r"\n\s*【[^】]+】", text[body_start:])
        body_end = body_start + next_section.start() if next_section else len(text)
        core_body = text[body_start:body_end].strip()
        refusal_first = re.search(
            r"(无法直接|不能直接|我不能|不建议直接|超出.{0,12}安全边界|首要建议是立即就医)",
            core_body[:220],
        )
        if not refusal_first or core_body.startswith("基于当前图谱证据"):
            return text
        lead = (
            "基于当前图谱证据，可以先给出辅助食养方向和筛选结论："
            "优先考虑药食同源合法、风味温和、低苦味，并与症状方向相符的原料或产品；"
            "传统成方、成人方和剂量不作为家庭直接照用方案。"
        )
        softened = re.sub(r"我无法直接为你推荐任何药方[，。]?", "我不会输出儿童剂量或可直接照用的家庭完整处方。", core_body)
        softened = re.sub(r"无法直接为你推荐任何药方[，。]?", "不输出儿童剂量或可直接照用的家庭完整处方。", softened)
        new_body = f"{lead}\n{softened}"
        return f"{text[:body_start]}{new_body}{text[body_end:]}"

    def _ensure_flavor_follow_up_questions(
        self,
        follow_ups: list[str],
        question_type: str,
        qa_route: str | None = None,
    ) -> list[str]:
        questions = self._dedupe_follow_ups(follow_ups, limit=4)
        if not self._should_ask_flavor_preference(question_type, qa_route):
            return questions
        if self._has_flavor_follow_up(questions):
            return questions
        if len(questions) >= 3:
            questions = questions[:2]
        questions.append(FLAVOR_PREFERENCE_FOLLOW_UP)
        return self._dedupe_follow_ups(questions, limit=4)

    @staticmethod
    def _should_ask_flavor_preference(question_type: str, qa_route: str | None = None) -> bool:
        if qa_route == "constitution_assessment":
            return False
        if qa_route in {
            "product_development",
            "formula_foodification",
            "herb_replacement",
            "flavor_form_factor",
            "market_analysis",
            "personalized_food_recommendation",
            "personal_product_fit",
            "formula_relation",
            "herb_efficacy",
            "entity_explanation",
        }:
            return True
        return question_type in {
            "product_recommendation",
            "constitution_recommendation",
            "formula_replacement",
            "formula_relation",
            "herb_efficacy",
            "entity_explanation",
        }

    @staticmethod
    def _has_flavor_follow_up(items: list[str]) -> bool:
        compact = re.sub(r"\s+", "", " ".join(item or "" for item in items))
        has_flavor_subject = any(keyword in compact for keyword in FLAVOR_FOLLOW_UP_SUBJECT_KEYWORDS)
        has_preference_action = any(keyword in compact for keyword in FLAVOR_FOLLOW_UP_PREFERENCE_KEYWORDS)
        return has_flavor_subject and has_preference_action

    @staticmethod
    def _follow_up_section_text(text: str) -> str:
        marker = "【追问建议】"
        if marker not in text:
            return ""
        tail = text.split(marker, 1)[1]
        next_section = re.search(r"\n\s*【[^】]+】", tail)
        if next_section:
            tail = tail[: next_section.start()]
        return tail.strip()

    @staticmethod
    def _next_follow_up_index(section_text: str) -> int:
        indexes = [
            int(value)
            for value in re.findall(r"(?m)^\s*(\d+)[.、)]", section_text or "")
            if value.isdigit()
        ]
        return max(indexes, default=0) + 1

    @staticmethod
    def _remove_internal_leak_lines(text: str) -> str:
        blocked_patterns = [
            r"<\/?think\b",
            r"提示词",
            r"prompt",
            r"系统提示",
            r"system\s*prompt",
            r"内部设定",
            r"开发者",
            r"developer",
            r"规则词",
            r"answer_rules",
            r"rendering_rules",
            r"schema",
            r"输出协议",
            r"格式冲突",
            r"JSON\s*字段",
            r"字段名",
            r"conclusion",
            r"evidence_summary",
            r"related_entities",
            r"follow_up_questions",
            r"cautions",
            r"我被要求",
            r"按照系统.*要求",
            r"按照提示词.*要求",
        ]
        kept: list[str] = []
        for raw_line in (text or "").splitlines():
            line = raw_line.strip()
            if not line:
                kept.append(raw_line)
                continue
            if any(re.search(pattern, line, re.I) for pattern in blocked_patterns):
                continue
            kept.append(raw_line)
        return "\n".join(kept).strip()

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

    def _backfill_answer_payload(
        self,
        payload: dict,
        selected_entities: list[dict],
        graph: dict,
        question: str = "",
        question_type: str = "entity_explanation",
        constitution_profile: dict | None = None,
        qa_route: str | None = None,
    ) -> dict:
        if not payload.get("evidence_summary"):
            payload["evidence_summary"] = self._build_missing_evidence_summary(selected_entities, graph)
        if not payload.get("related_entities"):
            payload["related_entities"] = self._build_missing_related_entities(selected_entities, graph)
        generated_follow_ups = self._build_follow_ups(
            selected_entities,
            question=question,
            question_type=question_type,
            graph=graph,
            constitution_profile=constitution_profile,
            qa_route=qa_route,
        )
        existing_follow_ups = payload.get("follow_up_questions", [])
        if isinstance(existing_follow_ups, str):
            existing_follow_ups = [existing_follow_ups]
        elif not isinstance(existing_follow_ups, list):
            existing_follow_ups = []
        payload["follow_up_questions"] = self._dedupe_follow_ups(generated_follow_ups + existing_follow_ups)
        payload = self._ensure_flavor_population_section(
            payload,
            question_type,
            selected_entities,
            graph,
            constitution_profile=constitution_profile,
        )
        return payload

    def _ensure_flavor_population_section(
        self,
        payload: dict,
        question_type: str,
        selected_entities: list[dict],
        graph: dict,
        constitution_profile: dict | None = None,
    ) -> dict:
        if question_type not in {"herb_efficacy", "formula_relation", "formula_replacement", "entity_explanation"}:
            return payload
        conclusion = self._normalize_text_field(payload.get("conclusion", ""))
        if "【风味与人群适配】" in conclusion:
            return payload
        entity_types = {entity.get("entity_type") for entity in selected_entities}
        node_types = {node.get("type") for node in graph.get("nodes", [])}
        if not ({"Herb", "Formula"} & (entity_types | node_types)):
            return payload
        context = self._build_flavor_population_context(
            graph,
            selected_entities,
            constitution_profile=constitution_profile,
        )
        lines = self._format_flavor_population_lines(context)
        if not lines:
            lines = ["建议补充剂型、口味偏好和目标人群信息，并通过 KB3 感官小试与人群验证进一步确认。"]
        payload["conclusion"] = self._merge_text_blocks(
            conclusion,
            "【风味与人群适配】\n" + "\n".join(lines),
        )
        return payload

    def _build_missing_evidence_summary(self, selected_entities: list[dict], graph: dict) -> str:
        names = [entity.get("name") or entity["id"] for entity in selected_entities[:6]]
        evidence_lines: list[str] = []
        if names:
            evidence_lines.append(
                f"图谱检索与证据整理摘要：本次回答纳入了 {len(selected_entities)} 个核心实体：{self._join_names(names)}。"
            )
        if evidence_lines:
            return "\n".join(evidence_lines)
        if graph.get("nodes") or graph.get("edges"):
            return "图谱检索与证据整理摘要：已检索到相关证据子图，可点击「查看更多详情」查看节点、关系。"
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
