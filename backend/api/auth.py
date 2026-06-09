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
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import secrets # Import secrets for CSRF token generation
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt # Sử dụng python-jose như trong code hiện tại
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database.connection import get_db, get_redis_client
from backend.database.repository import UserRepository # Import UserRepository
from backend.database.models import User

logger = logging.getLogger(__name__)

auth_router = APIRouter()

# tokenUrl is used by Swagger UI's "Authorize" button to know where to POST.
# auto_error=False so we can return a consistent 401 with a clear message.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# ── Lockout Helpers ──────────────────────────────────────────────────────────
def _get_lockout_key(username: str) -> str:
    return f"auth:lockout:{username}"

def _get_failed_attempts_key(username: str) -> str:
    return f"auth:failed_attempts:{username}"

def is_user_locked_out(username: str) -> bool:
    """Kiểm tra xem user có đang bị khóa không."""
    if not settings.enable_account_lockout:
        return False
    try:
        r = get_redis_client()
        return r.exists(_get_lockout_key(username))
    except Exception:
        return False

def record_failed_attempt(username: str):
    """Tăng số lần đăng nhập sai và thực hiện khóa nếu vượt ngưỡng."""
    if not settings.enable_account_lockout:
        return
    try:
        r = get_redis_client()
        key = _get_failed_attempts_key(username)
        attempts = r.incr(key)
        r.expire(key, 1800) # Reset sau 30 phút nếu không thử tiếp

        if attempts >= settings.auth_max_failed_attempts:
            lockout_key = _get_lockout_key(username)
            r.setex(lockout_key, settings.auth_lockout_minutes * 60, "locked")
            logger.warning("Account %r locked due to multiple failed attempts", username)
    except Exception as e:
        logger.error("Error recording failed login for %r: %e", username, e)

def reset_failed_attempts(username: str):
    """Xóa lịch sử đăng nhập sai khi thành công."""
    try:
        r = get_redis_client()
        r.delete(_get_failed_attempts_key(username))
    except Exception:
        pass


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


def hash_password(plain_password: str) -> str: # Đã có trong UserRepository, nhưng giữ lại để nhất quán
    """Hash a password with bcrypt (matches init_db seeding)."""
    pwd = plain_password.encode('utf-8')[:72]
    return bcrypt.hashpw(pwd, bcrypt.gensalt()).decode('utf-8')


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Return the User on valid credentials, else None."""
    user = UserRepository.get_by_username(db, username)
    if user is None:
        verify_password(password, "$2b$12$" + "x" * 53)
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


# ── Dependencies ──────────────────────────────────────────────────────────
async def get_current_user_from_cookie(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency — validate the JWT from an HttpOnly cookie and return the matching User.

    Raises 401 if the token is missing, invalid, expired, or the user no
    longer exists.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    # Remove "Bearer " prefix if present
    token_value = token.replace("Bearer ", "")

    try:
        payload = jwt.decode(token_value, settings.secret_key, algorithms=[settings.algorithm])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

async def verify_csrf_token(request: Request):
    csrf_cookie = request.cookies.get("csrf_token")
    csrf_header = request.headers.get("X-CSRF-Token")

    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token mismatch or missing"
        )
    return True


# ── Routes ───────────────────────────────────────────────────────────────────
@auth_router.post("/login") # Removed response_model=TokenResponse
async def login(response: Response, payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with username + password and receive a JWT.

    The token must be sent as ``Authorization: Bearer <token>`` on subsequent
    requests to protected endpoints.
    """
    # 1. Kiểm tra lockout trước
    if is_user_locked_out(payload.username):
        logger.warning("Blocked login attempt for locked account: %r", payload.username)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tài khoản bị tạm khóa do nhập sai nhiều lần. Vui lòng thử lại sau {settings.auth_lockout_minutes} phút."
        )

    user = authenticate_user(db, payload.username, payload.password)
    if user is None:
        logger.warning("Failed login attempt for username=%r", payload.username)
        # 2. Ghi nhận lần thử thất bại
        record_failed_attempt(payload.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Reset lịch sử khi thành công
    reset_failed_attempts(user.username)
    
    # Generate JWT token
    token, expires_in = UserRepository.create_access_token(subject=user.username, role=user.role)

    # Generate CSRF token
    csrf_token = secrets.token_urlsafe(32) # Generate a random string

    # Set HttpOnly access_token cookie
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        max_age=expires_in,
        samesite="lax", # Or "strict" for higher security, but might break some legitimate cross-site navigation
        secure=settings.environment == "production", # Use True in production with HTTPS
        path="/"
    )

    # Set JS-readable CSRF token cookie
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        max_age=expires_in,
        samesite="lax",
        secure=settings.environment == "production",
        path="/"
    )

    logger.info("User %r logged in successfully", user.username)


