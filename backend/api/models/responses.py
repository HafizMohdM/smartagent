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
    access_token: str
    token_type: str = "bearer"
    session_id: str
    expires_in: int = Field(description="Token expiry in seconds")

class UserResponse(BaseModel):
    """User profile response."""
    id: UUID
    name: Optional[str]
    email: str
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
    """Service connection result."""
    id: UUID
    connection_name: str
    db_type: str
    host: str
    port: int
    database_name: str
    username: str
    ssl_enabled: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# ── Saved Queries ───────────────────────────────────────────────────

class SavedQueryResponse(BaseModel):
    id: UUID
    connection_id: UUID
    query_name: str
    natural_language_query: str
    generated_sql: str
    query_result_snapshot: Optional[list]
    execution_time_ms: Optional[int]
    row_count: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Chat ────────────────────────────────────────────────────────────

class ChatResponse(BaseModel):
    """Agent response to a user query."""
    response: str
    tool_used: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ChatMessageItemResponse(BaseModel):
    """Single chat message."""
    id: UUID
    role: str
    message_text: str
    generated_sql: Optional[str] = None
    query_result_snapshot: Optional[Any] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionResponse(BaseModel):
    """Chat session with message history."""
    session_id: UUID
    connection_id: UUID
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
