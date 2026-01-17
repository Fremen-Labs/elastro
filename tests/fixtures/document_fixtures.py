"""
Test fixtures for documents.
"""

# Sample valid document
VALID_DOCUMENT = {
    "title": "Test Document",
    "content": "This is a test document for unit testing",
    "date": "2023-05-15T12:00:00",
    "tags": ["test", "document"],
    "views": 0,
}

# Another valid document for bulk operations
VALID_DOCUMENT_2 = {
    "title": "Another Test Document",
    "content": "This is another test document for bulk operations",
    "date": "2023-05-16T14:30:00",
    "tags": ["test", "bulk"],
    "views": 5,
}

# Sample invalid document (wrong data type)
INVALID_DOCUMENT = {
    "title": "Invalid Document",
    "content": "This document has an invalid date",
    "date": "not-a-date",
    "tags": ["invalid"],
    "views": "not-a-number",
}

# Sample document list for bulk operations
BULK_DOCUMENTS = [
    {"_id": "doc1", "_source": VALID_DOCUMENT},
    {"_id": "doc2", "_source": VALID_DOCUMENT_2},
]

# Bulk documents in the format expected by ES bulk API
ES_BULK_DOCUMENTS = [
    {"index": {"_index": "test-index", "_id": "doc1"}},
    VALID_DOCUMENT,
    {"index": {"_index": "test-index", "_id": "doc2"}},
    VALID_DOCUMENT_2,
]

# Mock document GET response
MOCK_GET_DOCUMENT_RESPONSE = {
    "_index": "test-index",
    "_type": "_doc",
    "_id": "doc1",
    "_version": 1,
    "_seq_no": 0,
    "_primary_term": 1,
    "found": True,
    "_source": VALID_DOCUMENT,
}

# Mock document index response
MOCK_INDEX_DOCUMENT_RESPONSE = {
    "_index": "test-index",
    "_type": "_doc",
    "_id": "doc1",
    "_version": 1,
    "result": "created",
    "_shards": {"total": 2, "successful": 2, "failed": 0},
    "_seq_no": 0,
    "_primary_term": 1,
}

# Mock bulk index response
MOCK_BULK_INDEX_RESPONSE = {
    "took": 30,
    "errors": False,
    "items": [
        {
            "index": {
                "_index": "test-index",
                "_type": "_doc",
                "_id": "doc1",
                "_version": 1,
                "result": "created",
                "_shards": {"total": 2, "successful": 2, "failed": 0},
                "_seq_no": 0,
                "_primary_term": 1,
                "status": 201,
            }
        },
        {
            "index": {
                "_index": "test-index",
                "_type": "_doc",
                "_id": "doc2",
                "_version": 1,
                "result": "created",
                "_shards": {"total": 2, "successful": 2, "failed": 0},
                "_seq_no": 1,
                "_primary_term": 1,
                "status": 201,
            }
        },
    ],
}

# Mock search response
MOCK_SEARCH_RESPONSE = {
    "took": 5,
    "timed_out": False,
    "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
    "hits": {
        "total": {"value": 1, "relation": "eq"},
        "max_score": 1.0,
        "hits": [
            {
                "_index": "test-index",
                "_type": "_doc",
                "_id": "doc1",
                "_score": 1.0,
                "_source": VALID_DOCUMENT,
            }
        ],
    },
}
