"""
Example demonstrating how to use the configuration system.

This example shows how to load and use configuration with the Elastro package.
"""

import os
import json
import yaml
from elastro import ElasticsearchClient
from elastro.config import load_config, get_config, DEFAULT_CONFIG


def main():
    """
    Main function demonstrating configuration usage.
    """
    # Display default configuration
    print("Default configuration:")
    print(json.dumps(DEFAULT_CONFIG, indent=2))
    print()

    # Create a sample configuration file
    sample_config = {
        "default": {
            "elasticsearch": {
                "hosts": ["https://localhost:9200"],
                "auth": {
                    "type": "basic",
                    "username": "elastic",
                    "password": "changeme",
                },
                "timeout": 60,
                "retry_on_timeout": True,
                "max_retries": 5,
            },
            "logging": {"level": "DEBUG"},
        },
        "production": {
            "elasticsearch": {
                "hosts": ["https://production-es-cluster:9200"],
                "auth": {"type": "api_key", "api_key": "sample_api_key"},
            },
            "logging": {"level": "INFO"},
        },
    }

    # Write sample configuration to file
    with open("elastic.yaml", "w") as f:
        yaml.dump(sample_config, f)

    # Load configuration from file
    config_default = load_config(profile="default")
    print("Loaded default profile configuration:")
    print(json.dumps(config_default, indent=2))
    print()

    config_prod = load_config(profile="production")
    print("Loaded production profile configuration:")
    print(json.dumps(config_prod, indent=2))
    print()

    # Set environment variable and reload config
    os.environ["ELASTIC_ELASTICSEARCH_TIMEOUT"] = "120"
    os.environ["ELASTIC_LOGGING_LEVEL"] = "WARNING"

    # Reload configuration (will pick up environment variables)
    config = load_config()
    print("Configuration with environment variables:")
    print(json.dumps(config, indent=2))
    print()

    # Initialize client using configuration
    client = ElasticsearchClient()
    print(f"Client hosts: {client.hosts}")
    print(f"Client timeout: {client.timeout}")

    # Initialize client with explicit parameters (override config)
    custom_client = ElasticsearchClient(
        hosts=["https://custom-host:9200"],
        timeout=45,
        use_config=True,  # Will still load other settings from config
    )
    print(f"Custom client hosts: {custom_client.hosts}")
    print(f"Custom client timeout: {custom_client.timeout}")

    # Clean up
    os.remove("elastic.yaml")


if __name__ == "__main__":
    main()
