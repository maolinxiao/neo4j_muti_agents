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
    app_name: str = os.getenv("APP_NAME", "药食同源知识问答平台")
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
