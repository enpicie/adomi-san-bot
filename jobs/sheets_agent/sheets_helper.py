import datetime
import json
import re

import boto3
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import constants
import participants_sheet
import report_log
from participants_sheet import (
    SHEET_NAME as PARTICIPANTS_SHEET,
    SHEET_RANGE as PARTICIPANTS_RANGE,
    COLUMN_HEADERS,
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
        secret_name = constants.GOOGLE_SHEETS_SECRET_NAME
        print(f"[sheets] _get_sheets_service: loading credentials from secret={secret_name!r}")
        client = boto3.client("secretsmanager", region_name=constants.AWS_REGION)
        response = client.get_secret_value(SecretId=secret_name)
        raw = response.get("SecretString", "")
        if not raw:
            raise RuntimeError(
                f"[sheets] _get_sheets_service: secret {secret_name!r} is empty — "
                "populate it with the service account JSON in AWS Secrets Manager"
            )
        try:
            service_account_info = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"[sheets] _get_sheets_service: secret {secret_name!r} is not valid JSON — {e}"
            )
        creds = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=_SCOPES
        )
        _sheets_service = build("sheets", "v4", credentials=creds)
        print(f"[sheets] _get_sheets_service: service initialized OK")
    return _sheets_service


def extract_spreadsheet_id(url: str) -> str | None:
    match = _SHEETS_ID_PATTERN.search(url)
    return match.group(1) if match else None


