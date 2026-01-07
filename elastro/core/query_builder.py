from typing import Dict, Any, List, Optional, Union

class QueryBuilder:
    """Helper class to build Elasticsearch DSL queries from simplified inputs."""

    @staticmethod
    def parse_range(value: str) -> Dict[str, Any]:
        """
        Parse range string like 'gte:10,lte:20' or 'gt:now-1d' into dict.
        """
        parts = value.split(',')
        range_query = {}
        for part in parts:
            if ':' in part:
                op, val = part.split(':', 1)
                if op in ['gt', 'gte', 'lt', 'lte', 'format', 'boost', 'time_zone']:
                    # Try to convert to number if possible
                    try:
                        if '.' in val:
                            range_query[op] = float(val)
                        else:
                            range_query[op] = int(val)
                    except ValueError:
                        # Keep as string (dates, datemath)
                        range_query[op] = val
        return range_query

    @staticmethod
    def build_bool_query(
        must_match: List[str] = None,
        must_match_phrase: List[str] = None,
        must_term: List[str] = None,
        must_terms: List[str] = None,
        must_range: List[str] = None,
        must_prefix: List[str] = None,
        must_wildcard: List[str] = None,
        must_exists: List[str] = None,
        must_ids: List[str] = None,
        must_fuzzy: List[str] = None,
        exclude_match: List[str] = None,
        exclude_term: List[str] = None,
        query_string: str = None
    ) -> Dict[str, Any]:
        """
        Construct a boolean query from various lists of constraints.
        Inputs are usually list of "field=value" strings.
        """
        must_clauses = []
        must_not_clauses = []
        
        # Helper to parse field=value
        def parse_kv(item: str) -> Optional[tuple]:
            if '=' in item:
                return item.split('=', 1)
            return None

        # 1. Match (Text)
        if must_match:
            for m in must_match:
                kv = parse_kv(m)
                if kv:
                    must_clauses.append({"match": {kv[0]: kv[1]}})
        
        # 2. Match Phrase
        if must_match_phrase:
            for m in must_match_phrase:
                kv = parse_kv(m)
                if kv:
                    must_clauses.append({"match_phrase": {kv[0]: kv[1]}})

        # 3. Term (Exact)
        if must_term:
            for m in must_term:
                kv = parse_kv(m)
                if kv:
                    must_clauses.append({"term": {kv[0]: kv[1]}})

        # 4. Terms (Array)
        if must_terms:
            for m in must_terms:
                kv = parse_kv(m)
                if kv:
                    values = [v.strip() for v in kv[1].split(',')]
                    must_clauses.append({"terms": {kv[0]: values}})

        # 5. Range
        if must_range:
            for m in must_range:
                kv = parse_kv(m)
                if kv:
                    r = QueryBuilder.parse_range(kv[1])
                    if r:
                        must_clauses.append({"range": {kv[0]: r}})

        # 6. Prefix
        if must_prefix:
            for m in must_prefix:
                kv = parse_kv(m)
                if kv:
                    must_clauses.append({"prefix": {kv[0]: kv[1]}})

        # 7. Wildcard
        if must_wildcard:
            for m in must_wildcard:
                kv = parse_kv(m)
                if kv:
                    must_clauses.append({"wildcard": {kv[0]: kv[1]}})
        
        # 8. Exists
        if must_exists:
            for field in must_exists:
                must_clauses.append({"exists": {"field": field}})

        # 9. IDs
        if must_ids:
            # must_ids might be comma sep string or list of strings?
            # CLI passes tuple of strings if multiple=True.
            # If user does --ids id1 --ids id2, we get ('id1', 'id2')
            # If user does --ids id1,id2, we get ('id1,id2',)
            all_ids = []
            for chunk in must_ids:
                all_ids.extend([i.strip() for i in chunk.split(',')])
            if all_ids:
                must_clauses.append({"ids": {"values": all_ids}})

        # 10. Fuzzy
        if must_fuzzy:
            for m in must_fuzzy:
                kv = parse_kv(m)
                if kv:
                    must_clauses.append({"fuzzy": {kv[0]: {"value": kv[1]}}})

        # Query String (Top Level)
        if query_string:
            must_clauses.append({"query_string": {"query": query_string}})

        # Excludes / Must Not
        if exclude_match:
            for m in exclude_match:
                kv = parse_kv(m)
                if kv:
                    must_not_clauses.append({"match": {kv[0]: kv[1]}})
        
        if exclude_term:
            for m in exclude_term:
                kv = parse_kv(m)
                if kv:
                    must_not_clauses.append({"term": {kv[0]: kv[1]}})

        # Construct Bool Query
        bool_query = {}
        if must_clauses:
            bool_query["must"] = must_clauses
        if must_not_clauses:
            bool_query["must_not"] = must_not_clauses

        # If simplifiable (only 1 clause and no must_not), unwrap? 
        # No, consistent "bool" return is safer unless empty.
        
        if not bool_query:
            return {"match_all": {}}
            
        return {"bool": bool_query}
