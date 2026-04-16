from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime


# ── Widget schemas ────────────────────────────────────────────────

class WidgetConfig(BaseModel):
    x_axis:    Optional[str] = None
    y_axis:    Optional[str] = None
    value_col: Optional[str] = None

class WidgetCreateRequest(BaseModel):
    dashboard_id:   UUID
    saved_query_id: Optional[UUID] = None
    title:      str = "Widget"
    chart_type: str = "bar"
    config:     WidgetConfig = WidgetConfig()
    grid_x: int = 0
    grid_y: int = 0
    grid_w: int = 6
    grid_h: int = 4

class WidgetUpdateRequest(BaseModel):
    title:      Optional[str]         = None
    chart_type: Optional[str]         = None
    config:     Optional[WidgetConfig] = None
    grid_x:     Optional[int]         = None
    grid_y:     Optional[int]         = None
    grid_w:     Optional[int]         = None
    grid_h:     Optional[int]         = None

class WidgetResponse(BaseModel):
    id:             UUID
    dashboard_id:   UUID
    saved_query_id: Optional[UUID]
    title:      str
    chart_type: str
    config:     Dict[str, Any]
    grid_x: int
    grid_y: int
    grid_w: int
    grid_h: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── Dashboard schemas ─────────────────────────────────────────────

class DashboardCreateRequest(BaseModel):
    name:          str
    connection_id: Optional[UUID] = None

class DashboardUpdateRequest(BaseModel):
    name:          Optional[str]  = None
    connection_id: Optional[UUID] = None

class DashboardResponse(BaseModel):
    id:            UUID
    user_id:       UUID
    tenant_id:     UUID
    connection_id: Optional[UUID]
    name:          str
    created_at:    datetime
    updated_at:    datetime
    model_config = ConfigDict(from_attributes=True)

class DashboardDetailResponse(DashboardResponse):
    widgets: List[WidgetResponse] = []


# ── Bulk layout update ────────────────────────────────────────────

class LayoutItem(BaseModel):
    id:     UUID
    grid_x: int
    grid_y: int
    grid_w: int
    grid_h: int

class BulkLayoutRequest(BaseModel):
    layout: List[LayoutItem]
