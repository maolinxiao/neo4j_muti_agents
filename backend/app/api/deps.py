from collections.abc import Generator

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db.models import AppUser
from app.db.sqlalchemy import get_db_session
from app.repositories.neo4j_repository import Neo4jRepository
from app.repositories.postgres_repository import PostgresRepository
from app.services.auth_service import AuthService
from app.services.entity_resolver import EntityResolver
from app.services.graph_retriever import GraphRetriever
from app.services.minimax_client import MiniMaxClient
from app.services.qa_orchestrator import QAOrchestrator
from app.services.rnd_workflow_orchestrator import RnDWorkflowOrchestrator


def get_pg_repository(session: Session) -> PostgresRepository:
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


def get_qa_orchestrator(session: Session, neo4j_repository: Neo4jRepository) -> QAOrchestrator:
    postgres_repository = PostgresRepository(session)
    resolver = EntityResolver(neo4j_repository)
    retriever = GraphRetriever(neo4j_repository, postgres_repository)
    minimax_client = MiniMaxClient()
    return QAOrchestrator(postgres_repository, resolver, retriever, minimax_client)


def get_rnd_workflow_orchestrator(session: Session, neo4j_repository: Neo4jRepository) -> RnDWorkflowOrchestrator:
    postgres_repository = PostgresRepository(session)
    minimax_client = MiniMaxClient()
    return RnDWorkflowOrchestrator(postgres_repository, neo4j_repository, minimax_client)