def setup_league_participants_sheet(spreadsheet_url: str) -> bool:
    """Returns True if the Participants tab already existed, False if it was newly created."""
    """Creates the Participants sheet tab with bold headers. Raises PermissionError if not shared."""
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    print(f"[sheets] setup_league_participants_sheet: spreadsheet_id={spreadsheet_id!r}")
    if not spreadsheet_id:
        raise ValueError(f"[sheets] setup_league_participants_sheet: could not extract ID from url={spreadsheet_url!r}")

    try:
        service = _get_sheets_service()
        metadata = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="properties.title,sheets.properties,sheets.conditionalFormats",
        ).execute()
        print(f"[sheets] setup_league_participants_sheet: accessible, title={metadata.get('properties', {}).get('title')!r}")
    except HttpError as e:
        print(f"[sheets] setup_league_participants_sheet: HttpError status={e.resp.status} body={e.content}")
        if e.resp.status in (403, 404):
            raise PermissionError(SHEET_NOT_ACCESSIBLE_ERROR)
        raise

    sheets = metadata.get("sheets", [])
    existing_titles = [s["properties"]["title"] for s in sheets]

    already_existed = PARTICIPANTS_SHEET in existing_titles
    if not already_existed:
        result = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": PARTICIPANTS_SHEET}}}]}
        ).execute()
        sheet_id = result["replies"][0]["addSheet"]["properties"]["sheetId"]
        existing_rule_count = 0
        print(f"[sheets] setup_league_participants_sheet: created Participants tab sheet_id={sheet_id}")
    else:
        sheet_data = next(s for s in sheets if s["properties"]["title"] == PARTICIPANTS_SHEET)
        sheet_id = sheet_data["properties"]["sheetId"]
        existing_rule_count = len(sheet_data.get("conditionalFormats", []))
        print(f"[sheets] setup_league_participants_sheet: Participants tab exists sheet_id={sheet_id} existing_rules={existing_rule_count}")

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{PARTICIPANTS_SHEET}!A1",
        valueInputOption="USER_ENTERED",
        body={"values": [COLUMN_HEADERS + [participants_sheet.CURRENT_ROTATION_LABEL, ""]]}
    ).execute()

    num_cols = len(COLUMN_HEADERS)
    status_col_range = {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 10000, "startColumnIndex": 0, "endColumnIndex": 1}

    def _status_rule(status: str, red: float, green: float, blue: float) -> dict:
        return {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [status_col_range],
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

    delete_requests = [
        {"deleteConditionalFormatRule": {"sheetId": sheet_id, "index": i}}
        for i in range(existing_rule_count - 1, -1, -1)
    ]

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                *delete_requests,
                # Participant Name column (C, index 2): 2x default width (200px)
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": ParticipantsColumn.PARTICIPANT_NAME,
                            "endIndex": ParticipantsColumn.PARTICIPANT_NAME + 1,
                        },
                        "properties": {"pixelSize": 200},
                        "fields": "pixelSize",
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": ParticipantsColumn.NOTES,
                            "endIndex": ParticipantsColumn.NOTES + 1,
                        },
                        "properties": {"pixelSize": 400},
                        "fields": "pixelSize",
                    }
                },
                # Status column (A): center all text
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startColumnIndex": 0,
                            "endColumnIndex": 1,
                        },
                        "cell": {
                            "userEnteredFormat": {"horizontalAlignment": "CENTER"}
                        },
                        "fields": "userEnteredFormat.horizontalAlignment",
                    }
                },
                # Freeze header row
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sheet_id,
                            "gridProperties": {"frozenRowCount": 1},
                        },
                        "fields": "gridProperties.frozenRowCount",
                    }
                },
                # Header row: black background, white bold text
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
                                "backgroundColor": {"red": 0.0, "green": 0.0, "blue": 0.0},
                                "textFormat": {"bold": True, "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}},
                            }
                        },
                        "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat.bold,userEnteredFormat.textFormat.foregroundColor",
                    }
                },
                # Data rows: explicitly not bold
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": num_cols,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": False},
                            }
                        },
                        "fields": "userEnteredFormat.textFormat.bold",
                    }
                },
                _status_rule(participants_sheet.STATUS_ACTIVE,   red=0.820, green=0.894, blue=0.820),
                _status_rule(participants_sheet.STATUS_QUEUED,   red=0.957, green=0.941, blue=0.796),
                _status_rule(participants_sheet.STATUS_INACTIVE, red=0.878, green=0.878, blue=0.878),
                _status_rule(participants_sheet.STATUS_DNF,      red=0.957, green=0.816, blue=0.816),
                # Light grey right border on Notes column — visual separator before score reporting columns
                {
                    "updateBorders": {
                        "range": {
                            "sheetId": sheet_id,
                            "startColumnIndex": ParticipantsColumn.NOTES,
                            "endColumnIndex": ParticipantsColumn.NOTES + 1,
                        },
                        "right": {
                            "style": "SOLID_MEDIUM",
                            "color": {"red": 0.6, "green": 0.6, "blue": 0.6},
                        },
                    }
                },
                # Metadata header cells (Current Rotation: label + value): subtle grey background, label bold
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": participants_sheet.CURRENT_ROTATION_LABEL_COL,
                            "endColumnIndex": participants_sheet.CURRENT_ROTATION_VALUE_COL + 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                                "textFormat": {"bold": False, "foregroundColor": {"red": 0.0, "green": 0.0, "blue": 0.0}},
                            }
                        },
                        "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat.bold,userEnteredFormat.textFormat.foregroundColor",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": participants_sheet.CURRENT_ROTATION_LABEL_COL,
                            "endColumnIndex": participants_sheet.CURRENT_ROTATION_LABEL_COL + 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": True},
                            }
                        },
                        "fields": "userEnteredFormat.textFormat.bold",
                    }
                },
                # Status column dropdown validation (rows 2+)
                {
                    "setDataValidation": {
                        "range": status_col_range,
                        "rule": {
                            "condition": {
                                "type": "ONE_OF_LIST",
                                "values": [{"userEnteredValue": s} for s in participants_sheet.ALL_STATUSES],
                            },
                            "showCustomUi": True,
                            "strict": False,
                        },
                    }
                },
            ]
        }
    ).execute()
    print(f"[sheets] setup_league_participants_sheet: headers and formatting applied OK already_existed={already_existed}")
    return already_existed


