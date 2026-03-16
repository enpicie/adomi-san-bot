import unittest

from commands.event.startgg.startgg_api import is_valid_startgg_url


class TestIsValidStartggUrl(unittest.TestCase):
    def test_valid_url(self):
        self.assertTrue(is_valid_startgg_url(
            "https://www.start.gg/tournament/midweek-melting/event/mbaacc-bracket"
        ))

    def test_valid_url_with_numbers_and_hyphens(self):
        self.assertTrue(is_valid_startgg_url(
            "https://www.start.gg/tournament/summit-2026/event/main-double-elim"
        ))

    def test_http_not_allowed(self):
        self.assertFalse(is_valid_startgg_url(
            "http://www.start.gg/tournament/test/event/main"
        ))

    def test_missing_www_not_allowed(self):
        self.assertFalse(is_valid_startgg_url(
            "https://start.gg/tournament/test/event/main"
        ))

    def test_wrong_domain(self):
        self.assertFalse(is_valid_startgg_url(
            "https://www.smash.gg/tournament/test/event/main"
        ))

    def test_missing_event_segment(self):
        self.assertFalse(is_valid_startgg_url(
            "https://www.start.gg/tournament/test"
        ))

    def test_extra_path_after_event(self):
        self.assertFalse(is_valid_startgg_url(
            "https://www.start.gg/tournament/test/event/main/extra"
        ))

    def test_empty_tournament_slug(self):
        self.assertFalse(is_valid_startgg_url(
            "https://www.start.gg/tournament//event/main"
        ))

    def test_empty_event_slug(self):
        self.assertFalse(is_valid_startgg_url(
            "https://www.start.gg/tournament/test/event/"
        ))

    def test_empty_string(self):
        self.assertFalse(is_valid_startgg_url(""))


if __name__ == "__main__":
    unittest.main()
