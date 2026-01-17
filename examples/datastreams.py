#!/usr/bin/env python3
"""
Elastro - Datastream Operations Example

This example demonstrates how to create and manage Elasticsearch datastreams,
which are time series optimized indices for append-only data like logs or metrics.
"""

from elastro import (
    ElasticsearchClient,
    IndexManager,
    DocumentManager,
    DatastreamManager,
)
import time
import datetime


def create_client():
    """Create and connect an Elasticsearch client"""
    client = ElasticsearchClient()
    client.connect()
    return client


def create_index_template(client, template_name):
    """Create an index template for the datastream"""
    print(f"Creating index template '{template_name}'...")

    # Define component template for mappings
    mappings_template = {
        "template": {
            "mappings": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "message": {"type": "text"},
                    "level": {"type": "keyword"},
                    "service": {"type": "keyword"},
                    "host": {"type": "keyword"},
                    "trace_id": {"type": "keyword"},
                    "duration_ms": {"type": "float"},
                }
            }
        }
    }

    # Define component template for settings
    settings_template = {
        "template": {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "index.lifecycle.name": "logs_policy",
            }
        }
    }

    # Create component templates
    client.rest_client.cluster.put_component_template(
        name=f"{template_name}-mappings", body=mappings_template
    )

    client.rest_client.cluster.put_component_template(
        name=f"{template_name}-settings", body=settings_template
    )

    # Create index template that uses the component templates
    index_template = {
        "index_patterns": [f"{template_name}-*"],
        "data_stream": {},
        "composed_of": [f"{template_name}-mappings", f"{template_name}-settings"],
        "priority": 500,
    }

    client.rest_client.indices.put_index_template(
        name=template_name, body=index_template
    )

    print(f"Index template '{template_name}' created.")


def create_lifecycle_policy(client, policy_name):
    """Create an ILM policy for the datastream"""
    print(f"Creating lifecycle policy '{policy_name}'...")

    policy = {
        "policy": {
            "phases": {
                "hot": {
                    "min_age": "0ms",
                    "actions": {
                        "rollover": {
                            "max_age": "1d",
                            "max_size": "5gb",
                            "max_docs": 100000,
                        },
                        "set_priority": {"priority": 100},
                    },
                },
                "warm": {
                    "min_age": "2d",
                    "actions": {
                        "set_priority": {"priority": 50},
                        "forcemerge": {"max_num_segments": 1},
                        "shrink": {"number_of_shards": 1},
                    },
                },
                "cold": {
                    "min_age": "7d",
                    "actions": {"set_priority": {"priority": 0}, "freeze": {}},
                },
                "delete": {"min_age": "30d", "actions": {"delete": {}}},
            }
        }
    }

    client.rest_client.ilm.put_lifecycle(name=policy_name, body=policy)

    print(f"Lifecycle policy '{policy_name}' created.")


def create_datastream(ds_manager, datastream_name):
    """Create a datastream"""
    print(f"Creating datastream '{datastream_name}'...")

    result = ds_manager.create(datastream_name)

    print(f"Datastream created: {result}")
    return datastream_name


def list_datastreams(ds_manager):
    """List all datastreams"""
    print("Listing all datastreams...")

    datastreams = ds_manager.list()

    print(f"Found {len(datastreams)} datastreams:")
    for ds in datastreams:
        print(f"  - {ds}")

    return datastreams


def get_datastream_info(ds_manager, datastream_name):
    """Get information about a datastream"""
    print(f"Getting information for datastream '{datastream_name}'...")

    info = ds_manager.get(datastream_name)

    print(f"Datastream '{datastream_name}' information:")
    print(f"  Backing indices: {info['data_stream']['indices']}")
    print(f"  Generation: {info['data_stream']['generation']}")
    print(f"  Timestamp field: {info['data_stream']['timestamp_field']['name']}")

    return info


