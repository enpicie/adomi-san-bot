# MIRROR: src/aws_client.py — keep in sync (independent Lambda packaging prevents imports)
import boto3

import constants
from aws_services import AWSServices

_dynamodb = boto3.resource("dynamodb", region_name=constants.AWS_REGION)
_sqs = boto3.resource("sqs", region_name=constants.AWS_REGION)

_aws_services: AWSServices | None = None


def get_aws_services() -> AWSServices:
    """Return the lazily created AWSServices singleton (DynamoDB table + remove-role SQS queue)."""
    global _aws_services
    if _aws_services is None:
        _aws_services = AWSServices(
            dynamodb_table=_dynamodb.Table(constants.DYNAMODB_TABLE_NAME),
            remove_role_sqs_queue=_sqs.Queue(constants.SQS_REMOVE_ROLE_QUEUE_URL),
        )
    return _aws_services
