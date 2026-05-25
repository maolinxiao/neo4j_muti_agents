from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.chat import GraphSnapshotRead


class WorkflowSessionCreateResponse(BaseModel):
    id: str
    session_id: str
    title: str | None = None


class WorkflowSessionRead(BaseModel):
    id: str
    title: str | None = None
    status: str
    last_brief: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class WorkflowRunCreate(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    reuse_last_brief: bool = False


class WorkflowStepRunRead(BaseModel):
    id: str
    run_id: str
    agent_key: str
    sequence: int
    status: str
    input_payload: dict[str, Any] | None = None
    output_payload: dict[str, Any] | None = None
    latency_ms: int
    graph_snapshot_id: str | None = None
    prompt_version: str | None = None
    created_at: datetime
    updated_at: datetime


class WorkflowRunRead(BaseModel):
    id: str
    session_id: str
    question: str
    brief: dict[str, Any]
    final_report: dict[str, Any] | None = None
    summary_metrics: dict[str, Any] | None = None
    related_graph_snapshots: list[str] = Field(default_factory=list)
    status: str
    steps: list[WorkflowStepRunRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class WorkflowRunResponse(BaseModel):
    session_id: str
    run_id: str
    brief: dict[str, Any]
    final_report: dict[str, Any] | None = None
    steps: list[WorkflowStepRunRead] = Field(default_factory=list)
    summary_metrics: dict[str, Any] | None = None
    related_graph_snapshots: list[str] = Field(default_factory=list)
    status: str


class WorkflowStepDetailRead(WorkflowStepRunRead):
    graph_snapshot: GraphSnapshotRead | None = None
