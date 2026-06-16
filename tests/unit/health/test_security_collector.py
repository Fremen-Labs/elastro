"""Unit tests for security collector."""

import unittest
from unittest.mock import MagicMock

from elastro.core.client import ElasticsearchClient
from elastro.health.collectors.base import CollectContext
from elastro.health.collectors.security import SecurityCollector


class TestSecurityCollector(unittest.TestCase):
    def setUp(self):
        self.mock_es = MagicMock()
        self.mock_client = MagicMock(spec=ElasticsearchClient)
        self.mock_client.client = self.mock_es
        self.mock_client.hosts = ["http://localhost:9200"]
        self.ctx = CollectContext(client=self.mock_client)

    def test_detects_plain_http_connection(self):
        result = SecurityCollector().collect(self.ctx)
        self.assertEqual(result.status, "ok")
        ids = {finding.id for finding in result.data["findings"]}
        self.assertIn("security.tls.plain_http", ids)

    def test_detects_enabled_elastic_user(self):
        self.mock_client.hosts = ["https://localhost:9200"]
        self.mock_es.security.get_user.return_value = {
            "elastic": {"enabled": True, "roles": ["superuser"]},
        }
        self.mock_es.security.get_role.return_value = {}

        result = SecurityCollector().collect(self.ctx)
        ids = {finding.id for finding in result.data["findings"]}
        self.assertIn("security.user.elastic_enabled", ids)

    def test_skips_when_security_api_unavailable(self):
        self.mock_client.hosts = ["https://localhost:9200"]
        self.mock_es.security.get_user.side_effect = Exception("security_exception")

        result = SecurityCollector().collect(self.ctx)
        ids = {finding.id for finding in result.data["findings"]}
        self.assertIn("security.api.unavailable", ids)


if __name__ == "__main__":
    unittest.main()
