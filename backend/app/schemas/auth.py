from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas import ORMModel


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class UserOut(ORMModel):
    user_id: str
    username: str
    email: str
    employee_id: Optional[str] = None
    is_active: bool
    can_view_sensitive: bool = False
    roles: List[str] = []
    permissions: List[str] = []
    last_login_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
