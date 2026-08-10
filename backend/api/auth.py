"""
JWT Authentication
==================
Lightweight single-admin login for the IDS dashboard.

Scope decision (graduation project)
-----------------------------------
This module intentionally implements a *minimal* authentication layer:
a username/password login and registration that returns a short-lived JWT 
used by the React dashboard. It deliberately does NOT include password reset,
email verification, or step-up/OTP — those are out of scope for a 
single-operator IDS and would only add attack surface and maintenance cost.

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
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt # Sử dụng python-jose như trong code hiện tại
from pydantic import BaseModel, Field, field_validator
import re
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database.connection import get_db
from backend.database.repository import UserRepository # Import UserRepository
from backend.database.models import User
from backend.audit.logger import record_audit, get_client_ip

logger = logging.getLogger(__name__)

auth_router = APIRouter()

# tokenUrl is used by Swagger UI's "Authorize" button to know where to POST.
# auto_error=False so we can return a consistent 401 with a clear message.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# ── Lockout Helpers ──────────────────────────────────────────────────────────
# Sử dụng bộ nhớ trong thay cho Redis để tinh gọn hệ thống
_failed_attempts_storage: dict[str, list[datetime]] = {}
_lockouts_storage: dict[str, datetime] = {}

def _get_lockout_key(username: str) -> str:
    return f"auth:lockout:{username}"

def is_user_locked_out(username: str) -> bool:
    """Kiểm tra xem user có đang bị khóa không."""
    if not settings.enable_account_lockout:
        return False
    lock_time = _lockouts_storage.get(username)
    if lock_time and datetime.now(timezone.utc) < lock_time + timedelta(minutes=settings.auth_lockout_minutes):
        return True
    return False

def record_failed_attempt(username: str):
    """Tăng số lần đăng nhập sai và thực hiện khóa nếu vượt ngưỡng."""
    if not settings.enable_account_lockout:
        return
    attempts = _failed_attempts_storage.get(username, [])
    attempts.append(datetime.now(timezone.utc))
    _failed_attempts_storage[username] = attempts
    
    if len(attempts) >= settings.auth_max_failed_attempts:
        _lockouts_storage[username] = datetime.now(timezone.utc)
        logger.warning("Account %r locked (In-memory)", username)

def reset_failed_attempts(username: str):
    """Xóa lịch sử đăng nhập sai khi thành công."""
    _failed_attempts_storage.pop(username, None)
    _lockouts_storage.pop(username, None)


# ── Pydantic schemas ──────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    """JSON login body (the React dashboard posts JSON, not form-encoded)."""

    username: str = Field(..., min_length=1, max_length=50, examples=["admin"])
    password: str = Field(..., min_length=1, max_length=128, examples=["admin123"])


class UserInfo(BaseModel):
    id: Optional[int] = None
    username: str
    email: Optional[str] = None
    role: str
    created_at: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until expiry
    user: UserInfo


class PasswordChangeRequest(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if not re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$", v):
            raise ValueError(
                "Mật khẩu mới phải có ít nhất 8 ký tự, bao gồm chữ hoa, chữ thường và số."
            )
        return v


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(default="operator")


class UserUpdateRoleRequest(BaseModel):
    role: str = Field(..., min_length=3, max_length=20)


class UserResetPasswordRequest(BaseModel):
    new_password: Optional[str] = Field(None, min_length=8, max_length=128)


# ── Password + token helpers ────────────────────────────────────────────────
def create_access_token(subject: str, role: str) -> tuple[str, int]:
    """Create a JWT and return (token, expires_in_seconds)."""
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expires_in = int(expires_delta.total_seconds())
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": subject, "role": role, "exp": expire}
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return token, expires_in


def _extract_bearer_token(request: Request) -> Optional[str]:
    """Read JWT from HttpOnly cookie or Authorization header."""
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token.replace("Bearer ", "")
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None

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
    token_value = _extract_bearer_token(request)
    if not token_value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

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
@auth_router.post("/register", response_model=UserInfo, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreateRequest, db: Session = Depends(get_db)):
    """
    Endpoint đăng ký công khai. 
    Tạo người dùng mới với vai trò mặc định là 'operator'.
    """
    if UserRepository.get_by_username(db, user_data.username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tên đăng nhập đã tồn tại")
    
    if UserRepository.get_by_email(db, user_data.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email đã tồn tại")

    try:
        # Ép kiểu role về 'operator' để bảo mật, tránh việc người dùng tự set mình làm admin
        registration_data = user_data.model_dump()
        registration_data['role'] = 'operator' 

        new_user = UserRepository.create(db, registration_data)
        logger.info("Người dùng mới đã đăng ký: %r", new_user.username)
        return UserInfo(id=new_user.id, username=new_user.username, email=new_user.email, role=new_user.role)
    except Exception as e:
        logger.error(f"Lỗi không xác định khi đăng ký người dùng: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Đã xảy ra lỗi hệ thống khi đăng ký.")


@auth_router.post("/login", response_model=TokenResponse)
async def login(response: Response, request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
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
    token, expires_in = create_access_token(subject=user.username, role=user.role)

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
    record_audit(db, user.username, "login", client_ip=get_client_ip(request))

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserInfo(id=user.id, username=user.username, email=user.email, role=user.role),
    )


@auth_router.post("/logout")
async def logout(response: Response, request: Request, db: Session = Depends(get_db)):
    """
    Xóa HttpOnly cookie 'access_token' để đăng xuất người dùng.
    """
    username = "unknown"
    try:
        token = _extract_bearer_token(request)
        if token:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            username = payload.get("sub") or username
    except Exception:
        pass

    record_audit(db, username, "logout", client_ip=get_client_ip(request))
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
        id=current_user.id,
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
    record_audit(db, current_user.username, "change_password")
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
    return [UserInfo(id=u.id, username=u.username, email=u.email, role=u.role,
                     created_at=u.created_at.isoformat() if u.created_at else None) for u in users]


@auth_router.post("/users", response_model=UserInfo, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreateRequest,
    request: Request,
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

    new_user = UserRepository.create(db, user_data.model_dump())
    record_audit(
        db, 
        current_user.username, 
        "create_user", 
        resource_type="user", 
        resource_id=str(new_user.id),
        client_ip=get_client_ip(request)
    )
    return UserInfo(id=new_user.id, username=new_user.username, email=new_user.email, role=new_user.role)


@auth_router.put("/users/{user_id}/role", response_model=UserInfo)
async def update_user_role(
    user_id: int,
    request: Request,
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
    
    old_role = user.role
    UserRepository.update_role(db, user_id, role_data.role)
    db.refresh(user)

    # Ghi log chi tiết hành vi để phân tích UEBA
    record_audit(
        db, 
        current_user.username, 
        "update_user_role", 
        resource_type="user", 
        resource_id=str(user_id),
        details={"old_role": old_role, "new_role": role_data.role},
        client_ip=get_client_ip(request)
    )
    return UserInfo(id=user.id, username=user.username, email=user.email, role=user.role)

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
    request: Request,
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
    
    record_audit(
        db, 
        current_user.username, 
        "delete_user", 
        resource_type="user", 
        resource_id=str(user_id),
        client_ip=get_client_ip(request)
    )
    return


# ── API Key endpoint ──────────────────────────────────────────────────────────
@auth_router.get("/api-key")
async def get_api_key(
    current_user: User = Depends(get_current_user_from_cookie),
):
    """
    GET /api/auth/api-key — trả về X-API-Key cho admin/operator.
    Frontend gọi endpoint này sau khi login để tự động lưu key vào localStorage.
    Chỉ user đã xác thực JWT mới truy cập được.
    """
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập API key",
        )
    return {"api_key": settings.api_key}
