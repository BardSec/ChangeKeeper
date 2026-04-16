import json
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import Change, ChangeTypeEnum
from app.schemas import ChangeCreate, ChangeFilter
from app.auth import get_current_user, require_write_access, require_admin
from app.services import AuditService, PDFGenerator, EmailService, SecretDetector

logger = logging.getLogger(__name__)
router = APIRouter(tags=["changes"])
templates = Jinja2Templates(directory="app/templates")

# Allowed enum values (source of truth)
VALID_CATEGORIES = {'Network', 'Identity', 'Endpoint', 'Application', 'Vendor', 'Other'}
VALID_IMPACTS = {'Low', 'Medium', 'High'}
VALID_USER_IMPACTS = {'None', 'Some', 'Many'}
VALID_STATUSES = {'Planned', 'In Progress', 'Completed', 'Rolled Back', 'Failed'}
VALID_CHANGE_TYPES = {'quick', 'full'}


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request."""
    return request.client.host if request.client else 'unknown'


def _escape_like(value: str) -> str:
    """Escape LIKE-special characters in user input."""
    return value.replace('%', r'\%').replace('_', r'\_')


def _validate_link(url: str) -> bool:
    """Validate that a URL uses http or https scheme."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc)
    except Exception:
        return False


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    category: Optional[str] = None,
    system: Optional[str] = None,
    impact_level: Optional[str] = None,
    implementer: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    change_type: Optional[str] = None,
    page: int = 1
):
    """Display dashboard with filterable list of changes."""
    # Clamp page to >= 1
    if page < 1:
        page = 1

    query = db.query(Change)

    if category:
        query = query.filter(Change.category == category)

    if system:
        query = query.filter(Change.systems_affected.contains(system))

    if impact_level:
        query = query.filter(Change.impact_level == impact_level)

    if implementer:
        safe = _escape_like(implementer)
        query = query.filter(Change.implementer.ilike(f'%{safe}%'))

    if status:
        query = query.filter(Change.status == status)

    if change_type and change_type in VALID_CHANGE_TYPES:
        query = query.filter(Change.change_type == change_type)

    if search:
        safe = _escape_like(search)
        search_term = f'%{safe}%'
        query = query.filter(
            or_(
                Change.title.ilike(search_term),
                Change.what_changed.ilike(search_term),
                Change.ticket_id.ilike(search_term)
            )
        )

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(Change.created_at >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(Change.created_at <= end_dt)
        except ValueError:
            pass

    query = query.order_by(Change.created_at.desc())

    page_size = 50
    total = query.count()
    total_pages = (total + page_size - 1) // page_size
    offset = (page - 1) * page_size

    changes = query.offset(offset).limit(page_size).all()

    for change in changes:
        change.systems_list = json.loads(change.systems_affected)
        if change.links:
            change.links_list = json.loads(change.links)
        else:
            change.links_list = []

    # Import here to avoid circular import
    from app.main import generate_csrf_token
    csrf_token = generate_csrf_token(request)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "changes": changes,
        "filters": {
            "category": category,
            "system": system,
            "impact_level": impact_level,
            "implementer": implementer,
            "status": status,
            "search": search,
            "start_date": start_date,
            "end_date": end_date,
            "change_type": change_type
        },
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "email_enabled": EmailService.is_enabled(),
        "csrf_token": csrf_token,
    })


@router.get("/changes/new", response_class=HTMLResponse)
async def new_change_wizard(
    request: Request,
    user: dict = Depends(require_write_access)
):
    """Display multi-step change wizard."""
    from app.main import generate_csrf_token
    csrf_token = generate_csrf_token(request)

    return templates.TemplateResponse("change_wizard.html", {
        "request": request,
        "user": user,
        "default_implementer": user.get('email', ''),
        "email_enabled": EmailService.is_enabled(),
        "csrf_token": csrf_token,
    })


@router.get("/changes/quick", response_class=HTMLResponse)
async def quick_log_form(
    request: Request,
    user: dict = Depends(require_write_access)
):
    """Display single-screen quick log form."""
    from app.main import generate_csrf_token
    csrf_token = generate_csrf_token(request)

    return templates.TemplateResponse("quick_log.html", {
        "request": request,
        "user": user,
        "default_implementer": user.get('email', ''),
        "csrf_token": csrf_token,
    })


