import json
import unittest
from unittest.mock import Mock

from utils.queue_role_removal import enqueue_remove_role_jobs


class TestEnqueueRemoveRoleJobs(unittest.TestCase):
    def _make_queue(self):
        return Mock()

    def test_single_user_sends_one_batch(self):
        queue = self._make_queue()
        enqueue_remove_role_jobs("guild1", ["u1"], "role1", queue)
        queue.send_messages.assert_called_once()
        entries = queue.send_messages.call_args.kwargs["Entries"]
        self.assertEqual(len(entries), 1)

    def test_message_body_contains_correct_fields(self):
        queue = self._make_queue()
        enqueue_remove_role_jobs("guild1", ["u1"], "role1", queue)
        body = json.loads(queue.send_messages.call_args.kwargs["Entries"][0]["MessageBody"])
        self.assertEqual(body["guild_id"], "guild1")
        self.assertEqual(body["user_id"], "u1")
        self.assertEqual(body["role_id"], "role1")

    def test_empty_user_list_sends_no_messages(self):
        queue = self._make_queue()
        enqueue_remove_role_jobs("guild1", [], "role1", queue)
        queue.send_messages.assert_not_called()

    def test_ten_users_sends_one_batch(self):
        queue = self._make_queue()
        users = [f"u{i}" for i in range(10)]
        enqueue_remove_role_jobs("guild1", users, "role1", queue)
        queue.send_messages.assert_called_once()
        entries = queue.send_messages.call_args.kwargs["Entries"]
        self.assertEqual(len(entries), 10)

    def test_eleven_users_sends_two_batches(self):
        queue = self._make_queue()
        users = [f"u{i}" for i in range(11)]
        enqueue_remove_role_jobs("guild1", users, "role1", queue)
        self.assertEqual(queue.send_messages.call_count, 2)
        first_batch = queue.send_messages.call_args_list[0].kwargs["Entries"]
        second_batch = queue.send_messages.call_args_list[1].kwargs["Entries"]
        self.assertEqual(len(first_batch), 10)
        self.assertEqual(len(second_batch), 1)

    def test_twenty_users_sends_two_full_batches(self):
        queue = self._make_queue()
        users = [f"u{i}" for i in range(20)]
        enqueue_remove_role_jobs("guild1", users, "role1", queue)
        self.assertEqual(queue.send_messages.call_count, 2)

    def test_all_user_ids_included_across_batches(self):
        queue = self._make_queue()
        users = [f"u{i}" for i in range(15)]
        enqueue_remove_role_jobs("guild1", users, "role1", queue)
        all_entries = []
        for call in queue.send_messages.call_args_list:
            all_entries.extend(call.kwargs["Entries"])
        user_ids_sent = {json.loads(e["MessageBody"])["user_id"] for e in all_entries}
        self.assertEqual(user_ids_sent, set(users))


if __name__ == "__main__":
    unittest.main()
