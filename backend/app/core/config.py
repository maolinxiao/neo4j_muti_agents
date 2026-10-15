from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _as_bool(value: str, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "食源智汇药食同源多Agent智能体系统")
    app_env: str = os.getenv("APP_ENV", "dev")
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    postgres_dsn: str = os.getenv(
        "POSTGRES_DSN",
        "postgresql+psycopg://postgres:1234@localhost:5432/postgres",
    )
    neo4j_uri: str = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
    neo4j_username: str = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "3217858658")
    llm_api_base: str = os.getenv("DEEPSEEK_API_BASE") or os.getenv("MINIMAX_API_BASE", "https://api.deepseek.com")
    llm_api_key: str = os.getenv("DEEPSEEK_API_KEY") or os.getenv("MINIMAX_API_KEY", "")
    llm_model: str = os.getenv("DEEPSEEK_MODEL") or os.getenv("MINIMAX_MODEL", "deepseek-v4-pro")
    llm_reasoning_enabled: bool = _as_bool(
        os.getenv("DEEPSEEK_THINKING_ENABLED") or os.getenv("MINIMAX_REASONING_SPLIT"),
        True,
    )
    max_graph_nodes: int = int(os.getenv("MAX_GRAPH_NODES", "40"))
    max_graph_edges: int = int(os.getenv("MAX_GRAPH_EDGES", "80"))
    default_temperature: float = float(os.getenv("DEFAULT_TEMPERATURE", "0.2"))
    default_max_completion_tokens: int = int(os.getenv("DEFAULT_MAX_COMPLETION_TOKENS", "1200"))
    default_admin_username: str = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    default_admin_password: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123456")
    auth_session_ttl_hours: int = int(os.getenv("AUTH_SESSION_TTL_HOURS", "24"))
    # --- 认证/账号基座配置 ---
    captcha_enabled: bool = _as_bool(os.getenv("CAPTCHA_ENABLED"), True)
    captcha_length: int = int(os.getenv("CAPTCHA_LENGTH", "4"))
    captcha_ttl_seconds: int = int(os.getenv("CAPTCHA_TTL_SECONDS", "300"))
    captcha_fail_max: int = int(os.getenv("CAPTCHA_FAIL_MAX", "5"))
    auth_max_sessions_per_user: int = int(os.getenv("AUTH_MAX_SESSIONS_PER_USER", "5"))
    password_min_length: int = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
    login_fail_lock_minutes: int = int(os.getenv("LOGIN_FAIL_LOCK_MINUTES", "15"))
    # --- 个人中心/上传 ---
    upload_dir: str = os.getenv("UPLOAD_DIR", str(Path(__file__).resolve().parents[2] / "uploads"))
    max_avatar_bytes: int = int(os.getenv("MAX_AVATAR_BYTES", str(2 * 1024 * 1024)))
    # --- 管理端表格导入 / 知识图谱写入 ---
    max_import_bytes: int = int(os.getenv("MAX_IMPORT_BYTES", str(20 * 1024 * 1024)))
    import_max_rows: int = int(os.getenv("IMPORT_MAX_ROWS", "50000"))
    import_batch_size: int = int(os.getenv("IMPORT_BATCH_SIZE", "500"))
    import_snapshot_max: int = int(os.getenv("IMPORT_SNAPSHOT_MAX", "50000"))
    # --- 工作流 Agent 配置编辑（2026-10-12 新增）---
    agent_temperature_min: float = float(os.getenv("AGENT_TEMPERATURE_MIN", "0.0"))
    agent_temperature_max: float = float(os.getenv("AGENT_TEMPERATURE_MAX", "1.0"))
    agent_max_tokens_min: int = int(os.getenv("AGENT_MAX_TOKENS_MIN", "200"))
    agent_max_tokens_max: int = int(os.getenv("AGENT_MAX_TOKENS_MAX", "4000"))
    agent_prompt_max_chars: int = int(os.getenv("AGENT_PROMPT_MAX_CHARS", "20000"))
    # --- 并发与连接池（负载优化，参数与默认行为保持一致，可通过 .env 调整） ---
    pg_pool_size: int = int(os.getenv("PG_POOL_SIZE", "20"))
    pg_max_overflow: int = int(os.getenv("PG_MAX_OVERFLOW", "20"))
    pg_pool_recycle_seconds: int = int(os.getenv("PG_POOL_RECYCLE_SECONDS", "1800"))
    neo4j_max_connection_pool_size: int = int(os.getenv("NEO4J_MAX_CONNECTION_POOL_SIZE", "50"))
    neo4j_connection_acquisition_timeout: int = int(os.getenv("NEO4J_CONNECTION_ACQUISITION_TIMEOUT", "15"))
    neo4j_max_connection_lifetime: int = int(os.getenv("NEO4J_MAX_CONNECTION_LIFETIME", "1800"))
    llm_connect_timeout: float = float(os.getenv("LLM_CONNECT_TIMEOUT", "5.0"))
    llm_read_timeout: float = float(os.getenv("LLM_READ_TIMEOUT", "120.0"))
    llm_write_timeout: float = float(os.getenv("LLM_WRITE_TIMEOUT", "10.0"))
    llm_pool_timeout: float = float(os.getenv("LLM_POOL_TIMEOUT", "10.0"))
    llm_max_connections: int = int(os.getenv("LLM_MAX_CONNECTIONS", "30"))
    llm_max_keepalive_connections: int = int(os.getenv("LLM_MAX_KEEPALIVE_CONNECTIONS", "10"))
    llm_retry_attempts: int = int(os.getenv("LLM_RETRY_ATTEMPTS", "2"))
    llm_retry_backoff_seconds: float = float(os.getenv("LLM_RETRY_BACKOFF_SECONDS", "0.6"))
    # --- uvicorn 单 worker 负载参数（run_server.py 消费） ---
    app_backlog: int = int(os.getenv("APP_BACKLOG", "2048"))
    app_limit_concurrency: int = int(os.getenv("APP_LIMIT_CONCURRENCY", "300"))
    app_keepalive_timeout: int = int(os.getenv("APP_KEEPALIVE_TIMEOUT", "65"))
    # --- 应用层限流与慢请求观测 ---
    rate_limit_enabled: bool = _as_bool(os.getenv("RATE_LIMIT_ENABLED"), True)
    rate_limit_requests: int = int(os.getenv("RATE_LIMIT_REQUESTS", "120"))
    rate_limit_window_seconds: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    rate_limit_auth_requests: int = int(os.getenv("RATE_LIMIT_AUTH_REQUESTS", "10"))
    rate_limit_auth_window_seconds: int = int(os.getenv("RATE_LIMIT_AUTH_WINDOW_SECONDS", "60"))
    slow_request_ms: int = int(os.getenv("SLOW_REQUEST_MS", "1000"))
    # --- LangGraph 研发协同双引擎开关（2026-10-15，阶段一）---
    # 默认与关闭语义：rnd_engine 默认 legacy；其余新开关一律"关闭/保守"。
    # 生产**不新增任何 env 键**：以下键均可缺省，缺省即取这里的默认值。
    rnd_engine: str = os.getenv("RND_ENGINE", "legacy")
    rnd_engine_cache_ttl_seconds: int = int(os.getenv("RND_ENGINE_CACHE_TTL_SECONDS", "15"))
    rnd_langgraph_schema: str = os.getenv("RND_LANGGRAPH_SCHEMA", "langgraph")
    rnd_langgraph_pool_max: int = int(os.getenv("RND_LANGGRAPH_POOL_MAX", "2"))
    rnd_langgraph_validate_on_start: bool = _as_bool(os.getenv("RND_LANGGRAPH_VALIDATE_ON_START"), True)
    # 恢复开关仅用于隔离环境手动 invoke(None)；生产恒为关（v2.1 §C.4 前置 3）
    rnd_langgraph_resume_enabled: bool = _as_bool(os.getenv("RND_LANGGRAPH_RESUME_ENABLED"), False)
    # 孤儿清扫（W3）：默认关闭，且只作用于 pin=langgraph 的 Run
    rnd_orphan_sweep_enabled: bool = _as_bool(os.getenv("RND_ORPHAN_SWEEP_ENABLED"), False)
    rnd_orphan_stale_minutes: int = int(os.getenv("RND_ORPHAN_STALE_MINUTES", "30"))

    @property
    def minimax_api_base(self) -> str:
        return self.llm_api_base

    @property
    def minimax_api_key(self) -> str:
        return self.llm_api_key

    @property
    def minimax_model(self) -> str:
        return self.llm_model

    @property
    def minimax_reasoning_split(self) -> bool:
        return self.llm_reasoning_enabled


settings = Settings()
