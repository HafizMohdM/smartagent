import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.models.base import Base

class SavedQuery(Base):
    __tablename__ = "saved_queries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("db_connections.id", ondelete="CASCADE"), nullable=False)
    query_name = Column(String, nullable=False)
    natural_language_query = Column(String, nullable=False)
    generated_sql = Column(String, nullable=False)
    query_result_snapshot = Column(JSONB, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    row_count = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
