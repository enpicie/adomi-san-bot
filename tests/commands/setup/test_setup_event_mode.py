# TODO: Re-enable when event-mode functionality is enabled again.
# import pytest
# from unittest.mock import MagicMock

# import commands.setup.server_commands as setup
# from commands.models.response_message import ResponseMessage
# from enums import EventMode


# def _make_event(event_mode=None):
#     """Helper to build a mock DiscordEvent for reuse."""
#     mock_event = MagicMock()
#     mock_event.get_server_id.return_value = "123"
#     mock_event.get_command_input_value.return_value = event_mode
#     return mock_event


# # ----------------------------------------------------
# #  Permissions Tests
# # ----------------------------------------------------

# def test_setup_event_mode_insufficient_permissions(monkeypatch):
#     mock_table = MagicMock()
#     mock_event = _make_event()
#     mock_event.get_user_permission_int.return_value = 0  # No permissions

#     monkeypatch.setattr(setup.db_helper, "get_server_config", lambda sid, t: {"PK": "SERVER#123", "SK": "CONFIG"})
#     monkeypatch.setattr(setup.db_helper, "get_server_pk", lambda sid: f"SERVER#{sid}")

#     response = setup.setup_event_mode(mock_event, mock_table)

#     assert isinstance(response, ResponseMessage)
#     assert "Manage Server" in response.content
#     mock_table.update_item.assert_not_called()


# # ----------------------------------------------------
# #  CONFIG existence tests
# # ----------------------------------------------------

# def test_setup_event_mode_config_missing(monkeypatch):
#     mock_table = MagicMock()
#     mock_event = _make_event(EventMode.PER_CHANNEL.value)
#     mock_event.get_user_permission_int.return_value = (1 << 5)

#     monkeypatch.setattr(setup.db_helper, "get_server_config", lambda sid, t: None)
#     monkeypatch.setattr(setup.db_helper, "get_server_pk", lambda sid: f"SERVER#{sid}")

#     response = setup.setup_event_mode(mock_event, mock_table)

#     assert isinstance(response, ResponseMessage)
#     assert "not set up" in response.content
#     mock_table.update_item.assert_not_called()


# # ----------------------------------------------------
# #  Event mode unchanged
# # ----------------------------------------------------

# def test_setup_event_mode_no_change(monkeypatch):
#     """Returns early if the new event_mode is the same as current."""
#     mock_table = MagicMock()
#     event_mode = EventMode.SERVER_WIDE.value
#     mock_event = _make_event(event_mode)
#     mock_event.get_user_permission_int.return_value = (1 << 5)

#     monkeypatch.setattr(
#         setup.db_helper,
#         "get_server_config",
#         lambda sid, t: {"PK": "SERVER#123", "SK": "CONFIG", "event_mode": event_mode}
#     )
#     monkeypatch.setattr(setup.db_helper, "get_server_pk", lambda sid: f"SERVER#{sid}")

#     response = setup.setup_event_mode(mock_event, mock_table)

#     assert isinstance(response, ResponseMessage)
#     assert "already" in response.content
#     mock_table.update_item.assert_not_called()


# # ----------------------------------------------------
# #  Successful Update Tests
# # ----------------------------------------------------

# def test_setup_event_mode_updates_to_per_channel(monkeypatch):
#     """Updates event_mode to PER_CHANNEL and deletes SERVER records."""
#     mock_table = MagicMock()
#     event_mode = EventMode.PER_CHANNEL.value
#     mock_event = _make_event(event_mode)
#     mock_event.get_user_permission_int.return_value = (1 << 5)

#     monkeypatch.setattr(
#         setup.db_helper,
#         "get_server_config",
#         lambda sid, t: {"PK": "SERVER#123", "SK": "CONFIG", "event_mode": EventMode.SERVER_WIDE.value}
#     )
#     monkeypatch.setattr(setup.db_helper, "get_server_pk", lambda sid: f"SERVER#{sid}")

#     # Mock SERVER records
#     monkeypatch.setattr(
#         setup.db_helper,
#         "query_items_by_sk",
#         lambda sid, tbl, sk: [{"PK": f"SERVER#{sid}", "SK": sk}]
#     )

#     response = setup.setup_event_mode(mock_event, mock_table)

#     # update_item should be called for CONFIG
#     mock_table.update_item.assert_called_once()
#     # delete_item should be called for SERVER record
#     mock_table.delete_item.assert_called_once()
#     assert response.content.startswith("👍 Changed event mode")


# def test_setup_event_mode_updates_to_server_wide(monkeypatch):
#     """Updates event_mode to SERVER_WIDE, deletes CHANNEL* records, creates SERVER record."""
#     mock_table = MagicMock()
#     event_mode = EventMode.SERVER_WIDE.value
#     mock_event = _make_event(event_mode)
#     mock_event.get_user_permission_int.return_value = (1 << 5)

#     monkeypatch.setattr(
#         setup.db_helper,
#         "get_server_config",
#         lambda sid, t: {"PK": "SERVER#123", "SK": "CONFIG", "event_mode": EventMode.PER_CHANNEL.value}
#     )
#     monkeypatch.setattr(setup.db_helper, "get_server_pk", lambda sid: f"SERVER#{sid}")

#     # Mock CHANNEL* records
#     monkeypatch.setattr(
#         setup.db_helper,
#         "query_items_with_sk_prefix",
#         lambda sid, tbl, prefix: [{"PK": f"SERVER#{sid}", "SK": f"{prefix}#1"}, {"PK": f"SERVER#{sid}", "SK": f"{prefix}#2"}]
#     )

#     response = setup.setup_event_mode(mock_event, mock_table)

#     # update_item should be called for CONFIG
#     mock_table.update_item.assert_called_once()
#     # delete_item should be called for each CHANNEL* record
#     assert mock_table.delete_item.call_count == 2
#     # put_item should be called to create SERVER record
#     mock_table.put_item.assert_called_once()
#     assert response.content.startswith("👍 Changed event mode")
