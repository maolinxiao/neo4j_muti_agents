from typing import Any

from pydantic import BaseModel, Field


class APIMessage(BaseModel):
    message: str


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    props: dict[str, Any] = Field(default_factory=dict)
    score: float = 0.0


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    props: dict[str, Any] = Field(default_factory=dict)
    score: float = 0.0


class GraphPath(BaseModel):
    node_ids: list[str] = Field(default_factory=list)
    edge_ids: list[str] = Field(default_factory=list)
    reason: str = ""
