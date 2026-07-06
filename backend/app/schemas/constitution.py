from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConstitutionTypeRead(BaseModel):
    id: str
    constitution_type_name: str
    constitution_category: str | None = None
    summary: str | None = None
    diet_direction: str | None = None
    food_homology_direction: str | None = None
    suitable_ingredient_examples: str | None = None
    caution_herbs: list[str] = Field(default_factory=list)
    recommended_herbs: list[str] = Field(default_factory=list)
    judgement_rule: str | None = None
    source: str | None = None


class ConstitutionQuestionRead(BaseModel):
    id: str
    question_code: str
    question_no: int | None = None
    question_text: str
    constitution_type_name: str | None = None
    reverse_scored: bool = False
    score_1: str = "从不"
    score_2: str = "很少"
    score_3: str = "有时"
    score_4: str = "经常"
    score_5: str = "总是"
    applicable_group: str | None = None
    source_page: str | None = None


class ConstitutionProfileRead(BaseModel):
    id: str
    user_id: str
    primary_constitution: str
    secondary_constitutions: list[str] = Field(default_factory=list)
    source: str
    scores: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    last_assessment_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ConstitutionProfileUpdate(BaseModel):
    primary_constitution: str = Field(min_length=1, max_length=128)
    secondary_constitutions: list[str] = Field(default_factory=list, max_length=5)
    source: str = Field(default="manual", pattern="^(manual|assessment)$")
    scores: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=2000)
    last_assessment_id: str | None = None


class ConstitutionAssessmentCreate(BaseModel):
    answers: dict[str, int] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=2000)


class ConstitutionAssessmentRead(BaseModel):
    id: str
    user_id: str
    answers: dict[str, int] = Field(default_factory=dict)
    scores: dict[str, Any] = Field(default_factory=dict)
    primary_constitution: str
    secondary_constitutions: list[str] = Field(default_factory=list)
    result_summary: str | None = None
    created_at: datetime
    updated_at: datetime


class ConstitutionAssessmentResult(BaseModel):
    assessment: ConstitutionAssessmentRead
    profile: ConstitutionProfileRead
    matched_questions: list[ConstitutionQuestionRead] = Field(default_factory=list)
