from __future__ import annotations

from statistics import mean
from typing import Any

from app.repositories.neo4j_repository import Neo4jRepository
from app.repositories.postgres_repository import PostgresRepository


class ConstitutionService:
    SCORE_OPTIONS = [
        {"value": 1, "label": "从不"},
        {"value": 2, "label": "很少"},
        {"value": 3, "label": "有时"},
        {"value": 4, "label": "经常"},
        {"value": 5, "label": "总是"},
    ]

    def __init__(self, postgres_repository: PostgresRepository, neo4j_repository: Neo4jRepository) -> None:
        self.postgres_repository = postgres_repository
        self.neo4j_repository = neo4j_repository

    def list_constitution_types(self) -> list[dict[str, Any]]:
        return self.neo4j_repository.list_constitution_types()

    def list_constitution_questions(self) -> list[dict[str, Any]]:
        return self.neo4j_repository.list_constitution_questions()

    def get_constitution_profile(self, user_id: str):
        return self.postgres_repository.get_constitution_profile(user_id)

    def build_questionnaire_payload(self, user_id: str) -> dict[str, Any]:
        profile = self.get_constitution_profile(user_id)
        return {
            "mode": "existing_profile" if profile is not None else "need_user_choice",
            "types": self.list_constitution_types(),
            "questions": self.list_constitution_questions(),
            "score_options": self.SCORE_OPTIONS,
            "existing_profile": self._serialize_profile(profile) if profile is not None else None,
        }

    def upsert_profile(self, user_id: str, payload: dict[str, Any]):
        profile = self.postgres_repository.upsert_constitution_profile(
            user_id,
            {
                "primary_constitution": payload["primary_constitution"],
                "secondary_constitutions": payload.get("secondary_constitutions", []),
                "source": payload.get("source", "manual"),
                "scores": payload.get("scores", {}),
                "notes": payload.get("notes"),
                "last_assessment_id": payload.get("last_assessment_id"),
            },
        )
        return profile

    def create_assessment(self, user_id: str, payload: dict[str, Any]) -> tuple[Any, Any, list[dict[str, Any]]]:
        answers = payload.get("answers", {}) or {}
        questions = self.list_constitution_questions()
        question_lookup = {item["question_code"]: item for item in questions}
        matched_questions = [question_lookup[code] for code in answers if code in question_lookup]
        result = self._calculate_assessment_result(answers, matched_questions)
        assessment = self.postgres_repository.create_constitution_assessment(user_id, payload, result)
        profile = self.postgres_repository.upsert_constitution_profile(
            user_id,
            {
                "primary_constitution": result["primary_constitution"],
                "secondary_constitutions": result["secondary_constitutions"],
                "source": "assessment",
                "scores": result["scores"],
                "notes": payload.get("notes"),
                "last_assessment_id": assessment.id,
            },
        )
        return assessment, profile, matched_questions

    def list_assessments(self, user_id: str):
        return self.postgres_repository.list_constitution_assessments(user_id)

    def get_assessment(self, assessment_id: str):
        return self.postgres_repository.get_constitution_assessment(assessment_id)

    def get_food_rule_summary(self, constitution_name: str) -> dict[str, Any] | None:
        return self.neo4j_repository.get_constitution_food_rules(constitution_name)

    def _calculate_assessment_result(self, answers: dict[str, int], matched_questions: list[dict[str, Any]]) -> dict[str, Any]:
        grouped_scores: dict[str, list[int]] = {}
        raw_scores: dict[str, dict[str, Any]] = {}
        for question in matched_questions:
            code = question["question_code"]
            constitution_name = question.get("constitution_type_name") or "未标注体质"
            raw_value = int(answers.get(code, 0) or 0)
            if raw_value < 1 or raw_value > 5:
                continue
            adjusted = 6 - raw_value if question.get("reverse_scored") else raw_value
            grouped_scores.setdefault(constitution_name, []).append(adjusted)
            raw_scores[code] = {
                "raw_score": raw_value,
                "adjusted_score": adjusted,
                "reverse_scored": bool(question.get("reverse_scored")),
                "constitution_type_name": constitution_name,
            }

        score_summary: dict[str, Any] = {}
        for constitution_name, values in grouped_scores.items():
            average = round(mean(values), 2)
            total = sum(values)
            score_summary[constitution_name] = {
                "question_count": len(values),
                "average_score": average,
                "total_score": total,
            }

        ranked = sorted(
            score_summary.items(),
            key=lambda item: (
                -item[1]["average_score"],
                -item[1]["total_score"],
                item[0],
            ),
        )
        primary = ranked[0][0] if ranked else "平和质"
        secondary = [
            item[0]
            for item in ranked[1:]
            if item[1]["average_score"] >= max(3.0, ranked[0][1]["average_score"] - 0.3)
        ][:2] if ranked else []

        summary = (
            f"本次量表共纳入 {len(raw_scores)} 道有效题目，主体质倾向为“{primary}”。"
            + (f" 兼夹体质包括：{'、'.join(secondary)}。" if secondary else "")
            + " 结果仅用于体质辨识辅助判断，不替代临床诊断。"
        )
        return {
            "scores": {
                "by_constitution": score_summary,
                "by_question": raw_scores,
            },
            "primary_constitution": primary,
            "secondary_constitutions": secondary,
            "result_summary": summary,
        }

    @staticmethod
    def _serialize_profile(profile) -> dict[str, Any]:
        return {
            "id": profile.id,
            "user_id": profile.user_id,
            "primary_constitution": profile.primary_constitution,
            "secondary_constitutions": list(profile.secondary_constitutions or []),
            "source": profile.source,
            "scores": profile.scores or {},
            "notes": profile.notes,
            "last_assessment_id": profile.last_assessment_id,
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        }
