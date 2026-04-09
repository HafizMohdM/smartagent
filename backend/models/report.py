import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.models.base import Base

class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("db_connections.id", ondelete="CASCADE"), nullable=False)
    saved_query_id = Column(UUID(as_uuid=True), ForeignKey("saved_queries.id", ondelete="SET NULL"), nullable=True)
    report_name = Column(String, nullable=False)
    chart_type = Column(String, nullable=False) # bar, line, pie, table
    chart_config = Column(JSONB, nullable=False) # { x_axis: str, y_axis: str, grouping?: str }
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
