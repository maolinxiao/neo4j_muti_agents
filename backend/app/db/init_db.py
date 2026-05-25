import csv
from pathlib import Path

from sqlalchemy import inspect, select, text

from app.db.models import (
    AppUser,
    Base,
    CypherTemplate,
    EntityProfile,
    PromptTemplate,
    SystemConfig,
    WorkflowRun,
    WorkflowSession,
)
from app.db.seed_data import DEFAULT_CYPHER_TEMPLATES, DEFAULT_PROMPTS, DEFAULT_SYSTEM_CONFIG
from app.db.sqlalchemy import SessionLocal, engine
from app.services.auth_service import hash_password
from app.core.config import settings


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    _apply_additive_migrations()
    with SessionLocal() as session:
        for item in DEFAULT_PROMPTS:
            exists = session.scalar(select(PromptTemplate).where(PromptTemplate.key == item["key"]))
            if not exists:
                session.add(PromptTemplate(**item))
            else:
                for key, value in item.items():
                    setattr(exists, key, value)
        for item in DEFAULT_CYPHER_TEMPLATES:
            exists = session.scalar(select(CypherTemplate).where(CypherTemplate.key == item["key"]))
            if not exists:
                session.add(CypherTemplate(**item))
            else:
                for key, value in item.items():
                    setattr(exists, key, value)
        for item in DEFAULT_SYSTEM_CONFIG:
            exists = session.scalar(select(SystemConfig).where(SystemConfig.config_key == item["config_key"]))
            if not exists:
                session.add(SystemConfig(**item))
            else:
                for key, value in item.items():
                    setattr(exists, key, value)
        _seed_default_admin(session)
        _seed_food_homology_profiles(session)
        session.commit()


def _apply_additive_migrations() -> None:
    inspector = inspect(engine)
    if "prompt_template" in inspector.get_table_names():
        existing = {column["name"] for column in inspector.get_columns("prompt_template")}
        statements = []
        if "scenario" not in existing:
            statements.append("ALTER TABLE prompt_template ADD COLUMN scenario VARCHAR(64) NOT NULL DEFAULT 'knowledge_qa'")
        if "agent_key" not in existing:
            statements.append("ALTER TABLE prompt_template ADD COLUMN agent_key VARCHAR(64)")
        if "output_schema" not in existing:
            statements.append("ALTER TABLE prompt_template ADD COLUMN output_schema JSONB")
        for sql in statements:
            with engine.begin() as conn:
                conn.execute(text(sql))


def _seed_default_admin(session) -> None:
    username = settings.default_admin_username.strip()
    password = settings.default_admin_password
    if not username or not password:
        return
    exists = session.scalar(select(AppUser).where(AppUser.username == username))
    if exists:
        return
    session.add(
        AppUser(
            username=username,
            display_name="管理员",
            password_hash=hash_password(password),
            role="admin",
            is_active=True,
        )
    )


def _seed_food_homology_profiles(session) -> None:
    csv_path = (
        Path(__file__).resolve().parents[3]
        / "origin_data"
        / "data_2"
        / "数据库"
        / "药食同源"
        / "中国药典中药材数据_106种药食同源.csv"
    )
    if not csv_path.exists():
        return
    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            herb_name = (row.get("herb_name") or "").strip()
            if not herb_name:
                continue
            exists = session.scalar(select(EntityProfile).where(EntityProfile.neo4j_key == herb_name))
            if exists:
                exists.display_name = herb_name
                exists.entity_type = "Herb"
                exists.aliases = [value for value in [row.get("pinyin_name"), row.get("latin_name")] if value]
                exists.summary = row.get("core_efficacy_tcm") or row.get("core_efficacy_modern")
                exists.contraindications = row.get("contraindications")
                exists.metadata_json = row
                continue
            session.add(
                EntityProfile(
                    neo4j_key=herb_name,
                    display_name=herb_name,
                    entity_type="Herb",
                    aliases=[value for value in [row.get("pinyin_name"), row.get("latin_name")] if value],
                    summary=row.get("core_efficacy_tcm") or row.get("core_efficacy_modern"),
                    contraindications=row.get("contraindications"),
                    recommended_questions=[
                        f"{herb_name}有什么功效？",
                        f"{herb_name}适合哪些人群？",
                    ],
                    metadata_json=row,
                )
            )
