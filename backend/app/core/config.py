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
    minimax_api_base: str = os.getenv("MINIMAX_API_BASE", "https://api.minimaxi.com/v1")
    minimax_api_key: str = os.getenv("MINIMAX_API_KEY", "")
    minimax_model: str = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")
    minimax_reasoning_split: bool = _as_bool(os.getenv("MINIMAX_REASONING_SPLIT"), True)
    max_graph_nodes: int = int(os.getenv("MAX_GRAPH_NODES", "40"))
    max_graph_edges: int = int(os.getenv("MAX_GRAPH_EDGES", "80"))
    default_temperature: float = float(os.getenv("DEFAULT_TEMPERATURE", "0.2"))
    default_max_completion_tokens: int = int(os.getenv("DEFAULT_MAX_COMPLETION_TOKENS", "1200"))
    default_admin_username: str = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    default_admin_password: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123456")
    auth_session_ttl_hours: int = int(os.getenv("AUTH_SESSION_TTL_HOURS", "24"))


settings = Settings()
