import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_login_page_unauthenticated():
    """Test login page is accessible and shows available providers."""
    response = client.get("/login")
    assert response.status_code == 200
    content = response.content
    assert b"Sign in with Microsoft" in content or b"Sign in with Google" in content


def test_dashboard_requires_auth():
    """Test dashboard redirects to login when not authenticated."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["location"]


def test_secret_detection():
    """Test secret detection service."""
    from app.services.secret_detection import SecretDetector

    # Test private key detection
    text_with_secret = "Here is my key: -----BEGIN PRIVATE KEY-----"
    has_secrets, findings = SecretDetector.has_secrets({"what_changed": text_with_secret})
    assert has_secrets is True
    assert len(findings) > 0

    # Test clean text
    clean_text = "This is a normal change description"
    has_secrets, findings = SecretDetector.has_secrets({"what_changed": clean_text})
    assert has_secrets is False
    assert len(findings) == 0


def test_role_determination():
    """Test role configuration."""
    from app.config import RoleConfig

    config = RoleConfig()

    # Test default role
    role = config.get_user_role([])
    assert role == "user"

    # Test with unknown group
    role = config.get_user_role(["unknown-group-id"])
    assert role == "user"


def test_google_login_route_exists():
    """Test that Google login route is registered."""
    from app.auth.oidc import google_enabled
    response = client.get("/auth/google/login", follow_redirects=False)
    if google_enabled:
        assert response.status_code in (302, 307)
    else:
        assert response.status_code == 404


def test_microsoft_login_route_exists():
    """Test that Microsoft login route is registered."""
    from app.auth.oidc import microsoft_enabled
    response = client.get("/auth/login", follow_redirects=False)
    if microsoft_enabled:
        assert response.status_code in (302, 307)
    else:
        assert response.status_code == 404


def test_logout():
    """Test logout clears session and redirects."""
    response = client.get("/auth/logout", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["location"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
