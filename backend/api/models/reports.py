from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class ReportBase(BaseModel):
    report_name: str
    chart_type: str
    chart_config: Dict[str, Any]
    saved_query_id: UUID
    connection_id: UUID

class ReportCreateRequest(ReportBase):
    pass

class ReportResponse(ReportBase):
    id: UUID
    user_id: UUID
    tenant_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ReportDataResponse(BaseModel):
    report_id: UUID
    data: List[Dict[str, Any]]
    chart_type: str
    chart_config: Dict[str, Any]
    row_count: int
    execution_time_ms: int

class SystemStatisticsResponse(BaseModel):
    queries_today: int
    avg_execution_time: float
    success_rate: float
    model_config = ConfigDict(from_attributes=True)
