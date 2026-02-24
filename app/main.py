import secrets
import logging

from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from app.config import get_settings
from app.auth import get_current_user_optional, microsoft_enabled, google_enabled
from app.routers import auth, changes, reports
from app.database import engine, Base

logger = logging.getLogger(__name__)
settings = get_settings()

# Create database tables (for development; use Alembic in production)
# Base.metadata.create_all(bind=engine)

# Initialize FastAPI app -- disable docs endpoints
app = FastAPI(
    title=settings.app_name,
    description="IT Change Management System",
    version="2.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


# --- Security headers middleware ---

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "frame-ancestors 'none'"
        )
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# Add proxy headers middleware -- restrict to localhost by default
app.add_middleware(
    ProxyHeadersMiddleware,
    trusted_hosts=["127.0.0.1", "::1"]
)

# Add session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie=settings.session_cookie_name,
    max_age=settings.session_max_age,
    same_site='lax',
    https_only=True
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(auth.router)
app.include_router(changes.router)
app.include_router(reports.router)


# --- CSRF helpers (importable by routers) ---

def generate_csrf_token(request: Request) -> str:
    """Return (and lazily create) a per-session CSRF token."""
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def verify_csrf_token(request: Request, token: str) -> bool:
    """Verify a submitted CSRF token against the session."""
    expected = request.session.get("csrf_token")
    if not expected or not token:
        return False
    return secrets.compare_digest(expected, token)


@app.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    user: dict = Depends(get_current_user_optional)
):
    """Display login page or redirect if already authenticated."""
    if user:
        return RedirectResponse(url='/', status_code=302)

    return templates.TemplateResponse("login.html", {
        "request": request,
        "microsoft_enabled": microsoft_enabled,
        "google_enabled": google_enabled,
    })


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# --- Error messages (no internal details leaked) ---

_ERROR_MESSAGES = {
    400: "The request could not be processed.",
    403: "You do not have permission to access this resource.",
    404: "The requested page was not found.",
    500: "An internal error occurred. Please try again later.",
}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with user-friendly messages."""
    if exc.status_code == 401:
        return RedirectResponse(url='/login', status_code=302)

    # Log the real detail server-side
    logger.warning("HTTP %s on %s: %s", exc.status_code, request.url.path, exc.detail)

    # 400 validation errors carry user-facing messages (e.g. "Title is required");
    # 500 and other server errors get a generic message to avoid leaking internals.
    if exc.status_code == 400:
        safe_detail = exc.detail
    else:
        safe_detail = _ERROR_MESSAGES.get(exc.status_code, "Something went wrong.")

    accepts_json = 'application/json' in (request.headers.get('accept') or '')

    if accepts_json:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": safe_detail}
        )

    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "status_code": exc.status_code,
            "detail": safe_detail
        },
        status_code=exc.status_code
    )
