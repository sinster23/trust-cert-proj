"""M1 authentication endpoints.

Include in the shared application (app/main.py) with:

    from app.auth.router import router as auth_router
    app.include_router(auth_router)

No business logic lives here; see service.py.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ..database.models.user import User
from .dependencies import get_auth_service, get_current_user
from .schemas import ErrorResponse, GoogleLoginRequest, TokenResponse, UserPublic
from .security import AuthConfigurationError, InvalidGoogleTokenError
from .service import AccountUnavailableError, AuthService, ServiceUnavailableError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/google",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def login_with_google(
    body: GoogleLoginRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Exchange a Google ID token for a Credence JWT."""
    try:
        result = await service.authenticate_with_google(body.id_token)
    except InvalidGoogleTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except AccountUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not available",
        )
    except (ServiceUnavailableError, AuthConfigurationError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        )

    return TokenResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        user=UserPublic.from_user(result.user),
    )


@router.get(
    "/me",
    response_model=UserPublic,
    responses={401: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def read_current_user(
    user: Annotated[User, Depends(get_current_user)],
) -> UserPublic:
    """Return the currently authenticated Credence user."""
    return UserPublic.from_user(user)