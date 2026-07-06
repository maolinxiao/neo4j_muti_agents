from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import (
    ChatMessage,
    ChatSession,
    ConstitutionAssessment,
    ConstitutionProfile,
    CypherTemplate,
    EntityProfile,
    GraphSnapshot,
    PromptTemplate,
    QATrace,
    WorkflowRun,
    WorkflowSession,
    WorkflowStepRun,
)


class PostgresRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_chat_session(self) -> ChatSession:
        chat_session = ChatSession()
        self.session.add(chat_session)
        self.session.flush()
        return chat_session

    def get_chat_session(self, session_id: str) -> ChatSession | None:
        return self.session.get(ChatSession, session_id)

    def list_chat_sessions(self) -> list[ChatSession]:
        stmt = select(ChatSession).where(ChatSession.status != "workflow_shadow").order_by(desc(ChatSession.updated_at))
        return list(self.session.scalars(stmt))

    def create_message(self, session_id: str, role: str, content: str, extra_payload: dict | None = None) -> ChatMessage:
        message = ChatMessage(session_id=session_id, role=role, content=content, extra_payload=extra_payload)
        self.session.add(message)
        self.session.flush()
        return message

    def list_messages(self, session_id: str) -> list[ChatMessage]:
        stmt = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())
        return list(self.session.scalars(stmt))

    def create_graph_snapshot(self, session_id: str, question: str, graph_data: dict) -> GraphSnapshot:
        snapshot = GraphSnapshot(session_id=session_id, question=question, graph_data=graph_data)
        self.session.add(snapshot)
        self.session.flush()
        return snapshot

    def get_graph_snapshot(self, snapshot_id: str) -> GraphSnapshot | None:
        return self.session.get(GraphSnapshot, snapshot_id)

    def get_latest_graph_snapshot(self, session_id: str) -> GraphSnapshot | None:
        stmt = (
            select(GraphSnapshot)
            .where(GraphSnapshot.session_id == session_id)
            .order_by(GraphSnapshot.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)

    def create_trace(
        self,
        session_id: str,
        question: str,
        question_type: str,
        entities: list[dict],
        cypher_template_key: str,
        trace_summary: str,
        retrieval_ms: int,
        llm_ms: int,
        graph_snapshot_id: str | None,
        reasoning_payload: dict | None,
    ) -> QATrace:
        trace = QATrace(
            session_id=session_id,
            question=question,
            question_type=question_type,
            entities=entities,
            cypher_template_key=cypher_template_key,
            trace_summary=trace_summary,
            retrieval_ms=retrieval_ms,
            llm_ms=llm_ms,
            graph_snapshot_id=graph_snapshot_id,
            reasoning_payload=reasoning_payload,
        )
        self.session.add(trace)
        self.session.flush()
        return trace

    def list_traces(self) -> list[QATrace]:
        stmt = select(QATrace).order_by(QATrace.created_at.desc()).limit(200)
        return list(self.session.scalars(stmt))

    def list_prompt_templates(self) -> list[PromptTemplate]:
        return list(self.session.scalars(select(PromptTemplate).order_by(PromptTemplate.updated_at.desc())))

    def get_prompt_template_by_key(self, key: str) -> PromptTemplate | None:
        return self.session.scalar(select(PromptTemplate).where(PromptTemplate.key == key))

    def get_prompt_template_by_scenario_agent(self, scenario: str, agent_key: str) -> PromptTemplate | None:
        stmt = (
            select(PromptTemplate)
            .where(PromptTemplate.scenario == scenario, PromptTemplate.agent_key == agent_key)
            .order_by(PromptTemplate.updated_at.desc())
        )
        return self.session.scalar(stmt)

    def get_prompt_template(self, template_id: str) -> PromptTemplate | None:
        return self.session.get(PromptTemplate, template_id)

    def list_cypher_templates(self) -> list[CypherTemplate]:
        return list(self.session.scalars(select(CypherTemplate).order_by(CypherTemplate.updated_at.desc())))

    def get_cypher_template_by_key(self, key: str) -> CypherTemplate | None:
        return self.session.scalar(select(CypherTemplate).where(CypherTemplate.key == key))

    def get_cypher_template(self, template_id: str) -> CypherTemplate | None:
        return self.session.get(CypherTemplate, template_id)

    def get_entity_profile(self, neo4j_key: str) -> EntityProfile | None:
        return self.session.scalar(select(EntityProfile).where(EntityProfile.neo4j_key == neo4j_key))

    def search_entity_profiles(self, query: str) -> list[EntityProfile]:
        stmt = (
            select(EntityProfile)
            .where(EntityProfile.display_name.ilike(f"%{query}%"))
            .order_by(EntityProfile.updated_at.desc())
            .limit(20)
        )
        return list(self.session.scalars(stmt))

    def get_constitution_profile(self, user_id: str) -> ConstitutionProfile | None:
        stmt = select(ConstitutionProfile).where(ConstitutionProfile.user_id == user_id)
        return self.session.scalar(stmt)

    def upsert_constitution_profile(self, user_id: str, payload: dict) -> ConstitutionProfile:
        profile = self.get_constitution_profile(user_id)
        if profile is None:
            profile = ConstitutionProfile(user_id=user_id, **payload)
            self.session.add(profile)
        else:
            for field, value in payload.items():
                setattr(profile, field, value)
        self.session.flush()
        return profile

    def create_constitution_assessment(self, user_id: str, payload: dict, result: dict) -> ConstitutionAssessment:
        assessment = ConstitutionAssessment(
            user_id=user_id,
            answers=payload.get("answers", {}),
            scores=result.get("scores", {}),
            primary_constitution=result.get("primary_constitution", ""),
            secondary_constitutions=result.get("secondary_constitutions", []),
            result_summary=result.get("result_summary"),
        )
        self.session.add(assessment)
        self.session.flush()
        return assessment

    def list_constitution_assessments(self, user_id: str) -> list[ConstitutionAssessment]:
        stmt = (
            select(ConstitutionAssessment)
            .where(ConstitutionAssessment.user_id == user_id)
            .order_by(desc(ConstitutionAssessment.created_at))
        )
        return list(self.session.scalars(stmt))

    def get_constitution_assessment(self, assessment_id: str) -> ConstitutionAssessment | None:
        return self.session.get(ConstitutionAssessment, assessment_id)

    def create_workflow_session(self, title: str | None = None, last_brief: dict | None = None) -> WorkflowSession:
        workflow_session = WorkflowSession(title=title, last_brief=last_brief)
        self.session.add(workflow_session)
        self.session.flush()
        shadow_chat_session = ChatSession(
            id=workflow_session.id,
            title=title,
            status="workflow_shadow",
            last_question=None,
        )
        self.session.add(shadow_chat_session)
        self.session.flush()
        return workflow_session

    def get_workflow_session(self, session_id: str) -> WorkflowSession | None:
        return self.session.get(WorkflowSession, session_id)

    def list_workflow_sessions(self) -> list[WorkflowSession]:
        stmt = select(WorkflowSession).order_by(desc(WorkflowSession.updated_at))
        return list(self.session.scalars(stmt))

    def create_workflow_run(
        self,
        session_id: str,
        question: str,
        brief: dict,
        status: str = "pending",
    ) -> WorkflowRun:
        workflow_run = WorkflowRun(
            session_id=session_id,
            question=question,
            brief=brief,
            status=status,
            related_graph_snapshots=[],
        )
        self.session.add(workflow_run)
        self.session.flush()
        return workflow_run

    def get_workflow_run(self, run_id: str) -> WorkflowRun | None:
        return self.session.get(WorkflowRun, run_id)

    def list_workflow_runs(self, session_id: str | None = None, limit: int = 100) -> list[WorkflowRun]:
        stmt = select(WorkflowRun)
        if session_id:
            stmt = stmt.where(WorkflowRun.session_id == session_id)
        stmt = stmt.order_by(desc(WorkflowRun.created_at)).limit(limit)
        return list(self.session.scalars(stmt))

    def create_workflow_step_run(
        self,
        run_id: str,
        agent_key: str,
        sequence: int,
        input_payload: dict | None,
        status: str = "pending",
        output_payload: dict | None = None,
        latency_ms: int = 0,
        graph_snapshot_id: str | None = None,
        prompt_version: str | None = None,
    ) -> WorkflowStepRun:
        step_run = WorkflowStepRun(
            run_id=run_id,
            agent_key=agent_key,
            sequence=sequence,
            input_payload=input_payload,
            output_payload=output_payload,
            status=status,
            latency_ms=latency_ms,
            graph_snapshot_id=graph_snapshot_id,
            prompt_version=prompt_version,
        )
        self.session.add(step_run)
        self.session.flush()
        return step_run

    def get_workflow_step_run(self, step_id: str) -> WorkflowStepRun | None:
        return self.session.get(WorkflowStepRun, step_id)

    def list_workflow_step_runs(self, run_id: str) -> list[WorkflowStepRun]:
        stmt = select(WorkflowStepRun).where(WorkflowStepRun.run_id == run_id).order_by(WorkflowStepRun.sequence.asc())
        return list(self.session.scalars(stmt))
