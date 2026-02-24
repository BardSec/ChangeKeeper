from pydantic_settings import BaseSettings
from functools import lru_cache
import yaml
from pathlib import Path


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Database
    database_url: str

    # Security
    secret_key: str

    # Microsoft Entra ID (Azure AD) - optional if using Google
    entra_client_id: str = ""
    entra_client_secret: str = ""
    entra_tenant_id: str = ""
    redirect_uri: str = ""

    # Google Workspace - optional if using Microsoft
    google_client_id: str = ""
    google_client_secret: str = ""

    # Email (optional)
    enable_email: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    
    # Session
    session_cookie_name: str = "changekeeper_session"
    session_max_age: int = 86400  # 24 hours
    
    # Application
    app_name: str = "ChangeKeeper"
    app_port: int = 8000
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


class RoleConfig:
    """Load and manage role configuration from roles.yaml."""
    
    def __init__(self, config_path: str = "roles.yaml"):
        self.config_path = Path(config_path)
        self.roles_data = self._load_config()
    
    def _load_config(self) -> dict:
        """Load roles configuration from YAML file."""
        if not self.config_path.exists():
            return {"roles": {}, "default_role": "user"}
        
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f) or {"roles": {}, "default_role": "user"}
    
    def get_user_role(self, group_ids: list[str]) -> str:
        """
        Determine user role based on identity provider group membership.

        Args:
            group_ids: List of group IDs (Entra ID Object IDs or Google Workspace group emails)

        Returns:
            Role name (admin, auditor, or user)
        """
        if not group_ids:
            return self.roles_data.get("default_role", "user")
        
        # Check admin groups first (highest priority)
        admin_groups = self.roles_data.get("roles", {}).get("admin", {}).get("groups", [])
        if any(gid in admin_groups for gid in group_ids):
            return "admin"
        
        # Check auditor groups
        auditor_groups = self.roles_data.get("roles", {}).get("auditor", {}).get("groups", [])
        if any(gid in auditor_groups for gid in group_ids):
            return "auditor"
        
        # Default to user role
        return self.roles_data.get("default_role", "user")


@lru_cache()
def get_role_config() -> RoleConfig:
    """Get cached role configuration instance."""
    return RoleConfig()
