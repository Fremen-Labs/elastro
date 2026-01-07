import sys
import os
import json
from elastro import ElasticsearchClient, IndexManager, DocumentManager

def test_api_actions():
    print("----------------------------------------------------------------")
    print("Starting API Verification")
    print("----------------------------------------------------------------")

    # 1. Connection
    print("\n[1] Testing Client Connection...")
    try:
        client = ElasticsearchClient(
            hosts=["http://localhost:9200"],
            auth={"username": "elastic", "password": "elastic_password"},
            verify_certs=False
        )
        client.connect()
        print("✅ Client connected successfully")
    except Exception as e:
        print(f"❌ Client connection failed: {e}")
        return

    # 2. Index Management
    print("\n[2] Testing Index Management...")
    index_manager = IndexManager(client)
    test_index = "test-products"

    # Clean up if exists
    if index_manager.exists(test_index):
        index_manager.delete(test_index)
        print(f"   Cleaned up existing index '{test_index}'")

    # Create
    try:
        index_manager.create(
            name=test_index,
            settings={"number_of_shards": 1, "number_of_replicas": 0},
            mappings={
                "properties": {
                    "name": {"type": "text"},
                    "price": {"type": "float"},
                    "created": {"type": "date"}
                }
            }
        )
        print("✅ Index created successfully")
    except Exception as e:
        print(f"❌ Index creation failed: {e}")

    # Exists
    exists = index_manager.exists(test_index)
    if exists:
        print("✅ Index exists check passed")
    else:
        print("❌ Index exists check failed")

    # 3. Document Operations
    print("\n[3] Testing Document Operations...")
    doc_manager = DocumentManager(client)

    # Index Document
    try:
        doc_manager.index(
            index=test_index,
            id="1",
            document={
                "name": "Test Laptop",
                "price": 999.99,
                "created": "2023-01-01T12:00:00"
            }
        )
        print("✅ Document indexed successfully")
    except Exception as e:
        print(f"❌ Document indexing failed: {e}")

    # Refresh index to make document searchable immediately
    try:
        client.client.indices.refresh(index=test_index)
        print("   Index refreshed")
    except Exception as e:
        print(f"⚠️ Failed to refresh index: {e}")

    # Search
    try:
        results = doc_manager.search(
            index=test_index,
            query={"match": {"name": "Laptop"}}
        )
        # Handle different response structures if necessary, assuming standard SearchResponse
        hits = results.get('hits', {}).get('hits', [])
        if len(hits) > 0:
            print(f"✅ Search successful. Found {len(hits)} documents")
        else:
            print("❌ Search returned 0 results")
    except Exception as e:
        print(f"❌ Search failed: {e}")

    # 4. Cleanup
    print("\n[4] Cleanup...")
    try:
        index_manager.delete(test_index)
        print("✅ Test index deleted")
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")

if __name__ == "__main__":
    try:
        test_api_actions()
    except ImportError as e:
         print(f"❌ Import Error: {e}. Make sure 'elastro' is installed.")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
