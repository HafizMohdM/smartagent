"""
Dynamic tool registry.
Tools register themselves here at startup. The agent orchestrator
queries the registry to discover available tools and route execution.
Adding a new service = creating a new BaseTool subclass and calling
`ToolRegistry.register(tool)`.
"""

import logging
from typing import Dict, List, Optional

from backend.tools.base import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Singleton registry of all available agent tools."""

    _instance: Optional["ToolRegistry"] = None
    _tools: Dict[str, BaseTool]

    def __new__(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance

    # ── Registration ───────────────────────────────────────────────────

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance. Overwrites if name already exists."""
        self._tools[tool.name] = tool
        logger.info(f"Tool registered: {tool.name}")

    def unregister(self, name: str) -> None:
        """Remove a tool by name."""
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Tool unregistered: {name}")

    # ── Lookup ─────────────────────────────────────────────────────────

    def get(self, name: str) -> Optional[BaseTool]:
        """Retrieve a registered tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, str]]:
        """Return schema descriptions of all registered tools."""
        return [tool.to_schema() for tool in self._tools.values()]

    def list_tool_names(self) -> List[str]:
        """Return names of all registered tools."""
        return list(self._tools.keys())

    @property
    def count(self) -> int:
        return len(self._tools)

    # ── Utility ────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Clear all registered tools (useful for testing)."""
        self._tools.clear()
