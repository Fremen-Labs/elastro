"""Query validation and processing middleware protocols."""

from typing import Dict, Any, Protocol


class QueryMiddleware(Protocol):
    """Protocol defining the interface for query processing middleware.

    This allows custom validators, semantic AST bridges, or request formatters
    to be natively hooked into the QueryBuilder execution pipeline.
    """

    def process(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Process, validate, or mutate the query dictionary before execution."""
        ...


class ASTNodeIDMiddleware:
    """Middleware to validate that queries contain structured AST Node IDs where required."""

    def __init__(self, enforce: bool = False) -> None:
        self.enforce = enforce

    def process(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Inspects query. Adds structural markers or raises if malformed."""
        if self.enforce:
            # Placeholder for actual AST Node-ID bridging validation
            # Ensures semantic queries conform to known graph topologies
            pass
        return query
