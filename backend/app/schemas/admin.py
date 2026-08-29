from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UserAdminRead(BaseModel):
    id: str
    username: str
    display_name: str | None = None
    email: str | None = None
    role: str
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime | None = None


class UserCreateAdmin(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    display_name: str | None = Field(default=None, max_length=128)
    email: str | None = Field(default=None, max_length=128)
    role: str = Field(default="user", max_length=32)


class UserUpdateAdmin(BaseModel):
    display_name: str | None = Field(default=None, max_length=128)
    email: str | None = Field(default=None, max_length=128)
    role: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=1, max_length=256)


class UserPage(BaseModel):
    items: list[UserAdminRead]
    total: int
    page: int
    page_size: int


class OverviewResponse(BaseModel):
    postgres_ok: bool
    neo4j_ok: bool
    llm_configured: bool
    entity_profile_count: int
    workflow_session_count: int
    workflow_run_count: int
    prompt_template_count: int
    cypher_template_count: int
    graph_label_counts: list[dict[str, Any]]
    graph_metrics: dict[str, Any] = {}


class PromptTemplateRead(BaseModel):
    id: str
    key: str
    scenario: str
    agent_key: str | None = None
    name: str
    description: str | None = None
    system_prompt: str
    answer_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    is_active: bool
    updated_at: datetime


class PromptTemplateUpdate(BaseModel):
    scenario: str
    agent_key: str | None = None
    name: str
    description: str | None = None
    system_prompt: str
    answer_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    is_active: bool


class CypherTemplateRead(BaseModel):
    id: str
    key: str
    name: str
    description: str | None = None
    question_type: str
    cypher_query: str
    parameter_schema: dict[str, Any] | None = None
    is_active: bool
    updated_at: datetime


class CypherTemplateUpdate(BaseModel):
    name: str
    description: str | None = None
    question_type: str
    cypher_query: str
    parameter_schema: dict[str, Any] | None = None
    is_active: bool


class ChatLogRead(BaseModel):
    id: str
    session_id: str
    question: str
    question_type: str
    trace_summary: str
    retrieval_ms: int
    llm_ms: int
    created_at: datetime


class WorkflowLogRead(BaseModel):
    id: str
    session_id: str
    question: str
    status: str
    created_at: datetime
    updated_at: datetime
    summary_metrics: dict[str, Any] | None = None
