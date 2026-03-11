"""
Service permission control.
Enforces operation-level permissions per service type to ensure
read-only access for databases and appropriate controls for future services.
"""

import logging
from enum import Enum
from typing import Dict, Set

logger = logging.getLogger(__name__)


class ServiceType(str, Enum):
    DATABASE = "database"
    GMAIL = "gmail"
    GITHUB = "github"
    HRMS = "hrms"
    BROWSER = "browser"


class Operation(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    EXECUTE = "execute"


# Default permission matrix — each service type maps to its allowed operations.
DEFAULT_PERMISSIONS: Dict[ServiceType, Set[Operation]] = {
    ServiceType.DATABASE: {Operation.READ},
    ServiceType.GMAIL: {Operation.READ},
    ServiceType.GITHUB: {Operation.READ},
    ServiceType.HRMS: {Operation.READ},
    ServiceType.BROWSER: {Operation.READ, Operation.EXECUTE},
}


class PermissionManager:
    """Enforces operation-level access control per service type."""

    def __init__(self, permissions: Dict[ServiceType, Set[Operation]] | None = None):
        self._permissions = permissions or DEFAULT_PERMISSIONS

    def check_permission(self, service: str, operation: str) -> bool:
        """Check whether an operation is allowed for the given service."""
        try:
            svc = ServiceType(service)
            op = Operation(operation)
        except ValueError:
            logger.warning(f"Unknown service '{service}' or operation '{operation}'")
            return False

        allowed = op in self._permissions.get(svc, set())
        if not allowed:
            logger.warning(
                f"Permission denied: {operation} on {service}. "
                f"Allowed: {self._permissions.get(svc, set())}"
            )
        return allowed

    def get_allowed_operations(self, service: str) -> Set[str]:
        """Return the set of allowed operations for a service."""
        try:
            svc = ServiceType(service)
        except ValueError:
            return set()
        return {op.value for op in self._permissions.get(svc, set())}
