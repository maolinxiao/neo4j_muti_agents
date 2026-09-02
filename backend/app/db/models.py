import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.sqlalchemy import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class ChatSession(Base, TimestampMixin):
    __tablename__ = "chat_session"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), index=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    last_question: Mapped[str | None] = mapped_column(Text)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    traces: Mapped[list["QATrace"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class AppUser(Base, TimestampMixin):
    __tablename__ = "app_user"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128))
    email: Mapped[str | None] = mapped_column(String(128), index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="admin", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    avatar_url: Mapped[str | None] = mapped_column(String(255))

    auth_sessions: Mapped[list["AuthSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    constitution_profiles: Mapped[list["ConstitutionProfile"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    constitution_assessments: Mapped[list["ConstitutionAssessment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AuthSession(Base, TimestampMixin):
    __tablename__ = "auth_session"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # 多会话：user_id 非唯一索引（同一用户可有多台设备/多个会话）；token_hash 保持唯一
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    user_agent: Mapped[str | None] = mapped_column(String(256))
    ip: Mapped[str | None] = mapped_column(String(64))

    user: Mapped[AppUser] = relationship(back_populates="auth_sessions")


class CaptchaCode(Base, TimestampMixin):
    """图形验证码记录（DB 化预留，当前逻辑以内存 CaptchaStore 为准）。"""

    __tablename__ = "captcha_code"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64))


class ChatMessage(Base, TimestampMixin):
    __tablename__ = "chat_message"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_session.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    extra_payload: Mapped[dict | None] = mapped_column(JSONB)

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class GraphSnapshot(Base, TimestampMixin):
    __tablename__ = "graph_snapshot"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_session.id"), index=True, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    graph_data: Mapped[dict] = mapped_column(JSONB, nullable=False)


class QATrace(Base, TimestampMixin):
    __tablename__ = "qa_trace"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_session.id"), index=True, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entities: Mapped[list | dict] = mapped_column(JSONB, nullable=False)
    cypher_template_key: Mapped[str] = mapped_column(String(64), nullable=False)
    trace_summary: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    llm_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    graph_snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("graph_snapshot.id"))
    reasoning_payload: Mapped[dict | None] = mapped_column(JSONB)

    session: Mapped[ChatSession] = relationship(back_populates="traces")


class EntityProfile(Base, TimestampMixin):
    __tablename__ = "entity_profile"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    neo4j_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aliases: Mapped[list | None] = mapped_column(JSONB)
    summary: Mapped[str | None] = mapped_column(Text)
    contraindications: Mapped[str | None] = mapped_column(Text)
    recommended_questions: Mapped[list | None] = mapped_column(JSONB)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)


class PromptTemplate(Base, TimestampMixin):
    __tablename__ = "prompt_template"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    scenario: Mapped[str] = mapped_column(String(64), default="knowledge_qa", index=True, nullable=False)
    agent_key: Mapped[str | None] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    answer_schema: Mapped[dict | None] = mapped_column(JSONB)
    output_schema: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CypherTemplate(Base, TimestampMixin):
    __tablename__ = "cypher_template"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    question_type: Mapped[str] = mapped_column(String(64), nullable=False)
    cypher_query: Mapped[str] = mapped_column(Text, nullable=False)
    parameter_schema: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class UserFeedback(Base, TimestampMixin):
    __tablename__ = "user_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_session.id"), index=True, nullable=False)
    message_id: Mapped[str | None] = mapped_column(ForeignKey("chat_message.id"))
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)


class SystemConfig(Base, TimestampMixin):
    __tablename__ = "system_config"
    __table_args__ = (UniqueConstraint("config_key", name="uq_system_config_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    config_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    config_value: Mapped[str | None] = mapped_column(Text)
    config_json: Mapped[dict | None] = mapped_column(JSONB)
    config_type: Mapped[str] = mapped_column(String(32), default="string", nullable=False)


class ConstitutionAssessment(Base, TimestampMixin):
    __tablename__ = "constitution_assessment"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), index=True, nullable=False)
    answers: Mapped[dict] = mapped_column(JSONB, nullable=False)
    scores: Mapped[dict] = mapped_column(JSONB, nullable=False)
    primary_constitution: Mapped[str] = mapped_column(String(128), nullable=False)
    secondary_constitutions: Mapped[list | None] = mapped_column(JSONB)
    result_summary: Mapped[str | None] = mapped_column(Text)

    user: Mapped[AppUser] = relationship(back_populates="constitution_assessments")


class ConstitutionProfile(Base, TimestampMixin):
    __tablename__ = "constitution_profile"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), index=True, nullable=False)
    primary_constitution: Mapped[str] = mapped_column(String(128), nullable=False)
    secondary_constitutions: Mapped[list | None] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    scores: Mapped[dict | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)
    last_assessment_id: Mapped[str | None] = mapped_column(ForeignKey("constitution_assessment.id"))

    user: Mapped[AppUser] = relationship(back_populates="constitution_profiles")
    last_assessment: Mapped[ConstitutionAssessment | None] = relationship(foreign_keys=[last_assessment_id])


class WorkflowSession(Base, TimestampMixin):
    __tablename__ = "workflow_session"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), index=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    last_brief: Mapped[dict | None] = mapped_column(JSONB)

    runs: Mapped[list["WorkflowRun"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class WorkflowRun(Base, TimestampMixin):
    __tablename__ = "workflow_run"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("workflow_session.id"), index=True, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    brief: Mapped[dict] = mapped_column(JSONB, nullable=False)
    final_report: Mapped[dict | None] = mapped_column(JSONB)
    summary_metrics: Mapped[dict | None] = mapped_column(JSONB)
    related_graph_snapshots: Mapped[list | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)

    session: Mapped[WorkflowSession] = relationship(back_populates="runs")
    steps: Mapped[list["WorkflowStepRun"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class WorkflowStepRun(Base, TimestampMixin):
    __tablename__ = "workflow_step_run"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_run.id"), index=True, nullable=False)
    agent_key: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    input_payload: Mapped[dict | None] = mapped_column(JSONB)
    output_payload: Mapped[dict | None] = mapped_column(JSONB)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    graph_snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("graph_snapshot.id"))
    prompt_version: Mapped[str | None] = mapped_column(String(128))

    run: Mapped[WorkflowRun] = relationship(back_populates="steps")
