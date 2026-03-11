"""
Base tool interface.
Every service tool (Database, Gmail, GitHub, etc.) must subclass BaseTool
and implement `execute()`. This ensures the agent orchestrator can call
any tool through a uniform interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Standardised result envelope returned by every tool."""
    success: bool = True
    data: Any = None
    error: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseTool(ABC):
    """Abstract base class for all agent tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the tool."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Natural-language description used by the planner to select the tool."""
        ...

    @abstractmethod
    async def execute(self, params: Dict[str, Any], session_id: str) -> ToolResult:
        """
        Run the tool with the given parameters.

        Args:
            params: Tool-specific parameters extracted by the planner.
            session_id: The current session ID for retrieving connections/state.

        Returns:
            ToolResult with success status, data, and optional error.
        """
        ...

    def to_schema(self) -> Dict[str, Any]:
        """Return a JSON-serialisable schema describing this tool for the LLM."""
        return {
            "name": self.name,
            "description": self.description,
        }
