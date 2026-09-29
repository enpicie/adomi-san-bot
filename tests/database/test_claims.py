import unittest
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError, EndpointConnectionError, ReadTimeoutError

import database.claims as claims


def _conditional_check_failed() -> ClientError:
    return ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "already exists"}},
        "PutItem",
    )


def _throttled() -> ClientError:
    return ClientError(
        {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "slow down"}},
        "PutItem",
    )


class ClaimLifecycleContract:
    """Behaviour both MIRROR twins must share (src/database/claims.py and
    jobs/deferred_worker/claims.py). Mixed into a TestCase per twin with
    `claims_module` set; not collected on its own."""

    claims_module = None
    SERVER = "server123"
    IDENTITY = "startgg:tournament/t/event/e"

    def _pk(self):
        return f"EVENTCREATE#{self.SERVER}#{self.IDENTITY}"

    def test_expired_claim_can_be_retaken_before_dynamodb_sweeps_it(self):
        # DynamoDB sweeps expired items only "typically within a few days", and
        # until then they still exist for conditional writes. The put must treat
        # an item whose expires_at has passed as free.
        table = Mock()
        with patch.object(self.claims_module.time, "time", return_value=1_000_000):
            self.assertTrue(self.claims_module.try_claim_event_create(self.SERVER, self.IDENTITY, table))

        kwargs = table.put_item.call_args.kwargs
        self.assertEqual(kwargs["ConditionExpression"], "attribute_not_exists(PK) OR expires_at < :now")
        self.assertEqual(kwargs["ExpressionAttributeValues"], {":now": 1_000_000})
        self.assertEqual(kwargs["Item"]["expires_at"], 1_000_000 + self.claims_module.EVENT_CREATE_TTL_SECONDS)

    def test_live_claim_is_lost(self):
        table = Mock()
        table.put_item.side_effect = _conditional_check_failed()

        self.assertFalse(self.claims_module.try_claim_event_create(self.SERVER, self.IDENTITY, table))

    def test_claim_fails_open_on_a_non_client_error(self):
        table = Mock()
        table.put_item.side_effect = EndpointConnectionError(endpoint_url="https://dynamodb.us-east-2.amazonaws.com")

        self.assertTrue(self.claims_module.try_claim_event_create(self.SERVER, self.IDENTITY, table))

    def test_release_deletes_exactly_the_claim_key(self):
        table = Mock()

        self.claims_module.release_event_create_claim(self.SERVER, self.IDENTITY, table)

        table.delete_item.assert_called_once_with(Key={"PK": self._pk(), "SK": "CLAIM"})

    def test_release_fails_open(self):
        # The create has already happened or failed by the time we release; a
        # table blip must not turn that outcome into an error for the organizer.
        for error in (_throttled(), EndpointConnectionError(endpoint_url="https://dynamodb.us-east-2.amazonaws.com")):
            table = Mock()
            table.delete_item.side_effect = error
            self.claims_module.release_event_create_claim(self.SERVER, self.IDENTITY, table)

    def test_release_without_identity_writes_nothing(self):
        # No identity means no claim was written, so there is nothing to delete.
        table = Mock()

        self.claims_module.release_event_create_claim(self.SERVER, "", table)

        table.delete_item.assert_not_called()


class TestSrcClaimLifecycle(ClaimLifecycleContract, unittest.TestCase):
    claims_module = claims


class TestClaimsFailOpen(unittest.TestCase):
    """Claims run before the work they guard, so anything other than a lost claim
    must let the command through. A blocked claim would block the whole bot."""

    def test_connection_error_is_not_a_client_error_and_still_fails_open(self):
        table = Mock()
        table.put_item.side_effect = EndpointConnectionError(endpoint_url="https://dynamodb.us-east-2.amazonaws.com")

        self.assertTrue(claims.try_claim_event_create("server123", "startgg:tournament/t/event/e", table))

    def test_read_timeout_fails_open(self):
        table = Mock()
        table.put_item.side_effect = ReadTimeoutError(endpoint_url="https://dynamodb.us-east-2.amazonaws.com")

        self.assertTrue(claims.try_claim_event_create("server123", "startgg:tournament/t/event/e", table))

    def test_unexpected_error_type_fails_open(self):
        table = Mock()
        table.put_item.side_effect = RuntimeError("something new")

        self.assertTrue(claims.try_claim_event_create("server123", "startgg:tournament/t/event/e", table))


class TestTryClaimEventCreate(unittest.TestCase):
    """Guards the window a read-then-write duplicate check cannot: two invocations
    that both read "no duplicate" before either has written."""

    def test_first_create_wins_the_claim(self):
        table = Mock()

        self.assertTrue(claims.try_claim_event_create("server123", "startgg:tournament/t/event/e", table))

        kwargs = table.put_item.call_args.kwargs
        self.assertEqual(kwargs["Item"]["PK"], "EVENTCREATE#server123#startgg:tournament/t/event/e")
        self.assertEqual(kwargs["ConditionExpression"], "attribute_not_exists(PK) OR expires_at < :now")

    def test_concurrent_create_of_same_event_loses_the_claim(self):
        table = Mock()
        table.put_item.side_effect = _conditional_check_failed()

        self.assertFalse(claims.try_claim_event_create("server123", "startgg:tournament/t/event/e", table))

    def test_same_identity_on_different_servers_does_not_collide(self):
        table = Mock()
        claims.try_claim_event_create("server_a", "name:Weekly|2099-01-01T18:00:00Z", table)
        first = table.put_item.call_args.kwargs["Item"]["PK"]
        claims.try_claim_event_create("server_b", "name:Weekly|2099-01-01T18:00:00Z", table)
        second = table.put_item.call_args.kwargs["Item"]["PK"]

        self.assertNotEqual(first, second)

    def test_claim_records_its_expiry_as_now_plus_a_short_ttl(self):
        table = Mock()
        with patch.object(claims.time, "time", return_value=1_000_000):
            claims.try_claim_event_create("server123", "startgg:tournament/t/event/e", table)
        expires_at = table.put_item.call_args.kwargs["Item"][claims.EXPIRES_AT_ATTR]
        self.assertEqual(expires_at, 1_000_000 + claims.EVENT_CREATE_TTL_SECONDS)
        self.assertLessEqual(claims.EVENT_CREATE_TTL_SECONDS, 300)

    def test_missing_identity_is_allowed_through_without_a_write(self):
        table = Mock()

        self.assertTrue(claims.try_claim_event_create("server123", "", table))

        table.put_item.assert_not_called()


if __name__ == "__main__":
    unittest.main()
