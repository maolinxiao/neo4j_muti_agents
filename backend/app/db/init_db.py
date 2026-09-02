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
        # 迁移必须在任何 ORM 查询之前执行：AppUser/ChatSession 模型已映射新增列，
        # 先补齐物理列才能安全运行下方种子与 admin 初始化（迁移本身幂等，存量回填见 ensure_auth_migration）。
        ensure_auth_migration(session)
        ensure_chat_session_migration(session)
        ensure_profile_migration(session)
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


def ensure_auth_migration(session) -> None:
    """幂等内容迁移：多用户/多会话/验证码表。

    必须在任何 AppUser/ChatSession ORM 查询之前调用（模型已映射新增列，物理列需先就位）。
    面向存量库逐步补齐（新库由 create_all 直接建好，此函数全部走跳过分支）：
    1. auth_session.user_id 由唯一约束降为普通索引（多会话；token_hash 仍唯一）。
    2. app_user 增加 email 列与普通索引（非空邮箱唯一性由服务层保证）。
    3. chat_session / workflow_session 增加 user_id，存量数据回填为最早创建的 admin，
       再 SET NOT NULL 并补外键。
    4. captcha_code 表（与 ORM 定义一致）。
    """
    # 1) auth_session 多会话：唯一约束/唯一索引 → 普通索引
    #    兼容两类残留：(a) 唯一约束（DROP CONSTRAINT）；(b) 唯一索引（DROP INDEX，IF EXISTS 幂等）
    session.execute(text("ALTER TABLE auth_session DROP CONSTRAINT IF EXISTS ix_auth_session_user_id"))
    session.execute(text("DROP INDEX IF EXISTS ix_auth_session_user_id"))
    session.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_session_user_id ON auth_session (user_id)"))

    # 2) app_user.email
    session.execute(text("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS email VARCHAR(128)"))
    session.execute(text("CREATE INDEX IF NOT EXISTS ix_app_user_email ON app_user (email)"))

    # 3) chat_session / workflow_session 归属
    for table in ("chat_session", "workflow_session"):
        session.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS user_id VARCHAR(36)"))
        # 存量回填：优先最早的 admin，其次最早任意用户（缺省兜底）
        session.execute(
            text(
                f"""
                UPDATE {table} SET user_id = (
                    SELECT COALESCE(
                        (SELECT id FROM app_user WHERE role = 'admin' ORDER BY created_at LIMIT 1),
                        (SELECT id FROM app_user ORDER BY created_at LIMIT 1)
                    )
                ) WHERE user_id IS NULL
                """
            )
        )
        session.execute(text(f"ALTER TABLE {table} ALTER COLUMN user_id SET NOT NULL"))
        # 外键：IF NOT EXISTS 对约束无效，用 DO 块按列检查，保证幂等
        session.execute(
            text(
                f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint c
                        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
                        WHERE c.contype = 'f'
                          AND c.conrelid = '{table}'::regclass
                          AND a.attname = 'user_id'
                    ) THEN
                        ALTER TABLE {table}
                            ADD CONSTRAINT fk_{table}_user_id_app_user
                            FOREIGN KEY (user_id) REFERENCES app_user(id);
                    END IF;
                END $$;
                """
            )
        )
        session.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_user_id ON {table} (user_id)"))

    # 4) captcha_code 表
    session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS captcha_code (
                id VARCHAR(36) PRIMARY KEY,
                code_hash VARCHAR(64) NOT NULL,
                expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                used BOOLEAN NOT NULL DEFAULT FALSE,
                ip VARCHAR(64),
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
            )
            """
        )
    )


def ensure_chat_session_migration(session) -> None:
    """幂等迁移：chat_session 增加 pinned（置顶）列（新库由 create_all 直接建好）。"""
    session.execute(text("ALTER TABLE chat_session ADD COLUMN IF NOT EXISTS pinned BOOLEAN NOT NULL DEFAULT FALSE"))


def ensure_profile_migration(session) -> None:
    """幂等迁移：个人中心相关列（app_user.avatar_url、auth_session.user_agent/ip）。"""
    session.execute(text("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(255)"))
    session.execute(text("ALTER TABLE auth_session ADD COLUMN IF NOT EXISTS user_agent VARCHAR(256)"))
    session.execute(text("ALTER TABLE auth_session ADD COLUMN IF NOT EXISTS ip VARCHAR(64)"))


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
