import unittest
from unittest.mock import Mock

import utils.permissions_helper as permissions_helper
from commands.models.response_message import ResponseMessage


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


if __name__ == "__main__":
    unittest.main()
