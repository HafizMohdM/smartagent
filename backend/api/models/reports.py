from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class ReportBase(BaseModel):
    report_name: str
    chart_type: str
    chart_config: Dict[str, Any]
    query_id: Optional[UUID] = None
    connection_id: Optional[UUID] = None

class ReportCreateRequest(ReportBase):
    pass

class ReportResponse(ReportBase):
    id: UUID
    user_id: UUID
    tenant_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

from backend.api.models.responses import SQLDataContract

class ReportDataResponse(BaseModel):
    report_id: UUID
    results: SQLDataContract
    chart_type: str
    chart_config: Dict[str, Any]
    cache_status: Optional[str] = "MISS"
    request_id: Optional[str] = None


class SystemStatisticsResponse(BaseModel):
    queries_today: int
    avg_execution_time: float
    success_rate: float
    model_config = ConfigDict(from_attributes=True)
