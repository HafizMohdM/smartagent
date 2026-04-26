"""
TenantEmbedding — unified pgvector-backed store for metrics, cache, entities, and relationships.

Tenant-isolated: every row is scoped to (tenant_id, source_id).
Entity/relationship rows have NULL embedding (keyword-only lookup).
Metric/cache rows have embeddings for ANN search via partial HNSW indexes.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from backend.models.base import Base

# Valid type values for CheckConstraint
VALID_TYPES = ('metric', 'cache', 'entity', 'relationship')


class TenantEmbedding(Base):
    __tablename__ = "tenant_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    source_id = Column(String, nullable=False)  # connection_id or 'global'
    type = Column(String, nullable=False)        # metric | cache | entity | relationship
    
    # Unique business key for entities/relationships (e.g., entity name, relationship pair)
    key = Column(String, nullable=True)
    
    content = Column(Text, nullable=False)
    meta_data = Column(JSONB, nullable=True)      # Structured data: SQL snippets, join_on, etc.
    embedding = Column(Vector(1536), nullable=True)  # NULL for entity/relationship (keyword-only)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        # Type safety
        CheckConstraint(
            "type IN ('metric', 'cache', 'entity', 'relationship')",
            name="ck_tenant_embeddings_type"
        ),
        # Prevent duplicate entities/relationships per tenant+source
        UniqueConstraint('tenant_id', 'source_id', 'type', 'key', name='uq_tenant_source_type_key'),
        # Composite index for filtered lookups (all queries use tenant_id + source_id + type)
        Index('idx_tenant_embeddings_lookup', 'tenant_id', 'source_id', 'type'),
        # Partial HNSW index for metric embeddings only
        Index(
            'idx_tenant_embeddings_metric_hnsw', 'embedding',
            postgresql_using='hnsw',
            postgresql_ops={'embedding': 'vector_cosine_ops'},
            postgresql_where="type = 'metric' AND embedding IS NOT NULL",
        ),
        # Partial HNSW index for cache embeddings only
        Index(
            'idx_tenant_embeddings_cache_hnsw', 'embedding',
            postgresql_using='hnsw',
            postgresql_ops={'embedding': 'vector_cosine_ops'},
            postgresql_where="type = 'cache' AND embedding IS NOT NULL",
        ),
    )