@auth_router.post("/logout")
async def logout(response: Response):
    """
    Xóa HttpOnly cookie 'access_token' để đăng xuất người dùng.
    """
    response.delete_cookie(
        key="access_token",
        httponly=True,
        samesite="lax",
        secure=settings.environment == "production",
        path="/"
    )
    response.delete_cookie(
        key="csrf_token",
        httponly=False,
        samesite="lax",
        secure=settings.environment == "production",
        path="/"
    )
    return {"message": "Logged out successfully"}


@auth_router.get("/me", response_model=UserInfo)
async def read_me(current_user: User = Depends(get_current_user_from_cookie)):
    """Return the currently authenticated user's profile (validates the token)."""
    return UserInfo(
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
    )


@auth_router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user_from_cookie),
    _csrf_verified: bool = Depends(verify_csrf_token),
    db: Session = Depends(get_db),
):
    """Allow a logged-in user to change their password."""
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mật khẩu cũ không chính xác")

    if not UserRepository.update_password(db, current_user.id, payload.new_password):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Lỗi hệ thống khi cập nhật mật khẩu")

    logger.info("User %r changed password successfully", current_user.username)
    return {"success": True, "message": "Đổi mật khẩu thành công"}


@auth_router.get("/users", response_model=List[UserInfo])
async def list_users(
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """List all users (Admin only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập")
    
    users = UserRepository.get_all(db)
    return [UserInfo(username=u.username, email=u.email, role=u.role) for u in users]


@auth_router.post("/users", response_model=UserInfo, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreateRequest,
    current_user: User = Depends(get_current_user_from_cookie),
    _csrf_verified: bool = Depends(verify_csrf_token), # Add CSRF protection
    db: Session = Depends(get_db)
):
    """Create a new user (Admin only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền tạo người dùng")
    
    if UserRepository.get_by_username(db, user_data.username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tên đăng nhập đã tồn tại")
    
    if UserRepository.get_by_email(db, user_data.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email đã tồn tại")

    new_user = UserRepository.create(db, user_data.dict())
    return UserInfo(username=new_user.username, email=new_user.email, role=new_user.role)


@auth_router.put("/users/{user_id}/role", response_model=UserInfo)
async def update_user_role(
    user_id: int,
    role_data: UserUpdateRoleRequest,
    current_user: User = Depends(get_current_user_from_cookie),
    _csrf_verified: bool = Depends(verify_csrf_token), # Add CSRF protection
    db: Session = Depends(get_db)
):
    """Update a user's role (Admin only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền cập nhật vai trò")
    
    if user_id == current_user.id and role_data.role != "admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không thể hạ cấp vai trò của chính mình")

    user = UserRepository.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Người dùng không tồn tại")
    
    UserRepository.update_role(db, user_id, role_data.role)
    db.refresh(user)
    return UserInfo(username=user.username, email=user.email, role=user.role)

@auth_router.post("/users/{user_id}/reset-password", response_model=dict)
async def reset_user_password(
    user_id: int,
    payload: UserResetPasswordRequest,
    current_user: User = Depends(get_current_user_from_cookie),
    _csrf_verified: bool = Depends(verify_csrf_token), # Add CSRF protection
    db: Session = Depends(get_db)
):
    """Admin có thể đặt lại mật khẩu cho người dùng khác."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền đặt lại mật khẩu")
    
    user_to_reset = UserRepository.get_by_id(db, user_id)
    if not user_to_reset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Người dùng không tồn tại")
    
    if payload.new_password:
        new_plain_password = payload.new_password
    else:
        new_plain_password = str(uuid.uuid4())[:12] # Tạo mật khẩu ngẫu nhiên 12 ký tự

    new_password_hash = hash_password(new_plain_password)
    
    if not UserRepository.reset_password(db, user_id, new_password_hash):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Lỗi hệ thống khi đặt lại mật khẩu")
    
    return {"message": "Mật khẩu đã được đặt lại thành công", "new_password": new_plain_password}

@auth_router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    _csrf_verified: bool = Depends(verify_csrf_token), # Add CSRF protection
    db: Session = Depends(get_db)
):
    """Delete a user (Admin only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xóa người dùng")
    
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không thể xóa tài khoản của chính mình")

    if not UserRepository.delete(db, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Người dùng không tồn tại")
    
    return
