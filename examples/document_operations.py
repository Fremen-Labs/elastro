#!/usr/bin/env python3
"""
Elastro - Document Operations Example

This example demonstrates how to index, retrieve, update, and delete documents
using the DocumentManager class.
"""

from elastro import ElasticsearchClient, IndexManager, DocumentManager


def create_client():
    """Create and connect an Elasticsearch client"""
    client = ElasticsearchClient()
    client.connect()
    return client


def setup_index(client):
    """Create a test index for document operations"""
    index_manager = IndexManager(client)
    index_name = "products"

    # Create the index if it doesn't exist
    if not index_manager.exists(index_name):
        print(f"Creating index '{index_name}'...")
        index_manager.create(
            name=index_name,
            settings={"number_of_shards": 1, "number_of_replicas": 0},
            mappings={
                "properties": {
                    "name": {"type": "text"},
                    "price": {"type": "float"},
                    "description": {"type": "text"},
                    "category": {"type": "keyword"},
                    "tags": {"type": "keyword"},
                    "in_stock": {"type": "boolean"},
                    "created": {"type": "date"},
                }
            },
        )
    else:
        print(f"Index '{index_name}' already exists.")

    return index_name


def index_document(doc_manager, index_name):
    """Index a single document"""
    document = {
        "name": "Laptop",
        "price": 999.99,
        "description": "High-performance laptop with 16GB RAM and 512GB SSD",
        "category": "electronics",
        "tags": ["computer", "laptop", "tech"],
        "in_stock": True,
        "created": "2023-05-01T12:00:00",
    }

    doc_id = "1"
    print(f"Indexing document with ID '{doc_id}'...")
    result = doc_manager.index(index_name, doc_id, document)

    print(f"Document indexed: {result}")
    return doc_id


def bulk_index_documents(doc_manager, index_name):
    """Index multiple documents in bulk"""
    documents = [
        {
            "id": "2",
            "document": {
                "name": "Smartphone",
                "price": 699.99,
                "description": "Latest smartphone with high-resolution camera",
                "category": "electronics",
                "tags": ["phone", "mobile", "tech"],
                "in_stock": True,
                "created": "2023-05-02T12:00:00",
            },
        },
        {
            "id": "3",
            "document": {
                "name": "Headphones",
                "price": 199.99,
                "description": "Noise-cancelling wireless headphones",
                "category": "electronics",
                "tags": ["audio", "wireless", "tech"],
                "in_stock": True,
                "created": "2023-05-03T12:00:00",
            },
        },
        {
            "id": "4",
            "document": {
                "name": "Tablet",
                "price": 499.99,
                "description": "Lightweight tablet with long battery life",
                "category": "electronics",
                "tags": ["tablet", "mobile", "tech"],
                "in_stock": False,
                "created": "2023-05-04T12:00:00",
            },
        },
    ]

    print(f"Bulk indexing {len(documents)} documents...")
    result = doc_manager.bulk_index(index_name, documents)

    print(f"Bulk indexing result: {len(result['items'])} documents indexed")
    return [doc["id"] for doc in documents]


def get_document(doc_manager, index_name, doc_id):
    """Retrieve a document by ID"""
    print(f"Getting document with ID '{doc_id}'...")
    document = doc_manager.get(index_name, doc_id)

    print(f"Retrieved document:")
    print(f"  Name: {document['_source']['name']}")
    print(f"  Price: ${document['_source']['price']}")
    print(f"  Category: {document['_source']['category']}")

    return document


def update_document(doc_manager, index_name, doc_id):
    """Update a document"""
    print(f"Updating document with ID '{doc_id}'...")

    # Partial update
    update_data = {"price": 899.99, "in_stock": False}

    result = doc_manager.update(index_name, doc_id, update_data, partial=True)
    print(f"Update result: {result}")

    # Verify update
    updated_doc = doc_manager.get(index_name, doc_id)
    print(f"Updated price: ${updated_doc['_source']['price']}")
    print(f"Updated stock status: {updated_doc['_source']['in_stock']}")

    return updated_doc


def delete_document(doc_manager, index_name, doc_id):
    """Delete a document"""
    print(f"Deleting document with ID '{doc_id}'...")
    result = doc_manager.delete(index_name, doc_id)

    print(f"Delete result: {result}")

    # Verify deletion
    try:
        doc_manager.get(index_name, doc_id)
        print(f"Document with ID '{doc_id}' still exists (unexpected)")
    except Exception as e:
        print(f"Document with ID '{doc_id}' was successfully deleted")


def bulk_delete_documents(doc_manager, index_name, doc_ids):
    """Delete multiple documents in bulk"""
    print(f"Bulk deleting {len(doc_ids)} documents...")
    result = doc_manager.bulk_delete(index_name, doc_ids)

    print(f"Bulk delete result: {result}")

    # Verify deletion
    for doc_id in doc_ids:
        try:
            doc_manager.get(index_name, doc_id)
            print(f"Document with ID '{doc_id}' still exists (unexpected)")
        except Exception:
            print(f"Document with ID '{doc_id}' was successfully deleted")


def cleanup(client, index_name):
    """Clean up by removing the test index"""
    index_manager = IndexManager(client)
    if index_manager.exists(index_name):
        print(f"Cleaning up: deleting index '{index_name}'...")
        index_manager.delete(index_name)
        print(f"Index '{index_name}' deleted.")


def main():
    """Main function demonstrating document operations"""
    try:
        # Create a client and document manager
        client = create_client()
        doc_manager = DocumentManager(client)

        # Set up test index
        index_name = setup_index(client)

        # Index documents
        doc_id = index_document(doc_manager, index_name)
        bulk_ids = bulk_index_documents(doc_manager, index_name)

        # Get a document
        get_document(doc_manager, index_name, doc_id)

        # Update a document
        update_document(doc_manager, index_name, doc_id)

        # Delete a document
        delete_document(doc_manager, index_name, doc_id)

        # Bulk delete documents
        bulk_delete_documents(doc_manager, index_name, bulk_ids)

        # Clean up
        cleanup(client, index_name)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
