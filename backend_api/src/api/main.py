from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.auth.deps import CurrentUser, get_current_user
from src.routers.profiles import router as profiles_router
from src.routers.repairs import router as repairs_router

openapi_tags = [
    {"name": "Health", "description": "Service health and readiness endpoints."},
    {"name": "Auth", "description": "Authentication/authorization helper endpoints."},
    {"name": "Profiles", "description": "User profile and role helper endpoints."},
    {"name": "Repairs", "description": "Repair CRUD, assignment, and status workflows."},
]

app = FastAPI(
    title="Mobile Repair Service Management API",
    description="Backend API for role-based mobile repair service management.",
    version="0.1.0",
    openapi_tags=openapi_tags,
)

# Keep permissive for now per requirements. We'll harden later.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
