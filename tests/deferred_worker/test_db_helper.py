"""jobs/deferred_worker/db_helper.py — key construction that must match src."""
import unittest
from unittest.mock import Mock

import db_helper


class TestDeleteSchedulePlan(unittest.TestCase):
    def test_display_name_is_normalized_to_hit_the_stored_key(self):
        # MIRROR of src/database/dynamodb_utils.py delete_schedule_plan: plans are
        # stored under SchedulePlan.normalize_name(plan_name) while the item's
        # plan_name keeps the display name the sync passes in. Deleting on the raw
        # display name misses the key and DynamoDB reports no error.
        table = Mock()

        db_helper.delete_schedule_plan("server123", "  Weekly Bracket ", table)

        table.delete_item.assert_called_once_with(
            Key={"PK": "SERVER#server123", "SK": "SCHEDULE_PLAN#weekly bracket"}
        )


if __name__ == "__main__":
    unittest.main()