def index_documents_to_datastream(client, datastream_name, count=10):
    """Index sample documents to the datastream"""
    print(f"Indexing {count} sample log entries to datastream '{datastream_name}'...")

    doc_manager = DocumentManager(client)

    # Sample log levels and services
    log_levels = ["INFO", "WARN", "ERROR", "DEBUG"]
    services = [
        "web-server",
        "auth-service",
        "payment-processor",
        "notification-service",
    ]
    hosts = ["host-1", "host-2", "host-3"]

    # Generate and index documents
    for i in range(count):
        # Generate a random timestamp within the last hour
        timestamp = datetime.datetime.utcnow() - datetime.timedelta(minutes=i * 6)
        timestamp_str = timestamp.isoformat() + "Z"

        # Create a log entry
        log_entry = {
            "@timestamp": timestamp_str,
            "message": f"Sample log message #{i+1}",
            "level": log_levels[i % len(log_levels)],
            "service": services[i % len(services)],
            "host": hosts[i % len(hosts)],
            "trace_id": f"trace-{i:04d}",
            "duration_ms": float(i * 10.5),
        }

        # Index without explicit ID (Elasticsearch will generate one)
        doc_manager.index(datastream_name, None, log_entry)

    # Refresh to make documents searchable immediately
    client.rest_client.indices.refresh(index=datastream_name)
    print(f"Indexed {count} documents to datastream '{datastream_name}'.")


def search_datastream(client, datastream_name):
    """Search for documents in the datastream"""
    print(f"Searching datastream '{datastream_name}'...")

    doc_manager = DocumentManager(client)

    # Search for documents
    query = {"match_all": {}}

    results = doc_manager.search(
        datastream_name, query, {"sort": [{"@timestamp": "desc"}], "size": 5}
    )

    print(f"Found {results['hits']['total']['value']} documents.")
    print("Most recent entries:")
    for hit in results["hits"]["hits"]:
        source = hit["_source"]
        print(
            f"  {source['@timestamp']} | {source['level']} | {source['service']} | {source['message']}"
        )

    return results


def rollover_datastream(ds_manager, datastream_name):
    """Manually rollover a datastream"""
    print(f"Rolling over datastream '{datastream_name}'...")

    # Define rollover conditions
    conditions = {
        "max_age": "1m",  # Just for demonstration purposes - normally this would be longer
        "max_docs": 5,
    }

    result = ds_manager.rollover(datastream_name, conditions)

    print(f"Rollover result: {result}")
    return result


def delete_datastream(ds_manager, datastream_name):
    """Delete a datastream"""
    print(f"Deleting datastream '{datastream_name}'...")

    result = ds_manager.delete(datastream_name)

    print(f"Datastream deleted: {result}")
    return result


def cleanup(client, policy_name, template_name):
    """Clean up resources"""
    print("Cleaning up resources...")

    # Delete ILM policy
    try:
        client.rest_client.ilm.delete_lifecycle(name=policy_name)
        print(f"Lifecycle policy '{policy_name}' deleted.")
    except Exception as e:
        print(f"Error deleting lifecycle policy: {e}")

    # Delete index template and component templates
    try:
        client.rest_client.indices.delete_index_template(name=template_name)
        print(f"Index template '{template_name}' deleted.")

        client.rest_client.cluster.delete_component_template(
            name=f"{template_name}-mappings"
        )
        client.rest_client.cluster.delete_component_template(
            name=f"{template_name}-settings"
        )
        print(f"Component templates deleted.")
    except Exception as e:
        print(f"Error deleting templates: {e}")


def main():
    """Main function demonstrating datastream operations"""
    try:
        # Create a client and datastream manager
        client = create_client()
        ds_manager = DatastreamManager(client)

        # Set up resources
        template_name = "logs-template"
        policy_name = "logs_policy"
        datastream_name = "logs-app"

        # Create lifecycle policy
        create_lifecycle_policy(client, policy_name)

        # Create index template
        create_index_template(client, template_name)

        # Create a datastream
        create_datastream(ds_manager, datastream_name)

        # List all datastreams
        list_datastreams(ds_manager)

        # Get datastream info
        get_datastream_info(ds_manager, datastream_name)

        # Index documents to the datastream
        index_documents_to_datastream(client, datastream_name, 10)

        # Search the datastream
        search_datastream(client, datastream_name)

        # Wait a moment to demonstrate rollover
        print("Waiting 10 seconds before rollover...")
        time.sleep(10)

        # Rollover the datastream
        rollover_datastream(ds_manager, datastream_name)

        # Get updated datastream info after rollover
        get_datastream_info(ds_manager, datastream_name)

        # Delete the datastream
        delete_datastream(ds_manager, datastream_name)

        # Clean up resources
        cleanup(client, policy_name, template_name)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
