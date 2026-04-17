import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, Table
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from backend.models.base import Base

# Many-to-many relationship between queries and connections
query_connections = Table(
    "query_connections",
    Base.metadata,
    Column("query_id", UUID(as_uuid=True), ForeignKey("queries.id", ondelete="CASCADE"), primary_key=True),
    Column("connection_id", UUID(as_uuid=True), ForeignKey("db_connections.id", ondelete="CASCADE"), primary_key=True),
)

class Query(Base):
    __tablename__ = "queries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    query_text = Column(String, nullable=False) # Natural language query
    generated_sql = Column(Text, nullable=True) # [NEW] Single source of truth for dynamic execution
    username = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    executions = relationship("QueryExecution", back_populates="query", cascade="all, delete-orphan")
    widgets = relationship("DashboardWidget", back_populates="query")
    connections = relationship("DBConnection", secondary=query_connections, backref="queries")

    # Transient attributes (not persisted) used for dynamic execution responses
    results = None
    failed_sources = None
    execution_stats = None


class QueryExecution(Base):
    """
    Execution audit log. 
    [REFACTORED] Stores execution metadata only. No result snapshots.
    """
    __tablename__ = "query_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id = Column(UUID(as_uuid=True), ForeignKey("queries.id", ondelete="CASCADE"), nullable=False)
    database_name = Column(String, nullable=False)
    sql = Column(Text, nullable=True)
    status = Column(String, nullable=False) # e.g. "success", "failed"
    # result_json REMOVED to prevent data duplication/staleness
    error = Column(Text, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    row_count = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    query = relationship("Query", back_populates="executions")

