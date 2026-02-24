from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
import csv
import io
import json

from app.database import get_db
from app.models import Change
from app.auth import require_admin
from app.services import AuditService

router = APIRouter(prefix="/reports", tags=["reports"])


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request."""
    return request.client.host if request.client else 'unknown'


def _sanitize_csv_cell(value: str) -> str:
    """Prefix formula-triggering characters to prevent CSV injection."""
    if value and value[0] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + value
    return value


@router.get("/changes.csv")
async def export_changes_csv(
    request: Request,
    start: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end: str = Query(..., description="End date in YYYY-MM-DD format"),
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin)
):
    """Export changes to CSV for a date range (admin only)."""
    try:
        start_date = datetime.strptime(start, '%Y-%m-%d')
        end_date = datetime.strptime(end, '%Y-%m-%d')
        end_date = end_date.replace(hour=23, minute=59, second=59)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Start date must be before end date")

    changes = db.query(Change).filter(
        Change.created_at >= start_date,
        Change.created_at <= end_date
    ).order_by(Change.created_at).all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'ID', 'Created At', 'Created By', 'Updated At', 'Title',
        'Category', 'Systems Affected', 'Planned Start', 'Planned End',
        'Implementer', 'Impact Level', 'User Impact', 'Maintenance Window',
        'Backout Plan', 'What Changed', 'Ticket/Issue ID', 'Links',
        'Status', 'Outcome Notes', 'Post-Change Issues'
    ])

    for change in changes:
        systems = ', '.join(json.loads(change.systems_affected))
        links = ', '.join(json.loads(change.links)) if change.links else ''

        writer.writerow([
            change.id,
            change.created_at.strftime('%Y-%m-%d %H:%M:%S') if change.created_at else '',
            _sanitize_csv_cell(change.created_by),
            change.updated_at.strftime('%Y-%m-%d %H:%M:%S') if change.updated_at else '',
            _sanitize_csv_cell(change.title),
            change.category.value,
            _sanitize_csv_cell(systems),
            change.planned_start.strftime('%Y-%m-%d %H:%M:%S') if change.planned_start else '',
            change.planned_end.strftime('%Y-%m-%d %H:%M:%S') if change.planned_end else '',
            _sanitize_csv_cell(change.implementer),
            change.impact_level.value,
            change.user_impact.value,
            'Yes' if change.maintenance_window else 'No',
            _sanitize_csv_cell(change.backout_plan or ''),
            _sanitize_csv_cell(change.what_changed),
            _sanitize_csv_cell(change.ticket_id or ''),
            _sanitize_csv_cell(links),
            change.status.value,
            _sanitize_csv_cell(change.outcome_notes or ''),
            _sanitize_csv_cell(change.post_change_issues or '')
        ])

    AuditService.log_export(
        db=db, user=user, export_type='csv',
        details={'start_date': start, 'end_date': end, 'record_count': len(changes)},
        ip_address=get_client_ip(request)
    )

    output.seek(0)
    filename = f"changekeeper_export_{start}_to_{end}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
