import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AppUser, AuthSession

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 210_000


def hash_password(password: str, salt: str | None = None) -> str:
    raw_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        raw_salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    ).hex()
    return f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}${raw_salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt, expected = password_hash.split("$", 3)
        if algorithm != PASSWORD_ALGORITHM:
            return False
        iterations = int(iterations_text)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return hmac.compare_digest(digest, expected)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def authenticate(self, username: str, password: str) -> AppUser | None:
        """用户名 + 密码认证；图形验证码由路由层在调用前校验（P2 实现）。"""
        user = self.session.scalar(select(AppUser).where(AppUser.username == username.strip()))
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def create_session(self, user: AppUser) -> tuple[str, AuthSession]:
        # 多会话：不再先删除旧会话，仅插入新会话；超出 auth_max_sessions_per_user 时挤掉最旧会话
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=settings.auth_session_ttl_hours)
        auth_session = AuthSession(
            user_id=user.id,
            token_hash=token_digest(token),
            expires_at=expires_at,
        )
        user.last_login_at = datetime.utcnow()
        self.session.add(auth_session)
        self.session.flush()
        self._trim_excess_sessions(user.id)
        return token, auth_session

    def _trim_excess_sessions(self, user_id: str) -> None:
        """会话数超限时撤销最旧的若干会话（按创建时间升序）。"""
        limit = settings.auth_max_sessions_per_user
        if limit <= 0:
            return
        active = list(
            self.session.scalars(
                select(AuthSession)
                .where(AuthSession.user_id == user_id)
                .where(AuthSession.revoked_at.is_(None))
                .order_by(AuthSession.created_at.asc())
            )
        )
        excess = active[: max(0, len(active) - limit)]
        if not excess:
            return
        now = datetime.utcnow()
        for item in excess:
            item.revoked_at = now
        self.session.flush()

    def register_user(
        self,
        username: str,
        password: str,
        email: str | None = None,
        display_name: str | None = None,
        role: str = "user",
        is_active: bool = False,
    ) -> tuple[AppUser, str]:
        """注册新用户：用户名唯一；邮箱非空时唯一（服务层保证）。

        公开注册：role='user'、is_active=False（待管理员审核，审核前不能登录）。
        管理员创建时可通过 role/is_active 覆盖（如 role='admin', is_active=True）。
        返回 (user, 已哈希密码)；校验失败抛 ValueError。
        """
        username = (username or "").strip()
        if not username:
            raise ValueError("用户名不能为空")
        if len(password) < settings.password_min_length:
            raise ValueError(f"密码长度不能少于 {settings.password_min_length} 位")
        if self.session.scalar(select(AppUser).where(AppUser.username == username)) is not None:
            raise ValueError("用户名已存在")
        normalized_email = (email or "").strip().lower() or None
        if normalized_email is not None:
            if self.session.scalar(select(AppUser).where(AppUser.email == normalized_email)) is not None:
                raise ValueError("邮箱已被使用")
        password_hash = hash_password(password)
        user = AppUser(
            username=username,
            display_name=display_name or username,
            email=normalized_email,
            password_hash=password_hash,
            role=role,
            is_active=is_active,
        )
        self.session.add(user)
        self.session.flush()
        return user, password_hash

    def change_password(self, user: AppUser, old_password: str, new_password: str) -> None:
        """修改密码：校验旧密码 → 哈希新密码 → 撤销该用户全部会话（含当前，需重新登录）。"""
        if not verify_password(old_password, user.password_hash):
            raise ValueError("原密码不正确")
        if len(new_password) < settings.password_min_length:
            raise ValueError(f"新密码长度不能少于 {settings.password_min_length} 位")
        user.password_hash = hash_password(new_password)
        self.session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user.id)
            .where(AuthSession.revoked_at.is_(None))
            .values(revoked_at=datetime.utcnow())
        )
        self.session.flush()

    def get_user_for_token(self, token: str) -> AppUser | None:
        auth_session = self.session.scalar(
            select(AuthSession)
            .where(AuthSession.token_hash == token_digest(token))
            .where(AuthSession.revoked_at.is_(None))
            .where(AuthSession.expires_at > datetime.utcnow())
        )
        if auth_session is None or auth_session.user is None or not auth_session.user.is_active:
            return None
        return auth_session.user

    def revoke_token(self, token: str) -> bool:
        auth_session = self.session.scalar(
            select(AuthSession)
            .where(AuthSession.token_hash == token_digest(token))
            .where(AuthSession.revoked_at.is_(None))
        )
        if auth_session is None:
            return False
        auth_session.revoked_at = datetime.utcnow()
        self.session.flush()
        return True