def append_league_participant(spreadsheet_url: str, discord_id: str, participant_name: str) -> None:
    """Appends a participant row to the Participants sheet. Raises PermissionError if not shared,
    SheetNotSetupError if the Participants tab doesn't exist."""
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    print(f"[sheets] append_league_participant: spreadsheet_id={spreadsheet_id!r} discord_id={discord_id!r} name={participant_name!r}")
    if not spreadsheet_id:
        raise ValueError(f"[sheets] append_league_participant: could not extract ID from url={spreadsheet_url!r}")

    row = [""] * len(COLUMN_HEADERS)
    row[ParticipantsColumn.DISCORD_ID] = discord_id
    row[ParticipantsColumn.PARTICIPANT_NAME] = participant_name
    row[ParticipantsColumn.STATUS] = participants_sheet.STATUS_QUEUED

    try:
        service = _get_sheets_service()
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=PARTICIPANTS_RANGE,
            valueInputOption="USER_ENTERED",
            insertDataOption="OVERWRITE",
            body={"values": [row]},
        ).execute()
        print(f"[sheets] append_league_participant: appended OK discord_id={discord_id!r}")
    except HttpError as e:
        print(f"[sheets] append_league_participant: HttpError status={e.resp.status} body={e.content}")
        if e.resp.status in (403, 404):
            raise PermissionError(SHEET_NOT_ACCESSIBLE_ERROR)
        if e.resp.status == 400:
            raise SheetNotSetupError("Participants sheet tab not found or range is invalid.")
        raise


def find_participant(spreadsheet_url: str, discord_id: str) -> tuple[int | None, str | None]:
    """Returns (sheet_row_number, status) for a participant matched by discord_id, or (None, None) if not found.
    sheet_row_number is 1-based (row 2 = first data row). Raises PermissionError if not shared."""
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    print(f"[sheets] find_participant: spreadsheet_id={spreadsheet_id!r} discord_id={discord_id!r}")
    if not spreadsheet_id:
        raise ValueError(f"[sheets] find_participant: could not extract ID from url={spreadsheet_url!r}")

    try:
        service = _get_sheets_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=PARTICIPANTS_RANGE,
        ).execute()
    except HttpError as e:
        if e.resp.status in (403, 404):
            raise PermissionError(SHEET_NOT_ACCESSIBLE_ERROR)
        raise

    rows = result.get("values", [])
    for i, row in enumerate(rows[1:], start=2):
        row_id = row[ParticipantsColumn.DISCORD_ID] if len(row) > ParticipantsColumn.DISCORD_ID else ""
        if row_id == discord_id:
            status = row[ParticipantsColumn.STATUS] if len(row) > ParticipantsColumn.STATUS else ""
            print(f"[sheets] find_participant: found discord_id={discord_id!r} at row={i} status={status!r}")
            return i, status

    print(f"[sheets] find_participant: discord_id={discord_id!r} not found")
    return None, None


def update_participant_status(spreadsheet_url: str, row_number: int, new_status: str) -> None:
    """Updates the Status cell of a participant row. Raises PermissionError if not shared."""
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    print(f"[sheets] update_participant_status: spreadsheet_id={spreadsheet_id!r} row={row_number} status={new_status!r}")
    if not spreadsheet_id:
        raise ValueError(f"[sheets] update_participant_status: could not extract ID from url={spreadsheet_url!r}")

    try:
        service = _get_sheets_service()
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{PARTICIPANTS_SHEET}!A{row_number}",
            valueInputOption="USER_ENTERED",
            body={"values": [[new_status]]},
        ).execute()
        print(f"[sheets] update_participant_status: updated OK row={row_number} status={new_status!r}")
    except HttpError as e:
        if e.resp.status in (403, 404):
            raise PermissionError(SHEET_NOT_ACCESSIBLE_ERROR)
        raise


def get_active_participants(spreadsheet_url: str) -> dict:
    """Returns {discord_id: participant_name} for all ACTIVE participants. Raises PermissionError if not shared."""
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    print(f"[sheets] get_active_participants: spreadsheet_id={spreadsheet_id!r}")
    if not spreadsheet_id:
        raise ValueError(f"[sheets] get_active_participants: could not extract ID from url={spreadsheet_url!r}")

    try:
        service = _get_sheets_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=PARTICIPANTS_RANGE,
        ).execute()
    except HttpError as e:
        print(f"[sheets] get_active_participants: HttpError status={e.resp.status} body={e.content}")
        if e.resp.status in (403, 404):
            raise PermissionError(SHEET_NOT_ACCESSIBLE_ERROR)
        raise

    rows = result.get("values", [])
    print(f"[sheets] get_active_participants: got {len(rows)} rows (including header)")
    active = {}
    for row in rows[1:]:
        status = row[ParticipantsColumn.STATUS] if len(row) > ParticipantsColumn.STATUS else ""
        if status != participants_sheet.STATUS_ACTIVE:
            continue
        discord_id = row[ParticipantsColumn.DISCORD_ID] if len(row) > ParticipantsColumn.DISCORD_ID else ""
        participant_name = row[ParticipantsColumn.PARTICIPANT_NAME] if len(row) > ParticipantsColumn.PARTICIPANT_NAME else ""
        if discord_id:
            active[discord_id] = participant_name
    print(f"[sheets] get_active_participants: found {len(active)} ACTIVE participant(s)")
    return active