@router.post("/changes/quick")
async def create_quick_log(
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_write_access)
):
    """Create a quick log change record with minimal fields."""
    form_data = await request.form()

    from app.main import verify_csrf_token
    submitted_token = form_data.get('csrf_token', '')
    if not verify_csrf_token(request, submitted_token):
        raise HTTPException(status_code=403, detail="CSRF token validation failed")

    # Normalise enums
    category_map = {
        'NETWORK': 'Network', 'IDENTITY': 'Identity', 'ENDPOINT': 'Endpoint',
        'APPLICATION': 'Application', 'VENDOR': 'Vendor', 'OTHER': 'Other',
        'Network': 'Network', 'Identity': 'Identity', 'Endpoint': 'Endpoint',
        'Application': 'Application', 'Vendor': 'Vendor', 'Other': 'Other',
    }
    status_map = {
        'PLANNED': 'Planned', 'IN PROGRESS': 'In Progress', 'COMPLETED': 'Completed',
        'ROLLED BACK': 'Rolled Back', 'FAILED': 'Failed',
        'Planned': 'Planned', 'In Progress': 'In Progress', 'Completed': 'Completed',
        'Rolled Back': 'Rolled Back', 'Failed': 'Failed',
    }

    impact_map = {
        'LOW': 'Low', 'MEDIUM': 'Medium', 'HIGH': 'High',
        'Low': 'Low', 'Medium': 'Medium', 'High': 'High',
    }

    raw_category = form_data.get('category', '')
    raw_status = form_data.get('status', 'Completed')
    raw_impact = form_data.get('impact_level', 'Low')
    category = category_map.get(raw_category.upper(), category_map.get(raw_category))
    status_val = status_map.get(raw_status.upper(), status_map.get(raw_status))
    impact_level = impact_map.get(raw_impact.upper(), impact_map.get(raw_impact)) or 'Low'

    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")
    if status_val not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    if impact_level not in VALID_IMPACTS:
        raise HTTPException(status_code=400, detail="Invalid impact level")

    title = form_data.get('title', '').strip()
    systems = form_data.getlist('systems_affected')

    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    if len(title) > 500:
        raise HTTPException(status_code=400, detail="Title must be 500 characters or fewer")
    if not systems:
        raise HTTPException(status_code=400, detail="At least one system is required")

    is_high = impact_level == 'High'

    # For high impact, require expanded fields
    what_changed = form_data.get('what_changed', '').strip() if is_high else title
    backout_plan = form_data.get('backout_plan', '').strip() if is_high else None
    maintenance_window = form_data.get('maintenance_window') == 'true' if is_high else False
    user_impact_val = form_data.get('user_impact', 'None') if is_high else 'None'
    outcome_notes = form_data.get('outcome_notes', '').strip() or None if is_high else None

    if is_high:
        if not what_changed:
            raise HTTPException(status_code=400, detail="What Changed is required for High impact changes")
        if not backout_plan:
            raise HTTPException(status_code=400, detail="Backout plan is required for High impact changes")

    # Secret detection
    check_data = {'title': title, 'what_changed': what_changed or title}
    if backout_plan:
        check_data['backout_plan'] = backout_plan
    has_secrets, findings = SecretDetector.has_secrets(check_data)
    confirm_no_secrets = form_data.get('confirm_no_secrets') == 'true'
    if has_secrets and not confirm_no_secrets:
        finding_types = ', '.join(set(name for name, _ in findings))
        raise HTTPException(
            status_code=400,
            detail=f"Potential secrets detected ({finding_types}). Please review and confirm."
        )

    change = Change(
        title=title,
        category=category,
        systems_affected=json.dumps(systems),
        implementer=user.get('email', ''),
        impact_level=impact_level,
        user_impact=user_impact_val,
        maintenance_window=maintenance_window,
        what_changed=what_changed or title,
        backout_plan=backout_plan,
        outcome_notes=outcome_notes,
        status=status_val,
        created_by=user.get('email', ''),
        change_type='full' if is_high else 'quick'
    )

    db.add(change)
    db.commit()
    db.refresh(change)

    AuditService.log_action(
        db=db,
        action='create',
        user_email=user.get('email', ''),
        user_name=user.get('name', ''),
        change_id=change.id,
        details={'change_type': 'full' if is_high else 'quick'},
        ip_address=get_client_ip(request)
    )

    return {"success": True, "change_id": change.id}


