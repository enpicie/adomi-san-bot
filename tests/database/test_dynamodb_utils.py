import os
import unittest
from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

# Fake AWS credentials/region so moto never touches a real account.
os.environ["AWS_ACCESS_KEY_ID"] = "test-access-key"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test-secret-key"
os.environ["AWS_SECURITY_TOKEN"] = "test-token"
os.environ["AWS_SESSION_TOKEN"] = "test-token"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

import boto3
from moto import mock_aws

import database.dynamodb_utils as dynamodb_utils
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData
from database.models.server_config import ServerConfig

_SERVER_ID = "123456789012345678"
_NOW = datetime(2026, 4, 10, 12, 0, 0, tzinfo=dt_timezone.utc)


class TestKeyBuilders(unittest.TestCase):
    def test_build_server_pk_prefixes_server_id(self):
        self.assertEqual(dynamodb_utils.build_server_pk(_SERVER_ID), f"SERVER#{_SERVER_ID}")

    def test_build_event_key_builds_pk_and_event_prefixed_sk(self):
        key = dynamodb_utils.build_event_key(_SERVER_ID, "111222333")
        self.assertEqual(key, {"PK": f"SERVER#{_SERVER_ID}", "SK": "EVENT#111222333"})


class DynamoDbTableTestCase(unittest.TestCase):
    """Base class that spins up a moto-backed table matching the production schema."""

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
                {"AttributeName": "server_id", "AttributeType": "S"},
                {"AttributeName": "event_name", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "EventNameIndex",
                    "KeySchema": [
                        {"AttributeName": "server_id", "KeyType": "HASH"},
                        {"AttributeName": "event_name", "KeyType": "RANGE"},
                    ],
                    "Projection": {
                        "ProjectionType": "INCLUDE",
                        "NonKeyAttributes": ["event_id", "start_time", "end_time", "description"],
                    },
                },
            ],
        )

    def _put_config(self, **overrides):
        item = {
            "PK": f"SERVER#{_SERVER_ID}",
            "SK": "CONFIG",
            "server_id": _SERVER_ID,
            "server_name": "Test Server",
            "organizer_role": "333000111",
            "default_participant_role": "444000111",
        }
        item.update(overrides)
        self.table.put_item(Item=item)

    def _put_event(self, event_id: str, event_name: str, **overrides):
        item = {
            "PK": f"SERVER#{_SERVER_ID}",
            "SK": f"EVENT#{event_id}",
            "server_id": _SERVER_ID,
            "event_id": event_id,
            "event_name": event_name,
            "checked_in": {},
            "registered": {},
            "queue": {},
            "participant_role": "555000111",
            "check_in_enabled": False,
            "register_enabled": True,
            "start_message": "start",
            "end_message": "end",
        }
        item.update(overrides)
        self.table.put_item(Item=item)


class TestGetServerConfigOrFail(DynamoDbTableTestCase):
    def test_existing_config_returns_server_config(self):
        self._put_config()
        result = dynamodb_utils.get_server_config_or_fail(_SERVER_ID, self.table)
        self.assertIsInstance(result, ServerConfig)
        self.assertEqual(result.server_id, _SERVER_ID)
        self.assertEqual(result.server_name, "Test Server")

    def test_missing_config_returns_response_message(self):
        result = dynamodb_utils.get_server_config_or_fail(_SERVER_ID, self.table)
        self.assertIsInstance(result, ResponseMessage)


class TestGetServerEventDataOrFail(DynamoDbTableTestCase):
    def test_fetch_by_numeric_event_id_returns_event_data(self):
        self._put_event("111222333", "Weekly Bracket")
        result = dynamodb_utils.get_server_event_data_or_fail(_SERVER_ID, "111222333", self.table)
        self.assertIsInstance(result, EventData)
        self.assertEqual(result.event_id, "111222333")
        self.assertEqual(result.event_name, "Weekly Bracket")

    def test_fetch_by_event_name_resolves_id_through_gsi(self):
        self._put_event("111222333", "Weekly Bracket")
        self._put_event("999888777", "Monthly Major")
        result = dynamodb_utils.get_server_event_data_or_fail(_SERVER_ID, "Monthly Major", self.table)
        self.assertIsInstance(result, EventData)
        self.assertEqual(result.event_id, "999888777")
        self.assertEqual(result.event_name, "Monthly Major")

    def test_missing_event_returns_response_message(self):
        result = dynamodb_utils.get_server_event_data_or_fail(_SERVER_ID, "000000000", self.table)
        self.assertIsInstance(result, ResponseMessage)

    def test_unknown_event_name_returns_response_message(self):
        self._put_event("111222333", "Weekly Bracket")
        result = dynamodb_utils.get_server_event_data_or_fail(_SERVER_ID, "No Such Event", self.table)
        self.assertIsInstance(result, ResponseMessage)


class TestGetEventsForServer(DynamoDbTableTestCase):
    def test_returns_name_id_tuples_for_all_server_events(self):
        self._put_event("111222333", "Weekly Bracket")
        self._put_event("999888777", "Monthly Major")
        events = dynamodb_utils.get_events_for_server(_SERVER_ID, self.table)
        self.assertEqual(
            sorted(events),
            [("Monthly Major", "999888777"), ("Weekly Bracket", "111222333")],
        )

    def test_returns_empty_list_when_server_has_no_events(self):
        self._put_config()  # CONFIG record has no event_name, must not appear in the GSI
        events = dynamodb_utils.get_events_for_server(_SERVER_ID, self.table)
        self.assertEqual(events, [])


class TestDeletePastRealEvents(DynamoDbTableTestCase):
    def _run_with_fixed_now(self):
        with patch.object(dynamodb_utils, "datetime") as mock_dt:
            mock_dt.now.return_value = _NOW
            mock_dt.fromisoformat.side_effect = datetime.fromisoformat
            return dynamodb_utils.delete_past_real_events(_SERVER_ID, self.table)

    def _remaining_event_sks(self):
        response = self.table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(f"SERVER#{_SERVER_ID}")
            & boto3.dynamodb.conditions.Key("SK").begins_with("EVENT#")
        )
        return {item["SK"] for item in response["Items"]}

    def test_deletes_only_past_events_and_returns_their_names(self):
        self._put_event("111", "Past Event", start_time="2026-04-09T12:00:00Z")
        self._put_event("222", "Future Event", start_time="2026-04-11T12:00:00Z")
        deleted = self._run_with_fixed_now()
        self.assertEqual(deleted, ["Past Event"])
        self.assertEqual(self._remaining_event_sks(), {"EVENT#222"})

    def test_unparseable_start_time_is_skipped_not_deleted_and_does_not_crash(self):
        self._put_event("111", "Past Event", start_time="2026-04-09T12:00:00Z")
        self._put_event("333", "Broken Event", start_time="not-a-date")
        deleted = self._run_with_fixed_now()
        self.assertEqual(deleted, ["Past Event"])
        self.assertIn("EVENT#333", self._remaining_event_sks())

    def test_event_with_missing_start_time_is_not_deleted(self):
        self._put_event("444", "Planned Event")  # no start_time attribute
        deleted = self._run_with_fixed_now()
        self.assertEqual(deleted, [])
        self.assertEqual(self._remaining_event_sks(), {"EVENT#444"})


if __name__ == "__main__":
    unittest.main()
