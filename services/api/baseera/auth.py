from __future__ import annotations

# FastAPI dependency declarations intentionally call Depends in signatures.
# ruff: noqa: B008
import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .errors import AppError
from .models import AuthSession, Membership, Organization, User, utcnow

SESSION_COOKIE = "baseera_session"
CSRF_HEADER = "X-CSRF-Token"
PBKDF2_ITERATIONS = 310_000


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    encoded_salt = base64.urlsafe_b64encode(salt).decode()
    encoded_derived = base64.urlsafe_b64encode(derived).decode()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${encoded_salt}${encoded_derived}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, expected_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode())
        expected = base64.urlsafe_b64decode(expected_text.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations_text))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def get_db(request: Request):
    with request.app.state.session_factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


@dataclass(frozen=True, slots=True)
class AuthContext:
    user: User
    membership: Membership
    organization: Organization
    auth_session: AuthSession

    @property
    def tenant_id(self) -> str:
        return self.organization.id

    @property
    def department_ids(self) -> set[str]:
        return set(self.membership.department_ids or [])

    @property
    def scoped_departments(self) -> set[str] | None:
        return self.department_ids if self.membership.role == "department_manager" else None

    def can(self, permission: str) -> bool:
        return permission in set(self.membership.permissions or []) or "*" in set(
            self.membership.permissions or []
        )


def create_session(
    db: Session, membership: Membership, session_hours: int
) -> tuple[str, str, AuthSession]:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    record = AuthSession(
        token_hash=_digest(token),
        membership_id=membership.id,
        csrf_hash=_digest(csrf),
        expires_at=utcnow() + timedelta(hours=session_hours),
    )
    db.add(record)
    db.commit()
    return token, csrf, record


def authenticate(db: Session, email: str, password: str) -> tuple[User, Membership] | None:
    user = db.scalar(select(User).where(User.email == email.lower().strip(), User.active.is_(True)))
    if user is None or not verify_password(password, user.password_hash):
        return None
    membership = db.scalar(
        select(Membership).where(Membership.user_id == user.id, Membership.active.is_(True))
    )
    if membership is None:
        return None
    return user, membership


def get_auth_context(request: Request, db: Session = Depends(get_db)) -> AuthContext:
    raw_token = request.cookies.get(SESSION_COOKIE)
    if not raw_token:
        raise AppError(401, "authentication_required", "Authentication is required")
    auth_session = db.get(AuthSession, _digest(raw_token))
    now = utcnow()
    if (
        auth_session is None
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= now
    ):
        raise AppError(401, "session_expired", "The session is invalid or expired")
    membership = db.get(Membership, auth_session.membership_id)
    if membership is None or not membership.active:
        raise AppError(403, "permission_revoked", "Access has been revoked")
    user = db.get(User, membership.user_id)
    organization = db.get(Organization, membership.organization_id)
    if user is None or not user.active or organization is None:
        raise AppError(401, "session_invalid", "The session is no longer valid")
    context = AuthContext(user, membership, organization, auth_session)
    db.info["auth_context"] = context
    if not context.can("analytics:read"):
        raise AppError(403, "permission_denied", "Analytics access is not granted")
    return context


def require_csrf(request: Request, context: AuthContext = Depends(get_auth_context)) -> AuthContext:
    supplied = request.headers.get(CSRF_HEADER, "")
    if not supplied or not hmac.compare_digest(_digest(supplied), context.auth_session.csrf_hash):
        raise AppError(403, "csrf_failed", "A valid CSRF token is required")
    if request.url.path != "/api/v1/auth/logout" and not context.can("artifacts:write"):
        raise AppError(403, "permission_denied", "Artifact write access is not granted")
    return context


def rotate_csrf(db: Session, context: AuthContext) -> str:
    token = secrets.token_urlsafe(32)
    context.auth_session.csrf_hash = _digest(token)
    db.commit()
    return token


def require_roles(*roles: str):
    allowed = set(roles)

    def dependency(context: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if context.membership.role not in allowed:
            raise AppError(403, "permission_denied", "Your role cannot perform this operation")
        return context

    return dependency
