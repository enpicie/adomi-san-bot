import unittest
from unittest import mock

import commands.event.startgg.startgg_api as startgg_api


def _make_entrant(entrant_id, gamer_tag, discord_id=None):
    return {
        "id": entrant_id,
        "participants": [{
            "gamerTag": gamer_tag,
            "user": {
                "authorizations": [{"externalId": discord_id}] if discord_id else None
            }
        }]
    }


def _make_page_payload(nodes, total):
    return {
        "data": {
            "event": {
                "id": 1,
                "name": "Main Bracket",
                "startAt": 1735689600,
                "tournament": {
                    "name": "Midweek Melting",
                    "venueName": "The Arena",
                    "venueAddress": None,
                },
                "entrants": {
                    "pageInfo": {"total": total},
                    "nodes": nodes,
                },
            }
        }
    }


def _make_response(payload):
    response = mock.Mock()
    response.ok = True
    response.status_code = 200
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class TestQueryStartggEventPagination(unittest.TestCase):
    def setUp(self):
        token_patcher = mock.patch.object(
            startgg_api, "_get_startgg_api_token", return_value="fake-token"
        )
        token_patcher.start()
        self.addCleanup(token_patcher.stop)

    def test_multi_page_fetches_all_entrants(self):
        total = 85
        page_one_nodes = [
            _make_entrant(i, f"Player{i}", discord_id=f"U{i}") for i in range(75)
        ]
        page_two_nodes = [
            _make_entrant(i, f"Player{i}", discord_id=f"U{i}") for i in range(75, total)
        ]
        responses = [
            _make_response(_make_page_payload(page_one_nodes, total)),
            _make_response(_make_page_payload(page_two_nodes, total)),
        ]

        with mock.patch.object(
            startgg_api, "_post_graphql", side_effect=responses
        ) as mock_post:
            event = startgg_api.query_startgg_event(
                "https://www.start.gg/tournament/test/event/main"
            )

        self.assertEqual(mock_post.call_count, 2)
        requested_pages = [call.args[0]["page"] for call in mock_post.call_args_list]
        self.assertEqual(requested_pages, [1, 2])

        accounted = len(event.participants) + len(event.no_discord_participants)
        self.assertEqual(accounted, total)
        self.assertEqual(
            sorted(p.display_name for p in event.participants),
            sorted(f"Player{i}" for i in range(total)),
        )

    def test_single_page_makes_exactly_one_request(self):
        total = 10
        nodes = [_make_entrant(i, f"Player{i}", discord_id=f"U{i}") for i in range(total)]
        responses = [_make_response(_make_page_payload(nodes, total))]

        with mock.patch.object(
            startgg_api, "_post_graphql", side_effect=responses
        ) as mock_post:
            event = startgg_api.query_startgg_event(
                "https://www.start.gg/tournament/test/event/main"
            )

        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(mock_post.call_args.args[0]["page"], 1)
        self.assertEqual(len(event.participants), total)


if __name__ == "__main__":
    unittest.main()
