import os
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.auth.deps import CurrentUser, get_current_user
from src.core.settings import get_settings
from src.routers.profiles import router as profiles_router
from src.routers.repairs import router as repairs_router

# Best-effort local .env loading. Some deployment environments do not automatically
# inject the container's `.env` file into the process environment.
try:
    from dotenv import load_dotenv  # type: ignore

    _ENV_PATH = Path(__file__).resolve().parents[2] / ".env"  # backend_api/.env
    load_dotenv(_ENV_PATH, override=False)
except Exception:
    # If python-dotenv is unavailable or .env is absent, we rely on the real
    # environment. Validation below will still give clear errors.
    pass


def _validate_required_env() -> None:
    """
    Validate critical environment variables early so startup failures are explicit.

    Rules:
    - If SUPABASE_JWT_SECRET is set, local JWT verification is possible.
      (SUPABASE_URL is still recommended to derive issuer unless SUPABASE_JWT_ISSUER is set.)
    - If SUPABASE_JWT_SECRET is not set, we must validate tokens via Supabase Auth API,
      which requires SUPABASE_URL and SUPABASE_KEY.
    """
    settings = get_settings()

    if settings.supabase_jwt_secret:
        # Local verification enabled; allow missing URL (issuer checks can be disabled),
        # but warn via error only if issuer checks are implicitly expected (not enforced here).
        return

    missing = []
    if not settings.supabase_url:
        missing.append("SUPABASE_URL")
    if not settings.supabase_key:
        missing.append("SUPABASE_KEY")

    if missing:
        raise RuntimeError(
            "Backend configuration error: missing required environment variables "
            f"{', '.join(missing)}. Provide SUPABASE_URL and SUPABASE_KEY, "
            "or set SUPABASE_JWT_SECRET to enable local JWT verification."
        )

openapi_tags = [
    {"name": "Health", "description": "Service health and readiness endpoints."},
    {"name": "Auth", "description": "Authentication/authorization helper endpoints."},
    {"name": "Profiles", "description": "User profile and role helper endpoints."},
    {"name": "Repairs", "description": "Repair CRUD, assignment, and status workflows."},
]

# Validate settings on import so misconfiguration is obvious in logs and the
# container fails fast (instead of failing later on first authenticated request).
_validate_required_env()

app = FastAPI(
    title="Mobile Repair Service Management API",
    description="Backend API for role-based mobile repair service management.",
    version="0.1.0",
    openapi_tags=openapi_tags,
)

# CORS: allow only the configured frontend origin.
# IMPORTANT: Set FRONTEND_ORIGIN in backend env for deployed environments.
#
# This repo's `.env` also commonly uses:
# - FRONTEND_URL
# - ALLOWED_ORIGINS (comma-separated)
# We support these as fallbacks to reduce startup friction.
frontend_origin = (
    os.getenv("FRONTEND_ORIGIN")
    or os.getenv("FRONTEND_URL")
    or "http://localhost:3000"
).strip() or "http://localhost:3000"

allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "").strip()
allowed_origins = (
    [x.strip() for x in allowed_origins_raw.split(",") if x.strip()]
    if allowed_origins_raw
    else [frontend_origin]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Domain routers
app.include_router(profiles_router)
app.include_router(repairs_router)


@app.get("/", tags=["Health"], summary="Health check")
# PUBLIC_INTERFACE
def health_check():
    """Health check endpoint used for uptime and readiness probes."""
    return {"message": "Healthy"}


@app.get(
    "/auth/me",
    tags=["Auth"],
    summary="Return current authenticated user",
    description="Protected endpoint. Requires `Authorization: Bearer <supabase-access-token>`.",
)
# PUBLIC_INTERFACE
async def auth_me(user: CurrentUser = Depends(get_current_user)):
    """
    Return the resolved CurrentUser payload from the provided Supabase Bearer JWT.

    This is a simple wiring verification endpoint for frontend integration.
    """
    return user.model_dump()
