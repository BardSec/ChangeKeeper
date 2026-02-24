from authlib.integrations.starlette_client import OAuth
from authlib.integrations.base_client import OAuthError
from app.config import get_settings
import secrets

settings = get_settings()

# Configure OAuth
oauth = OAuth()

# Register Microsoft Entra ID provider (if configured)
microsoft_enabled = bool(settings.entra_client_id and settings.entra_client_secret and settings.entra_tenant_id)
if microsoft_enabled:
    oauth.register(
        name='microsoft',
        client_id=settings.entra_client_id,
        client_secret=settings.entra_client_secret,
        server_metadata_url=f'https://login.microsoftonline.com/{settings.entra_tenant_id}/v2.0/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile User.Read',
            'token_endpoint_auth_method': 'client_secret_post',
        }
    )

# Register Google Workspace provider (if configured)
google_enabled = bool(settings.google_client_id and settings.google_client_secret)
if google_enabled:
    oauth.register(
        name='google',
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile',
        }
    )


def generate_nonce() -> str:
    """Generate a secure random nonce for OIDC flow."""
    return secrets.token_urlsafe(32)


def generate_state() -> str:
    """Generate a secure random state for OIDC flow."""
    return secrets.token_urlsafe(32)


async def validate_token(token: dict) -> dict:
    """
    Validate OIDC token.

    Args:
        token: Token dictionary from OIDC provider

    Returns:
        Validated token claims

    Raises:
        OAuthError: If token validation fails
    """
    # Token validation is handled by authlib during token exchange
    # Additional custom validation can be added here if needed

    if not token:
        raise OAuthError(description="Invalid token")

    # Verify token has required claims
    required_claims = ['iss', 'aud', 'exp', 'sub']
    for claim in required_claims:
        if claim not in token:
            raise OAuthError(description=f"Missing required claim: {claim}")

    return token


def extract_user_info(token: dict) -> dict:
    """
    Extract user information from OIDC token.

    Args:
        token: Validated token dictionary

    Returns:
        Dictionary with user information
    """
    return {
        'email': token.get('email') or token.get('preferred_username', ''),
        'name': token.get('name', ''),
        'sub': token.get('sub', ''),
        'groups': token.get('groups', [])
    }
