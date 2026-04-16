from sqlalchemy.orm import Session
from app.models import AuditLog
from typing import Optional
import json


class AuditService:
    """Service for audit logging."""
    
    @staticmethod
    def log_action(
        db: Session,
        action: str,
        user_email: str,
        user_name: Optional[str] = None,
        change_id: Optional[int] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """
        Create an audit log entry.
        
        Args:
            db: Database session
            action: Action type (create, edit, export, view, etc.)
            user_email: User email address
            user_name: User display name
            change_id: Related change record ID
            details: Additional context as dictionary
            ip_address: User IP address
            
        Returns:
            Created AuditLog instance
        """
        audit_entry = AuditLog(
            action=action,
            user_email=user_email,
            user_name=user_name,
            change_id=change_id,
            details=json.dumps(details) if details else None,
            ip_address=ip_address
        )
        
        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)
        
        return audit_entry
    
    @staticmethod
    def log_change_create(
        db: Session,
        user: dict,
        change_id: int,
        ip_address: Optional[str] = None
    ):
        """Log change creation."""
        return AuditService.log_action(
            db=db,
            action='create',
            user_email=user.get('email', ''),
            user_name=user.get('name', ''),
            change_id=change_id,
            ip_address=ip_address
        )
    
    @staticmethod
    def log_change_edit(
        db: Session,
        user: dict,
        change_id: int,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None
    ):
        """Log change edit."""
        return AuditService.log_action(
            db=db,
            action='edit',
            user_email=user.get('email', ''),
            user_name=user.get('name', ''),
            change_id=change_id,
            details=details,
            ip_address=ip_address
        )
    
    @staticmethod
    def log_export(
        db: Session,
        user: dict,
        export_type: str,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None
    ):
        """Log export action."""
        return AuditService.log_action(
            db=db,
            action=f'export_{export_type}',
            user_email=user.get('email', ''),
            user_name=user.get('name', ''),
            details=details,
            ip_address=ip_address
        )
    
    @staticmethod
    def log_change_promote(
        db: Session,
        user: dict,
        change_id: int,
        ip_address: Optional[str] = None
    ):
        """Log quick log promotion to full change."""
        return AuditService.log_action(
            db=db,
            action='promote',
            user_email=user.get('email', ''),
            user_name=user.get('name', ''),
            change_id=change_id,
            details={'from_type': 'quick', 'to_type': 'full'},
            ip_address=ip_address
        )

    @staticmethod
    def log_view(
        db: Session,
        user: dict,
        change_id: int,
        ip_address: Optional[str] = None
    ):
        """Log change view (optional, can be noisy)."""
        return AuditService.log_action(
            db=db,
            action='view',
            user_email=user.get('email', ''),
            user_name=user.get('name', ''),
            change_id=change_id,
            ip_address=ip_address
        )