@router.get("/changes/{change_id}/promote", response_class=HTMLResponse)
async def promote_form(
    request: Request,
    change_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_write_access)
):
    """Display promotion wizard for a quick log."""
    change = db.query(Change).filter(Change.id == change_id).first()
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    if not change.change_type or change.change_type.value != 'quick':
        return RedirectResponse(url=f'/changes/{change_id}', status_code=302)

    # Authorization: creator or admin
    if change.created_by != user.get('email', '') and user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Not authorized to promote this change")

    from app.main import generate_csrf_token
    csrf_token = generate_csrf_token(request)

    # Build pre-fill data for the wizard JS
    prefill_data = {
        'title': change.title,
        'category': change.category.value if hasattr(change.category, 'value') else change.category,
        'systems_affected': json.loads(change.systems_affected),
        'implementer': change.implementer,
        'impact_level': change.impact_level.value if hasattr(change.impact_level, 'value') else change.impact_level,
        'user_impact': change.user_impact.value if hasattr(change.user_impact, 'value') else change.user_impact,
        'maintenance_window': 'true' if change.maintenance_window else 'false',
        'what_changed': change.what_changed,
        'status': change.status.value if hasattr(change.status, 'value') else change.status,
        'backout_plan': change.backout_plan or '',
        'ticket_id': change.ticket_id or '',
        'links': json.loads(change.links) if change.links else [],
        'planned_start': change.planned_start.isoformat() if change.planned_start else '',
        'planned_end': change.planned_end.isoformat() if change.planned_end else '',
        'outcome_notes': change.outcome_notes or '',
        'post_change_issues': change.post_change_issues or '',
    }

    return templates.TemplateResponse("change_wizard.html", {
        "request": request,
        "user": user,
        "default_implementer": change.implementer,
        "email_enabled": EmailService.is_enabled(),
        "csrf_token": csrf_token,
        "promote_mode": True,
        "promote_change_id": change_id,
        "prefill_json": json.dumps(prefill_data),
    })


