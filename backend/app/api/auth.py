from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.common import client_ip, user_out
from app.config import get_settings
from app.dependencies import get_current_user, get_db
from app.models.user import UserAccount
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.security.auth import create_access_token
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(token: str, user: UserAccount) -> TokenResponse:
    return TokenResponse(
        access_token=token,
        expires_in=get_settings().access_token_expire_minutes * 60,
        user=user_out(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    token, user = auth_service.login(db, body.username, body.password, client_ip(request))
    return _token_response(token, user)


@router.post("/token", response_model=TokenResponse, include_in_schema=False)
def token_form(
    request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> TokenResponse:
    """OAuth2 password-flow endpoint so the Swagger UI 'Authorize' button works."""
    token, user = auth_service.login(db, form.username, form.password, client_ip(request))
    return _token_response(token, user)


@router.post("/logout", status_code=204)
def logout(
    request: Request, user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    auth_service.logout(db, user, client_ip(request))


@router.get("/me", response_model=UserOut)
def me(user: UserAccount = Depends(get_current_user)) -> UserOut:
    return user_out(user)
