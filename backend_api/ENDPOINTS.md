# Backend API Endpoints

## Overview

The backend is a FastAPI service that exposes repair-management and profile endpoints. Authentication is handled via Supabase JWTs passed as a Bearer token. Authorization is enforced using role guards for `customer`, `technician`, and `admin`.

FastAPI also serves interactive API docs at `/docs` (Swagger UI) and `/redoc` (ReDoc) when the server is running.

## OpenAPI

A static OpenAPI JSON snapshot is committed here:

`backend_api/interfaces/openapi.json`

This file should represent the current state of the code in `backend_api/src/api/main.py` and the routers in `backend_api/src/routers/`.

## Authentication

### Required header

Protected endpoints require:

`Authorization: Bearer <SUPABASE_ACCESS_TOKEN>`

The backend accepts Supabase access tokens and validates them in one of two ways:

1. If `SUPABASE_JWT_SECRET` is set, the backend validates the token locally with HS256 and verifies time-based claims. It derives the issuer from `SUPABASE_URL` unless `SUPABASE_JWT_ISSUER` is set.
2. Otherwise, it falls back to Supabase Auth API token validation using `SUPABASE_URL` and `SUPABASE_KEY` by calling `auth.get_user(token)` server-side.

### Role extraction

Roles are derived from common Supabase/custom claim structures, including:

- `app_metadata.role` (string)
- `app_metadata.roles` (list of strings)
- `role` (string)
- `roles` (list of strings)

### Role guards used by this API

The following guards exist and are used throughout the routers:

- `require_role(Role.customer, Role.admin)` ensures at least one required role is present.
- `get_current_user` ensures the request is authenticated but does not enforce a specific role. Routes may implement their own “scope” rules based on `CurrentUser.roles`.

## Environment variables

### Backend (`backend_api`)

The backend reads the following environment variables (see `src/core/settings.py` and `src/api/main.py`):

- `FRONTEND_ORIGIN`: The only origin allowed by CORS. Defaults to `http://localhost:3000` if not set.
- `SUPABASE_URL`: Supabase project URL. Required if using the Supabase Auth API fallback validation, and also used to derive expected JWT issuer if `SUPABASE_JWT_ISSUER` is unset.
- `SUPABASE_KEY`: Supabase API key used server-side when validating via Supabase Auth API. A service role key is recommended for backend usage.
- `SUPABASE_JWT_SECRET`: Optional but recommended. If set, the backend verifies Bearer JWTs locally (HS256) and does not need to call Supabase Auth API.
- `SUPABASE_JWT_ISSUER`: Optional override for issuer verification.
- `SUPABASE_JWT_AUDIENCE`: Optional audience verification. If unset, audience verification is disabled for compatibility.
- `BACKEND_BASE_URL`: Optional externally reachable base URL (used for docs/links if needed).

Note: The codebase uses `SUPABASE_KEY` as the backend key variable name. If you have a separate `SUPABASE_SERVICE_ROLE_KEY`, map it to `SUPABASE_KEY` at runtime for the backend container.

### Frontend (`frontend_react`)

The frontend uses:

- `SUPABASE_URL`
- `SUPABASE_KEY` (frontend anon key)
- `REACT_APP_BACKEND_BASE_URL` (preferred for CRA builds)
- `BACKEND_BASE_URL` (supported fallback in code)
  
The frontend code explicitly expects `SUPABASE_URL` and `SUPABASE_KEY` at runtime (see `frontend_react/src/lib/supabaseClient.js`).

## Routes

## Health

### GET `/`

Returns a health response.

Response body:

```json
{ "message": "Healthy" }
```

Example:

```bash
curl -sS "$BACKEND_BASE_URL/"
```

## Auth

### GET `/auth/me` (protected)

Returns the server’s resolved `CurrentUser` context from the Bearer token. This is useful for debugging token and role wiring.

Auth: Bearer token required.

Response model: `CurrentUser`

Example:

```bash
curl -sS "$BACKEND_BASE_URL/auth/me" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN"
```

## Profiles

### GET `/profiles/me` (protected)

Returns the current user’s profile row.

Auth: Bearer token required.

Response model: `ProfileRead`

Example:

```bash
curl -sS "$BACKEND_BASE_URL/profiles/me" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN"
```

### PUT `/profiles/me` (protected)

Creates or updates the current user’s profile row.

Auth: Bearer token required.

Request model: `ProfileUpsert`

Response model: `ProfileRead`

Example:

```bash
curl -sS -X PUT "$BACKEND_BASE_URL/profiles/me" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "customer",
    "full_name": "Ada Lovelace"
  }'
```

