import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from pgvector.sqlalchemy import Vector
from backend.models.base import Base

class TableMetadataStore(Base):
    """
    Persistent store for database table metadata including embeddings for semantic search.
    Tenant-isolated: every row is scoped to (tenant_id, connection_id).
    """
    __tablename__ = "table_metadata_store"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("db_connections.id", ondelete="CASCADE"), nullable=False, index=True)
    
    schema_name = Column(String, nullable=False, default="public")
    table_name = Column(String, nullable=False)
    
    columns = Column(JSONB, nullable=False) # List of column names or structured column info
    description = Column(Text, nullable=True)
    synonyms = Column(ARRAY(String), nullable=False, default=[])
    relationships = Column(JSONB, nullable=True) # Pre-calculated Foreign Key info
    column_embeddings = Column(JSONB, nullable=True)  # {col_name: [float...]} — cached per-column embeddings
    
    embedding = Column(Vector(1536), nullable=False) # OpenAI text-embedding-3-small dimension
    
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('tenant_id', 'connection_id', 'schema_name', 'table_name', name='uq_tenant_connection_schema_table'),
        Index('idx_table_metadata_tenant_conn', 'tenant_id', 'connection_id'),
        Index('idx_table_metadata_embedding', 'embedding', postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'}),
    )
