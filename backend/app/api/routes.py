from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import (
    get_constitution_service,
    get_current_user,
    get_neo4j_repository,
    get_qa_orchestrator,
    get_rnd_workflow_orchestrator,
)
from app.core.config import settings
from app.db.models import AppUser, CypherTemplate, EntityProfile, PromptTemplate, WorkflowRun, WorkflowSession
from app.db.sqlalchemy import SessionLocal, get_db_session
from app.repositories.neo4j_repository import Neo4jRepository
from app.repositories.postgres_repository import PostgresRepository
from app.schemas.admin import (
    ChatLogRead,
    CypherTemplateRead,
    CypherTemplateUpdate,
    OverviewResponse,
    PromptTemplateRead,
    PromptTemplateUpdate,
    WorkflowLogRead,
)
from app.schemas.auth import LoginRequest, LoginResponse, UserRead
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageRead,
    ChatSessionCreateResponse,
    GraphSnapshotRead,
    ChatSessionRead,
    GraphResponse,
    QAResponse,
)
from app.schemas.constitution import (
    ConstitutionAssessmentCreate,
    ConstitutionAssessmentRead,
    ConstitutionAssessmentResult,
    ConstitutionProfileRead,
    ConstitutionProfileUpdate,
    ConstitutionQuestionRead,
    ConstitutionTypeRead,
)
from app.schemas.entity import EntityRead, EntitySearchRead
from app.schemas.rnd import (
    WorkflowRunCreate,
    WorkflowRunRead,
    WorkflowRunResponse,
    WorkflowSessionCreateResponse,
    WorkflowSessionRead,
    WorkflowStepDetailRead,
    WorkflowStepRunRead,
)
from app.services.deepseek_client import DeepSeekClient
from app.services.constitution_service import ConstitutionService
from app.services.qa_orchestrator import QAOrchestrator
from app.services.rnd_workflow_orchestrator import RnDWorkflowOrchestrator
from app.services.auth_service import AuthService


health_router = APIRouter(tags=["health"])
auth_router = APIRouter(prefix="/auth", tags=["auth"])
chat_router = APIRouter(tags=["chat"])
entity_router = APIRouter(tags=["entity"])
constitution_router = APIRouter(prefix="/constitution", tags=["constitution"])
rnd_router = APIRouter(prefix="/rnd", tags=["rnd"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])


def _workflow_run_read(repository: PostgresRepository, run: WorkflowRun) -> WorkflowRunRead:
    steps = repository.list_workflow_step_runs(run.id)
    return WorkflowRunRead(
        id=run.id,
        session_id=run.session_id,
        question=run.question,
        brief=run.brief,
        final_report=run.final_report,
        summary_metrics=run.summary_metrics,
        related_graph_snapshots=run.related_graph_snapshots or [],
        status=run.status,
        steps=[WorkflowStepRunRead.model_validate(step, from_attributes=True) for step in steps],
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _run_workflow_in_background(run_id: str) -> None:
    db = SessionLocal()
    neo4j = Neo4jRepository()
    try:
        orchestrator = RnDWorkflowOrchestrator(PostgresRepository(db), neo4j, DeepSeekClient())
        orchestrator.resume_run(run_id)
    finally:
        neo4j.close()
        db.close()


def _bearer_from_header(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    return token.strip()


@auth_router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db_session)) -> LoginResponse:
    service = AuthService(db)
    user = service.authenticate(payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token, auth_session = service.create_session(user)
    db.commit()
    db.refresh(user)
    return LoginResponse(
        access_token=token,
        expires_at=auth_session.expires_at,
        user=UserRead.model_validate(user, from_attributes=True),
    )


@auth_router.get("/me", response_model=UserRead)
def me(current_user: AppUser = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user, from_attributes=True)


@auth_router.post("/logout")
def logout(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db_session),
) -> dict:
    AuthService(db).revoke_token(_bearer_from_header(authorization))
    db.commit()
    return {"message": "ok"}


@health_router.get("/health")
def health_check(db: Session = Depends(get_db_session), neo4j: Neo4jRepository = Depends(get_neo4j_repository)) -> dict:
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "postgres": True,
        "neo4j": neo4j.health_check(),
        "llm_configured": bool(settings.llm_api_key),
    }


@chat_router.post("/chat/sessions", response_model=ChatSessionCreateResponse)
def create_chat_session(db: Session = Depends(get_db_session)) -> ChatSessionCreateResponse:
    repository = PostgresRepository(db)
    session = repository.create_chat_session()
    db.commit()
    return ChatSessionCreateResponse(session_id=session.id, title=session.title)


