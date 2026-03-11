"""
Pydantic request models for all API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional


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
    """Send a chat message within a persistent session tied to a connection."""
    connection_id: str = Field(..., description="Database connection ID")
    message: str = Field(..., min_length=1, description="User message / query")

# ── Saved Queries ───────────────────────────────────────────────────

class SavedQueryCreateRequest(BaseModel):
    """Payload to save an executed query."""
    connection_id: str = Field(..., description="Connection ID used")
    query_name: str = Field(..., description="Friendly name for the saved query")
    natural_language_query: str = Field(..., description="Original user question")
    generated_sql: str = Field(..., description="The generated SQL")
    query_result_snapshot: Optional[list] = Field(default=None, description="JSON snapshot of query results")
    execution_time_ms: Optional[int] = Field(default=None, description="Execution time in milliseconds")
    row_count: Optional[int] = Field(default=None, description="Number of rows returned")


# ── Session ─────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    """Request to create a new session."""
    user_id: Optional[str] = Field(default=None, description="User identifier")