@router.post("/changes/{change_id}/promote")
async def promote_change(
    request: Request,
    change_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_write_access)
):
    """Promote a quick log to a full change."""
    change = db.query(Change).filter(Change.id == change_id).first()
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    if not change.change_type or change.change_type.value != 'quick':
        raise HTTPException(status_code=400, detail="Only quick logs can be promoted")

    if change.created_by != user.get('email', '') and user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Not authorized to promote this change")

    form_data = await request.form()

    from app.main import verify_csrf_token
    submitted_token = form_data.get('csrf_token', '')
    if not verify_csrf_token(request, submitted_token):
        raise HTTPException(status_code=403, detail="CSRF token validation failed")

    # Same validation as create_change
    category_map = {
        'NETWORK': 'Network', 'IDENTITY': 'Identity', 'ENDPOINT': 'Endpoint',
        'APPLICATION': 'Application', 'VENDOR': 'Vendor', 'OTHER': 'Other',
        'Network': 'Network', 'Identity': 'Identity', 'Endpoint': 'Endpoint',
        'Application': 'Application', 'Vendor': 'Vendor', 'Other': 'Other',
    }
    impact_map = {
        'LOW': 'Low', 'MEDIUM': 'Medium', 'HIGH': 'High',
        'Low': 'Low', 'Medium': 'Medium', 'High': 'High',
    }
    user_impact_map = {
        'NONE': 'None', 'SOME': 'Some', 'MANY': 'Many',
        'None': 'None', 'Some': 'Some', 'Many': 'Many',
    }
    status_map = {
        'PLANNED': 'Planned', 'IN PROGRESS': 'In Progress', 'COMPLETED': 'Completed',
        'ROLLED BACK': 'Rolled Back', 'FAILED': 'Failed',
        'Planned': 'Planned', 'In Progress': 'In Progress', 'Completed': 'Completed',
        'Rolled Back': 'Rolled Back', 'Failed': 'Failed',
    }

    raw_category = form_data.get('category', '')
    raw_impact = form_data.get('impact_level', '')
    raw_user_impact = form_data.get('user_impact', '')
    raw_status = form_data.get('status', '')

    category = category_map.get(raw_category.upper(), category_map.get(raw_category))
    impact_level = impact_map.get(raw_impact.upper(), impact_map.get(raw_impact))
    user_impact = user_impact_map.get(raw_user_impact.upper(), user_impact_map.get(raw_user_impact))
    status_val = status_map.get(raw_status.upper(), status_map.get(raw_status))

    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")
    if impact_level not in VALID_IMPACTS:
        raise HTTPException(status_code=400, detail="Invalid impact level")
    if user_impact not in VALID_USER_IMPACTS:
        raise HTTPException(status_code=400, detail="Invalid user impact")
    if status_val not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    raw_links = [link for link in form_data.getlist('links') if link]
    for link in raw_links:
        if not _validate_link(link):
            raise HTTPException(status_code=400, detail="Links must use http:// or https://")

    title = form_data.get('title', '')
    implementer_val = form_data.get('implementer', '')
    what_changed = form_data.get('what_changed', '')
    ticket_id = form_data.get('ticket_id') or None

    if len(title) > 500:
        raise HTTPException(status_code=400, detail="Title must be 500 characters or fewer")
    if len(implementer_val) > 255:
        raise HTTPException(status_code=400, detail="Implementer must be 255 characters or fewer")
    if ticket_id and len(ticket_id) > 100:
        raise HTTPException(status_code=400, detail="Ticket ID must be 100 characters or fewer")

    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    if not category:
        raise HTTPException(status_code=400, detail="Category is required")
    systems = form_data.getlist('systems_affected')
    if not systems:
        raise HTTPException(status_code=400, detail="At least one system is required")
    if not implementer_val:
        raise HTTPException(status_code=400, detail="Implementer is required")
    if not what_changed:
        raise HTTPException(status_code=400, detail="What changed is required")
    if not status_val:
        raise HTTPException(status_code=400, detail="Status is required")

    backout_plan = form_data.get('backout_plan') or None
    if impact_level in ['Medium', 'High']:
        if not backout_plan or not backout_plan.strip():
            raise HTTPException(status_code=400, detail="Backout plan is required for Medium or High impact changes")

    # Secret detection
    check_data = {
        'title': title, 'what_changed': what_changed,
        'backout_plan': backout_plan or '', 'outcome_notes': form_data.get('outcome_notes', ''),
    }
    has_secrets, findings = SecretDetector.has_secrets(check_data)
    confirm_no_secrets = form_data.get('confirm_no_secrets') == 'true'
    if has_secrets and not confirm_no_secrets:
        finding_types = ', '.join(set(name for name, _ in findings))
        raise HTTPException(
            status_code=400,
            detail=f"Potential secrets detected ({finding_types}). Please review and confirm."
        )

    # Update the existing record
    change.title = title
    change.category = category
    change.systems_affected = json.dumps(systems)
    change.planned_start = form_data.get('planned_start') or None
    change.planned_end = form_data.get('planned_end') or None
    change.implementer = implementer_val
    change.impact_level = impact_level
    change.user_impact = user_impact
    change.maintenance_window = form_data.get('maintenance_window') == 'true'
    change.backout_plan = backout_plan
    change.what_changed = what_changed
    change.ticket_id = ticket_id
    change.links = json.dumps(raw_links) if raw_links else None
    change.status = status_val
    change.outcome_notes = form_data.get('outcome_notes') or None
    change.post_change_issues = form_data.get('post_change_issues') or None
    change.change_type = 'full'

    db.commit()
    db.refresh(change)

    AuditService.log_action(
        db=db,
        action='promote',
        user_email=user.get('email', ''),
        user_name=user.get('name', ''),
        change_id=change.id,
        details={'from_type': 'quick', 'to_type': 'full'},
        ip_address=get_client_ip(request)
    )

    return {"success": True, "change_id": change.id}


