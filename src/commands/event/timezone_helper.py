from dataclasses import dataclass
from datetime import datetime
from typing import List
from zoneinfo import ZoneInfo

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


def to_utc_iso(datetime_str: str, zoneinfo_key: str) -> str:
    """Convert a local datetime string and IANA timezone key to a UTC ISO 8601 string.

    datetime_str: "YYYY-MM-DD HH:MM" (24-hour time, as entered by the user)
    zoneinfo_key: value from TimezoneOption / autocomplete (e.g. "America/New_York")
    returns: "YYYY-MM-DDTHH:MM:SSZ" (UTC, suitable for Discord API and database storage)
    """
    tz = ZoneInfo(zoneinfo_key)
    local_dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
