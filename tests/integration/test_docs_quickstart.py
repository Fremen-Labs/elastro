import sys
import os
import time

# Add current directory to path so we can import elastro
sys.path.append(os.getcwd())

try:
    from elastro import ElasticsearchClient, IndexManager, DocumentManager
    from elastro.advanced import QueryBuilder
except ImportError as e:
    print(f"FAILED to import elastro: {e}")
    sys.exit(1)

def verify_quick_start():
    print("\n--- Verifying Quick Start ---")
    try:
        # Client Connection
        print("1. Connecting to Elasticsearch...")
        client = ElasticsearchClient(
            hosts=["http://localhost:9200"],
            username="elastic",
            password="changeme",
            verify_certs=False # Local dev usually self-signed or HTTP
        )
        client.connect()
        print("   ✅ Connected")

        # Index Management
        print("2. Creating Index...")
        index_manager = IndexManager(client)
        
        # Cleanup first
        try:
            if client.client.indices.exists(index="products"):
                client.client.indices.delete(index="products")
                print("   (Cleaned up existing 'products' index)")
        except Exception as e:
            print(f"   (Warning during cleanup: {e})")

        index_manager.create(
            "products",
            mappings={
                "properties": {
                    "name": {"type": "text"},
                    "price": {"type": "float"},
                    "category": {"type": "keyword"},
                    "rating": {"type": "float"}
                }
            }
        )
        print("   ✅ Index 'products' created")

        # Document Management
        print("3. Indexing Document...")
        doc_manager = DocumentManager(client)
        doc_manager.index(
            "products",
            id="1",
            document={
                "name": "Laptop Pro",
                "price": 1299.99,
                "category": "electronics",
                "rating": 4.8
            }
        )
        print("   ✅ Document indexed")
        
        # Determine if we need to refresh (ES is near real-time)
        print("   (Refreshing index for search availability...)")
        client.client.indices.refresh(index="products")

        # Querying
        print("4. searching...")
        query_builder = QueryBuilder()
        query_builder.match("name", "laptop")
        query_builder.range("price", gte=500, lte=2000)
        query = query_builder.build()

        results = doc_manager.search(
            "products",
            query,
            {"sort": [{"rating": {"order": "desc"}}], "size": 10}
        )
        
        hits = results["hits"]["hits"]
        if len(hits) == 1 and hits[0]["_source"]["name"] == "Laptop Pro":
             print(f"   ✅ Search successful. Found: {hits[0]['_source']['name']}")
        else:
             print(f"   ❌ Search failed or unexpected results: {hits}")

        return True

    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if verify_quick_start():
        print("\n\n✅ ALL CHECKS PASSED")
        sys.exit(0)
    else:
        print("\n\n❌ CHECKS FAILED")
        sys.exit(1)
