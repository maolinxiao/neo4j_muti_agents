from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    # 图形验证码（登录必填；服务层/路由校验）
    captcha_id: str = Field(min_length=1, max_length=64)
    captcha_text: str = Field(min_length=1, max_length=16)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    email: str | None = Field(default=None, max_length=128)
    captcha_id: str = Field(min_length=1, max_length=64)
    captcha_text: str = Field(min_length=1, max_length=16)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)
    # 图形验证码（修改密码必填；与登录一致）
    captcha_id: str = Field(min_length=1, max_length=64)
    captcha_text: str = Field(min_length=1, max_length=16)


class RegisterResponse(BaseModel):
    message: str
    user_id: str


class CaptchaResponse(BaseModel):
    captcha_id: str
    image_base64: str
    mime: str = "image/png"


class UserRead(BaseModel):
    id: str
    username: str
    display_name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    role: str
    is_active: bool
    last_login_at: datetime | None = None


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=128)
    email: str | None = Field(default=None, max_length=128)


class SessionRead(BaseModel):
    id: str
    is_current: bool = False
    created_at: datetime
    expires_at: datetime
    ip: str | None = None
    user_agent: str | None = None


class UserStats(BaseModel):
    chat_sessions: int = 0
    chat_messages: int = 0
    workflow_sessions: int = 0
    workflow_runs: int = 0
    constitution_assessments: int = 0


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserRead
