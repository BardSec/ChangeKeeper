from sqlalchemy import Column, Integer, String, DateTime, Text, Enum, Boolean
from sqlalchemy.sql import func
from datetime import datetime
import enum
from app.database import Base


class CategoryEnum(str, enum.Enum):
    """Change category options."""
    NETWORK = "Network"
    IDENTITY = "Identity"
    ENDPOINT = "Endpoint"
    APPLICATION = "Application"
    VENDOR = "Vendor"
    OTHER = "Other"


class ImpactLevelEnum(str, enum.Enum):
    """Impact level options."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class UserImpactEnum(str, enum.Enum):
    """Expected user impact options."""
    NONE = "None"
    SOME = "Some"
    MANY = "Many"


class StatusEnum(str, enum.Enum):
    """Change status options."""
    PLANNED = "Planned"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    ROLLED_BACK = "Rolled Back"
    FAILED = "Failed"


class ChangeTypeEnum(str, enum.Enum):
    """Quick log vs full change."""
    QUICK = "quick"
    FULL = "full"


class Change(Base):
    """Change record model."""
    __tablename__ = "changes"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Step 1: Basics
    title = Column(String(500), nullable=False, index=True)
    category = Column(
        Enum(CategoryEnum, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True
    )
    systems_affected = Column(Text, nullable=False)  # JSON array stored as text
    planned_start = Column(DateTime(timezone=True), nullable=True)
    planned_end = Column(DateTime(timezone=True), nullable=True)
    implementer = Column(String(255), nullable=False, index=True)
    
    # Step 2: Risk
    impact_level = Column(
        Enum(ImpactLevelEnum, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True
    )
    user_impact = Column(
        Enum(UserImpactEnum, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False
    )
    maintenance_window = Column(Boolean, nullable=False, default=False)
    backout_plan = Column(Text, nullable=True)
    
    # Step 3: Work details
    what_changed = Column(Text, nullable=False)
    ticket_id = Column(String(100), nullable=True, index=True)
    links = Column(Text, nullable=True)  # JSON array stored as text
    
    # Step 4: Completion
    status = Column(
        Enum(StatusEnum, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
        default=StatusEnum.PLANNED
    )
    outcome_notes = Column(Text, nullable=True)
    post_change_issues = Column(Text, nullable=True)
    
    # Type
    change_type = Column(
        Enum(ChangeTypeEnum, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=ChangeTypeEnum.FULL,
        server_default='full',
        index=True
    )

    # Metadata
    created_by = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Change(id={self.id}, title='{self.title}', status='{self.status}')>"


class AuditLog(Base):
    """Audit log model for tracking actions."""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(50), nullable=False, index=True)  # create, edit, export, view
    user_email = Column(String(255), nullable=False, index=True)
    user_name = Column(String(255), nullable=True)
    change_id = Column(Integer, nullable=True, index=True)
    details = Column(Text, nullable=True)  # JSON with additional context
    ip_address = Column(String(45), nullable=True)  # IPv6 max length
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}', user='{self.user_email}')>"