@chat_router.get("/chat/sessions/{session_id}", response_model=ChatSessionRead)
def get_chat_session(session_id: str, db: Session = Depends(get_db_session)) -> ChatSessionRead:
    repository = PostgresRepository(db)
    session = repository.get_chat_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return ChatSessionRead.model_validate(session, from_attributes=True)


@chat_router.get("/chat/sessions", response_model=list[ChatSessionRead])
def list_chat_sessions(db: Session = Depends(get_db_session)) -> list[ChatSessionRead]:
    repository = PostgresRepository(db)
    return [ChatSessionRead.model_validate(item, from_attributes=True) for item in repository.list_chat_sessions()]


@chat_router.post("/chat/sessions/{session_id}/messages", response_model=QAResponse)
def ask_question(
    session_id: str,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db_session),
    neo4j: Neo4jRepository = Depends(get_neo4j_repository),
    current_user: AppUser = Depends(get_current_user),
) -> QAResponse:
    orchestrator = get_qa_orchestrator(db, neo4j)
    current_user_snapshot = {"id": current_user.id}
    try:
        result = orchestrator.ask(session_id, payload.question, current_user=current_user_snapshot)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return QAResponse(**result)


@chat_router.post("/chat/sessions/{session_id}/messages/stream")
def ask_question_stream(
    session_id: str,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db_session),
    neo4j: Neo4jRepository = Depends(get_neo4j_repository),
    current_user: AppUser = Depends(get_current_user),
):
    repo = PostgresRepository(db)
    session = repo.get_chat_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    repo.create_message(session_id, "user", payload.question)
    session.last_question = payload.question
    session.title = session.title or payload.question[:40]
    repo.session.commit()

    orchestrator = get_qa_orchestrator(db, neo4j)
    current_user_snapshot = {"id": current_user.id}
    return StreamingResponse(
        orchestrator.ask_stream(session_id, payload.question, current_user=current_user_snapshot),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@chat_router.get("/chat/sessions/{session_id}/messages", response_model=list[ChatMessageRead])
def list_messages(session_id: str, db: Session = Depends(get_db_session)) -> list[ChatMessageRead]:
    repository = PostgresRepository(db)
    messages = repository.list_messages(session_id)
    return [ChatMessageRead.model_validate(item, from_attributes=True) for item in messages]


@chat_router.get("/chat/sessions/{session_id}/graph", response_model=GraphResponse)
def get_session_graph(session_id: str, db: Session = Depends(get_db_session)) -> GraphResponse:
    repository = PostgresRepository(db)
    snapshot = repository.get_latest_graph_snapshot(session_id)
    if snapshot is None:
        return GraphResponse(nodes=[], edges=[], focus_paths=[], legend={}, metrics={})
    return GraphResponse(**snapshot.graph_data)


@chat_router.get("/chat/graph-snapshots/{snapshot_id}", response_model=GraphSnapshotRead)
def get_graph_snapshot(snapshot_id: str, db: Session = Depends(get_db_session)) -> GraphSnapshotRead:
    repository = PostgresRepository(db)
    snapshot = repository.get_graph_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Graph snapshot not found")
    return GraphSnapshotRead(
        id=snapshot.id,
        session_id=snapshot.session_id,
        question=snapshot.question,
        graph_data=GraphResponse(**snapshot.graph_data),
        created_at=snapshot.created_at,
    )


@entity_router.get("/entities/search", response_model=EntitySearchRead)
def search_entities(q: str, neo4j: Neo4jRepository = Depends(get_neo4j_repository)) -> EntitySearchRead:
    items = [EntityRead(**item) for item in neo4j.search_entities(q, limit=20)]
    return EntitySearchRead(items=items)


@entity_router.get("/entities/{entity_id}", response_model=EntityRead)
def get_entity(entity_id: str, neo4j: Neo4jRepository = Depends(get_neo4j_repository)) -> EntityRead:
    entity = neo4j.get_entity(entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return EntityRead(**entity)


@constitution_router.get("/types", response_model=list[ConstitutionTypeRead])
def list_constitution_types(service: ConstitutionService = Depends(get_constitution_service)) -> list[ConstitutionTypeRead]:
    return [ConstitutionTypeRead(**item) for item in service.list_constitution_types()]


@constitution_router.get("/questionnaire")
def get_constitution_questionnaire(
    current_user: AppUser = Depends(get_current_user),
    service: ConstitutionService = Depends(get_constitution_service),
) -> dict:
    return service.build_questionnaire_payload(current_user.id)


@constitution_router.get("/profile", response_model=ConstitutionProfileRead | None)
def get_constitution_profile(
    current_user: AppUser = Depends(get_current_user),
    service: ConstitutionService = Depends(get_constitution_service),
) -> ConstitutionProfileRead | None:
    profile = service.get_constitution_profile(current_user.id)
    if profile is None:
        return None
    return ConstitutionProfileRead.model_validate(profile, from_attributes=True)


@constitution_router.put("/profile", response_model=ConstitutionProfileRead)
def update_constitution_profile(
    payload: ConstitutionProfileUpdate,
    current_user: AppUser = Depends(get_current_user),
    service: ConstitutionService = Depends(get_constitution_service),
    db: Session = Depends(get_db_session),
) -> ConstitutionProfileRead:
    profile = service.upsert_profile(current_user.id, payload.model_dump())
    db.commit()
    db.refresh(profile)
    return ConstitutionProfileRead.model_validate(profile, from_attributes=True)


@constitution_router.post("/assessments", response_model=ConstitutionAssessmentResult)
def create_constitution_assessment(
    payload: ConstitutionAssessmentCreate,
    current_user: AppUser = Depends(get_current_user),
    service: ConstitutionService = Depends(get_constitution_service),
    db: Session = Depends(get_db_session),
) -> ConstitutionAssessmentResult:
    assessment, profile, matched_questions = service.create_assessment(current_user.id, payload.model_dump())
    db.commit()
    db.refresh(assessment)
    db.refresh(profile)
    return ConstitutionAssessmentResult(
        assessment=ConstitutionAssessmentRead.model_validate(assessment, from_attributes=True),
        profile=ConstitutionProfileRead.model_validate(profile, from_attributes=True),
        matched_questions=[ConstitutionQuestionRead(**item) for item in matched_questions],
    )


@constitution_router.get("/assessments", response_model=list[ConstitutionAssessmentRead])
def list_constitution_assessments(
    current_user: AppUser = Depends(get_current_user),
    service: ConstitutionService = Depends(get_constitution_service),
) -> list[ConstitutionAssessmentRead]:
    assessments = service.list_assessments(current_user.id)
    return [ConstitutionAssessmentRead.model_validate(item, from_attributes=True) for item in assessments]


@constitution_router.get("/assessments/{assessment_id}", response_model=ConstitutionAssessmentRead)
def get_constitution_assessment(
    assessment_id: str,
    current_user: AppUser = Depends(get_current_user),
    service: ConstitutionService = Depends(get_constitution_service),
) -> ConstitutionAssessmentRead:
    assessment = service.get_assessment(assessment_id)
    if assessment is None or assessment.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Constitution assessment not found")
    return ConstitutionAssessmentRead.model_validate(assessment, from_attributes=True)


@admin_router.get("/overview", response_model=OverviewResponse)
def get_overview(db: Session = Depends(get_db_session), neo4j: Neo4jRepository = Depends(get_neo4j_repository)) -> OverviewResponse:
    prompt_count = db.query(PromptTemplate).count()
    cypher_count = db.query(CypherTemplate).count()
    profile_count = db.query(EntityProfile).count()
    workflow_session_count = db.query(WorkflowSession).count()
    workflow_run_count = db.query(WorkflowRun).count()
    db.execute(text("SELECT 1"))
    return OverviewResponse(
        postgres_ok=True,
        neo4j_ok=neo4j.health_check(),
        llm_configured=DeepSeekClient().health_check(),
        entity_profile_count=profile_count,
        workflow_session_count=workflow_session_count,
        workflow_run_count=workflow_run_count,
        prompt_template_count=prompt_count,
        cypher_template_count=cypher_count,
        graph_label_counts=neo4j.label_counts(),
        graph_metrics=neo4j.graph_metrics(),
    )


@admin_router.get("/chat-logs", response_model=list[ChatLogRead])
def list_chat_logs(db: Session = Depends(get_db_session)) -> list[ChatLogRead]:
    repository = PostgresRepository(db)
    return [ChatLogRead.model_validate(item, from_attributes=True) for item in repository.list_traces()]


@admin_router.get("/workflow-logs", response_model=list[WorkflowLogRead])
def list_workflow_logs(db: Session = Depends(get_db_session)) -> list[WorkflowLogRead]:
    repository = PostgresRepository(db)
    runs = repository.list_workflow_runs(limit=200)
    return [WorkflowLogRead.model_validate(item, from_attributes=True) for item in runs]


@admin_router.get("/prompts", response_model=list[PromptTemplateRead])
def list_prompts(db: Session = Depends(get_db_session)) -> list[PromptTemplateRead]:
    repository = PostgresRepository(db)
    return [PromptTemplateRead.model_validate(item, from_attributes=True) for item in repository.list_prompt_templates()]


@admin_router.put("/prompts/{prompt_id}", response_model=PromptTemplateRead)
def update_prompt(prompt_id: str, payload: PromptTemplateUpdate, db: Session = Depends(get_db_session)) -> PromptTemplateRead:
    repository = PostgresRepository(db)
    prompt = repository.get_prompt_template(prompt_id)
    if prompt is None:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    for field, value in payload.model_dump().items():
        setattr(prompt, field, value)
    db.commit()
    db.refresh(prompt)
    return PromptTemplateRead.model_validate(prompt, from_attributes=True)


@admin_router.get("/cypher-templates", response_model=list[CypherTemplateRead])
def list_cypher_templates(db: Session = Depends(get_db_session)) -> list[CypherTemplateRead]:
    repository = PostgresRepository(db)
    return [CypherTemplateRead.model_validate(item, from_attributes=True) for item in repository.list_cypher_templates()]


@admin_router.put("/cypher-templates/{template_id}", response_model=CypherTemplateRead)
def update_cypher_template(
    template_id: str,
    payload: CypherTemplateUpdate,
    db: Session = Depends(get_db_session),
) -> CypherTemplateRead:
    repository = PostgresRepository(db)
    template = repository.get_cypher_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Cypher template not found")
    for field, value in payload.model_dump().items():
        setattr(template, field, value)
    db.commit()
    db.refresh(template)
    return CypherTemplateRead.model_validate(template, from_attributes=True)


@rnd_router.post("/sessions", response_model=WorkflowSessionCreateResponse)
def create_workflow_session(db: Session = Depends(get_db_session)) -> WorkflowSessionCreateResponse:
    repository = PostgresRepository(db)
    session = repository.create_workflow_session()
    db.commit()
    return WorkflowSessionCreateResponse(id=session.id, session_id=session.id, title=session.title)


@rnd_router.get("/sessions", response_model=list[WorkflowSessionRead])
def list_workflow_sessions(db: Session = Depends(get_db_session)) -> list[WorkflowSessionRead]:
    repository = PostgresRepository(db)
    return [WorkflowSessionRead.model_validate(item, from_attributes=True) for item in repository.list_workflow_sessions()]


@rnd_router.post("/sessions/{session_id}/runs", response_model=WorkflowRunResponse)
def create_workflow_run(
    session_id: str,
    payload: WorkflowRunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    neo4j: Neo4jRepository = Depends(get_neo4j_repository),
) -> WorkflowRunResponse:
    orchestrator = get_rnd_workflow_orchestrator(db, neo4j)
    try:
        result = orchestrator.start_run(session_id, payload.question, reuse_last_brief=payload.reuse_last_brief)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    background_tasks.add_task(_run_workflow_in_background, result["run_id"])
    return WorkflowRunResponse(
        session_id=result["session_id"],
        run_id=result["run_id"],
        brief=result["brief"],
        final_report=result["final_report"],
        steps=[WorkflowStepRunRead.model_validate(step, from_attributes=True) for step in result["steps"]],
        summary_metrics=result["summary_metrics"],
        related_graph_snapshots=result["related_graph_snapshots"],
        status=result["status"],
    )


@rnd_router.get("/runs/{run_id}", response_model=WorkflowRunRead)
def get_workflow_run(run_id: str, db: Session = Depends(get_db_session)) -> WorkflowRunRead:
    repository = PostgresRepository(db)
    run = repository.get_workflow_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return _workflow_run_read(repository, run)


@rnd_router.get("/runs/{run_id}/steps/{step_id}", response_model=WorkflowStepDetailRead)
def get_workflow_step_detail(run_id: str, step_id: str, db: Session = Depends(get_db_session)) -> WorkflowStepDetailRead:
    repository = PostgresRepository(db)
    step = repository.get_workflow_step_run(step_id)
    if step is None or step.run_id != run_id:
        raise HTTPException(status_code=404, detail="Workflow step not found")
    snapshot = repository.get_graph_snapshot(step.graph_snapshot_id) if step.graph_snapshot_id else None
    return WorkflowStepDetailRead(
        **WorkflowStepRunRead.model_validate(step, from_attributes=True).model_dump(),
        graph_snapshot=(
            GraphSnapshotRead(
                id=snapshot.id,
                session_id=snapshot.session_id,
                question=snapshot.question,
                graph_data=GraphResponse(**snapshot.graph_data),
                created_at=snapshot.created_at,
            )
            if snapshot is not None
            else None
        ),
    )