def _cell_value(row: list, col: int) -> str:
    return row[col] if len(row) > col else ""


def get_score_report_data(spreadsheet_url: str, winner_id: str, loser_id: str) -> dict:
    """Looks up both participants and validates they share a tier/group.
    Returns a dict with positioning data and the current rotation sheet name.
    Raises ValueError for validation errors, PermissionError if not accessible."""
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    if not spreadsheet_id:
        raise ValueError(f"[sheets] get_score_report_data: could not extract ID from url={spreadsheet_url!r}")

    current_rotation_range = f"{PARTICIPANTS_SHEET}!K1"
    try:
        service = _get_sheets_service()
        result = service.spreadsheets().values().batchGet(
            spreadsheetId=spreadsheet_id,
            ranges=[PARTICIPANTS_RANGE, current_rotation_range],
        ).execute()
    except HttpError as e:
        print(f"[sheets] get_score_report_data: HttpError status={e.resp.status} body={e.content}")
        if e.resp.status in (403, 404):
            raise PermissionError(SHEET_NOT_ACCESSIBLE_ERROR)
        raise

    rows = result["valueRanges"][0].get("values", [])
    rotation_values = result["valueRanges"][1].get("values", [])
    current_rotation = rotation_values[0][0] if rotation_values and rotation_values[0] else ""
    if not current_rotation:
        raise ValueError("Current Rotation is not set on the Participants sheet (cell K1).")

    winner_row = loser_row = None
    for row in rows[1:]:
        rid = _cell_value(row, ParticipantsColumn.DISCORD_ID)
        if rid == winner_id:
            winner_row = row
        elif rid == loser_id:
            loser_row = row
        if winner_row is not None and loser_row is not None:
            break

    if winner_row is None:
        raise ValueError(f"Winner `@{winner_id}` not found in the Participants sheet.")
    if loser_row is None:
        raise ValueError(f"Loser `@{loser_id}` not found in the Participants sheet.")

    winner_tier  = _cell_value(winner_row, ParticipantsColumn.TIER)
    winner_group = _cell_value(winner_row, ParticipantsColumn.GROUP_NUMBER)
    loser_tier   = _cell_value(loser_row,  ParticipantsColumn.TIER)
    loser_group  = _cell_value(loser_row,  ParticipantsColumn.GROUP_NUMBER)

    if winner_tier != loser_tier or winner_group != loser_group:
        raise ValueError(
            f"Players are in different groups: `@{winner_id}` is Tier {winner_tier or '?'} Group {winner_group or '?'}, "
            f"`@{loser_id}` is Tier {loser_tier or '?'} Group {loser_group or '?'}."
        )

    winner_wins_row   = _cell_value(winner_row, ParticipantsColumn.WINS_ROW)
    winner_losses_col = _cell_value(winner_row, ParticipantsColumn.LOSSES_COL)
    loser_wins_row    = _cell_value(loser_row,  ParticipantsColumn.WINS_ROW)
    loser_losses_col  = _cell_value(loser_row,  ParticipantsColumn.LOSSES_COL)

    if not winner_wins_row or not winner_losses_col:
        raise ValueError(f"`@{winner_id}` is missing Wins Row or Losses Col data in the Participants sheet.")
    if not loser_wins_row or not loser_losses_col:
        raise ValueError(f"`@{loser_id}` is missing Wins Row or Losses Col data in the Participants sheet.")

    print(
        f"[sheets] get_score_report_data: winner={winner_id!r} wins_row={winner_wins_row} losses_col={winner_losses_col} | "
        f"loser={loser_id!r} wins_row={loser_wins_row} losses_col={loser_losses_col} | rotation={current_rotation!r}"
    )
    return {
        "current_rotation": current_rotation,
        "tier": winner_tier,
        "group": winner_group,
        "winner_wins_row":   winner_wins_row,
        "winner_losses_col": winner_losses_col,
        "loser_wins_row":    loser_wins_row,
        "loser_losses_col":  loser_losses_col,
    }


