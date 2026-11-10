import os
import unittest
from unittest.mock import Mock, patch

# Fake AWS credentials/region so moto never touches a real account.
os.environ["AWS_ACCESS_KEY_ID"] = "test-access-key"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test-secret-key"
os.environ["AWS_SECURITY_TOKEN"] = "test-token"
os.environ["AWS_SESSION_TOKEN"] = "test-token"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

import boto3
from moto import mock_aws

import commands.queue.queue_helper as queue_helper
from database.models.event_data import EventData

_KEY = {"PK": "SERVER#server123", "SK": "EVENT#event_111"}


def _event_data(queue):
    return EventData(
        checked_in={}, registered={}, queue=queue, participant_role=None,
        check_in_enabled=False, register_enabled=False, start_message="", end_message="",
        event_id="event_111",
    )


def _entry(name, joined_at):
    return {"display_name": name, "joined_at": joined_at}


class QueueTableTestCase(unittest.TestCase):
    """Runs the real update expressions against a moto-backed table."""

    def setUp(self):
        self._mock_aws = mock_aws()
        self._mock_aws.start()
        self.addCleanup(self._mock_aws.stop)
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        self.table = dynamodb.create_table(
            TableName="test-table",
            BillingMode="PAY_PER_REQUEST",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
        )

    def _put_event(self, **attrs):
        self.table.put_item(Item={**_KEY, **attrs})

    def _queue(self):
        return self.table.get_item(Key=_KEY)["Item"].get("queue")


class TestEnsureQueueMap(QueueTableTestCase):
    def test_creates_map_on_record_missing_it_so_joins_succeed(self):
        self._put_event()
        queue_helper.ensure_queue_map(self.table, _KEY, _event_data(queue=None))
        self.assertIsNotNone(queue_helper.join_queue(self.table, _KEY, "u1", "Alice"))
        self.assertIn("u1", self._queue())

    def test_skips_write_when_map_already_loaded(self):
        table = Mock()
        queue_helper.ensure_queue_map(table, _KEY, _event_data(queue={}))
        table.update_item.assert_not_called()


class TestJoinQueue(QueueTableTestCase):
    def test_join_appends_and_returns_updated_queue(self):
        self._put_event(queue={"u1": _entry("Alice", 100)})
        with patch("commands.queue.queue_helper.time.time", return_value=0.2):
            updated = queue_helper.join_queue(self.table, _KEY, "u2", "Bob")

        self.assertEqual(set(updated), {"u1", "u2"})
        self.assertEqual(queue_helper.get_position(updated, "u2"), 2)

    def test_repeat_join_returns_none_and_keeps_original_spot(self):
        self._put_event(queue={"u1": _entry("Alice", 100)})

        self.assertIsNone(queue_helper.join_queue(self.table, _KEY, "u1", "Alice"))
        self.assertEqual(self._queue(), {"u1": _entry("Alice", 100)})


class TestRemoveAndClear(QueueTableTestCase):
    def test_remove_drops_user(self):
        self._put_event(queue={"u1": _entry("Alice", 1), "u2": _entry("Bob", 2)})
        self.assertTrue(queue_helper.remove_from_queue(self.table, _KEY, "u1"))
        self.assertEqual(set(self._queue()), {"u2"})

    def test_remove_missing_user_returns_false(self):
        self._put_event(queue={})
        self.assertFalse(queue_helper.remove_from_queue(self.table, _KEY, "ghost"))

    def test_clear_empties_queue(self):
        self._put_event(queue={"u1": _entry("Alice", 1)})
        queue_helper.clear_queue(self.table, _KEY)
        self.assertEqual(self._queue(), {})


class TestPopQueue(QueueTableTestCase):
    def test_pops_oldest_first_up_to_count(self):
        queue = {"u3": _entry("C", 3), "u1": _entry("A", 1), "u2": _entry("B", 2)}
        self._put_event(queue=queue)

        popped = queue_helper.pop_queue(self.table, _KEY, queue, 2)

        self.assertEqual(popped, ["u1", "u2"])
        self.assertEqual(set(self._queue()), {"u3"})

    def test_skips_users_already_gone_so_no_one_is_popped_twice(self):
        stale = {"u1": _entry("A", 1), "u2": _entry("B", 2), "u3": _entry("C", 3)}
        self._put_event(queue={"u2": _entry("B", 2), "u3": _entry("C", 3)})  # u1 popped elsewhere

        popped = queue_helper.pop_queue(self.table, _KEY, stale, 1)

        self.assertEqual(popped, ["u2"])
        self.assertEqual(set(self._queue()), {"u3"})

    def test_count_larger_than_queue_pops_everyone(self):
        queue = {"u1": _entry("A", 1)}
        self._put_event(queue=queue)
        self.assertEqual(queue_helper.pop_queue(self.table, _KEY, queue, 5), ["u1"])


class TestOrdering(unittest.TestCase):
    def test_orders_by_join_time_then_user_id(self):
        queue = {"b": _entry("B", 5), "a": _entry("A", 5), "c": _entry("C", 1)}
        self.assertEqual([uid for uid, _ in queue_helper.order_queue(queue)], ["c", "a", "b"])

    def test_get_position_none_when_absent(self):
        self.assertIsNone(queue_helper.get_position({"a": _entry("A", 1)}, "z"))

    def test_build_queue_list_numbers_mentions_in_order(self):
        text = queue_helper.build_queue_list("H", {"u2": _entry("B", 2), "u1": _entry("A", 1)})
        self.assertEqual(text, "H\n**1.** <@u1>\n**2.** <@u2>")

    def test_build_queue_list_cuts_long_queue_under_discord_limit(self):
        queue = {f"{i:020d}": _entry("X", i) for i in range(200)}
        text = queue_helper.build_queue_list("H", queue)
        self.assertLess(len(text), 2000)
        self.assertIn("more", text.splitlines()[-1])