@router.post("/changes")
async def create_change(
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_write_access)
):
    """Create a new change record."""
    form_data = await request.form()

    # --- CSRF check ---
    from app.main import verify_csrf_token
    submitted_token = form_data.get('csrf_token', '')
    if not verify_csrf_token(request, submitted_token):
        raise HTTPException(status_code=403, detail="CSRF token validation failed")

    # --- Enum normalisation maps ---
    category_map = {
        'NETWORK': 'Network', 'IDENTITY': 'Identity', 'ENDPOINT': 'Endpoint',
        'APPLICATION': 'Application', 'VENDOR': 'Vendor', 'OTHER': 'Other',
        'Network': 'Network', 'Identity': 'Identity', 'Endpoint': 'Endpoint',
        'Application': 'Application', 'Vendor': 'Vendor', 'Other': 'Other',
    }
    impact_map = {
        'LOW': 'Low', 'MEDIUM': 'Medium', 'HIGH': 'High',
        'Low': 'Low', 'Medium': 'Medium', 'High': 'High',
    }
    user_impact_map = {
        'NONE': 'None', 'SOME': 'Some', 'MANY': 'Many',
        'None': 'None', 'Some': 'Some', 'Many': 'Many',
    }
    status_map = {
        'PLANNED': 'Planned', 'IN PROGRESS': 'In Progress', 'COMPLETED': 'Completed',
        'ROLLED BACK': 'Rolled Back', 'FAILED': 'Failed',
        'Planned': 'Planned', 'In Progress': 'In Progress', 'Completed': 'Completed',
        'Rolled Back': 'Rolled Back', 'Failed': 'Failed',
    }

    raw_category = form_data.get('category', '')
    raw_impact = form_data.get('impact_level', '')
    raw_user_impact = form_data.get('user_impact', '')
    raw_status = form_data.get('status', '')

    category = category_map.get(raw_category.upper(), category_map.get(raw_category))
    impact_level = impact_map.get(raw_impact.upper(), impact_map.get(raw_impact))
    user_impact = user_impact_map.get(raw_user_impact.upper(), user_impact_map.get(raw_user_impact))
    status_val = status_map.get(raw_status.upper(), status_map.get(raw_status))

    # Reject unmapped enum values
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")
    if impact_level not in VALID_IMPACTS:
        raise HTTPException(status_code=400, detail="Invalid impact level")
    if user_impact not in VALID_USER_IMPACTS:
        raise HTTPException(status_code=400, detail="Invalid user impact")
    if status_val not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    # Validate links (server-side URL scheme check)
    raw_links = [link for link in form_data.getlist('links') if link]
    for link in raw_links:
        if not _validate_link(link):
            raise HTTPException(status_code=400, detail="Links must use http:// or https://")

    title = form_data.get('title', '')
    implementer_val = form_data.get('implementer', '')
    what_changed = form_data.get('what_changed', '')
    ticket_id = form_data.get('ticket_id') or None

    # Length limits matching the DB schema
    if len(title) > 500:
        raise HTTPException(status_code=400, detail="Title must be 500 characters or fewer")
    if len(implementer_val) > 255:
        raise HTTPException(status_code=400, detail="Implementer must be 255 characters or fewer")
    if ticket_id and len(ticket_id) > 100:
        raise HTTPException(status_code=400, detail="Ticket ID must be 100 characters or fewer")

    change_data = {
        'title': title,
        'category': category,
        'systems_affected': form_data.getlist('systems_affected'),
        'planned_start': form_data.get('planned_start') or None,
        'planned_end': form_data.get('planned_end') or None,
        'implementer': implementer_val,
        'impact_level': impact_level,
        'user_impact': user_impact,
        'maintenance_window': form_data.get('maintenance_window') == 'true',
        'backout_plan': form_data.get('backout_plan') or None,
        'what_changed': what_changed,
        'ticket_id': ticket_id,
        'links': raw_links,
        'status': status_val,
        'outcome_notes': form_data.get('outcome_notes') or None,
        'post_change_issues': form_data.get('post_change_issues') or None,
    }

    email_copy = form_data.get('email_copy') == 'true'
    confirm_no_secrets = form_data.get('confirm_no_secrets') == 'true'

    # Secret detection -- do NOT echo matched text back to client
    has_secrets, findings = SecretDetector.has_secrets(change_data)
    if has_secrets and not confirm_no_secrets:
        finding_types = ', '.join(set(name for name, _ in findings))
        raise HTTPException(
            status_code=400,
            detail=f"Potential secrets detected ({finding_types}). Please review and confirm."
        )

    # Required-field validation
    if not change_data.get('title'):
        raise HTTPException(status_code=400, detail="Title is required")
    if not change_data.get('category'):
        raise HTTPException(status_code=400, detail="Category is required")
    if not change_data.get('systems_affected'):
        raise HTTPException(status_code=400, detail="At least one system is required")
    if not change_data.get('implementer'):
        raise HTTPException(status_code=400, detail="Implementer is required")
    if not change_data.get('impact_level'):
        raise HTTPException(status_code=400, detail="Impact level is required")
    if not change_data.get('user_impact'):
        raise HTTPException(status_code=400, detail="User impact is required")
    if not change_data.get('what_changed'):
        raise HTTPException(status_code=400, detail="What changed is required")
    if not change_data.get('status'):
        raise HTTPException(status_code=400, detail="Status is required")

    if change_data.get('impact_level') in ['Medium', 'High']:
        if not change_data.get('backout_plan') or not change_data.get('backout_plan').strip():
            raise HTTPException(status_code=400, detail="Backout plan is required for Medium or High impact changes")

    change = Change(
        title=change_data['title'],
        category=change_data['category'],
        systems_affected=json.dumps(change_data['systems_affected']),
        planned_start=change_data.get('planned_start'),
        planned_end=change_data.get('planned_end'),
        implementer=change_data['implementer'],
        impact_level=change_data['impact_level'],
        user_impact=change_data['user_impact'],
        maintenance_window=change_data['maintenance_window'],
        backout_plan=change_data.get('backout_plan'),
        what_changed=change_data['what_changed'],
        ticket_id=change_data.get('ticket_id'),
        links=json.dumps(change_data['links']) if change_data.get('links') else None,
        status=change_data['status'],
        outcome_notes=change_data.get('outcome_notes'),
        post_change_issues=change_data.get('post_change_issues'),
        created_by=user.get('email', ''),
        change_type='full'
    )

    db.add(change)
    db.commit()
    db.refresh(change)

    AuditService.log_change_create(
        db=db, user=user, change_id=change.id,
        ip_address=get_client_ip(request)
    )

    if email_copy and EmailService.is_enabled():
        change_url = str(request.url_for('view_change', change_id=change.id))
        change_dict = {
            'id': change.id,
            'title': change.title,
            'status': str(change.status),
            'category': str(change.category),
            'systems_affected': change.systems_affected,
            'impact_level': str(change.impact_level),
            'implementer': change.implementer
        }
        EmailService.send_change_summary(user.get('email', ''), change_dict, change_url)

    return {"success": True, "change_id": change.id}


