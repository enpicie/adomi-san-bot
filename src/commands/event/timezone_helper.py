from dataclasses import dataclass
from datetime import datetime
from typing import List
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from commands.models.command_param import ParamChoice


@dataclass
class TimezoneOption:
    display_name: str  # shown to user in autocomplete
    zoneinfo_key: str  # IANA key used with ZoneInfo() for UTC conversion

    def to_param_choice(self) -> ParamChoice:
        return ParamChoice(name=self.display_name, value=self.zoneinfo_key)


TIMEZONE_OPTIONS: List[TimezoneOption] = [
    TimezoneOption("UTC",                      "UTC"),
    TimezoneOption("Eastern Time (US)",        "America/New_York"),
    TimezoneOption("Central Time (US)",        "America/Chicago"),
    TimezoneOption("Mountain Time (US)",       "America/Denver"),
    TimezoneOption("Pacific Time (US)",        "America/Los_Angeles"),
    TimezoneOption("London",                   "Europe/London"),
    TimezoneOption("Paris / Berlin",           "Europe/Paris"),
    TimezoneOption("Tokyo",                    "Asia/Tokyo"),
    TimezoneOption("Shanghai",                 "Asia/Shanghai"),
    TimezoneOption("Sydney",                   "Australia/Sydney"),
    TimezoneOption("São Paulo (Brazil)",       "America/Sao_Paulo"),
    TimezoneOption("Buenos Aires (Argentina)", "America/Argentina/Buenos_Aires"),
    TimezoneOption("Santiago (Chile)",         "America/Santiago"),
    TimezoneOption("Bogotá (Colombia)",        "America/Bogota"),
    TimezoneOption("Lima (Peru)",              "America/Lima"),
    TimezoneOption("Caracas (Venezuela)",      "America/Caracas"),
]


_DISPLAY_NAME_TO_KEY = {opt.display_name: opt.zoneinfo_key for opt in TIMEZONE_OPTIONS}


def _resolve_zoneinfo_key(value: str) -> str:
    """Accept either an IANA key or a display name (Discord autocomplete repopulation fallback)."""
    return _DISPLAY_NAME_TO_KEY.get(value, value)


class InvalidTimeInputError(ValueError):
    """A time or timezone the user typed can't be read. The message is shown to the user as-is."""


# MIRROR: jobs/deferred_worker/timezone_helper.py — keep these messages in sync.
INVALID_TIMEZONE_MESSAGE = (
    "😖 Sorry! I don't recognize that timezone. "
    "Pick one from the list that pops up as you type in the `timezone` field."
)
INVALID_DATETIME_MESSAGE = (
    "😖 Sorry! I couldn't read that time. "
    "Use the format `2026-03-19 19:30` (year-month-day, 24-hour time)."
)


def to_utc_iso(datetime_str: str, zoneinfo_key: str) -> str:
    """Convert a local datetime string and IANA timezone key to a UTC ISO 8601 string.

    datetime_str: "YYYY-MM-DD HH:MM" (24-hour time, as entered by the user)
    zoneinfo_key: value from TimezoneOption / autocomplete (e.g. "America/New_York")
    returns: "YYYY-MM-DDTHH:MM:SSZ" (UTC, suitable for Discord API and database storage)
    :raises InvalidTimeInputError: if the timezone or the datetime string can't be read.
    """
    try:
        tz = ZoneInfo(_resolve_zoneinfo_key(zoneinfo_key))
    except (ZoneInfoNotFoundError, ValueError):
        raise InvalidTimeInputError(INVALID_TIMEZONE_MESSAGE) from None
    try:
        local_dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    except ValueError:
        raise InvalidTimeInputError(INVALID_DATETIME_MESSAGE) from None
    utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
