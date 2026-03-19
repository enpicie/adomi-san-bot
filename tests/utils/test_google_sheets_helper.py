import unittest
from unittest.mock import Mock, patch

import utils.google_sheets_helper as sheets_helper
from commands.league.participants_sheet import (
    ParticipantsColumn, STATUS_ACTIVE, STATUS_QUEUED, STATUS_INACTIVE, COLUMN_HEADERS
)


class TestExtractSpreadsheetId(unittest.TestCase):
    def test_valid_url_returns_id(self):
        url = "https://docs.google.com/spreadsheets/d/abc123XYZ/edit"
        self.assertEqual(sheets_helper.extract_spreadsheet_id(url), "abc123XYZ")

    def test_url_with_hyphens_and_underscores(self):
        url = "https://docs.google.com/spreadsheets/d/abc-123_XYZ/edit"
        self.assertEqual(sheets_helper.extract_spreadsheet_id(url), "abc-123_XYZ")

    def test_long_real_world_id(self):
        url = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/edit#gid=0"
        self.assertEqual(
            sheets_helper.extract_spreadsheet_id(url),
            "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"
        )

    def test_invalid_url_returns_none(self):
        self.assertIsNone(sheets_helper.extract_spreadsheet_id("https://google.com"))

    def test_empty_string_returns_none(self):
        self.assertIsNone(sheets_helper.extract_spreadsheet_id(""))


class TestGetActiveParticipants(unittest.TestCase):
    def _make_service(self, rows):
        service = Mock()
        service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
            "values": rows
        }
        return service

    def _row(self, discord_id, name, status):
        row = [""] * len(COLUMN_HEADERS)
        row[ParticipantsColumn.STATUS] = status
        row[ParticipantsColumn.DISCORD_ID] = discord_id
        row[ParticipantsColumn.PARTICIPANT_NAME] = name
        return row

    @patch("utils.google_sheets_helper._get_sheets_service")
    def test_returns_only_active_players(self, mock_get_service):
        mock_get_service.return_value = self._make_service([
            COLUMN_HEADERS,
            self._row("111", "Alice", STATUS_ACTIVE),
            self._row("222", "Bob", STATUS_QUEUED),
            self._row("333", "Carol", STATUS_INACTIVE),
        ])
        result = sheets_helper.get_active_participants("https://docs.google.com/spreadsheets/d/abc/edit")
        self.assertEqual(result, {"111": "Alice"})

    @patch("utils.google_sheets_helper._get_sheets_service")
    def test_multiple_active_players_all_returned(self, mock_get_service):
        mock_get_service.return_value = self._make_service([
            COLUMN_HEADERS,
            self._row("111", "Alice", STATUS_ACTIVE),
            self._row("222", "Bob", STATUS_ACTIVE),
        ])
        result = sheets_helper.get_active_participants("https://docs.google.com/spreadsheets/d/abc/edit")
        self.assertEqual(result, {"111": "Alice", "222": "Bob"})

    @patch("utils.google_sheets_helper._get_sheets_service")
    def test_empty_sheet_returns_empty_dict(self, mock_get_service):
        mock_get_service.return_value = self._make_service([])
        result = sheets_helper.get_active_participants("https://docs.google.com/spreadsheets/d/abc/edit")
        self.assertEqual(result, {})

    @patch("utils.google_sheets_helper._get_sheets_service")
    def test_header_only_returns_empty_dict(self, mock_get_service):
        mock_get_service.return_value = self._make_service([COLUMN_HEADERS])
        result = sheets_helper.get_active_participants("https://docs.google.com/spreadsheets/d/abc/edit")
        self.assertEqual(result, {})

    @patch("utils.google_sheets_helper._get_sheets_service")
    def test_row_without_discord_id_is_skipped(self, mock_get_service):
        # Only a status column, no discord_id
        mock_get_service.return_value = self._make_service([
            COLUMN_HEADERS,
            [STATUS_ACTIVE],
        ])
        result = sheets_helper.get_active_participants("https://docs.google.com/spreadsheets/d/abc/edit")
        self.assertEqual(result, {})

    def test_invalid_url_raises_value_error(self):
        with self.assertRaises(ValueError):
            sheets_helper.get_active_participants("not-a-valid-url")


