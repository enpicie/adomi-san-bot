import boto3

import constants
from aws_services import AWSServices

_dynamodb = boto3.resource("dynamodb", region_name=constants.AWS_REGION)
_sqs = boto3.resource("sqs", region_name=constants.AWS_REGION)

_aws_services: AWSServices | None = None


def get_aws_services() -> AWSServices:
    global _aws_services
    if _aws_services is None:
        _aws_services = AWSServices(
            dynamodb_table=_dynamodb.Table(constants.DYNAMODB_TABLE_NAME),
            remove_role_sqs_queue=_sqs.Queue(constants.SQS_REMOVE_ROLE_QUEUE_URL),
            sheets_agent_sqs_queue=_sqs.Queue(constants.SQS_SHEETS_AGENT_QUEUE_URL),
        )
    return _aws_services
