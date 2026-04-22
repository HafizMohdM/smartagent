import logging
from typing import List, Optional, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.models.dashboard import Dashboard, DashboardWidget

logger = logging.getLogger(__name__)


# ── Dashboard CRUD ────────────────────────────────────────────────

async def create_dashboard(db: AsyncSession, user_id: str, tenant_id: str,
                            name: str, connection_id: Optional[str] = None) -> Dashboard:
    d = Dashboard(user_id=user_id, tenant_id=tenant_id, name=name, connection_id=connection_id)
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return d


async def list_dashboards(db: AsyncSession, user_id: str) -> List[Dashboard]:
    r = await db.execute(select(Dashboard).where(Dashboard.user_id == user_id)
                         .order_by(Dashboard.created_at.desc()))
    return list(r.scalars().all())


async def get_dashboard(db: AsyncSession, dashboard_id: str, user_id: str) -> Optional[Dashboard]:
    r = await db.execute(select(Dashboard).where(
        Dashboard.id == dashboard_id, Dashboard.user_id == user_id))
    return r.scalar_one_or_none()


async def update_dashboard(db: AsyncSession, dashboard_id: str, user_id: str,
                            name: Optional[str] = None,
                            connection_id: Optional[str] = None) -> Optional[Dashboard]:
    d = await get_dashboard(db, dashboard_id, user_id)
    if not d:
        return None
    if name is not None:
        d.name = name
    if connection_id is not None:
        d.connection_id = connection_id
    await db.commit()
    await db.refresh(d)
    return d


async def delete_dashboard(db: AsyncSession, dashboard_id: str, user_id: str) -> bool:
    d = await get_dashboard(db, dashboard_id, user_id)
    if not d:
        return False
    await db.delete(d)
    await db.commit()
    return True


# ── Widget CRUD ───────────────────────────────────────────────────

async def list_widgets(db: AsyncSession, dashboard_id: str) -> List[DashboardWidget]:
    r = await db.execute(select(DashboardWidget)
                         .where(DashboardWidget.dashboard_id == dashboard_id)
                         .order_by(DashboardWidget.grid_y, DashboardWidget.grid_x))
    return list(r.scalars().all())


async def create_widget(db: AsyncSession, dashboard_id: str,
                         query_id: Optional[str], title: str,
                         chart_type: str, config: Dict[str, Any],
                         grid_x: int, grid_y: int, grid_w: int, grid_h: int) -> DashboardWidget:
    w = DashboardWidget(
        dashboard_id=dashboard_id, query_id=query_id,
        title=title, chart_type=chart_type, config=config,
        grid_x=grid_x, grid_y=grid_y, grid_w=grid_w, grid_h=grid_h,
    )
    db.add(w)
    await db.commit()
    await db.refresh(w)
    return w


async def get_widget(db: AsyncSession, widget_id: str, dashboard_id: str) -> Optional[DashboardWidget]:
    r = await db.execute(select(DashboardWidget).where(
        DashboardWidget.id == widget_id,
        DashboardWidget.dashboard_id == dashboard_id))
    return r.scalar_one_or_none()


async def update_widget(db: AsyncSession, widget_id: str, dashboard_id: str,
                         **kwargs) -> Optional[DashboardWidget]:
    w = await get_widget(db, widget_id, dashboard_id)
    if not w:
        return None
    for k, v in kwargs.items():
        if v is not None and hasattr(w, k):
            setattr(w, k, v)
    await db.commit()
    await db.refresh(w)
    return w


async def delete_widget(db: AsyncSession, widget_id: str, dashboard_id: str) -> bool:
    w = await get_widget(db, widget_id, dashboard_id)
    if not w:
        return False
    await db.delete(w)
    await db.commit()
    return True


async def bulk_update_layout(db: AsyncSession, dashboard_id: str,
                              layout: List[Dict[str, Any]]) -> None:
    """Update grid positions for multiple widgets at once."""
    for item in layout:
        w = await get_widget(db, str(item["id"]), dashboard_id)
        if w:
            w.grid_x = item["grid_x"]
            w.grid_y = item["grid_y"]
            w.grid_w = item["grid_w"]
            w.grid_h = item["grid_h"]
    await db.commit()
