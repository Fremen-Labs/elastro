"""
Test fixtures for datastreams.
"""

# Sample valid datastream settings
VALID_DATASTREAM_SETTINGS = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 1,
        "refresh_interval": "5s",
    },
    "mappings": {
        "properties": {
            "@timestamp": {"type": "date"},
            "message": {"type": "text"},
            "level": {"type": "keyword"},
            "service": {"type": "keyword"},
            "trace_id": {"type": "keyword"},
        }
    },
}

# Invalid datastream settings
INVALID_DATASTREAM_SETTINGS = {
    "settings": {"number_of_shards": "not_a_number"},
    "mappings": {},
}

# Mock datastream creation response
MOCK_DATASTREAM_CREATE_RESPONSE = {"acknowledged": True}

# Mock datastream get response
MOCK_DATASTREAM_GET_RESPONSE = {
    "data_streams": [
        {
            "name": "test-datastream",
            "timestamp_field": {"name": "@timestamp"},
            "indices": [
                {
                    "index_name": ".ds-test-datastream-000001",
                    "index_uuid": "tqkjLps7R7CRtYCCHxB3nA",
                }
            ],
            "generation": 1,
            "status": "GREEN",
            "template": "test-datastream-template",
        }
    ]
}

# Mock datastream list response
MOCK_DATASTREAM_LIST_RESPONSE = {
    "data_streams": [
        {
            "name": "test-datastream",
            "timestamp_field": {"name": "@timestamp"},
            "indices": [
                {
                    "index_name": ".ds-test-datastream-000001",
                    "index_uuid": "tqkjLps7R7CRtYCCHxB3nA",
                }
            ],
            "generation": 1,
            "status": "GREEN",
            "template": "test-datastream-template",
        },
        {
            "name": "logs-datastream",
            "timestamp_field": {"name": "@timestamp"},
            "indices": [
                {
                    "index_name": ".ds-logs-datastream-000001",
                    "index_uuid": "jFe345sRQICrtGHHxA6bZ",
                }
            ],
            "generation": 1,
            "status": "GREEN",
            "template": "logs-datastream-template",
        },
    ]
}

# Mock datastream rollover response
MOCK_DATASTREAM_ROLLOVER_RESPONSE = {
    "acknowledged": True,
    "shards_acknowledged": True,
    "old_index": ".ds-test-datastream-000001",
    "new_index": ".ds-test-datastream-000002",
    "rolled_over": True,
    "dry_run": False,
    "condition_status": {"max_age": True, "max_docs": False, "max_size": False},
}
