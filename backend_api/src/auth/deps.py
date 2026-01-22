from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Set

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from src.core.settings import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)


class Role(str, Enum):
    """Supported application roles."""

    customer = "customer"
    technician = "technician"
    admin = "admin"


class CurrentUser(BaseModel):
    """User context extracted from Supabase JWT / Auth API."""

    # PUBLIC_INTERFACE
    user_id: str = Field(..., description="Supabase Auth user id (JWT 'sub').")

    # PUBLIC_INTERFACE
    email: Optional[str] = Field(default=None, description="User email if available.")

    # PUBLIC_INTERFACE
    roles: List[str] = Field(
        default_factory=list,
        description="User roles derived from app_metadata.role/roles or custom claims.",
    )

    # PUBLIC_INTERFACE
    claims: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw decoded JWT claims or Supabase user object subset for debugging.",
    )

    # PUBLIC_INTERFACE
    def role_set(self) -> Set[str]:
        """Return roles as a set for quick membership checks."""
        return set(self.roles)


def _extract_roles_from_claims(claims: Dict[str, Any]) -> List[str]:
    """
    Extract roles from typical Supabase claim structures.

    We support:
    - claims['app_metadata']['role'] (string)
    - claims['app_metadata']['roles'] (list[str])
    - claims['role'] (string) for custom JWT claim
    - claims['roles'] (list[str]) for custom JWT claim
    """
    roles: List[str] = []

    app_md = claims.get("app_metadata") or {}
    if isinstance(app_md, dict):
        r = app_md.get("role")
        if isinstance(r, str) and r:
            roles.append(r)
        rs = app_md.get("roles")
        if isinstance(rs, list):
            roles.extend([x for x in rs if isinstance(x, str) and x])

    r2 = claims.get("role")
    if isinstance(r2, str) and r2:
        roles.append(r2)

    rs2 = claims.get("roles")
    if isinstance(rs2, list):
        roles.extend([x for x in rs2 if isinstance(x, str) and x])

    # De-dupe preserving order
    seen = set()
    out: List[str] = []
    for r in roles:
        if r not in seen:
            out.append(r)
            seen.add(r)
    return out


def _get_bearer_token(creds: Optional[HTTPAuthorizationCredentials]) -> Optional[str]:
    if not creds:
        return None
    if creds.scheme.lower() != "bearer":
        return None
    return creds.credentials


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(detail: str = "Not enough permissions") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _decode_and_verify_with_secret(token: str, jwt_secret: str) -> Dict[str, Any]:
    """
    Validate JWT with HS256 secret.

    Supabase typically signs access tokens with HS256 using the project's JWT secret.
    """
    try:
        claims = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            options={
                "verify_signature": True,
                "verify_aud": False,  # Supabase tokens may omit aud or set it variably
            },
        )
        if not isinstance(claims, dict):
            raise _unauthorized("Invalid token claims")
        return claims
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise _unauthorized("Invalid token") from exc


def _verify_via_supabase_auth_api(token: str, settings: Settings) -> Dict[str, Any]:
    """
    Validate token using Supabase Auth API as fallback.

    This requires SUPABASE_URL and SUPABASE_KEY to be set.
    Prefer using a service role key on the backend.

    Returns a dict that resembles the Supabase user response with enough fields
    for role extraction and user identification.
    """
    if not settings.supabase_url or not settings.supabase_key:
        raise _unauthorized("Server not configured for Supabase auth validation")

    # Import locally to keep module import cheap and make dependency explicit.
    from supabase import create_client  # type: ignore

    sb = create_client(settings.supabase_url, settings.supabase_key)

    try:
        res = sb.auth.get_user(token)
    except Exception as exc:  # Supabase client raises various http/client errors
        raise _unauthorized("Invalid token") from exc

    user = getattr(res, "user", None) if res is not None else None
    if user is None:
        # Some versions return dict-like
        if isinstance(res, dict):
            user = res.get("user")
    if not user:
        raise _unauthorized("Invalid token")

    # Normalize to dict
    if hasattr(user, "model_dump"):
        user_dict = user.model_dump()
    elif isinstance(user, dict):
        user_dict = user
    else:
        # last resort
        user_dict = dict(user)

    # Map into "claims-like" dict so downstream extraction is consistent.
    claims: Dict[str, Any] = {
        "sub": user_dict.get("id") or user_dict.get("sub"),
        "email": user_dict.get("email"),
        "app_metadata": user_dict.get("app_metadata") or {},
        "user_metadata": user_dict.get("user_metadata") or {},
        "raw_user": user_dict,
    }
    if not claims.get("sub"):
        raise _unauthorized("Invalid token")
    return claims


async def _build_current_user_from_token(token: str, settings: Settings) -> CurrentUser:
    # Prefer local verification if secret available
    claims: Dict[str, Any]
    if settings.supabase_jwt_secret:
        claims = _decode_and_verify_with_secret(token, settings.supabase_jwt_secret)
    else:
        claims = _verify_via_supabase_auth_api(token, settings)

    user_id = claims.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise _unauthorized("Invalid token subject")

    email = claims.get("email")
    if not isinstance(email, str):
        email = None

    roles = _extract_roles_from_claims(claims)

    return CurrentUser(
        user_id=user_id,
        email=email,
        roles=roles,
        claims=claims,
    )


# PUBLIC_INTERFACE
async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    """
    FastAPI dependency that validates `Authorization: Bearer <jwt>` and returns CurrentUser.

    Raises:
      - 401 if missing/invalid token
    """
    token = _get_bearer_token(creds)
    if not token:
        raise _unauthorized("Missing bearer token")
    return await _build_current_user_from_token(token, settings)


# PUBLIC_INTERFACE
def require_role(*required: Role):
    """
    Return a dependency that ensures the current user has at least one of the required roles.

    Usage:
        @app.get("/admin")
        async def admin_only(user: CurrentUser = Depends(require_role(Role.admin))):
            ...
    """

    async def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not required:
            return user
        required_set = {r.value for r in required}
        if user.role_set().intersection(required_set):
            return user
        raise _forbidden("Insufficient role")

    return _dep
