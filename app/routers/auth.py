from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from app.auth import oauth, generate_nonce, generate_state, extract_user_info, microsoft_enabled, google_enabled
from app.config import get_role_config
from authlib.integrations.base_client import OAuthError

router = APIRouter(prefix="/auth", tags=["auth"])
role_config = get_role_config()


def _build_session(request: Request, user_info: dict, provider: str) -> None:
    """Store authenticated user in session after successful OAuth callback."""
    group_ids = user_info.get('groups', [])
    role = role_config.get_user_role(group_ids)

    request.session['user'] = {
        'email': user_info['email'],
        'name': user_info['name'],
        'sub': user_info['sub'],
        'role': role,
        'provider': provider,
    }

    # Clean up OAuth temporary data
    request.session.pop('oauth_nonce', None)
    request.session.pop('oauth_state', None)


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

    redirect_uri = request.url_for('auth_callback')
    return await oauth.microsoft.authorize_redirect(
        request,
        redirect_uri,
        nonce=nonce,
        state=state
    )


@router.get("/callback")
async def auth_callback(request: Request):
    """Handle Microsoft OIDC callback."""
    try:
        state = request.query_params.get('state')
        stored_state = request.session.get('oauth_state')

        if not state or state != stored_state:
            raise HTTPException(status_code=400, detail="Invalid state parameter")

        token = await oauth.microsoft.authorize_access_token(request)

        stored_nonce = request.session.get('oauth_nonce')
        token_nonce = token.get('userinfo', {}).get('nonce')

        if stored_nonce and token_nonce and stored_nonce != token_nonce:
            raise HTTPException(status_code=400, detail="Invalid nonce")

        user_info = extract_user_info(token.get('userinfo', {}))
        _build_session(request, user_info, provider='microsoft')

        return RedirectResponse(url='/', status_code=302)

    except OAuthError as e:
        raise HTTPException(status_code=400, detail=f"OAuth error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")


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

    redirect_uri = request.url_for('google_callback')
    return await oauth.google.authorize_redirect(
        request,
        redirect_uri,
        nonce=nonce,
        state=state
    )


@router.get("/google/callback")
async def google_callback(request: Request):
    """Handle Google OIDC callback."""
    try:
        state = request.query_params.get('state')
        stored_state = request.session.get('oauth_state')

        if not state or state != stored_state:
            raise HTTPException(status_code=400, detail="Invalid state parameter")

        token = await oauth.google.authorize_access_token(request)

        stored_nonce = request.session.get('oauth_nonce')
        token_nonce = token.get('userinfo', {}).get('nonce')

        if stored_nonce and token_nonce and stored_nonce != token_nonce:
            raise HTTPException(status_code=400, detail="Invalid nonce")

        user_info = extract_user_info(token.get('userinfo', {}))
        _build_session(request, user_info, provider='google')

        return RedirectResponse(url='/', status_code=302)

    except OAuthError as e:
        raise HTTPException(status_code=400, detail=f"OAuth error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")


# --- Logout ---

@router.get("/logout")
async def logout(request: Request):
    """Logout and clear session."""
    request.session.clear()
    return RedirectResponse(url='/login', status_code=302)