### GET `/profiles/{user_id}` (admin only)

Fetch an arbitrary user’s profile by `user_id`.

Auth: Bearer token required.
Role: `admin`

Response model: `ProfileRead`

Example:

```bash
curl -sS "$BACKEND_BASE_URL/profiles/$USER_ID" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN"
```

## Repairs

### POST `/repairs` (customer or admin)

Create a new repair request.

Auth: Bearer token required.
Role: `customer` or `admin`

Request model: `RepairCreate`

Response model: `RepairRead`

Example:

```bash
curl -sS -X POST "$BACKEND_BASE_URL/repairs" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "device_type": "iPhone 13",
    "issue_description": "Screen cracked",
    "preferred_contact": "Text message preferred"
  }'
```

### GET `/repairs` (role-scoped)

List repairs visible to the caller.

Auth: Bearer token required.

Role behavior:

- `admin`: lists all repairs
- `technician`: lists repairs assigned to the current technician
- otherwise: defaults to customer scoping (lists the caller’s repairs)

Response model: `RepairsListResponse` (shape: `{ "items": [...] }`)

Example:

```bash
curl -sS "$BACKEND_BASE_URL/repairs" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN"
```

### GET `/repairs/{repair_id}` (role-scoped)

Returns repair detail, including status history, with role-based visibility checks:

- `admin`: can view any repair
- `customer`: can view repairs where `customer_user_id == current_user.user_id`
- `technician`: can view repairs where `technician_user_id == current_user.user_id`

Auth: Bearer token required.

Response model: `RepairDetail`

Example:

```bash
curl -sS "$BACKEND_BASE_URL/repairs/$REPAIR_ID" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN"
```

### PATCH `/repairs/{repair_id}` (customer owner or admin)

Update selected repair fields. This endpoint is intended for customer/admin edits of basic fields; technicians should update status via the status endpoint.

Auth: Bearer token required.

Role behavior:

- `admin`: can patch any repair
- `customer`: can patch only if the repair’s `customer_user_id` matches their user id
- `technician`: not permitted unless also has `admin`

Request model: `RepairUpdate`

Response model: `RepairRead`

Example:

```bash
curl -sS -X PATCH "$BACKEND_BASE_URL/repairs/$REPAIR_ID" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "preferred_contact": "Email only"
  }'
```

### POST `/repairs/{repair_id}/assign` (admin only)

Assigns a technician to the repair.

Auth: Bearer token required.
Role: `admin`

Request model: `RepairAssignRequest`

Response model: `RepairRead`

Example:

```bash
curl -sS -X POST "$BACKEND_BASE_URL/repairs/$REPAIR_ID/assign" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "technician_user_id": "00000000-0000-0000-0000-000000000000"
  }'
```

### POST `/repairs/{repair_id}/status` (technician assigned or admin)

Changes the repair’s status and returns the newly created history record.

Auth: Bearer token required.

Role behavior:

- `admin`: can change status for any repair
- `technician`: can change status only for repairs assigned to them (`technician_user_id == current_user.user_id`)

Request model: `RepairStatusChangeRequest`

Response model: `RepairStatusHistoryItem`

Example:

```bash
curl -sS -X POST "$BACKEND_BASE_URL/repairs/$REPAIR_ID/status" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "new_status": "in_progress",
    "note": "Started diagnostics"
  }'
```

### GET `/repairs/admin/summary` (admin only)

Returns a dashboard summary including total count, counts by current status, and a list of recent repairs.

Auth: Bearer token required.
Role: `admin`

Query params:

- `recent_limit` (default: 10)

Response model: `AdminRepairsSummary`

Example:

```bash
curl -sS "$BACKEND_BASE_URL/repairs/admin/summary?recent_limit=10" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN"
```

## Models (summary)

### `CurrentUser`

Returned by `/auth/me`. It contains:

- `user_id` (string)
- `email` (string or null)
- `roles` (list of strings)
- `claims` (object with decoded JWT claims or normalized Supabase user payload)

### `ProfileUpsert`

Used by `PUT /profiles/me`:

- `role` (string; expected values are `customer`, `technician`, `admin`)
- `full_name` (string or null)

### `RepairCreate`

Used by `POST /repairs`:

- `device_type` (string)
- `issue_description` (string)
- `preferred_contact` (string or null)

### `RepairUpdate`

Used by `PATCH /repairs/{repair_id}`. All fields are optional:

- `device_type` (string or null)
- `issue_description` (string or null)
- `preferred_contact` (string or null)

### `RepairStatusChangeRequest`

Used by `POST /repairs/{repair_id}/status`:

- `new_status` (string)
- `note` (string or null)