def update_score_cells(
    spreadsheet_url: str,
    score_data: dict,
    winner_score: int,
    loser_score: int,
) -> tuple[str, str]:
    """Writes winner and loser scores to the score matrix on the current rotation sheet.
    Returns (prev_winner_score, prev_loser_score) for transparency — empty string if cell was blank."""
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    if not spreadsheet_id:
        raise ValueError(f"[sheets] update_score_cells: could not extract ID from url={spreadsheet_url!r}")

    rotation = score_data["current_rotation"]
    # Winner's win cell: winner's row × loser's loss column
    winner_cell = f"{rotation}!{score_data['loser_losses_col']}{score_data['winner_wins_row']}"
    # Loser's win cell: loser's row × winner's loss column
    loser_cell  = f"{rotation}!{score_data['winner_losses_col']}{score_data['loser_wins_row']}"
    print(f"[sheets] update_score_cells: winner_cell={winner_cell!r} loser_cell={loser_cell!r}")

    try:
        service = _get_sheets_service()
        existing = service.spreadsheets().values().batchGet(
            spreadsheetId=spreadsheet_id,
            ranges=[winner_cell, loser_cell],
        ).execute()

        def _read_cell(value_range):
            vals = value_range.get("values", [])
            return vals[0][0] if vals and vals[0] else ""

        prev_winner = _read_cell(existing["valueRanges"][0])
        prev_loser  = _read_cell(existing["valueRanges"][1])

        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "valueInputOption": "USER_ENTERED",
                "data": [
                    {"range": winner_cell, "values": [[str(winner_score)]]},
                    {"range": loser_cell,  "values": [[str(loser_score)]]},
                ],
            },
        ).execute()
        print(f"[sheets] update_score_cells: wrote winner={winner_score} loser={loser_score} (prev: {prev_winner!r}, {prev_loser!r})")
        return prev_winner, prev_loser

    except HttpError as e:
        print(f"[sheets] update_score_cells: HttpError status={e.resp.status} body={e.content}")
        if e.resp.status in (403, 404):
            raise PermissionError(SHEET_NOT_ACCESSIBLE_ERROR)
        raise


def append_report_log(
    spreadsheet_url: str,
    league_id: str,
    tier: str,
    group: str,
    winner_id: str,
    loser_id: str,
    winner_score: int,
    loser_score: int,
) -> None:
    """Creates the ReportLog sheet if it does not exist, then appends one row."""
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    if not spreadsheet_id:
        raise ValueError(f"[sheets] append_report_log: could not extract ID from url={spreadsheet_url!r}")

    try:
        service = _get_sheets_service()
        metadata = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id, fields="sheets.properties"
        ).execute()
        existing_titles = [s["properties"]["title"] for s in metadata.get("sheets", [])]

        if report_log.SHEET_NAME not in existing_titles:
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": report_log.SHEET_NAME}}}]},
            ).execute()
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{report_log.SHEET_NAME}!A1",
                valueInputOption="USER_ENTERED",
                body={"values": [report_log.COLUMN_HEADERS]},
            ).execute()
            print(f"[sheets] append_report_log: created {report_log.SHEET_NAME} tab with headers")

        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        row = [""] * len(report_log.COLUMN_HEADERS)
        row[report_log.ReportLogColumn.LEAGUE_ID]     = league_id
        row[report_log.ReportLogColumn.TIER]          = tier
        row[report_log.ReportLogColumn.GROUP]         = group
        row[report_log.ReportLogColumn.WINNER]        = winner_id
        row[report_log.ReportLogColumn.LOSER]         = loser_id
        row[report_log.ReportLogColumn.WINNER_SCORE]  = str(winner_score)
        row[report_log.ReportLogColumn.LOSER_SCORE]   = str(loser_score)
        row[report_log.ReportLogColumn.TIMESTAMP]     = timestamp

        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=report_log.SHEET_RANGE,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
        print(f"[sheets] append_report_log: logged {winner_id} def {loser_id} {winner_score}-{loser_score}")

    except HttpError as e:
        print(f"[sheets] append_report_log: HttpError status={e.resp.status} body={e.content}")
        if e.resp.status in (403, 404):
            raise PermissionError(SHEET_NOT_ACCESSIBLE_ERROR)
        raise
