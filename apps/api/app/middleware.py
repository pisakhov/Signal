"""Security middleware for FastAPI application."""
import time
import logging
from typing import Callable

from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from .settings import settings


logger = logging.getLogger(__name__)


# Rate limiting storage (in-memory for simplicity; use Redis for production)
_rate_limit_store: dict[str, list[float]] = {}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware by user ID."""

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        burst: int = 30,  # Increased to handle parallel frontend requests
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst = burst  # Allow burst of requests in first second

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health check and GET requests (read-only)
        if request.url.path == "/health" or request.method == "GET":
            return await call_next(request)

        # Extract user_id from JWT if available
        user_id = self._get_user_id(request)

        # Rate limit by user_id or IP
        key = user_id or request.client.host
        now = time.time()

        # Clean old entries
        if key in _rate_limit_store:
            _rate_limit_store[key] = [
                t for t in _rate_limit_store[key] if now - t < 60
            ]

        # Check rate limit
        if key not in _rate_limit_store:
            _rate_limit_store[key] = []

        request_count = len(_rate_limit_store[key])

        # Allow burst in first second
        recent_count = len([t for t in _rate_limit_store[key] if now - t < 1])

        if request_count >= self.requests_per_minute or recent_count >= self.burst:
            logger.warning(f"Rate limit exceeded for {key}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )

        _rate_limit_store[key].append(now)

        return await call_next(request)

    def _get_user_id(self, request: Request) -> str | None:
        """Extract user_id from JWT token if available."""
        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return None

        try:
            from .auth import _decode
            return _decode(auth_header.split(" ", 1)[1])
        except Exception:
            return None


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Content Security Policy
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  # Allow Monaco inline scripts
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: https:",
            "font-src 'self' data:",
            "connect-src 'self' http://localhost:* http://127.0.0.1:* ws://localhost:* ws://127.0.0.1:*",
            "frame-src 'self' http://localhost:* http://127.0.0.1:*",
        ]

        # Allow frontend origin in CSP
        for origin in settings.cors_origins.split(","):
            origin = origin.strip()
            if origin and origin != "http://localhost:3000":
                csp_directives.append(f"connect-src {origin}")
                csp_directives.append(f"frame-src {origin}")

        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # HSTS (only in production with HTTPS)
        if settings.session_secret != "change-me":  # Basic prod check
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        # Log request
        logger.info(
            "Request: %s %s from %s",
            request.method,
            request.url.path,
            request.client.host if request.client else "unknown",
        )

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Log response
            logger.info(
                "Response: %s %s -> %d (%.2fs)",
                request.method,
                request.url.path,
                response.status_code,
                duration,
            )

            response.headers["X-Response-Time"] = f"{duration:.3f}"
            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "Error: %s %s -> %s (%.2fs)",
                request.method,
                request.url.path,
                str(e),
                duration,
            )
            raise
