import unittest

from commands.event.startgg.models.startgg_event import StartggEvent, _unix_to_utc_iso
from database.models.participant import Participant


class TestUnixToUtcIso(unittest.TestCase):
    def test_none_returns_none(self):
        self.assertIsNone(_unix_to_utc_iso(None))

    def test_unix_zero_returns_epoch(self):
        self.assertEqual(_unix_to_utc_iso(0), "1970-01-01T00:00:00Z")

    def test_known_timestamp(self):
        # 1735689600 = 2025-01-01T00:00:00Z
        self.assertEqual(_unix_to_utc_iso(1735689600), "2025-01-01T00:00:00Z")


class TestStartggEventFromDict(unittest.TestCase):
    def _base_event_data(self, **overrides):
        data = {
            "name": "Main Bracket",
            "startAt": 1735689600,  # 2025-01-01T00:00:00Z
            "endAt": 1735693200,    # 2025-01-01T01:00:00Z
            "tournament": {
                "name": "Midweek Melting",
                "venueName": "The Arena",
                "venueAddress": None,
            },
            "entrants": {"nodes": []},
        }
        data.update(overrides)
        return data

    def test_basic_fields_parsed(self):
        event = StartggEvent.from_dict(self._base_event_data())
        self.assertEqual(event.tourney_name, "Midweek Melting")
        self.assertEqual(event.event_name, "Main Bracket")
        self.assertEqual(event.start_time_utc, "2025-01-01T00:00:00Z")
        self.assertEqual(event.location, "The Arena")

    def test_event_name_falls_back_to_tourney_name(self):
        data = self._base_event_data()
        del data["name"]
        event = StartggEvent.from_dict(data)
        self.assertEqual(event.event_name, "Midweek Melting")

    def test_location_falls_back_to_venue_address(self):
        data = self._base_event_data()
        data["tournament"]["venueName"] = None
        data["tournament"]["venueAddress"] = "123 Main St"
        event = StartggEvent.from_dict(data)
        self.assertEqual(event.location, "123 Main St")

    def test_location_defaults_to_online_when_no_venue(self):
        data = self._base_event_data()
        data["tournament"]["venueName"] = None
        data["tournament"]["venueAddress"] = None
        event = StartggEvent.from_dict(data)
        self.assertEqual(event.location, "Online")

    def test_missing_times_are_none(self):
        data = self._base_event_data()
        data["startAt"] = None
        data["endAt"] = None
        event = StartggEvent.from_dict(data)
        self.assertIsNone(event.start_time_utc)
        self.assertIsNone(event.end_time_utc)

    def test_participant_with_discord_added_to_registered(self):
        data = self._base_event_data()
        data["entrants"]["nodes"] = [
            {
                "participants": [{
                    "gamerTag": "Player1",
                    "id": 42,
                    "user": {
                        "authorizations": [{"externalId": "U123"}]
                    }
                }]
            }
        ]
        event = StartggEvent.from_dict(data)
        self.assertEqual(len(event.participants), 1)
        self.assertEqual(event.participants[0].user_id, "U123")
        self.assertEqual(event.participants[0].display_name, "Player1")
        self.assertEqual(len(event.no_discord_participants), 0)

    def test_participant_without_discord_added_to_no_discord(self):
        data = self._base_event_data()
        data["entrants"]["nodes"] = [
            {
                "participants": [{
                    "gamerTag": "OfflinePlayer",
                    "id": 99,
                    "user": {"authorizations": None}
                }]
            }
        ]
        event = StartggEvent.from_dict(data)
        self.assertEqual(len(event.no_discord_participants), 1)
        self.assertEqual(event.no_discord_participants[0].display_name, "OfflinePlayer")
        self.assertEqual(event.no_discord_participants[0].user_id, Participant.DEFAULT_ID_PLACEHOLDER)
        self.assertEqual(len(event.participants), 0)

    def test_mixed_participants_split_correctly(self):
        data = self._base_event_data()
        data["entrants"]["nodes"] = [
            {
                "participants": [{
                    "gamerTag": "LinkedPlayer",
                    "id": 1,
                    "user": {"authorizations": [{"externalId": "U1"}]}
                }]
            },
            {
                "participants": [{
                    "gamerTag": "NoDiscordPlayer",
                    "id": 2,
                    "user": {"authorizations": None}
                }]
            }
        ]
        event = StartggEvent.from_dict(data)
        self.assertEqual(len(event.participants), 1)
        self.assertEqual(len(event.no_discord_participants), 1)

    def test_empty_entrants_returns_empty_lists(self):
        event = StartggEvent.from_dict(self._base_event_data())
        self.assertEqual(event.participants, [])
        self.assertEqual(event.no_discord_participants, [])


if __name__ == "__main__":
    unittest.main()
