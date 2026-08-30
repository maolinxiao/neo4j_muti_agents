import secrets
import threading
import time

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text
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
    ResetPasswordRequest,
    UserAdminCreateResponse,
    UserAdminRead,
    UserCreateAdmin,
    UserPage,
    UserUpdateAdmin,
    WorkflowLogRead,
)
from app.schemas.auth import (
    CaptchaResponse,
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    UserRead,
)
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
from app.services.captcha_service import (
    CAPTCHA_ATTEMPTS_EXCEEDED,
    CAPTCHA_EXPIRED,
    CAPTCHA_INVALID,
    CAPTCHA_IP_MISMATCH,
    CAPTCHA_OK,
    CAPTCHA_TEXT_MISMATCH,
    CAPTCHA_USED,
    CaptchaStore,
)
from app.services.constitution_service import ConstitutionService
from app.services.qa_orchestrator import QAOrchestrator
from app.services.rnd_workflow_orchestrator import RnDWorkflowOrchestrator
from app.services.auth_service import AuthService, hash_password


health_router = APIRouter(tags=["health"])
auth_router = APIRouter(prefix="/auth", tags=["auth"])
chat_router = APIRouter(tags=["chat"])
entity_router = APIRouter(tags=["entity"])
constitution_router = APIRouter(prefix="/constitution", tags=["constitution"])
rnd_router = APIRouter(prefix="/rnd", tags=["rnd"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# 内存守卫（单 worker 部署；多 worker 需升级为 DB/Redis 存储）
# ---------------------------------------------------------------------------
captcha_store = CaptchaStore()


class _RegisterRateLimiter:
    """注册 per-IP 限频：窗口内最多 limit 次（默认 5 次/小时），窗口滑动。"""

    def __init__(self, limit: int = 5, window_seconds: int = 3600) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._records: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            timestamps = [ts for ts in self._records.get(key, []) if now - ts < self.window_seconds]
            self._records[key] = timestamps
            return len(timestamps) < self.limit

    def record(self, key: str) -> None:
        now = time.time()
        with self._lock:
            self._records.setdefault(key, []).append(now)


class _LoginFailGuard:
    """登录失败锁：按 (username, ip) 连续失败 max_failures 次后锁定 lock_minutes 分钟，成功后清零。"""

    def __init__(self, max_failures: int = 5, lock_minutes: int = 15) -> None:
        self.max_failures = max_failures
        self.lock_minutes = lock_minutes
        self._records: dict[tuple[str, str], tuple[int, float]] = {}  # (user, ip) -> (fail_count, locked_until_ts)
        self._lock = threading.Lock()

    def locked_seconds(self, username: str, ip: str) -> int:
        key = (username, ip)
        now = time.time()
        with self._lock:
            record = self._records.get(key)
            if record is None:
                return 0
            fail_count, locked_until = record
            if locked_until > 0:
                if now < locked_until:
                    return max(1, int(locked_until - now))
                self._records.pop(key, None)
            elif fail_count >= self.max_failures:
                # 兜底：计数达到上限却没有 locked_until（异常状态），立即锁定
                self._records[key] = (fail_count, now + self.lock_minutes * 60)
                return self.lock_minutes * 60
            return 0

    def record_failure(self, username: str, ip: str) -> None:
        key = (username, ip)
        now = time.time()
        with self._lock:
            fail_count, locked_until = self._records.get(key, (0, 0.0))
            if locked_until > 0:
                return  # 已锁定期间不再累计
            fail_count += 1
            if fail_count >= self.max_failures:
                locked_until = now + self.lock_minutes * 60
            self._records[key] = (fail_count, locked_until)

    def reset(self, username: str, ip: str) -> None:
        with self._lock:
            self._records.pop((username, ip), None)


register_rate_limiter = _RegisterRateLimiter(limit=5, window_seconds=3600)
login_fail_guard = _LoginFailGuard(
    max_failures=5,
    lock_minutes=max(1, settings.login_fail_lock_minutes),
)


def _client_ip(request: Request) -> str:
    """取客户端 IP：优先 X-Forwarded-For 首项，其次直连地址。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


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


def _captcha_error_detail(reason: str) -> str:
    """验证码校验失败原因 → 用户可读提示（用户据此可直接对症：刷新验证码或重新输入）。"""
    details = {
        CAPTCHA_INVALID: "验证码无效或已被作废，请刷新验证码后重试",
        CAPTCHA_EXPIRED: "验证码已过期，请刷新验证码后重试",
        CAPTCHA_USED: "验证码已被使用，请刷新验证码后重试",
        CAPTCHA_ATTEMPTS_EXCEEDED: "验证码错误次数过多，请刷新验证码后重试",
        CAPTCHA_IP_MISMATCH: "验证码与当前网络环境不一致，请刷新验证码后重试",
        CAPTCHA_TEXT_MISMATCH: "验证码输入错误，请重新输入（不区分大小写）",
    }
    return details.get(reason, "验证码错误或已过期")


@auth_router.get("/captcha", response_model=CaptchaResponse)
def get_captcha(request: Request) -> CaptchaResponse:
    if not settings.captcha_enabled:
        raise HTTPException(status_code=404, detail="验证码功能未启用")
    ip = _client_ip(request)
    captcha_id, image_base64 = captcha_store.issue(ip)
    return CaptchaResponse(captcha_id=captcha_id, image_base64=image_base64)


@auth_router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db_session)) -> RegisterResponse:
    ip = _client_ip(request)
    if settings.captcha_enabled:
        captcha_reason = captcha_store.verify(payload.captcha_id, payload.captcha_text, ip)
        if captcha_reason != CAPTCHA_OK:
            raise HTTPException(status_code=400, detail=_captcha_error_detail(captcha_reason))
    if not register_rate_limiter.allow(ip):
        raise HTTPException(status_code=429, detail="注册请求过于频繁，请稍后再试")
    service = AuthService(db)
    try:
        user, _ = service.register_user(
            username=payload.username,
            password=payload.password,
            email=payload.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        register_rate_limiter.record(ip)
    db.commit()
    return RegisterResponse(message="注册成功，请等待管理员审核", user_id=user.id)


@auth_router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    service = AuthService(db)
    try:
        service.change_password(current_user, payload.old_password, payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return {"message": "密码已修改，请重新登录"}


@auth_router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db_session)) -> LoginResponse:
    ip = _client_ip(request)
    if settings.captcha_enabled:
        captcha_reason = captcha_store.verify(payload.captcha_id, payload.captcha_text, ip)
        if captcha_reason != CAPTCHA_OK:
            raise HTTPException(status_code=400, detail=_captcha_error_detail(captcha_reason))
    locked = login_fail_guard.locked_seconds(payload.username, ip)
    if locked > 0:
        raise HTTPException(status_code=429, detail=f"登录失败次数过多，请 {login_fail_guard.lock_minutes} 分钟后再试")
    service = AuthService(db)
    user = service.authenticate(payload.username, payload.password)
    if user is None:
        existing = db.scalar(select(AppUser).where(AppUser.username == payload.username.strip()))
        if existing is not None and not existing.is_active:
            # 账号存在但未启用：不是凭据错误，不计入失败锁（避免审核通过后仍被临时锁定）
            raise HTTPException(status_code=401, detail="账号未启用，请等待管理员审核")
        login_fail_guard.record_failure(payload.username, ip)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    login_fail_guard.reset(payload.username, ip)
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
def create_chat_session(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ChatSessionCreateResponse:
    repository = PostgresRepository(db)
    session = repository.create_chat_session(current_user.id)
    db.commit()
    return ChatSessionCreateResponse(session_id=session.id, title=session.title)


@chat_router.get("/chat/sessions/{session_id}", response_model=ChatSessionRead)
def get_chat_session(
    session_id: str,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ChatSessionRead:
    repository = PostgresRepository(db)
    session = repository.get_chat_session(session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return ChatSessionRead.model_validate(session, from_attributes=True)


@chat_router.get("/chat/sessions", response_model=list[ChatSessionRead])
def list_chat_sessions(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[ChatSessionRead]:
    repository = PostgresRepository(db)
    return [
        ChatSessionRead.model_validate(item, from_attributes=True)
        for item in repository.list_chat_sessions(current_user.id)
    ]


@chat_router.post("/chat/sessions/{session_id}/messages", response_model=QAResponse)
def ask_question(
    session_id: str,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db_session),
    neo4j: Neo4jRepository = Depends(get_neo4j_repository),
    current_user: AppUser = Depends(get_current_user),
) -> QAResponse:
    session = PostgresRepository(db).get_chat_session(session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
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
    session = repo.get_chat_session(session_id, current_user.id)
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
def list_messages(
    session_id: str,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[ChatMessageRead]:
    repository = PostgresRepository(db)
    session = repository.get_chat_session(session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = repository.list_messages(session_id)
    return [ChatMessageRead.model_validate(item, from_attributes=True) for item in messages]


@chat_router.get("/chat/sessions/{session_id}/graph", response_model=GraphResponse)
def get_session_graph(
    session_id: str,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> GraphResponse:
    repository = PostgresRepository(db)
    session = repository.get_chat_session(session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    snapshot = repository.get_latest_graph_snapshot(session_id)
    if snapshot is None:
        return GraphResponse(nodes=[], edges=[], focus_paths=[], legend={}, metrics={})
    return GraphResponse(**snapshot.graph_data)


@chat_router.get("/chat/graph-snapshots/{snapshot_id}", response_model=GraphSnapshotRead)
def get_graph_snapshot(
    snapshot_id: str,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> GraphSnapshotRead:
    repository = PostgresRepository(db)
    snapshot = repository.get_graph_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Graph snapshot not found")
    # 归属校验：快照所属会话必须属于当前用户（他人数据 → 404）
    owner_session = repository.get_chat_session(snapshot.session_id, current_user.id)
    if owner_session is None:
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
    assessment = service.get_assessment(assessment_id, current_user.id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Constitution assessment not found")
    return ConstitutionAssessmentRead.model_validate(assessment, from_attributes=True)


# ---------------------------------------------------------------------------
# 管理后台用户管理（get_current_admin 守卫在 main.py 路由级启用）
# ---------------------------------------------------------------------------
@admin_router.get("/users", response_model=UserPage)
def list_admin_users(
    query: str | None = None,
    role: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db_session),
) -> UserPage:
    repository = PostgresRepository(db)
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    items, total = repository.list_users(query=query, role=role, page=page, page_size=page_size)
    return UserPage(
        items=[UserAdminRead.model_validate(item, from_attributes=True) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@admin_router.post("/users", response_model=UserAdminCreateResponse)
def create_admin_user(payload: UserCreateAdmin, db: Session = Depends(get_db_session)) -> UserAdminCreateResponse:
    if payload.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="role 仅支持 admin 或 user")
    generated = None
    if payload.password is None or payload.password == "":
        generated = secrets.token_urlsafe(12)
        password = generated
    else:
        password = payload.password
    service = AuthService(db)
    try:
        user, _ = service.register_user(
            username=payload.username,
            password=password,
            email=payload.email,
            display_name=payload.display_name,
            role=payload.role,
            is_active=True,  # 管理员创建即视为已启用
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(user)
    return UserAdminCreateResponse(
        **UserAdminRead.model_validate(user, from_attributes=True).model_dump(),
        generated_password=generated,
    )


@admin_router.put("/users/{user_id}", response_model=UserAdminRead)
def update_admin_user(
    user_id: str,
    payload: UserUpdateAdmin,
    db: Session = Depends(get_db_session),
) -> UserAdminRead:
    repository = PostgresRepository(db)
    user = repository.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    data = payload.model_dump(exclude_unset=True)
    if "role" in data and data["role"] not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="role 仅支持 admin 或 user")
    is_seed_admin = user.username == settings.default_admin_username
    # 保护 1：种子管理员不可降级为 user
    if is_seed_admin and "role" in data and data["role"] != "admin":
        raise HTTPException(status_code=400, detail="种子管理员不能被降级")
    # 保护 2：最后一名启用状态的管理员不可被停用或降级
    becomes_non_admin = "role" in data and data["role"] != "admin" and user.role == "admin"
    becomes_inactive = "is_active" in data and data["is_active"] is False and user.is_active and user.role == "admin"
    if (becomes_non_admin or becomes_inactive) and repository.count_active_admins(exclude_user_id=user_id) == 0:
        raise HTTPException(status_code=400, detail="系统至少需要保留一名启用状态的管理员")
    if "email" in data and data["email"]:
        normalized = data["email"].strip().lower()
        duplicate = db.scalar(
            select(AppUser).where(AppUser.email == normalized, AppUser.id != user_id)
        )
        if duplicate is not None:
            raise HTTPException(status_code=400, detail="邮箱已被使用")
        data["email"] = normalized
    for field in ("display_name", "email", "role", "is_active"):
        if field in data:
            setattr(user, field, data[field])
    db.commit()
    db.refresh(user)
    return UserAdminRead.model_validate(user, from_attributes=True)


@admin_router.put("/users/{user_id}/password")
def reset_admin_user_password(
    user_id: str,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db_session),
) -> dict:
    repository = PostgresRepository(db)
    user = repository.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if len(payload.new_password) < settings.password_min_length:
        raise HTTPException(status_code=400, detail=f"密码长度不能少于 {settings.password_min_length} 位")
    user.password_hash = hash_password(payload.new_password)
    repository.revoke_all_sessions(user_id)
    db.commit()
    return {"message": "密码已重置，该用户全部会话已失效"}


@admin_router.post("/users/{user_id}/force-logout")
def force_logout_user(user_id: str, db: Session = Depends(get_db_session)) -> dict:
    repository = PostgresRepository(db)
    user = repository.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    revoked = repository.revoke_all_sessions(user_id)
    db.commit()
    return {"message": "ok", "revoked_sessions": revoked}


@admin_router.delete("/users/{user_id}")
def delete_admin_user(user_id: str, db: Session = Depends(get_db_session)) -> dict:
    repository = PostgresRepository(db)
    user = repository.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.username == settings.default_admin_username:
        raise HTTPException(status_code=400, detail="种子管理员不能被删除")
    repository.delete_user_with_data(user_id)
    db.commit()
    return {"message": "ok"}


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
def create_workflow_session(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> WorkflowSessionCreateResponse:
    repository = PostgresRepository(db)
    session = repository.create_workflow_session(current_user.id)
    db.commit()
    return WorkflowSessionCreateResponse(id=session.id, session_id=session.id, title=session.title)


@rnd_router.get("/sessions", response_model=list[WorkflowSessionRead])
def list_workflow_sessions(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[WorkflowSessionRead]:
    repository = PostgresRepository(db)
    return [
        WorkflowSessionRead.model_validate(item, from_attributes=True)
        for item in repository.list_workflow_sessions(current_user.id)
    ]


@rnd_router.post("/sessions/{session_id}/runs", response_model=WorkflowRunResponse)
def create_workflow_run(
    session_id: str,
    payload: WorkflowRunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    neo4j: Neo4jRepository = Depends(get_neo4j_repository),
    current_user: AppUser = Depends(get_current_user),
) -> WorkflowRunResponse:
    session = PostgresRepository(db).get_workflow_session(session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=404, detail="Workflow session not found")
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
def get_workflow_run(
    run_id: str,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> WorkflowRunRead:
    repository = PostgresRepository(db)
    run = repository.get_workflow_run(run_id, current_user.id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return _workflow_run_read(repository, run)


@rnd_router.get("/runs/{run_id}/steps/{step_id}", response_model=WorkflowStepDetailRead)
def get_workflow_step_detail(
    run_id: str,
    step_id: str,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> WorkflowStepDetailRead:
    repository = PostgresRepository(db)
    step = repository.get_workflow_step_run(step_id, current_user.id)
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
