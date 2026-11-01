import unittest
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import Mock, patch

import commands.event.event_helper as event_helper
from database.models.event_data import EventData


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


_NOW = datetime.now(dt_timezone.utc)
_FUTURE = _iso(_NOW + timedelta(days=2))
_PAST = _iso(_NOW - timedelta(days=2))


def _make_event_data(event_name="Weekly Bracket", startgg_url=None, end_time=_FUTURE, event_id="event_111",
                     start_time=None):
    return EventData(
        checked_in={},
        registered={},
        queue={},
        participant_role=None,
        check_in_enabled=False,
        register_enabled=True,
        start_message="",
        end_message="",
        start_time=start_time,
        end_time=end_time,
        event_id=event_id,
        event_name=event_name,
        startgg_url=startgg_url,
    )


class TestFindDuplicateEvent(unittest.TestCase):
    def _find(self, existing_events, **kwargs):
        table = Mock()
        with patch.object(event_helper.db_helper, "get_full_events_for_server", return_value=existing_events):
            return event_helper.find_duplicate_event("server123", table, **kwargs)

    def test_no_existing_events_is_not_a_duplicate(self):
        self.assertIsNone(self._find([], event_name="Weekly Bracket"))

    def test_same_startgg_bracket_is_a_duplicate(self):
        existing = _make_event_data(
            event_name="Something Else",
            startgg_url="https://www.start.gg/tournament/cte-2/event/cte-bracket",
        )
        # The same bracket cannot legitimately back two events, so the slug
        # matches even though the display names differ.
        result = self._find(
            [existing],
            event_name="Chained to Eternity 2",
            startgg_url="https://start.gg/tournament/cte-2/event/cte-bracket",
        )
        self.assertIs(result, existing)

    def test_startgg_url_matches_across_link_formatting_differences(self):
        existing = _make_event_data(
            startgg_url="https://www.start.gg/tournament/cte-2/event/cte-bracket/overview",
        )
        result = self._find(
            [existing],
            event_name="Anything",
            startgg_url="start.gg/tournament/cte-2/event/cte-bracket",
        )
        self.assertIs(result, existing)

    def test_different_bracket_with_different_name_is_not_a_duplicate(self):
        existing = _make_event_data(
            event_name="Other Weekly",
            startgg_url="https://www.start.gg/tournament/other/event/other-bracket",
        )
        result = self._find(
            [existing],
            event_name="Chained to Eternity 2",
            startgg_url="https://start.gg/tournament/cte-2/event/cte-bracket",
        )
        self.assertIsNone(result)

    def test_exact_name_match_is_a_duplicate_without_startgg(self):
        existing = _make_event_data(event_name="Weekly Bracket")
        self.assertIs(self._find([existing], event_name="Weekly Bracket"), existing)

    def test_ended_event_does_not_block_reusing_its_name(self):
        # A weekly reuses the same name every week; last week's event has ended.
        existing = _make_event_data(event_name="Weekly Bracket", end_time=_PAST)
        self.assertIsNone(self._find([existing], event_name="Weekly Bracket"))

    def test_ended_event_does_not_block_reusing_its_bracket(self):
        existing = _make_event_data(
            startgg_url="https://www.start.gg/tournament/cte-2/event/cte-bracket",
            end_time=_PAST,
        )
        result = self._find(
            [existing],
            event_name="Chained to Eternity 2",
            startgg_url="https://start.gg/tournament/cte-2/event/cte-bracket",
        )
        self.assertIsNone(result)

    def test_unparseable_end_time_is_treated_as_active(self):
        # Fail toward blocking the duplicate — a bad timestamp must not open the
        # door to the double-create this guard exists to stop.
        existing = _make_event_data(event_name="Weekly Bracket", end_time="not-a-date")
        self.assertIs(self._find([existing], event_name="Weekly Bracket"), existing)

    def test_missing_end_time_is_treated_as_active(self):
        existing = _make_event_data(event_name="Weekly Bracket", end_time=None)
        self.assertIs(self._find([existing], event_name="Weekly Bracket"), existing)

    def test_name_match_is_exact_not_fuzzy(self):
        existing = _make_event_data(event_name="Weekly Bracket")
        self.assertIsNone(self._find([existing], event_name="Weekly Bracket 2"))

    def test_returns_the_first_active_match_among_several_events(self):
        stale = _make_event_data(event_name="Weekly Bracket", end_time=_PAST, event_id="old")
        active = _make_event_data(event_name="Weekly Bracket", end_time=_FUTURE, event_id="current")
        self.assertIs(self._find([stale, active], event_name="Weekly Bracket"), active)


