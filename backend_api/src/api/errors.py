from __future__ import annotations

from fastapi import HTTPException, status


# PUBLIC_INTERFACE
def http_404(detail: str = "Not found") -> HTTPException:
    """Return a standardized 404 HTTPException."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


# PUBLIC_INTERFACE
def http_400(detail: str = "Bad request") -> HTTPException:
    """Return a standardized 400 HTTPException."""
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


# PUBLIC_INTERFACE
def http_409(detail: str = "Conflict") -> HTTPException:
    """Return a standardized 409 HTTPException."""
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


# PUBLIC_INTERFACE
def http_403(detail: str = "Forbidden") -> HTTPException:
    """Return a standardized 403 HTTPException."""
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
