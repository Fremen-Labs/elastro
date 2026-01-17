"""
Integration tests for the ElasticsearchClient class.
These tests require a running Elasticsearch instance.
"""

import pytest
import os
from unittest.mock import patch

from elastro.core.client import ElasticsearchClient
from elastro.core.errors import ConnectionError, AuthenticationError


# Mark as integration tests
@pytest.mark.integration
class TestElasticsearchClientIntegration:
    """Integration tests for ElasticsearchClient."""

    def test_connect_to_elasticsearch(self):
        """Test connecting to Elasticsearch."""
        # Create client
        client = ElasticsearchClient(
            hosts=["http://localhost:9200"],
            username="elastic",
            password="elastic_password",
            verify_certs=False,  # Disable certificate verification
        )

        # Connect
        client.connect()

        # Check connection
        assert client.is_connected() is True

        # Get cluster info
        info = client._client.info()
        assert "cluster_name" in info
        assert "version" in info

        # Disconnect
        client.disconnect()

    def test_reconnect_after_close(self):
        """Test reconnecting after closing the connection."""
        # Create client
        client = ElasticsearchClient(
            hosts=["http://localhost:9200"],
            username="elastic",
            password="elastic_password",
            verify_certs=False,  # Disable certificate verification
        )

        # Connect
        client.connect()
        assert client.is_connected() is True

        # Close connection
        client.disconnect()
        assert client.is_connected() is False

        # Reconnect
        client.connect()
        assert client.is_connected() is True

        # Close again
        client.disconnect()

    def test_invalid_host(self):
        """Test connecting to an invalid host."""
        # Create client with invalid host
        client = ElasticsearchClient(hosts=["http://nonexistent-host:9200"])

        # Try to connect
        with pytest.raises(ConnectionError):
            client.connect()

        assert client.is_connected() is False

    @pytest.mark.skipif(
        os.environ.get("TEST_ES_USERNAME") is None
        or os.environ.get("TEST_ES_PASSWORD") is None,
        reason="Authentication credentials not provided",
    )
    def test_authentication(self):
        """Test authentication with username and password."""
        # Get credentials from environment variables
        username = os.environ.get("TEST_ES_USERNAME")
        password = os.environ.get("TEST_ES_PASSWORD")

        # Create client with auth
        client = ElasticsearchClient(
            hosts=["http://localhost:9200"],
            username=username,
            password=password,
            verify_certs=False,  # Disable certificate verification
        )

        # Connect
        client.connect()

        # Check connection
        assert client.is_connected() is True

        # Close connection
        client.disconnect()

    @pytest.mark.skipif(
        os.environ.get("TEST_ES_API_KEY") is None, reason="API key not provided"
    )
    def test_api_key_authentication(self):
        """Test authentication with API key."""
        # Get API key from environment variable
        api_key = os.environ.get("TEST_ES_API_KEY")

        # Create client with API key
        client = ElasticsearchClient(
            hosts=["http://localhost:9200"],
            api_key=api_key,
            verify_certs=False,  # Disable certificate verification
        )

        # Connect
        client.connect()

        # Check connection
        assert client.is_connected() is True

        # Close connection
        client.disconnect()

    def test_invalid_authentication(self):
        """Test invalid authentication."""
        # Create client with invalid auth
        client = ElasticsearchClient(
            hosts=["http://localhost:9200"],
            username="invalid_user",
            password="invalid_password",
            verify_certs=False,  # Disable certificate verification
        )

        # Try to connect
        with pytest.raises((ConnectionError, AuthenticationError)):
            client.connect()

        assert client.is_connected() is False

    def test_connection_timeout(self):
        """Test connection timeout."""
        # Create client with very short timeout
        client = ElasticsearchClient(
            hosts=["http://localhost:9200"],
            timeout=0.001,  # 1ms timeout
            verify_certs=False,  # Disable certificate verification
        )

        # Try to connect
        try:
            client.connect()
            # If connect succeeds, timeout was still enough, so test can't verify timeout
            pytest.skip("Connection succeeded despite short timeout")
        except ConnectionError:
            # This is expected, connection should time out
            assert client.is_connected() is False
