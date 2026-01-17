#!/usr/bin/env python3
"""
Elastro - Client Connection Example

This example demonstrates different ways to connect to Elasticsearch
and perform basic client operations.
"""

from elastro import ElasticsearchClient


def connect_with_api_key():
    """Connect to Elasticsearch using an API key"""

    # Initialize the client with an API key
    client = ElasticsearchClient(
        hosts=["https://elasticsearch:9200"], auth={"api_key": "your-api-key-here"}
    )

    # Connect to Elasticsearch
    client.connect()

    return client


def connect_with_basic_auth():
    """Connect to Elasticsearch using basic authentication"""

    # Initialize the client with username and password
    client = ElasticsearchClient(
        hosts=["https://elasticsearch:9200"],
        auth={"username": "elastic", "password": "your-password-here"},
    )

    # Connect to Elasticsearch
    client.connect()

    return client


def connect_from_config():
    """Connect to Elasticsearch using configuration file or environment variables"""

    # Initialize the client without explicit configuration
    # This will look for elastic.yaml, elastic.json, or environment variables
    client = ElasticsearchClient()

    # Connect to Elasticsearch
    client.connect()

    return client


def connect_with_profile():
    """Connect to Elasticsearch using a specific profile"""

    # Initialize the client with a specific profile from configuration
    client = ElasticsearchClient(profile="production")

    # Connect to Elasticsearch
    client.connect()

    return client


def check_cluster_health(client):
    """Check the health of the Elasticsearch cluster"""

    # Get cluster health
    health = client.health()

    print(f"Cluster name: {health['cluster_name']}")
    print(f"Status: {health['status']}")
    print(f"Number of nodes: {health['number_of_nodes']}")
    print(f"Active shards: {health['active_shards']}")

    return health


def list_indices(client):
    """List all indices in the cluster"""

    # Get all indices
    indices = client.indices()

    print(f"Found {len(indices)} indices:")
    for index in indices:
        print(f" - {index}")

    return indices


def main():
    """Main function to demonstrate client functionality"""

    # Choose one of the connection methods
    try:
        # client = connect_with_api_key()
        # client = connect_with_basic_auth()
        client = connect_from_config()
        # client = connect_with_profile()

        print("Successfully connected to Elasticsearch!")

        # Check cluster health
        print("\nCluster Health:")
        check_cluster_health(client)

        # List indices
        print("\nIndices:")
        list_indices(client)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
