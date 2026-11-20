"""Unit tests for SecurityManager."""

import logging

import pytest

from elastro.core.errors import OperationError
from elastro.core.security import SecurityManager


class TestSecurityManager:
    def test_get_users_all(self, es_client) -> None:
        payload = {
            "elastic": {
                "full_name": "Elastic",
                "roles": ["superuser"],
                "email": "",
                "enabled": True,
            }
        }
        es_client.client.security.get_user.return_value = payload

        result = SecurityManager(es_client).get_users()

        assert result == payload
        es_client.client.security.get_user.assert_called_once_with()

    def test_get_users_by_username(self, es_client) -> None:
        payload = {"elastic": {"roles": ["superuser"], "enabled": True}}
        es_client.client.security.get_user.return_value = payload

        result = SecurityManager(es_client).get_users("elastic")

        assert result == payload
        es_client.client.security.get_user.assert_called_once_with(username="elastic")

    def test_get_users_failure_raises_operation_error(self, es_client) -> None:
        es_client.client.security.get_user.side_effect = Exception("No node reached")

        with pytest.raises(OperationError, match="Failed to list users"):
            SecurityManager(es_client).get_users()

    def test_get_users_does_not_log_user_document(self, es_client, caplog) -> None:
        payload = {
            "elastic": {
                "full_name": "Elastic Superuser",
                "roles": ["superuser"],
                "metadata": {"secret_marker": "DO_NOT_LOG_THIS_METADATA"},
                "enabled": True,
            }
        }
        es_client.client.security.get_user.return_value = payload

        with caplog.at_level(logging.DEBUG, logger="elastro.core.security"):
            SecurityManager(es_client).get_users()

        assert "DO_NOT_LOG_THIS_METADATA" not in caplog.text
        assert "Elastic Superuser" not in caplog.text

    def test_get_roles_all(self, es_client) -> None:
        payload = {"superuser": {"cluster": ["all"], "indices": []}}
        es_client.client.security.get_role.return_value = payload

        result = SecurityManager(es_client).get_roles()

        assert result == payload
        es_client.client.security.get_role.assert_called_once_with()

    def test_get_roles_by_name(self, es_client) -> None:
        payload = {"kibana_admin": {"cluster": ["monitor"]}}
        es_client.client.security.get_role.return_value = payload

        result = SecurityManager(es_client).get_roles("kibana_admin")

        assert result == payload
        es_client.client.security.get_role.assert_called_once_with(name="kibana_admin")

    def test_get_roles_failure_raises_operation_error(self, es_client) -> None:
        es_client.client.security.get_role.side_effect = Exception("No node reached")

        with pytest.raises(OperationError, match="Failed to list roles"):
            SecurityManager(es_client).get_roles()
