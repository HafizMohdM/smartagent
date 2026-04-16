import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.models.base import Base


class Dashboard(Base):
    __tablename__ = "dashboards"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id",         ondelete="CASCADE"), nullable=False, index=True)
    tenant_id  = Column(UUID(as_uuid=True), ForeignKey("tenants.id",       ondelete="CASCADE"), nullable=False)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("db_connections.id", ondelete="SET NULL"), nullable=True)
    name       = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class DashboardWidget(Base):
    __tablename__ = "dashboard_widgets"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dashboard_id   = Column(UUID(as_uuid=True), ForeignKey("dashboards.id",    ondelete="CASCADE"), nullable=False, index=True)
    saved_query_id = Column(UUID(as_uuid=True), ForeignKey("saved_queries.id", ondelete="SET NULL"), nullable=True)

    # Chart config
    title      = Column(String, nullable=False, default="Widget")
    chart_type = Column(String, nullable=False, default="bar")
    config     = Column(JSONB, nullable=False, default=dict)   # {x_axis, y_axis, value_col, ...}

    # Grid layout  (react-grid-layout compatible)
    grid_x = Column(Integer, nullable=False, default=0)
    grid_y = Column(Integer, nullable=False, default=0)
    grid_w = Column(Integer, nullable=False, default=6)
    grid_h = Column(Integer, nullable=False, default=4)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
