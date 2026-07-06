from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import GraphEdge, GraphNode, GraphPath


class ChatSessionCreateResponse(BaseModel):
    session_id: str
    title: str | None = None


class ChatMessageCreate(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class ChatMessageRead(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime
    extra_payload: dict[str, Any] | None = None


class ChatSessionRead(BaseModel):
    id: str
    title: str | None = None
    status: str
    last_question: str | None = None
    created_at: datetime
    updated_at: datetime


class QAResponse(BaseModel):
    session_id: str
    answer: str
    evidence_summary: str
    related_entities: list[dict[str, Any]] = Field(default_factory=list)
    graph_snapshot_id: str
    trace_summary: str
    cautions: str = ""
    follow_up_questions: list[str] = Field(default_factory=list)
    answer_mode: str = "graph_fallback"
    qa_route: dict[str, Any] | None = None
    process_summary: str = ""
    missing_slots: list[str] = Field(default_factory=list)
    constitution_assessment: dict[str, Any] | None = None


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    focus_paths: list[GraphPath] = Field(default_factory=list)
    legend: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)


class GraphSnapshotRead(BaseModel):
    id: str
    session_id: str
    question: str
    graph_data: GraphResponse
    created_at: datetime
