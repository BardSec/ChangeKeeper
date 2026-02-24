from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from app.config import get_settings
from app.auth import get_current_user_optional, microsoft_enabled, google_enabled
from app.routers import auth, changes, reports
from app.database import engine, Base

settings = get_settings()

# Create database tables (for development; use Alembic in production)
# Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="IT Change Management System",
    version="2.0.0"
)

# Add proxy headers middleware for Cloudflare Tunnel / reverse proxy support
app.add_middleware(
    ProxyHeadersMiddleware,
    trusted_hosts=["*"]
)

# Add session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie=settings.session_cookie_name,
    max_age=settings.session_max_age,
    same_site='none',  # Required for OAuth flows behind proxies
    https_only=True    # Set to True for production with HTTPS
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(auth.router)
app.include_router(changes.router)
app.include_router(reports.router)


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


# Global exception handler for better UX
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with user-friendly messages."""
    if exc.status_code == 401:
        # Redirect to login for unauthorized requests
        return RedirectResponse(url='/login', status_code=302)
    
    # For AJAX requests, return JSON
    if request.headers.get('accept') == 'application/json':
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
    
    # For regular requests, return error page
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "status_code": exc.status_code,
            "detail": exc.detail
        },
        status_code=exc.status_code
    )
