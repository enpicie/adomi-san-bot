import unittest
from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

import commands.schedule.schedule_helper as schedule_helper
from database.models.event_data import EventData
from database.models.schedule_plan import SchedulePlan

_NOW = datetime(2026, 4, 10, 12, 0, 0, tzinfo=dt_timezone.utc)

_PAST_ISO = "2026-04-09T12:00:00Z"
_FUTURE_ISO = "2026-04-11T12:00:00Z"
_LATER_FUTURE_ISO = "2026-04-12T12:00:00Z"

_PAST_EPOCH = int(datetime(2026, 4, 9, 12, 0, 0, tzinfo=dt_timezone.utc).timestamp())
_FUTURE_EPOCH = int(datetime(2026, 4, 11, 12, 0, 0, tzinfo=dt_timezone.utc).timestamp())
_LATER_FUTURE_EPOCH = int(datetime(2026, 4, 12, 12, 0, 0, tzinfo=dt_timezone.utc).timestamp())


def _make_event(event_name, start_time=None, startgg_url=None) -> EventData:
    return EventData(
        checked_in={},
        registered={},
        queue={},
        participant_role="555000111",
        check_in_enabled=False,
        register_enabled=True,
        start_message="start",
        end_message="end",
        start_time=start_time,
        event_name=event_name,
        startgg_url=startgg_url,
    )


class TestBuildScheduleContent(unittest.TestCase):
    def _build(self, title="Upcoming Events", real_events=None, planned_events=None) -> str:
        with patch.object(schedule_helper, "datetime") as mock_dt:
            mock_dt.now.return_value = _NOW
            mock_dt.fromisoformat.side_effect = datetime.fromisoformat
            return schedule_helper.build_schedule_content(
                title, real_events or [], planned_events or []
            )

    def test_empty_schedule_renders_no_events_placeholder_under_title(self):
        content = self._build(title="My Schedule")
        self.assertEqual(content, "# My Schedule\n\n*No events.*")

    def test_real_event_with_startgg_url_renders_markdown_link(self):
        event = _make_event("Weekly Bracket", start_time=_FUTURE_ISO, startgg_url="https://start.gg/test-tournament")
        content = self._build(real_events=[event])
        self.assertIn(
            f"- [Weekly Bracket](https://start.gg/test-tournament) - **<t:{_FUTURE_EPOCH}:F>**",
            content,
        )

    def test_real_event_without_url_renders_plain_name(self):
        event = _make_event("Weekly Bracket", start_time=_FUTURE_ISO)
        content = self._build(real_events=[event])
        self.assertIn(f"- Weekly Bracket - **<t:{_FUTURE_EPOCH}:F>**", content)
        self.assertNotIn("[Weekly Bracket]", content)

    def test_past_real_event_is_struck_through(self):
        event = _make_event("Old Event", start_time=_PAST_ISO)
        content = self._build(real_events=[event])
        self.assertIn(f"- ~~Old Event - **<t:{_PAST_EPOCH}:F>**~~", content)

    def test_planned_event_is_italicized(self):
        plan = SchedulePlan(plan_name="Planned Major", start_time=_FUTURE_ISO)
        content = self._build(planned_events=[plan])
        self.assertIn(f"- _Planned Major - **<t:{_FUTURE_EPOCH}:F>**_", content)

    def test_planned_event_with_link_renders_markdown_link_inside_italics(self):
        plan = SchedulePlan(plan_name="Planned Major", start_time=_FUTURE_ISO, event_link="https://start.gg/planned")
        content = self._build(planned_events=[plan])
        self.assertIn(f"- _[Planned Major](https://start.gg/planned) - **<t:{_FUTURE_EPOCH}:F>**_", content)

    def test_past_planned_event_is_omitted_entirely(self):
        plan = SchedulePlan(plan_name="Stale Plan", start_time=_PAST_ISO)
        content = self._build(planned_events=[plan])
        self.assertNotIn("Stale Plan", content)
        self.assertIn("*No events.*", content)

    def test_events_sorted_by_start_time_across_real_and_planned(self):
        late_event = _make_event("Late Real", start_time=_LATER_FUTURE_ISO)
        early_event = _make_event("Early Real", start_time=_FUTURE_ISO)
        middle_plan = SchedulePlan(plan_name="Middle Plan", start_time="2026-04-11T18:00:00Z")
        content = self._build(real_events=[late_event, early_event], planned_events=[middle_plan])
        self.assertLess(content.index("Early Real"), content.index("Middle Plan"))
        self.assertLess(content.index("Middle Plan"), content.index("Late Real"))

    def test_unparseable_start_time_renders_tbd_and_sorts_last(self):
        tbd_event = _make_event("Mystery Event", start_time="not-a-date")
        dated_event = _make_event("Dated Event", start_time=_FUTURE_ISO)
        content = self._build(real_events=[tbd_event, dated_event])
        self.assertIn("- Mystery Event - **TBD**", content)
        self.assertLess(content.index("Dated Event"), content.index("Mystery Event"))

    def test_missing_start_time_renders_tbd(self):
        event = _make_event("No Time Yet")
        content = self._build(real_events=[event])
        self.assertIn("- No Time Yet - **TBD**", content)

    def test_event_with_no_name_renders_unnamed_event(self):
        event = _make_event(None, start_time=_FUTURE_ISO)
        content = self._build(real_events=[event])
        self.assertIn("- Unnamed Event", content)

    def test_title_rendered_as_h1_with_blank_line(self):
        event = _make_event("Weekly Bracket", start_time=_FUTURE_ISO)
        content = self._build(title="Custom Title", real_events=[event])
        lines = content.split("\n")
        self.assertEqual(lines[0], "# Custom Title")
        self.assertEqual(lines[1], "")

    def test_no_events_placeholder_absent_when_events_exist(self):
        event = _make_event("Weekly Bracket", start_time=_FUTURE_ISO)
        content = self._build(real_events=[event])
        self.assertNotIn("*No events.*", content)


if __name__ == "__main__":
    unittest.main()
