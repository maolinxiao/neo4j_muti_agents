from datetime import datetime

from sqlalchemy import desc, func, or_, select, update, delete
from sqlalchemy.orm import Session

from app.db.models import (
    AppUser,
    AuthSession,
    ChatMessage,
    ChatSession,
    ConstitutionAssessment,
    ConstitutionProfile,
    CypherTemplate,
    EntityProfile,
    GraphSnapshot,
    PromptTemplate,
    QATrace,
    UserFeedback,
    WorkflowRun,
    WorkflowSession,
    WorkflowStepRun,
)


class PostgresRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_chat_session(self, user_id: str) -> ChatSession:
        chat_session = ChatSession(user_id=user_id)
        self.session.add(chat_session)
        self.session.flush()
        return chat_session

    def get_chat_session(self, session_id: str, user_id: str | None = None) -> ChatSession | None:
        stmt = select(ChatSession).where(ChatSession.id == session_id)
        if user_id is not None:
            stmt = stmt.where(ChatSession.user_id == user_id)
        return self.session.scalar(stmt)

    def list_chat_sessions(self, user_id: str | None = None) -> list[ChatSession]:
        stmt = select(ChatSession).where(ChatSession.status != "workflow_shadow")
        if user_id is not None:
            stmt = stmt.where(ChatSession.user_id == user_id)
        stmt = stmt.order_by(desc(ChatSession.pinned), desc(ChatSession.updated_at))
        return list(self.session.scalars(stmt))

    def update_chat_session(
        self,
        session_id: str,
        user_id: str,
        title: str | None = None,
        pinned: bool | None = None,
    ) -> ChatSession | None:
        chat_session = self.get_chat_session(session_id, user_id)
        if chat_session is None:
            return None
        if title is not None:
            chat_session.title = title
        if pinned is not None:
            chat_session.pinned = pinned
        self.session.flush()
        return chat_session

    def delete_chat_session(self, session_id: str, user_id: str) -> bool:
        """删除单个聊天会话（按外键依赖顺序级联清理，与 delete_user_with_data 保持一致）。"""
        chat_session = self.get_chat_session(session_id, user_id)
        if chat_session is None:
            return False
        self.session.execute(delete(UserFeedback).where(UserFeedback.session_id == session_id))
        self.session.execute(delete(QATrace).where(QATrace.session_id == session_id))
        self.session.execute(delete(GraphSnapshot).where(GraphSnapshot.session_id == session_id))
        self.session.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
        self.session.delete(chat_session)
        self.session.flush()
        return True

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

    def get_constitution_assessment(self, assessment_id: str, user_id: str | None = None) -> ConstitutionAssessment | None:
        stmt = select(ConstitutionAssessment).where(ConstitutionAssessment.id == assessment_id)
        if user_id is not None:
            stmt = stmt.where(ConstitutionAssessment.user_id == user_id)
        return self.session.scalar(stmt)

    def create_workflow_session(
        self,
        user_id: str,
        title: str | None = None,
        last_brief: dict | None = None,
    ) -> WorkflowSession:
        owner_id = user_id
        workflow_session = WorkflowSession(title=title, last_brief=last_brief, user_id=owner_id)
        self.session.add(workflow_session)
        self.session.flush()
        shadow_chat_session = ChatSession(
            id=workflow_session.id,
            user_id=owner_id,
            title=title,
            status="workflow_shadow",
            last_question=None,
        )
        self.session.add(shadow_chat_session)
        self.session.flush()
        return workflow_session

    def get_workflow_session(self, session_id: str, user_id: str | None = None) -> WorkflowSession | None:
        stmt = select(WorkflowSession).where(WorkflowSession.id == session_id)
        if user_id is not None:
            stmt = stmt.where(WorkflowSession.user_id == user_id)
        return self.session.scalar(stmt)

    def list_workflow_sessions(self, user_id: str | None = None) -> list[WorkflowSession]:
        stmt = select(WorkflowSession)
        if user_id is not None:
            stmt = stmt.where(WorkflowSession.user_id == user_id)
        stmt = stmt.order_by(desc(WorkflowSession.updated_at))
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

    def get_workflow_run(self, run_id: str, user_id: str | None = None) -> WorkflowRun | None:
        stmt = select(WorkflowRun).where(WorkflowRun.id == run_id)
        if user_id is not None:
            stmt = stmt.join(WorkflowSession, WorkflowRun.session_id == WorkflowSession.id).where(
                WorkflowSession.user_id == user_id
            )
        return self.session.scalar(stmt)

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

    def get_workflow_step_run(self, step_id: str, user_id: str | None = None) -> WorkflowStepRun | None:
        stmt = select(WorkflowStepRun).where(WorkflowStepRun.id == step_id)
        if user_id is not None:
            stmt = (
                stmt.join(WorkflowRun, WorkflowStepRun.run_id == WorkflowRun.id)
                .join(WorkflowSession, WorkflowRun.session_id == WorkflowSession.id)
                .where(WorkflowSession.user_id == user_id)
            )
        return self.session.scalar(stmt)

    def list_workflow_step_runs(self, run_id: str) -> list[WorkflowStepRun]:
        stmt = select(WorkflowStepRun).where(WorkflowStepRun.run_id == run_id).order_by(WorkflowStepRun.sequence.asc())
        return list(self.session.scalars(stmt))

    # ------------------------------------------------------------------
    # 用户管理（admin）
    # ------------------------------------------------------------------
    def get_user(self, user_id: str) -> AppUser | None:
        return self.session.get(AppUser, user_id)

    def get_user_by_username(self, username: str) -> AppUser | None:
        return self.session.scalar(select(AppUser).where(AppUser.username == username))

    def list_users(
        self,
        query: str | None = None,
        role: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AppUser], int]:
        conditions = []
        if query:
            pattern = f"%{query.strip()}%"
            conditions.append(
                or_(
                    AppUser.username.ilike(pattern),
                    AppUser.display_name.ilike(pattern),
                    AppUser.email.ilike(pattern),
                )
            )
        if role:
            conditions.append(AppUser.role == role)
        total = self.session.scalar(select(func.count()).select_from(AppUser).where(*conditions)) or 0
        stmt = (
            select(AppUser)
            .where(*conditions)
            .order_by(desc(AppUser.created_at))
            .offset(max(0, page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.session.scalars(stmt)), int(total)

    def count_active_admins(self, exclude_user_id: str | None = None) -> int:
        stmt = select(func.count()).select_from(AppUser).where(AppUser.role == "admin", AppUser.is_active.is_(True))
        if exclude_user_id is not None:
            stmt = stmt.where(AppUser.id != exclude_user_id)
        return int(self.session.scalar(stmt) or 0)

    def revoke_all_sessions(self, user_id: str) -> int:
        result = self.session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=datetime.utcnow())
        )
        self.session.flush()
        return int(result.rowcount or 0)

    def delete_user_with_data(self, user_id: str) -> None:
        """级联删除用户的全部业务数据（按外键依赖顺序手工清理）。

        覆盖表：workflow_step_run → workflow_run → workflow_session（含 shadow chat_session）、
        user_feedback / qa_trace / graph_snapshot / chat_message → chat_session、
        constitution_profile（先解除 last_assessment_id 引用）→ constitution_assessment、
        auth_session → app_user。
        """
        chat_ids = select(ChatSession.id).where(ChatSession.user_id == user_id)
        workflow_session_ids = select(WorkflowSession.id).where(WorkflowSession.user_id == user_id)
        workflow_run_ids = select(WorkflowRun.id).where(WorkflowRun.session_id.in_(workflow_session_ids))
        # 1) 工作流步骤（先于 graph_snapshot / workflow_run 删除）
        self.session.execute(delete(WorkflowStepRun).where(WorkflowStepRun.run_id.in_(workflow_run_ids)))
        # 2) 工作流运行
        self.session.execute(delete(WorkflowRun).where(WorkflowRun.session_id.in_(workflow_session_ids)))
        # 3) 评论反馈（引用 chat_session / chat_message）
        self.session.execute(delete(UserFeedback).where(UserFeedback.session_id.in_(chat_ids)))
        # 4) QA traces（引用 graph_snapshot，先删）
        self.session.execute(delete(QATrace).where(QATrace.session_id.in_(chat_ids)))
        # 5) 图谱快照（chat 与 workflow 的 shadow session 共用 chat_session.id）
        self.session.execute(delete(GraphSnapshot).where(GraphSnapshot.session_id.in_(chat_ids)))
        # 6) 聊天消息
        self.session.execute(delete(ChatMessage).where(ChatMessage.session_id.in_(chat_ids)))
        # 7) 体质档案：先解除对 assessment 的外键引用，再删 assessment / profile
        self.session.execute(
            update(ConstitutionProfile)
            .where(ConstitutionProfile.user_id == user_id, ConstitutionProfile.last_assessment_id.is_not(None))
            .values(last_assessment_id=None)
        )
        self.session.execute(delete(ConstitutionAssessment).where(ConstitutionAssessment.user_id == user_id))
        self.session.execute(delete(ConstitutionProfile).where(ConstitutionProfile.user_id == user_id))
        # 8) 登录会话
        self.session.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
        # 9) 工作流会话（含 shadow chat_session 关系先删会话本体）
        self.session.execute(delete(WorkflowSession).where(WorkflowSession.id.in_(workflow_session_ids)))
        # 10) 聊天会话（含 workflow_shadow）
        self.session.execute(delete(ChatSession).where(ChatSession.id.in_(chat_ids)))
        # 11) 用户本体
        self.session.execute(delete(AppUser).where(AppUser.id == user_id))
        self.session.flush()
