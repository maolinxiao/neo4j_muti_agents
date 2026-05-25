from typing import Any

from pydantic import BaseModel, Field


class EntityRead(BaseModel):
    id: str
    name: str
    entity_type: str
    props: dict[str, Any] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)


class EntitySearchRead(BaseModel):
    items: list[EntityRead] = Field(default_factory=list)
