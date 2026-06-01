"""
JWT Authentication
==================
Lightweight single-admin login for the IDS dashboard.

Scope decision (graduation project)
-----------------------------------
This module intentionally implements a *minimal* authentication layer:
a username/password login that returns a short-lived JWT used by the React
dashboard. It deliberately does NOT include user registration, password reset,
email verification, or step-up/OTP — those are out of scope for a single-operator
IDS and would only add attack surface and maintenance cost.

The existing ``X-API-Key`` mechanism (see ``dependencies.py``) remains the auth
method for programmatic/API access and is unaffected by this module.

Usage
-----
    from backend.api.auth import get_current_user

    @router.get("/protected")
    async def protected(user = Depends(get_current_user)):
        return {"hello": user.username}

The default seeded credentials (created by ``init_db.seed_data``) are
``admin`` / ``admin123`` — change the password hash in the DB for production.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database.connection import get_db
from backend.database.models import User

logger = logging.getLogger(__name__)

auth_router = APIRouter()

# tokenUrl is used by Swagger UI's "Authorize" button to know where to POST.
# auto_error=False so we can return a consistent 401 with a clear message.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ── Pydantic schemas ──────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    """JSON login body (the React dashboard posts JSON, not form-encoded)."""

    username: str = Field(..., min_length=1, max_length=50, examples=["admin"])
    password: str = Field(..., min_length=1, max_length=128, examples=["admin123"])


class UserInfo(BaseModel):
    username: str
    email: Optional[str] = None
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until expiry
    user: UserInfo


# ── Password + token helpers ────────────────────────────────────────────────
def verify_password(plain_password: str, password_hash: str) -> bool:
    """Constant-time bcrypt verification. Returns False on any malformed hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:72],  # bcrypt only uses first 72 bytes
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def hash_password(plain_password: str) -> str:
    """Hash a password with bcrypt (matches init_db seeding)."""
    return bcrypt.hashpw(
        plain_password.encode("utf-8")[:72], bcrypt.gensalt()
    ).decode("utf-8")


def create_access_token(subject: str, role: str) -> tuple[str, int]:
    """
    Build a signed JWT for ``subject`` (the username).

    Returns:
        (token, expires_in_seconds)
    """
    settings = get_settings()
    expire_minutes = settings.access_token_expire_minutes
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expire_minutes)
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": expire,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return token, expire_minutes * 60


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Return the User on valid credentials, else None."""
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        # Run a dummy hash check to keep response time ~constant (avoid user enumeration)
        verify_password(password, "$2b$12$" + "x" * 53)
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


# ── Dependency: extract + validate the current user from a Bearer token ─────
_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency — validate the JWT and return the matching User.

    Raises 401 if the token is missing, invalid, expired, or the user no
    longer exists.
    """
    if not token:
        raise _CREDENTIALS_EXC

    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise _CREDENTIALS_EXC
    except JWTError:
        raise _CREDENTIALS_EXC

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise _CREDENTIALS_EXC
    return user


# ── Routes ───────────────────────────────────────────────────────────────────
@auth_router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with username + password and receive a JWT.

    The token must be sent as ``Authorization: Bearer <token>`` on subsequent
    requests to protected endpoints.
    """
    user = authenticate_user(db, payload.username, payload.password)
    if user is None:
        logger.warning("Failed login attempt for username=%r", payload.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token, expires_in = create_access_token(subject=user.username, role=user.role)
    logger.info("User %r logged in successfully", user.username)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserInfo(username=user.username, email=user.email, role=user.role),
    )


@auth_router.get("/me", response_model=UserInfo)
async def read_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile (validates the token)."""
    return UserInfo(
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
    )