class TestSetupLeagueParticipantsSheet(unittest.TestCase):
    VALID_URL = "https://docs.google.com/spreadsheets/d/abc123/edit"

    def _make_service(self, existing_sheet=False, existing_rule_count=0):
        service = Mock()
        sheets = []
        if existing_sheet:
            sheets.append({
                "properties": {"title": "Participants", "sheetId": 42},
                "conditionalFormats": [{}] * existing_rule_count,
            })
        service.spreadsheets.return_value.get.return_value.execute.return_value = {"sheets": sheets}
        service.spreadsheets.return_value.batchUpdate.return_value.execute.return_value = {
            "replies": [{"addSheet": {"properties": {"sheetId": 99}}}]
        }
        return service

    def _last_batch_update_requests(self, service):
        calls = service.spreadsheets.return_value.batchUpdate.call_args_list
        return calls[-1].kwargs["body"]["requests"]

    @patch("utils.google_sheets_helper._get_sheets_service")
    def test_new_sheet_writes_header_row(self, mock_get_service):
        service = self._make_service()
        mock_get_service.return_value = service
        sheets_helper.setup_league_participants_sheet(self.VALID_URL)
        service.spreadsheets.return_value.values.return_value.update.assert_called_once()

    @patch("utils.google_sheets_helper._get_sheets_service")
    def test_three_conditional_format_rules_added(self, mock_get_service):
        service = self._make_service()
        mock_get_service.return_value = service
        sheets_helper.setup_league_participants_sheet(self.VALID_URL)
        requests = self._last_batch_update_requests(service)
        add_rules = [r for r in requests if "addConditionalFormatRule" in r]
        self.assertEqual(len(add_rules), 3)

    @patch("utils.google_sheets_helper._get_sheets_service")
    def test_existing_sheet_with_rules_deletes_them_first(self, mock_get_service):
        service = self._make_service(existing_sheet=True, existing_rule_count=3)
        mock_get_service.return_value = service
        sheets_helper.setup_league_participants_sheet(self.VALID_URL)
        requests = self._last_batch_update_requests(service)
        delete_reqs = [r for r in requests if "deleteConditionalFormatRule" in r]
        self.assertEqual(len(delete_reqs), 3)

    @patch("utils.google_sheets_helper._get_sheets_service")
    def test_new_sheet_has_no_delete_requests(self, mock_get_service):
        service = self._make_service()
        mock_get_service.return_value = service
        sheets_helper.setup_league_participants_sheet(self.VALID_URL)
        requests = self._last_batch_update_requests(service)
        delete_reqs = [r for r in requests if "deleteConditionalFormatRule" in r]
        self.assertEqual(len(delete_reqs), 0)

    @patch("utils.google_sheets_helper._get_sheets_service")
    def test_bold_header_request_included(self, mock_get_service):
        service = self._make_service()
        mock_get_service.return_value = service
        sheets_helper.setup_league_participants_sheet(self.VALID_URL)
        requests = self._last_batch_update_requests(service)
        bold_reqs = [r for r in requests if "repeatCell" in r]
        self.assertEqual(len(bold_reqs), 1)

    def test_invalid_url_raises_value_error(self):
        with self.assertRaises(ValueError):
            sheets_helper.setup_league_participants_sheet("not-a-url")


class TestAppendLeagueParticipant(unittest.TestCase):
    VALID_URL = "https://docs.google.com/spreadsheets/d/abc123/edit"

    @patch("utils.google_sheets_helper._get_sheets_service")
    def test_appends_row_with_queued_status(self, mock_get_service):
        service = Mock()
        mock_get_service.return_value = service
        sheets_helper.append_league_participant(self.VALID_URL, "user_123", "Alice")
        call_kwargs = service.spreadsheets.return_value.values.return_value.append.call_args.kwargs
        appended_row = call_kwargs["body"]["values"][0]
        self.assertEqual(appended_row[ParticipantsColumn.STATUS], STATUS_QUEUED)
        self.assertEqual(appended_row[ParticipantsColumn.DISCORD_ID], "user_123")
        self.assertEqual(appended_row[ParticipantsColumn.PARTICIPANT_NAME], "Alice")

    def test_invalid_url_raises_value_error(self):
        with self.assertRaises(ValueError):
            sheets_helper.append_league_participant("not-a-url", "uid", "name")


if __name__ == "__main__":
    unittest.main()
