import json
import re

import boto3
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import constants
from commands.league.participants_sheet import (
    SHEET_NAME as PARTICIPANTS_SHEET,
    SHEET_RANGE as PARTICIPANTS_RANGE,
    COLUMN_HEADERS,
    STATUS_QUEUED,
    STATUS_ACTIVE,
    STATUS_INACTIVE,
    ParticipantsColumn,
)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_SHEETS_ID_PATTERN = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")

SHEET_NOT_ACCESSIBLE_ERROR = (
    "The Google Sheet has not been shared with the bot's service account, or the link is invalid."
)

_sheets_service = None


class SheetNotSetupError(Exception):
    """Raised when the Participants sheet tab does not exist or its range is invalid."""
    pass


def _get_sheets_service():
    global _sheets_service
    if _sheets_service is None:
        print(f"[sheets] Loading service account credentials from secret: {constants.GOOGLE_SHEETS_SECRET_NAME}")
        client = boto3.client("secretsmanager", region_name=constants.AWS_REGION)
        response = client.get_secret_value(SecretId=constants.GOOGLE_SHEETS_SECRET_NAME)
        service_account_info = json.loads(response["SecretString"])
        creds = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=_SCOPES
        )
        _sheets_service = build("sheets", "v4", credentials=creds)
        print("[sheets] Sheets service initialized")
    return _sheets_service


def extract_spreadsheet_id(url: str) -> str | None:
    match = _SHEETS_ID_PATTERN.search(url)
    return match.group(1) if match else None


def setup_league_participants_sheet(spreadsheet_url: str) -> None:
    """Creates the Participants sheet tab with bold headers. Raises PermissionError if not shared."""
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    print(f"[sheets] setup_league_participants_sheet: url={spreadsheet_url!r} spreadsheet_id={spreadsheet_id!r}")
    if not spreadsheet_id:
        raise ValueError(f"Could not extract spreadsheet ID from URL: {spreadsheet_url}")

    try:
        service = _get_sheets_service()
        metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        print(f"[sheets] spreadsheet accessible, title={metadata.get('properties', {}).get('title')!r}")
    except HttpError as e:
        print(f"[sheets] HttpError accessing spreadsheet {spreadsheet_id!r}: status={e.resp.status} body={e.content}")
        if e.resp.status in (403, 404):
            raise PermissionError(SHEET_NOT_ACCESSIBLE_ERROR)
        raise
    except json.JSONDecodeError as e:
        print(f"[sheets] JSONDecodeError accessing spreadsheet {spreadsheet_id!r}: {e}")
        raise PermissionError(SHEET_NOT_ACCESSIBLE_ERROR)

    sheets = metadata.get("sheets", [])
    existing_titles = [s["properties"]["title"] for s in sheets]

    if PARTICIPANTS_SHEET not in existing_titles:
        result = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": PARTICIPANTS_SHEET}}}]}
        ).execute()
        sheet_id = result["replies"][0]["addSheet"]["properties"]["sheetId"]
        existing_rule_count = 0
    else:
        sheet_data = next(s for s in sheets if s["properties"]["title"] == PARTICIPANTS_SHEET)
        sheet_id = sheet_data["properties"]["sheetId"]
        existing_rule_count = len(sheet_data.get("conditionalFormats", []))

    # Write header row
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{PARTICIPANTS_SHEET}!A1",
        valueInputOption="USER_ENTERED",
        body={"values": [COLUMN_HEADERS]}
    ).execute()

    # Apply bold formatting to header row and conditional formatting for Status column
    num_cols = len(COLUMN_HEADERS)
    full_range = {"sheetId": sheet_id, "startRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": num_cols}

    def _status_rule(status: str, red: float, green: float, blue: float) -> dict:
        return {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [full_range],
                    "booleanRule": {
                        "condition": {
                            "type": "TEXT_EQ",
                            "values": [{"userEnteredValue": status}],
                        },
                        "format": {
                            "backgroundColor": {"red": red, "green": green, "blue": blue}
                        },
                    },
                },
                "index": 0,
            }
        }

    # Delete existing rules in reverse order so indices stay stable during deletion
    delete_requests = [
        {"deleteConditionalFormatRule": {"sheetId": sheet_id, "index": i}}
        for i in range(existing_rule_count - 1, -1, -1)
    ]

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                *delete_requests,
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": num_cols,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": True}
                            }
                        },
                        "fields": "userEnteredFormat.textFormat.bold",
                    }
                },
                # ACTIVE: subtle green  (#D9EAD3)
                _status_rule(STATUS_ACTIVE,   red=0.851, green=0.918, blue=0.827),
                # QUEUED: subtle yellow (#FFF2CC)
                _status_rule(STATUS_QUEUED,   red=1.0,   green=0.949, blue=0.800),
                # INACTIVE: subtle grey (#EFEFEF)
                _status_rule(STATUS_INACTIVE, red=0.937, green=0.937, blue=0.937),
            ]
        }
    ).execute()