@router.get("/changes/{change_id}", response_class=HTMLResponse)
async def view_change(
    request: Request,
    change_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """View change detail page."""
    change = db.query(Change).filter(Change.id == change_id).first()

    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    change.systems_list = json.loads(change.systems_affected)
    if change.links:
        change.links_list = json.loads(change.links)
    else:
        change.links_list = []

    return templates.TemplateResponse("change_detail.html", {
        "request": request,
        "user": user,
        "change": change,
        "email_enabled": EmailService.is_enabled()
    })


@router.get("/changes/{change_id}/pdf")
async def download_change_pdf(
    request: Request,
    change_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """Generate and download PDF for a change record."""
    change = db.query(Change).filter(Change.id == change_id).first()

    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    change_dict = {
        'id': change.id,
        'title': change.title,
        'category': change.category.value,
        'systems_affected': change.systems_affected,
        'planned_start': change.planned_start,
        'planned_end': change.planned_end,
        'implementer': change.implementer,
        'impact_level': change.impact_level.value,
        'user_impact': change.user_impact.value,
        'maintenance_window': change.maintenance_window,
        'backout_plan': change.backout_plan,
        'what_changed': change.what_changed,
        'ticket_id': change.ticket_id,
        'links': change.links,
        'status': change.status.value,
        'outcome_notes': change.outcome_notes,
        'post_change_issues': change.post_change_issues,
        'created_by': change.created_by,
        'created_at': change.created_at,
        'change_type': change.change_type.value if hasattr(change.change_type, 'value') else (change.change_type or 'full')
    }

    pdf_buffer = PDFGenerator.generate_change_pdf(change_dict)

    AuditService.log_export(
        db=db, user=user, export_type='pdf',
        details={'change_id': change_id},
        ip_address=get_client_ip(request)
    )

    filename = f"change_{change_id}_{datetime.now().strftime('%Y%m%d')}.pdf"

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
