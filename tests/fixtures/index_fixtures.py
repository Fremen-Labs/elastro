"""
Test fixtures for indices.
"""

# Sample valid index settings
VALID_INDEX_SETTINGS = {
    "settings": {
        "number_of_shards": 3,
        "number_of_replicas": 1,
        "refresh_interval": "1s",
    }
}

# Sample valid index mappings
VALID_INDEX_MAPPINGS = {
    "mappings": {
        "properties": {
            "title": {"type": "text"},
            "content": {"type": "text"},
            "date": {"type": "date"},
            "tags": {"type": "keyword"},
            "views": {"type": "integer"},
        }
    }
}

# Combined valid index creation body
VALID_INDEX_BODY = {**VALID_INDEX_SETTINGS, **VALID_INDEX_MAPPINGS}

# Invalid index settings (wrong type)
INVALID_INDEX_SETTINGS = {
    "settings": {"number_of_shards": "not_a_number", "number_of_replicas": 1}
}

# Mock index response from Elasticsearch
MOCK_INDEX_CREATION_RESPONSE = {
    "acknowledged": True,
    "shards_acknowledged": True,
    "index": "test-index",
}

# Mock get index response
MOCK_GET_INDEX_RESPONSE = {
    "test-index": {
        "aliases": {},
        "mappings": VALID_INDEX_MAPPINGS["mappings"],
        "settings": {
            "index": {
                "number_of_shards": "3",
                "number_of_replicas": "1",
                "refresh_interval": "1s",
                "creation_date": "1619712000000",
                "uuid": "jHrKDYjTSSmSBIvd7Kn1AQ",
                "version": {"created": "7100099"},
            }
        },
    }
}
