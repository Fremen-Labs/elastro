#!/usr/bin/env python3
"""
Elastro - Index Management Example

This example demonstrates how to create, manage, and delete indices
using the IndexManager class.
"""

from elastro import ElasticsearchClient, IndexManager


def create_client():
    """Create and connect an Elasticsearch client"""
    client = ElasticsearchClient()
    client.connect()
    return client


def create_basic_index(index_manager):
    """Create a basic index with default settings"""
    index_name = "basic-index"

    print(f"Creating basic index '{index_name}'...")
    result = index_manager.create(index_name)

    print(f"Index created: {result}")
    return index_name


def create_custom_index(index_manager):
    """Create an index with custom settings and mappings"""
    index_name = "products"

    # Define index settings
    settings = {
        "number_of_shards": 3,
        "number_of_replicas": 1,
        "analysis": {
            "analyzer": {
                "custom_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "stop", "snowball"],
                }
            }
        },
    }

    # Define index mappings
    mappings = {
        "properties": {
            "name": {
                "type": "text",
                "analyzer": "custom_analyzer",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "description": {"type": "text", "analyzer": "custom_analyzer"},
            "price": {"type": "float"},
            "category": {"type": "keyword"},
            "in_stock": {"type": "boolean"},
            "created": {"type": "date"},
            "tags": {"type": "keyword"},
        }
    }

    print(f"Creating custom index '{index_name}'...")
    result = index_manager.create(index_name, settings, mappings)

    print(f"Index created: {result}")
    return index_name


def update_index_settings(index_manager, index_name):
    """Update settings of an existing index"""
    print(f"Updating settings for index '{index_name}'...")

    # Update number of replicas
    settings = {"index": {"number_of_replicas": 2}}

    result = index_manager.update(index_name, settings)
    print(f"Index settings updated: {result}")


def get_index_info(index_manager, index_name):
    """Get information about an index"""
    print(f"Getting information for index '{index_name}'...")

    info = index_manager.get(index_name)

    print(f"Index information for '{index_name}':")
    print(f"  Settings: {info.get('settings', {}).get('index', {})}")
    if "mappings" in info:
        print(
            f"  Mappings: {list(info.get('mappings', {}).get('properties', {}).keys())}"
        )

    return info


def check_index_exists(index_manager, index_name):
    """Check if an index exists"""
    exists = index_manager.exists(index_name)
    print(f"Index '{index_name}' exists: {exists}")
    return exists


def open_close_index(index_manager, index_name):
    """Demonstrate opening and closing an index"""
    print(f"Closing index '{index_name}'...")
    result = index_manager.close(index_name)
    print(f"Index closed: {result}")

    print(f"Opening index '{index_name}'...")
    result = index_manager.open(index_name)
    print(f"Index opened: {result}")


def delete_index(index_manager, index_name):
    """Delete an index"""
    print(f"Deleting index '{index_name}'...")
    result = index_manager.delete(index_name)
    print(f"Index deleted: {result}")


def main():
    """Main function demonstrating index management operations"""
    try:
        # Create a client and index manager
        client = create_client()
        index_manager = IndexManager(client)

        # Create indices
        basic_index = create_basic_index(index_manager)
        custom_index = create_custom_index(index_manager)

        # Check if indices exist
        check_index_exists(index_manager, basic_index)
        check_index_exists(index_manager, custom_index)

        # Get index information
        get_index_info(index_manager, custom_index)

        # Update index settings
        update_index_settings(index_manager, custom_index)

        # Open and close an index
        open_close_index(index_manager, basic_index)

        # Delete indices
        delete_index(index_manager, basic_index)
        delete_index(index_manager, custom_index)

        # Verify deletion
        check_index_exists(index_manager, basic_index)
        check_index_exists(index_manager, custom_index)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
