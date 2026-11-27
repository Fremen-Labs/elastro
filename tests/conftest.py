import os
import pytest
from unittest.mock import MagicMock, patch
from elasticsearch import Elasticsearch

from elastro.core.client import ElasticsearchClient
from elastro.core.index import IndexManager
from elastro.core.document import DocumentManager
from elastro.core.datastream import DatastreamManager


@pytest.fixture
def mock_elasticsearch():
    """Return a mocked Elasticsearch client."""
    with patch("elasticsearch.Elasticsearch") as mock_es:
        mock_client = MagicMock()
        mock_es.return_value = mock_client
        yield mock_client


@pytest.fixture
def es_client(mock_elasticsearch):
    """Return an ElasticsearchClient instance with a mocked ES client."""
    client = ElasticsearchClient(hosts=["http://localhost:9200"])
    # Replace the _client with our mock
    client._client = mock_elasticsearch
    client._connected = True
    return client


@pytest.fixture
def index_manager(es_client):
    """Return an IndexManager instance with a mocked client."""
    return IndexManager(es_client)


@pytest.fixture
def document_manager(es_client):
    """Return a DocumentManager instance with a mocked client."""
    return DocumentManager(es_client)


@pytest.fixture
def datastream_manager(es_client):
    """Return a DatastreamManager instance with a mocked client."""
    return DatastreamManager(es_client)


def live_es_hosts() -> list:
    url = (
        os.environ.get("ELASTIC_URL")
        or os.environ.get("ELASTIC_HOSTS")
        or "http://localhost:9200"
    )
    return [url]


def live_es_auth() -> tuple:
    return (
        os.environ.get("ELASTIC_USERNAME", "elastic"),
        os.environ.get("ELASTIC_PASSWORD", "elastic_password"),
    )


def live_client_kwargs() -> dict:
    user, password = live_es_auth()
    return {
        "hosts": live_es_hosts(),
        "username": user,
        "password": password,
        "verify_certs": False,
    }


# Integration test fixtures
@pytest.fixture(scope="session")
def real_elasticsearch():
    """
    Return a real Elasticsearch client for integration tests.
    """
    user, password = live_es_auth()
    client = Elasticsearch(
        hosts=live_es_hosts(),
        basic_auth=(user, password),
        verify_certs=False,
        ssl_show_warn=False,
    )

    # Check if Elasticsearch is available
    try:
        if not client.ping():
            pytest.skip("Elasticsearch server is not available")
    except Exception as e:
        pytest.skip(f"Elasticsearch server is not available: {str(e)}")

    return client


@pytest.fixture(scope="session")
def real_es_client(real_elasticsearch):
    """Return a real ElasticsearchClient for integration tests."""
    user, password = live_es_auth()
    client = ElasticsearchClient(
        hosts=live_es_hosts(),
        username=user,
        password=password,
        verify_certs=False,
    )
    # Force client to use the real_elasticsearch instance
    client._client = real_elasticsearch
    client._connected = True
    return client
