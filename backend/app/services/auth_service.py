import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
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
        user = self.session.scalar(select(AppUser).where(AppUser.username == username.strip()))
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def create_session(self, user: AppUser) -> tuple[str, AuthSession]:
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
        return token, auth_session

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
