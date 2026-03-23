import unittest

from commands.event.startgg.startgg_api import extract_startgg_slug, is_valid_startgg_url


class TestExtractStartggSlug(unittest.TestCase):
    def test_clean_url_extracts_slug(self):
        slug = extract_startgg_slug("https://www.start.gg/tournament/midweek-melting/event/mbaacc-bracket")
        self.assertEqual(slug, "tournament/midweek-melting/event/mbaacc-bracket")

    def test_trailing_slash_ignored(self):
        slug = extract_startgg_slug("https://www.start.gg/tournament/test-event/event/main-bracket/")
        self.assertEqual(slug, "tournament/test-event/event/main-bracket")

    def test_extra_path_segments_ignored(self):
        slug = extract_startgg_slug("https://www.start.gg/tournament/test/event/main/standings")
        self.assertEqual(slug, "tournament/test/event/main")

    def test_numbers_and_hyphens_in_slug(self):
        slug = extract_startgg_slug("https://www.start.gg/tournament/summit-2026/event/main-double-elim")
        self.assertEqual(slug, "tournament/summit-2026/event/main-double-elim")

    def test_no_event_segment_returns_none(self):
        self.assertIsNone(extract_startgg_slug("https://www.start.gg/tournament/test"))

    def test_empty_tournament_slug_returns_none(self):
        self.assertIsNone(extract_startgg_slug("https://www.start.gg/tournament//event/main"))

    def test_empty_event_slug_returns_none(self):
        self.assertIsNone(extract_startgg_slug("https://www.start.gg/tournament/test/event/"))

    def test_empty_string_returns_none(self):
        self.assertIsNone(extract_startgg_slug(""))


class TestIsValidStartggUrl(unittest.TestCase):
    def test_valid_url_returns_true(self):
        self.assertTrue(is_valid_startgg_url("https://www.start.gg/tournament/test/event/main"))

    def test_trailing_slash_is_valid(self):
        self.assertTrue(is_valid_startgg_url("https://www.start.gg/tournament/test/event/main/"))

    def test_extra_path_segments_are_valid(self):
        self.assertTrue(is_valid_startgg_url("https://www.start.gg/tournament/test/event/main/standings"))

    def test_no_event_segment_returns_false(self):
        self.assertFalse(is_valid_startgg_url("https://www.start.gg/tournament/test"))

    def test_empty_event_slug_returns_false(self):
        self.assertFalse(is_valid_startgg_url("https://www.start.gg/tournament/test/event/"))

    def test_empty_string_returns_false(self):
        self.assertFalse(is_valid_startgg_url(""))


if __name__ == "__main__":
    unittest.main()
