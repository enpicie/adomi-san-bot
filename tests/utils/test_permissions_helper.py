import unittest
from unittest.mock import Mock

import utils.permissions_helper as permissions_helper
from commands.models.response_message import ResponseMessage
from database.models.server_config import ServerConfig


class TestRequireManageServerPermission(unittest.TestCase):
    def _make_event(self, permission_int: int) -> Mock:
        event = Mock()
        event.get_user_permission_int.return_value = permission_int
        return event

    def test_no_permissions_returns_error(self):
        result = permissions_helper.require_manage_server_permission(self._make_event(0))
        self.assertIsInstance(result, ResponseMessage)

    def test_manage_server_bit_set_returns_none(self):
        result = permissions_helper.require_manage_server_permission(self._make_event(0x20))
        self.assertIsNone(result)

    def test_manage_server_combined_with_other_bits_returns_none(self):
        result = permissions_helper.require_manage_server_permission(self._make_event(0x20 | 0x08 | 0x01))
        self.assertIsNone(result)

    def test_different_permission_bit_returns_error(self):
        # 0x10 = MANAGE_CHANNELS, not MANAGE_SERVER
        result = permissions_helper.require_manage_server_permission(self._make_event(0x10))
        self.assertIsInstance(result, ResponseMessage)


class TestRequireOrganizerRole(unittest.TestCase):
    def _make_config(self, organizer_role: str) -> Mock:
        config = Mock()
        config.organizer_role = organizer_role
        return config

    def _make_event(self, roles: list) -> Mock:
        event = Mock()
        event.get_user_roles.return_value = roles
        return event

    def test_user_has_organizer_role_returns_none(self):
        result = permissions_helper.require_organizer_role(
            self._make_config("ROLE_ORG"),
            self._make_event(["ROLE_MEMBER", "ROLE_ORG"])
        )
        self.assertIsNone(result)

    def test_user_missing_organizer_role_returns_error(self):
        result = permissions_helper.require_organizer_role(
            self._make_config("ROLE_ORG"),
            self._make_event(["ROLE_MEMBER"])
        )
        self.assertIsInstance(result, ResponseMessage)

    def test_empty_user_roles_returns_error(self):
        result = permissions_helper.require_organizer_role(
            self._make_config("ROLE_ORG"),
            self._make_event([])
        )
        self.assertIsInstance(result, ResponseMessage)

    def test_empty_organizer_role_id_returns_error(self):
        # An unconfigured (empty string) organizer role should never match
        result = permissions_helper.require_organizer_role(
            self._make_config(""),
            self._make_event(["ROLE_MEMBER"])
        )
        self.assertIsInstance(result, ResponseMessage)


class TestVerifyHasOrganizerRole(unittest.TestCase):
    _ORGANIZER_ROLE = "ROLE_ORG"

    def _make_aws(self, config_item=None):
        aws = Mock()
        aws.dynamodb_table.get_item.return_value = (
            {"Item": config_item} if config_item is not None else {}
        )
        return aws

    def _make_event(self, roles=None):
        event = Mock()
        event.get_server_id.return_value = "S1"
        event.get_user_roles.return_value = roles or []
        return event

    def _config_item(self, organizer_role=_ORGANIZER_ROLE):
        return {ServerConfig.Keys.SERVER_ID: "S1", ServerConfig.Keys.ORGANIZER_ROLE: organizer_role}

    def test_missing_config_returns_error(self):
        result = permissions_helper.verify_has_organizer_role(
            self._make_event(roles=[self._ORGANIZER_ROLE]),
            self._make_aws(config_item=None)
        )
        self.assertIsInstance(result, ResponseMessage)

    def test_user_missing_organizer_role_returns_error(self):
        result = permissions_helper.verify_has_organizer_role(
            self._make_event(roles=["OTHER_ROLE"]),
            self._make_aws(config_item=self._config_item())
        )
        self.assertIsInstance(result, ResponseMessage)

    def test_user_has_organizer_role_returns_none(self):
        result = permissions_helper.verify_has_organizer_role(
            self._make_event(roles=[self._ORGANIZER_ROLE]),
            self._make_aws(config_item=self._config_item())
        )
        self.assertIsNone(result)

    def test_user_with_multiple_roles_including_organizer_returns_none(self):
        result = permissions_helper.verify_has_organizer_role(
            self._make_event(roles=["MEMBER", self._ORGANIZER_ROLE, "BOOSTER"]),
            self._make_aws(config_item=self._config_item())
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