def append_league_participant(spreadsheet_url: str, discord_id: str, participant_name: str) -> None:
    """Appends a participant row to the Participants sheet. Raises PermissionError if not shared,
    SheetNotSetupError if the Participants tab doesn't exist."""
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    print(f"[sheets] append_league_participant: spreadsheet_id={spreadsheet_id!r} discord_id={discord_id!r}")
    if not spreadsheet_id:
        raise ValueError(f"Could not extract spreadsheet ID from URL: {spreadsheet_url}")

    row = [""] * len(COLUMN_HEADERS)
    row[ParticipantsColumn.DISCORD_ID] = discord_id
    row[ParticipantsColumn.PARTICIPANT_NAME] = participant_name
    row[ParticipantsColumn.STATUS] = STATUS_QUEUED

    try:
        service = _get_sheets_service()
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=PARTICIPANTS_RANGE,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
        print(f"[sheets] participant appended successfully: discord_id={discord_id!r}")
    except HttpError as e:
        print(f"[sheets] HttpError appending participant {discord_id!r} to {spreadsheet_id!r}: status={e.resp.status} body={e.content}")
        if e.resp.status in (403, 404):
            raise PermissionError(SHEET_NOT_ACCESSIBLE_ERROR)
        if e.resp.status == 400:
            raise SheetNotSetupError("Participants sheet tab not found or range is invalid.")
        raise
    except json.JSONDecodeError as e:
        print(f"[sheets] JSONDecodeError appending participant to {spreadsheet_id!r}: {e}")
        raise PermissionError(SHEET_NOT_ACCESSIBLE_ERROR)


def get_active_participants(spreadsheet_url: str) -> dict:
    """Returns {discord_id: participant_name} for all ACTIVE participants. Raises PermissionError if not shared."""
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    print(f"[sheets] get_active_participants: spreadsheet_id={spreadsheet_id!r}")
    if not spreadsheet_id:
        raise ValueError(f"Could not extract spreadsheet ID from URL: {spreadsheet_url}")

    try:
        service = _get_sheets_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=PARTICIPANTS_RANGE,
        ).execute()
    except HttpError as e:
        print(f"[sheets] HttpError reading participants from {spreadsheet_id!r}: status={e.resp.status} body={e.content}")
        if e.resp.status in (403, 404):
            raise PermissionError(SHEET_NOT_ACCESSIBLE_ERROR)
        raise
    except json.JSONDecodeError as e:
        print(f"[sheets] JSONDecodeError reading participants from {spreadsheet_id!r}: {e}")
        raise PermissionError(SHEET_NOT_ACCESSIBLE_ERROR)

    rows = result.get("values", [])
    active = {}
    for row in rows[1:]:  # skip header row
        status = row[ParticipantsColumn.STATUS] if len(row) > ParticipantsColumn.STATUS else ""
        if status != STATUS_ACTIVE:
            continue
        discord_id = row[ParticipantsColumn.DISCORD_ID] if len(row) > ParticipantsColumn.DISCORD_ID else ""
        participant_name = row[ParticipantsColumn.PARTICIPANT_NAME] if len(row) > ParticipantsColumn.PARTICIPANT_NAME else ""
        if discord_id:
            active[discord_id] = participant_name
    return active