class TestFindDuplicateEventStartTimeScoping(unittest.TestCase):
    """Without a start time the name alone decides, which blocks an organizer
    setting up a month of the same weekly in one sitting."""

    def _find(self, existing_events, **kwargs):
        table = Mock()
        with patch.object(event_helper.db_helper, "get_full_events_for_server", return_value=existing_events):
            return event_helper.find_duplicate_event("server123", table, **kwargs)

    def test_same_name_at_a_different_start_time_is_a_separate_event(self):
        existing = _make_event_data(event_name="Midweek Melting", start_time="2099-01-07T18:00:00Z")
        result = self._find(
            [existing], event_name="Midweek Melting", start_time_utc="2099-01-14T18:00:00Z"
        )
        self.assertIsNone(result)

    def test_same_name_at_the_same_start_time_is_a_duplicate(self):
        existing = _make_event_data(event_name="Midweek Melting", start_time="2099-01-07T18:00:00Z")
        result = self._find(
            [existing], event_name="Midweek Melting", start_time_utc="2099-01-07T18:00:00Z"
        )
        self.assertIs(result, existing)

    def test_startgg_slug_wins_even_at_a_different_start_time(self):
        # The bracket is the same one, so it is a duplicate regardless of when it
        # is scheduled — start.gg times get rewritten when they are in the past.
        existing = _make_event_data(
            event_name="Whatever",
            start_time="2099-01-07T18:00:00Z",
            startgg_url="https://www.start.gg/tournament/cte-2/event/cte-bracket",
        )
        result = self._find(
            [existing],
            event_name="Chained to Eternity 2",
            start_time_utc="2099-06-06T06:00:00Z",
            startgg_url="https://start.gg/tournament/cte-2/event/cte-bracket",
        )
        self.assertIs(result, existing)

    def test_naive_stored_end_time_does_not_raise(self):
        # An end_time without an offset parses to a naive datetime; comparing it
        # to an aware "now" raises TypeError, which would break every create on
        # that server. It must be treated as active instead.
        existing = _make_event_data(event_name="Weekly Bracket", end_time="2026-09-10T20:00:00")
        result = self._find([existing], event_name="Weekly Bracket")
        self.assertIs(result, existing)


class TestBuildEventIdentity(unittest.TestCase):
    def test_startgg_link_identifies_by_slug(self):
        identity = event_helper.build_event_identity(
            "Any Name", "2099-01-01T18:00:00Z",
            startgg_url="https://www.start.gg/tournament/cte-2/event/cte-bracket/overview",
        )
        self.assertEqual(identity, "startgg:tournament/cte-2/event/cte-bracket")

    def test_same_bracket_yields_the_same_identity_despite_a_different_start_time(self):
        # create_event_startgg rewrites a past start.gg time to "now + 1 minute",
        # which differs per invocation — the claim must not vary with it.
        first = event_helper.build_event_identity(
            "N", "2099-01-01T18:00:00Z", startgg_url="https://start.gg/tournament/t/event/e"
        )
        second = event_helper.build_event_identity(
            "N", "2099-01-01T18:01:00Z", startgg_url="https://start.gg/tournament/t/event/e"
        )
        self.assertEqual(first, second)

    def test_without_startgg_identity_is_name_and_start_time(self):
        identity = event_helper.build_event_identity("Weekly Bracket", "2099-01-01T18:00:00Z")
        self.assertEqual(identity, "name:Weekly Bracket|2099-01-01T18:00:00Z")

    def test_different_start_times_yield_different_identities(self):
        first = event_helper.build_event_identity("Weekly Bracket", "2099-01-07T18:00:00Z")
        second = event_helper.build_event_identity("Weekly Bracket", "2099-01-14T18:00:00Z")
        self.assertNotEqual(first, second)

    def test_unparseable_startgg_link_falls_back_to_name_and_time(self):
        identity = event_helper.build_event_identity(
            "Weekly Bracket", "2099-01-01T18:00:00Z", startgg_url="https://start.gg/not-an-event"
        )
        self.assertEqual(identity, "name:Weekly Bracket|2099-01-01T18:00:00Z")


if __name__ == "__main__":
    unittest.main()
