from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.models.dashboards import (
    DashboardCreateRequest, DashboardUpdateRequest,
    DashboardResponse, DashboardDetailResponse,
    WidgetCreateRequest, WidgetUpdateRequest, WidgetResponse,
    BulkLayoutRequest,
)
from backend.api.models.responses import StatusResponse
from backend.data.pool.session import get_db
from backend.security.jwt_auth import get_current_user
from backend.models.user import User
from backend.data.executor import dashboards_crud
from backend.data.executor.reports_crud import execute_report_query
from backend.api.models.reports import ReportDataResponse

router = APIRouter(prefix="/api/dashboards", tags=["Dashboards"])


# ── Dashboards ────────────────────────────────────────────────────

@router.post("", response_model=DashboardResponse, status_code=status.HTTP_201_CREATED)
async def create_dashboard(
    req: DashboardCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    d = await dashboards_crud.create_dashboard(
        db, user_id=str(user.id), tenant_id=str(user.tenant_id),
        name=req.name, connection_id=str(req.connection_id) if req.connection_id else None,
    )
    return d


@router.get("", response_model=List[DashboardResponse])
async def list_dashboards(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await dashboards_crud.list_dashboards(db, user_id=str(user.id))


@router.get("/{dashboard_id}", response_model=DashboardDetailResponse)
async def get_dashboard(
    dashboard_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    d = await dashboards_crud.get_dashboard(db, dashboard_id, str(user.id))
    if not d:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    widgets = await dashboards_crud.list_widgets(db, dashboard_id)
    return DashboardDetailResponse(
        id=d.id, user_id=d.user_id, tenant_id=d.tenant_id,
        connection_id=d.connection_id, name=d.name,
        created_at=d.created_at, updated_at=d.updated_at,
        widgets=widgets,
    )


@router.patch("/{dashboard_id}", response_model=DashboardResponse)
async def update_dashboard(
    dashboard_id: str,
    req: DashboardUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    d = await dashboards_crud.update_dashboard(
        db, dashboard_id, str(user.id),
        name=req.name,
        connection_id=str(req.connection_id) if req.connection_id else None,
    )
    if not d:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return d


@router.delete("/{dashboard_id}", response_model=StatusResponse)
async def delete_dashboard(
    dashboard_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ok = await dashboards_crud.delete_dashboard(db, dashboard_id, str(user.id))
    if not ok:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return StatusResponse(status="success", message="Dashboard deleted")


# ── Widgets ───────────────────────────────────────────────────────

@router.post("/{dashboard_id}/widgets", response_model=WidgetResponse, status_code=status.HTTP_201_CREATED)
async def add_widget(
    dashboard_id: str,
    req: WidgetCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Verify dashboard ownership
    d = await dashboards_crud.get_dashboard(db, dashboard_id, str(user.id))
    if not d:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    w = await dashboards_crud.create_widget(
        db, dashboard_id=dashboard_id,
        query_id=str(req.query_id) if req.query_id else None,
        title=req.title, chart_type=req.chart_type,
        config=req.config.model_dump(exclude_none=True),
        grid_x=req.grid_x, grid_y=req.grid_y, grid_w=req.grid_w, grid_h=req.grid_h,
    )
    return w


@router.put("/{dashboard_id}/widgets/{widget_id}", response_model=WidgetResponse)
async def update_widget(
    dashboard_id: str,
    widget_id: str,
    req: WidgetUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    d = await dashboards_crud.get_dashboard(db, dashboard_id, str(user.id))
    if not d:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    updates = req.model_dump(exclude_none=True)
    if "config" in updates:
        updates["config"] = updates["config"]  # already a dict from pydantic
    w = await dashboards_crud.update_widget(db, widget_id, dashboard_id, **updates)
    if not w:
        raise HTTPException(status_code=404, detail="Widget not found")
    return w


@router.delete("/{dashboard_id}/widgets/{widget_id}", response_model=StatusResponse)
async def delete_widget(
    dashboard_id: str,
    widget_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    d = await dashboards_crud.get_dashboard(db, dashboard_id, str(user.id))
    if not d:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    ok = await dashboards_crud.delete_widget(db, widget_id, dashboard_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Widget not found")
    return StatusResponse(status="success", message="Widget deleted")


@router.post("/{dashboard_id}/layout", response_model=StatusResponse)
async def save_layout(
    dashboard_id: str,
    req: BulkLayoutRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Bulk-update widget grid positions after drag/resize."""
    d = await dashboards_crud.get_dashboard(db, dashboard_id, str(user.id))
    if not d:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    await dashboards_crud.bulk_update_layout(
        db, dashboard_id,
        [item.model_dump() for item in req.layout],
    )
    return StatusResponse(status="success", message="Layout saved")


@router.get("/{dashboard_id}/widgets/{widget_id}/data", response_model=ReportDataResponse)
async def get_widget_data(
    dashboard_id: str,
    widget_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Execute the widget's saved query and return chart-ready data."""
    d = await dashboards_crud.get_dashboard(db, dashboard_id, str(user.id))
    if not d:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    w = await dashboards_crud.get_widget(db, widget_id, dashboard_id)
    if not w:
        raise HTTPException(status_code=404, detail="Widget not found")
    if not w.query_id:
        raise HTTPException(status_code=400, detail="Widget has no saved query")

    # Reuse the report execution logic — build a duck-typed object
    from types import SimpleNamespace
    from backend.models.query import Query
    from backend.models.db_connection import DBConnection
    from sqlalchemy.future import select as sa_select

    # Resolve connection_id: widget → dashboard → first connection
    conn_id = d.connection_id
    if not conn_id:
        raise HTTPException(status_code=400, detail="Dashboard has no database connection")

    fake_report = SimpleNamespace(
        query_id=w.query_id,
        connection_id=conn_id,
        chart_type=w.chart_type,
        chart_config=w.config or {},
    )
    try:
        results = await execute_report_query(db=db, report=fake_report)
        cfg = dict(w.config or {})
        if "x_axis" in results:
            cfg["x_axis"] = results["x_axis"]
        if "y_axis" in results:
            cfg["y_axis"] = results["y_axis"]
        return ReportDataResponse(
            report_id=w.id,
            data=results["rows"],
            chart_type=w.chart_type,
            chart_config=cfg,
            row_count=results["row_count"],
            execution_time_ms=int(results.get("execution_time_ms", 0)),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to execute widget query")
