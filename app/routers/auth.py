import logging

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from app.auth import oauth, generate_nonce, generate_state, validate_token, extract_user_info, microsoft_enabled, google_enabled
from app.config import get_settings, get_role_config
from app.services import AuditService
from app.database import get_db
from authlib.integrations.base_client import OAuthError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
role_config = get_role_config()


def _get_client_ip(request: Request) -> str:
    return request.client.host if request.client else 'unknown'


def _build_session(request: Request, user_info: dict, provider: str) -> None:
    """Clear old session and create a fresh authenticated session (prevents fixation)."""
    group_ids = user_info.get('groups', [])
    role = role_config.get_user_role(group_ids)

    # Regenerate session to prevent fixation
    request.session.clear()

    request.session['user'] = {
        'email': user_info['email'],
        'name': user_info['name'],
        'sub': user_info['sub'],
        'role': role,
        'provider': provider,
    }


def _log_auth_event(action: str, email: str, ip: str, details: dict = None) -> None:
    """Log an authentication event to the audit log."""
    try:
        db = next(get_db())
        AuditService.log_action(
            db=db,
            action=action,
            user_email=email,
            details=details,
            ip_address=ip,
        )
    except Exception:
        logger.exception("Failed to log auth event: %s for %s", action, email)


async def _handle_callback(request: Request, provider_name: str, oauth_client):
    """Shared callback logic for Microsoft and Google."""
    try:
        state = request.query_params.get('state')
        stored_state = request.session.get('oauth_state')

        if not state or state != stored_state:
            raise HTTPException(status_code=400, detail="Invalid state parameter")

        token = await oauth_client.authorize_access_token(request)
        userinfo = token.get('userinfo', {})

        # Validate token claims
        await validate_token(userinfo)

        # Strict nonce validation -- reject if either nonce is absent
        stored_nonce = request.session.get('oauth_nonce')
        token_nonce = userinfo.get('nonce')

        if not stored_nonce or not token_nonce or stored_nonce != token_nonce:
            raise HTTPException(status_code=400, detail="Invalid nonce")

        user_info = extract_user_info(userinfo)
        _build_session(request, user_info, provider=provider_name)

        _log_auth_event(
            'login', user_info['email'], _get_client_ip(request),
            {'provider': provider_name},
        )

        return RedirectResponse(url='/', status_code=302)

    except OAuthError:
        _log_auth_event(
            'login_failed', 'unknown', _get_client_ip(request),
            {'provider': provider_name, 'reason': 'oauth_error'},
        )
        raise HTTPException(status_code=400, detail="Authentication failed")
    except HTTPException:
        raise
    except Exception:
        logger.exception("Authentication callback failed for %s", provider_name)
        _log_auth_event(
            'login_failed', 'unknown', _get_client_ip(request),
            {'provider': provider_name, 'reason': 'unexpected_error'},
        )
        raise HTTPException(status_code=500, detail="Authentication failed")


# --- Microsoft Entra ID routes ---

@router.get("/login")
async def login(request: Request):
    """Initiate Microsoft OIDC login flow."""
    if not microsoft_enabled:
        raise HTTPException(status_code=404, detail="Microsoft sign-in is not configured")

    nonce = generate_nonce()
    state = generate_state()

    request.session['oauth_nonce'] = nonce
    request.session['oauth_state'] = state

    settings = get_settings()
    redirect_uri = settings.redirect_uri or str(request.url_for('auth_callback'))
    return await oauth.microsoft.authorize_redirect(
        request, redirect_uri, nonce=nonce, state=state
    )


@router.get("/callback")
async def auth_callback(request: Request):
    """Handle Microsoft OIDC callback."""
    return await _handle_callback(request, 'microsoft', oauth.microsoft)


# --- Google Workspace routes ---

@router.get("/google/login")
async def google_login(request: Request):
    """Initiate Google OIDC login flow."""
    if not google_enabled:
        raise HTTPException(status_code=404, detail="Google sign-in is not configured")

    nonce = generate_nonce()
    state = generate_state()

    request.session['oauth_nonce'] = nonce
    request.session['oauth_state'] = state

    settings = get_settings()
    if settings.redirect_uri:
        # Derive Google callback from the configured base URL
        base = settings.redirect_uri.rsplit('/auth/', 1)[0]
        redirect_uri = f"{base}/auth/google/callback"
    else:
        redirect_uri = str(request.url_for('google_callback'))
    return await oauth.google.authorize_redirect(
        request, redirect_uri, nonce=nonce, state=state
    )


@router.get("/google/callback")
async def google_callback(request: Request):
    """Handle Google OIDC callback."""
    return await _handle_callback(request, 'google', oauth.google)


# --- Logout (POST to prevent CSRF logout) ---

@router.post("/logout")
async def logout(request: Request):
    """Logout and clear session."""
    user = request.session.get('user', {})
    _log_auth_event('logout', user.get('email', 'unknown'), _get_client_ip(request))
    request.session.clear()
    return RedirectResponse(url='/login', status_code=302)


# Keep GET for backwards-compatible bookmarks -- just clears session and redirects
@router.get("/logout")
async def logout_get(request: Request):
    """Handle GET logout for nav link compatibility."""
    user = request.session.get('user', {})
    _log_auth_event('logout', user.get('email', 'unknown'), _get_client_ip(request))
    request.session.clear()
    return RedirectResponse(url='/login', status_code=302)
