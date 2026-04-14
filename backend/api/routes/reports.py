from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.api.models.reports import ReportCreateRequest, ReportResponse, ReportDataResponse, SystemStatisticsResponse
from backend.api.models.responses import StatusResponse
from backend.data.pool.session import get_db
from backend.security.jwt_auth import get_current_user
from backend.models.user import User
from backend.data.executor import reports_crud

router = APIRouter(prefix="/api/reports", tags=["Reports"])

@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_new_report(
    request: ReportCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new report configuration. Validates reports table existence first."""
    # Requirement 7: Ensure reports table exists
    from sqlalchemy import text
    try:
        # Quick check for table existence
        await db.execute(text("SELECT 1 FROM reports LIMIT 1"))
    except Exception as e:
        # Check if error is related to table not existing (handles PG and SQLite)
        err_msg = str(e).lower()
        if any(substring in err_msg for substring in ["relation \"reports\" does not exist", "table \"reports\" does not exist", "no such table: reports"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Reports table not initialized. Run migration."
            )
        # Any other DB error
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    report = await reports_crud.create_report(
        db=db,
        user_id=str(current_user.id),
        tenant_id=str(current_user.tenant_id),
        connection_id=str(request.connection_id),
        saved_query_id=str(request.saved_query_id),
        report_name=request.report_name,
        chart_type=request.chart_type,
        chart_config=request.chart_config
    )
    return report

@router.get("", response_model=List[ReportResponse])
async def get_all_reports(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all reports for the current user."""
    reports = await reports_crud.list_reports(db=db, user_id=str(current_user.id))
    return reports

@router.get("/statistics", response_model=SystemStatisticsResponse)
async def get_system_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get system-wide analytics for the dashboard. Admin only."""
    from backend.api.middleware.rbac import is_admin
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can access system analytics.")
    
    stats = await reports_crud.get_system_stats(db=db, tenant_id=str(current_user.tenant_id))
    return stats

@router.get("/{report_id}", response_model=ReportResponse)
async def get_report_metadata(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get metadata for a specific report."""
    report = await reports_crud.get_report_by_id(db=db, report_id=report_id, user_id=str(current_user.id))
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report

@router.get("/{report_id}/data", response_model=ReportDataResponse)
async def get_report_data(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Execute the report's underlying query and return fresh visual data."""
    report = await reports_crud.get_report_by_id(db=db, report_id=report_id, user_id=str(current_user.id))
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    try:
        results = await reports_crud.execute_report_query(db=db, report=report)
        return ReportDataResponse(
            report_id=report.id,
            data=results["rows"],
            chart_type=report.chart_type,
            chart_config=report.chart_config,
            row_count=results["row_count"],
            execution_time_ms=int(results.get("execution_time_ms", 0))
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to execute report query.")

@router.delete("/{report_id}", response_model=StatusResponse)
async def remove_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a report configuration."""
    deleted = await reports_crud.delete_report(db=db, report_id=report_id, user_id=str(current_user.id))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return StatusResponse(status="success", message="Report deleted successfully")
