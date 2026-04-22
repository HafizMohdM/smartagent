"""
Pydantic response models for all API endpoints.
"""

from uuid import UUID
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime


# ── Generic ─────────────────────────────────────────────────────────

class StatusResponse(BaseModel):
    """Standard status response."""
    status: str
    message: str


# ── Authentication ──────────────────────────────────────────────────

class LoginResponse(BaseModel):
    """Successful login response with JWT token."""
    success: bool = True
    token: Optional[str] = None
    access_token: str
    token_type: str = "bearer"
    session_id: str
    role: str
    user: Optional[Dict[str, Any]] = None
    expires_in: int = Field(description="Token expiry in seconds")

class UserResponse(BaseModel):
    """User profile response."""
    id: UUID
    name: Optional[str]
    email: str
    role: str
    status: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


# ── Services ────────────────────────────────────────────────────────

class ServiceInfo(BaseModel):
    """Description of an available service."""
    name: str
    type: str
    description: str
    required_fields: List[str]

class ConnectionResponse(BaseModel):
    """Result of a dynamic service connection attempt."""
    status: str
    service: str
    details: Any


class ServiceListResponse(BaseModel):
    """List of available services."""
    services: List[ServiceInfo]


class DBConnectionResponse(BaseModel):
    """Database connection response — includes RBAC fields."""
    id: UUID
    connection_name: str
    db_type: str
    host: str
    port: int
    database_name: str
    username: str
    ssl_enabled: bool
    status: str
    is_admin_owned: bool
    created_by: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True

# ── SQL Data Contract ───────────────────────────────────────────────

class SQLDataContract(BaseModel):
    """
    Strict API-level contract for all SQL query results.
    Enforces rows, columns, and meta structure.
    """
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    columns: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(
        default_factory=lambda: {
            "row_count": 0,
            "execution_time_ms": 0,
            "version": "v1"
        }
    )

# ── Saved Queries ───────────────────────────────────────────────────

class QueryExecutionResponse(BaseModel):
    id: UUID
    query_id: UUID
    database_name: str
    sql: Optional[str] = None
    status: str
    # result_json REMOVED - data must be fetched dynamically via /data endpoints
    error: Optional[str] = None

    execution_time_ms: Optional[int] = None
    row_count: Optional[int] = None
    created_at: datetime
    
    # Optional strict result data for detail views
    result: Optional[SQLDataContract] = None

    class Config:
        from_attributes = True

class SavedQueryResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    username: str
    title: str
    query_text: str
    generated_sql: str
    connection_ids: List[UUID] = []
    created_at: datetime
    executions: List[QueryExecutionResponse] = []
    
    # NEW fields for dynamic execution
    results: Optional[List[SQLDataContract]] = None
    failed_sources: Optional[List[Dict[str, Any]]] = None
    execution_stats: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# ── Chat ────────────────────────────────────────────────────────────

class ChatResponse(BaseModel):
    """Agent response to a user query."""
    response: str
    summary: Optional[str] = None
    sql: Optional[str] = None
    # Strictly enforced result structure
    results: Optional[SQLDataContract] = None
    chart: Optional[Dict[str, Any]] = None
    tool_used: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ChatMessageItemResponse(BaseModel):
    """Single chat message."""
    id: UUID
    role: str
    message_text: str
    generated_sql: Optional[str] = None
    # Strictly enforced result snapshot
    query_result_snapshot: Optional[SQLDataContract] = None
    created_at: datetime

    class Config:
        from_attributes = True



class ChatSessionMetaResponse(BaseModel):
    """Chat session metadata without messages."""
    session_id: UUID
    connection_id: Optional[UUID] = None
    session_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatSessionResponse(BaseModel):
    """Chat session with message history."""
    session_id: UUID
    connection_id: Optional[UUID] = None
    session_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageItemResponse] = []

    class Config:
        from_attributes = True


class ChatMessageSendResponse(BaseModel):
    """Response after sending a chat message."""
    user_message: ChatMessageItemResponse
    agent_message: ChatMessageItemResponse
    tool_used: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── Health ──────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """System health check response."""
    status: str = "healthy"
    version: str = "1.0.0"
    services: Dict[str, str] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
