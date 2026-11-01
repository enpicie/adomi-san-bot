# MIRROR: src/commands/event/timezone_helper.py — keep in sync (independent Lambda
# packaging prevents imports). Only the conversion side is mirrored; the autocomplete
# options live in src, which is what serves them.
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Display names Discord may repopulate an autocomplete field with instead of the
# IANA key. Must match TIMEZONE_OPTIONS in the src helper.
_DISPLAY_NAME_TO_KEY = {
    "UTC": "UTC",
    "Eastern Time (US)": "America/New_York",
    "Central Time (US)": "America/Chicago",
    "Mountain Time (US)": "America/Denver",
    "Pacific Time (US)": "America/Los_Angeles",
    "London": "Europe/London",
    "Paris / Berlin": "Europe/Paris",
    "Tokyo": "Asia/Tokyo",
    "Shanghai": "Asia/Shanghai",
    "Sydney": "Australia/Sydney",
    "São Paulo (Brazil)": "America/Sao_Paulo",
    "Buenos Aires (Argentina)": "America/Argentina/Buenos_Aires",
    "Santiago (Chile)": "America/Santiago",
    "Bogotá (Colombia)": "America/Bogota",
    "Lima (Peru)": "America/Lima",
    "Caracas (Venezuela)": "America/Caracas",
}


def _resolve_zoneinfo_key(value: str) -> str:
    """Accept either an IANA key or a display name (Discord autocomplete repopulation fallback)."""
    return _DISPLAY_NAME_TO_KEY.get(value, value)


class InvalidTimeInputError(ValueError):
    """A time or timezone the user typed can't be read. The message is shown to the user as-is."""


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
    returns: "YYYY-MM-DDTHH:MM:SSZ"
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
    return local_dt.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")
