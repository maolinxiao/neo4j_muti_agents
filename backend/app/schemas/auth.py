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
    role: str
    is_active: bool
    last_login_at: datetime | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserRead
