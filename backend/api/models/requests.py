"""
Pydantic request models for all API endpoints.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Any, List


# ── Authentication ──────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """Login credentials."""
    email: str = Field(..., min_length=1, description="Email address")
    password: str = Field(..., min_length=1, description="Password")

class UserRegisterRequest(BaseModel):
    """User registration payload."""
    name: Optional[str] = Field(default=None, description="Full name")
    email: str = Field(..., min_length=1, description="Email address")
    phone_number: Optional[str] = Field(default=None, description="Phone number")
    password: str = Field(..., min_length=6, description="Password")
    role: Optional[str] = Field(default="user", description="Role: 'user' or 'manager'")

# ── Service Connection ──────────────────────────────────────────────

class DatabaseConnectionRequest(BaseModel):
    """Payload to connect to a database for a session."""
    host: str = Field(..., description="Database host address")
    port: int = Field(default=5432, description="Database port")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    password: str = Field(..., description="Database password")

class ConnectionCreateRequest(BaseModel):
    """Payload to create a database connection."""
    connection_name: str = Field(..., description="Friendly name for the connection")
    db_type: str = Field(default="postgresql", description="Database type (e.g., postgresql)")
    host: str = Field(..., description="Database host address")
    port: int = Field(default=5432, ge=1, le=65535, description="Database port")
    database_name: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    password: str = Field(..., description="Database password")
    ssl_enabled: bool = Field(default=False, description="Use SSL for connection")
    extra_params: Optional[dict] = Field(default=None, description="Additional connection params")

class ConnectionUpdateRequest(BaseModel):
    """Payload to update an existing database connection."""
    connection_name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    database_name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    ssl_enabled: Optional[bool] = None
class ServiceConnectionRequest(BaseModel):
    """Generic wrapper for connecting to any service."""
    service_type: str = Field(..., description="Type of service (e.g., 'database')")
    credentials: dict = Field(..., description="Service-specific credentials")


# ── Chat ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """User query sent to the agent."""
    message: str = Field(..., min_length=1, description="User message / query")
    session_id: str = Field(..., description="Active session ID")
    connection_id: Optional[str] = Field(default=None, description="Database connection ID to use")

class ChatMessageRequest(BaseModel):
    """Send a chat message within a persistent session (connection is optional)."""
    connection_id: Optional[str] = Field(default=None, description="Single database connection ID")
    connection_ids: Optional[List[str]] = Field(default=None, description="Multiple connection IDs for multi-DB queries")
    session_id: Optional[str] = Field(default=None, description="Active session ID, if continuing a thread")
    message: str = Field(..., min_length=1, description="User message / query")

# ── Saved Queries ───────────────────────────────────────────────────

class SavedQueryCreateRequest(BaseModel):
    """Payload to save an executed query."""
    connection_id: str = Field(..., description="Connection ID used")
    title: str = Field(..., description="Friendly name for the saved query")
    natural_language_query: str = Field(..., description="Original user question")
    query: str = Field(..., min_length=1, description="The generated SQL")

    @validator("query")
    def query_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("SQL definition cannot be empty or just whitespace")
        return v.strip()
    query_result_snapshot: Optional[Any] = Field(default=None, description="JSON snapshot of query results")
    execution_time_ms: Optional[int] = Field(default=None, description="Execution time in milliseconds")
    row_count: Optional[int] = Field(default=None, description="Number of rows returned")


class ExecuteQueryRequest(BaseModel):
    """Payload to execute an arbitrary SQL query."""
    sql: str = Field(..., min_length=1, description="The SQL query to execute")
    connection_ids: List[str] = Field(..., min_length=1, description="List of connection IDs to run against")


class SavedQueryUpdateRequest(BaseModel):
    """Payload to update a saved query's metadata."""
    title: Optional[str] = Field(default=None, description="Updated friendly name")
    query: Optional[str] = Field(default=None, description="Updated SQL query")


# ── Session ─────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    """Request to create a new session."""
    user_id: Optional[str] = Field(default=None, description="User identifier")


class ChatSessionRenameRequest(BaseModel):
    """Request to rename a chat session."""
    session_name: str = Field(..., min_length=1, description="New name for the session")
