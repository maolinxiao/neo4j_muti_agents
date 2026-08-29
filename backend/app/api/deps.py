from collections.abc import Generator

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db.models import AppUser
from app.db.sqlalchemy import get_db_session
from app.repositories.neo4j_repository import Neo4jRepository
from app.repositories.postgres_repository import PostgresRepository
from app.services.auth_service import AuthService
from app.services.constitution_service import ConstitutionService
from app.services.entity_resolver import EntityResolver
from app.services.graph_retriever import GraphRetriever
from app.services.deepseek_client import DeepSeekClient
from app.services.qa_orchestrator import QAOrchestrator
from app.services.rnd_workflow_orchestrator import RnDWorkflowOrchestrator


def get_pg_repository(session: Session = Depends(get_db_session)) -> PostgresRepository:
    return PostgresRepository(session)


def get_neo4j_repository() -> Generator[Neo4jRepository, None, None]:
    repository = Neo4jRepository()
    try:
        yield repository
    finally:
        repository.close()


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    return token.strip()


def get_current_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_db_session),
) -> AppUser:
    token = _extract_bearer_token(authorization)
    user = AuthService(session).get_user_for_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


def get_current_admin(current_user: AppUser = Depends(get_current_user)) -> AppUser:
    """管理员守卫：仅 role='admin' 的账号可访问，否则 403。"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


def get_qa_orchestrator(
    session: Session = Depends(get_db_session),
    neo4j_repository: Neo4jRepository = Depends(get_neo4j_repository),
) -> QAOrchestrator:
    postgres_repository = PostgresRepository(session)
    resolver = EntityResolver(neo4j_repository)
    retriever = GraphRetriever(neo4j_repository, postgres_repository)
    llm_client = DeepSeekClient()
    return QAOrchestrator(postgres_repository, resolver, retriever, llm_client)


def get_constitution_service(
    session: Session = Depends(get_db_session),
    neo4j_repository: Neo4jRepository = Depends(get_neo4j_repository),
) -> ConstitutionService:
    postgres_repository = PostgresRepository(session)
    return ConstitutionService(postgres_repository, neo4j_repository)


def get_rnd_workflow_orchestrator(
    session: Session = Depends(get_db_session),
    neo4j_repository: Neo4jRepository = Depends(get_neo4j_repository),
) -> RnDWorkflowOrchestrator:
    postgres_repository = PostgresRepository(session)
    llm_client = DeepSeekClient()
    return RnDWorkflowOrchestrator(postgres_repository, neo4j_repository, llm_client)
