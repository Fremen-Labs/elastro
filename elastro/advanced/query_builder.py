"""Query builder for Elasticsearch queries."""

from typing import Any, Dict, List, Optional, Union


class QueryBuilder:
    """Builder for Elasticsearch query DSL.

    This class provides a fluent interface for building Elasticsearch queries without
    having to manually construct complex nested dictionaries.
    """

    def __init__(self) -> None:
        """Initialize an empty query builder."""
        self._query: Dict[str, Any] = {}

    def match(self, field: str, value: Any, operator: str = "or", fuzziness: Optional[str] = None) -> "QueryBuilder":
        """Create a match query.

        Args:
            field: The field to query
            value: The value to match
            operator: The operator to use (or, and)
            fuzziness: Optional fuzziness parameter (AUTO, 0, 1, 2)

        Returns:
            Self for method chaining
        """
        match_query: Dict[str, Any] = {"match": {field: {"query": value, "operator": operator}}}
        if fuzziness:
            match_query["match"][field]["fuzziness"] = fuzziness

        self._query = match_query
        return self

    def match_phrase(self, field: str, value: str, slop: int = 0) -> "QueryBuilder":
        """Create a match_phrase query.

        Args:
            field: The field to query
            value: The phrase to match
            slop: The number of positional edits allowed

        Returns:
            Self for method chaining
        """
        self._query = {
            "match_phrase": {
                field: {
                    "query": value,
                    "slop": slop
                }
            }
        }
        return self

    def term(self, field: str, value: Any) -> "QueryBuilder":
        """Create a term query (exact match).

        Args:
            field: The field to query
            value: The value for exact matching

        Returns:
            Self for method chaining
        """
        self._query = {"term": {field: value}}
        return self

    def terms(self, field: str, values: List[Any]) -> "QueryBuilder":
        """Create a terms query (multiple exact matches).

        Args:
            field: The field to query
            values: List of values for exact matching

        Returns:
            Self for method chaining
        """
        self._query = {"terms": {field: values}}
        return self

    def range(self, field: str, gte: Optional[Any] = None, lte: Optional[Any] = None,
              gt: Optional[Any] = None, lt: Optional[Any] = None) -> "QueryBuilder":
        """Create a range query.

        Args:
            field: The field to query
            gte: Greater than or equal value
            lte: Less than or equal value
            gt: Greater than value
            lt: Less than value

        Returns:
            Self for method chaining
        """
        range_params = {}
        if gte is not None:
            range_params["gte"] = gte
        if lte is not None:
            range_params["lte"] = lte
        if gt is not None:
            range_params["gt"] = gt
        if lt is not None:
            range_params["lt"] = lt

        self._query = {"range": {field: range_params}}
        return self

    def exists(self, field: str) -> "QueryBuilder":
        """Create an exists query.

        Args:
            field: The field that must exist

        Returns:
            Self for method chaining
        """
        self._query = {"exists": {"field": field}}
        return self

    def wildcard(self, field: str, value: str) -> "QueryBuilder":
        """Create a wildcard query.

        Args:
            field: The field to query
            value: The wildcard pattern (e.g., "ki*y")

        Returns:
            Self for method chaining
        """
        self._query = {"wildcard": {field: value}}
        return self

    def bool(self) -> "BoolQueryBuilder":
        """Start building a bool query.

        Returns:
            A BoolQueryBuilder instance
        """
        return BoolQueryBuilder(self)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the built query to a dictionary.

        Returns:
            The complete query as a dictionary
        """
        return self._query

    def build(self) -> Dict[str, Any]:
        """Build the query and return the dictionary representation.

        Returns:
            The complete query as a dictionary
        """
        return self.to_dict()


class BoolQueryBuilder:
    """Builder for Elasticsearch bool queries."""

    def __init__(self, parent: QueryBuilder) -> None:
        """Initialize a bool query builder.

        Args:
            parent: The parent QueryBuilder
        """
        self._parent = parent
        self._must: List[Dict[str, Any]] = []
        self._must_not: List[Dict[str, Any]] = []
        self._should: List[Dict[str, Any]] = []
        self._filter: List[Dict[str, Any]] = []
        self._minimum_should_match: Optional[Union[int, str]] = None

    def must(self, query: Union[QueryBuilder, Dict[str, Any]]) -> "BoolQueryBuilder":
        """Add a must clause to the bool query.

        Args:
            query: QueryBuilder or dict representing the query

        Returns:
            Self for method chaining
        """
        if isinstance(query, QueryBuilder):
            self._must.append(query.to_dict())
        else:
            self._must.append(query)
        return self

    def must_not(self, query: Union[QueryBuilder, Dict[str, Any]]) -> "BoolQueryBuilder":
        """Add a must_not clause to the bool query.

        Args:
            query: QueryBuilder or dict representing the query

        Returns:
            Self for method chaining
        """
        if isinstance(query, QueryBuilder):
            self._must_not.append(query.to_dict())
        else:
            self._must_not.append(query)
        return self

    def should(self, query: Union[QueryBuilder, Dict[str, Any]]) -> "BoolQueryBuilder":
        """Add a should clause to the bool query.

        Args:
            query: QueryBuilder or dict representing the query

        Returns:
            Self for method chaining
        """
        if isinstance(query, QueryBuilder):
            self._should.append(query.to_dict())
        else:
            self._should.append(query)
        return self

    def filter(self, query: Union[QueryBuilder, Dict[str, Any]]) -> "BoolQueryBuilder":
        """Add a filter clause to the bool query.

        Args:
            query: QueryBuilder or dict representing the query

        Returns:
            Self for method chaining
        """
        if isinstance(query, QueryBuilder):
            self._filter.append(query.to_dict())
        else:
            self._filter.append(query)
        return self

    def minimum_should_match(self, value: Union[int, str]) -> "BoolQueryBuilder":
        """Set the minimum_should_match parameter.

        Args:
            value: Number of should clauses that must match

        Returns:
            Self for method chaining
        """
        self._minimum_should_match = value
        return self

    def build(self) -> QueryBuilder:
        """Build the bool query and return to the parent builder.

        Returns:
            The parent QueryBuilder with the bool query set
        """
        bool_query: Dict[str, Any] = {}

        if self._must:
            bool_query["must"] = self._must
        if self._must_not:
            bool_query["must_not"] = self._must_not
        if self._should:
            bool_query["should"] = self._should
        if self._filter:
            bool_query["filter"] = self._filter
        if self._minimum_should_match is not None:
            bool_query["minimum_should_match"] = self._minimum_should_match

        self._parent._query = {"bool": bool_query}
        return self._parent
