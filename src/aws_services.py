from mypy_boto3_dynamodb.service_resource import Table
from mypy_boto3_sqs.service_resource import Queue

class AWSServices:
    dynamodb_table: Table
    remove_role_sqs_queue: Queue

    def __init__(self, dynamodb_table: Table, remove_role_sqs_queue: Queue):
        self.dynamodb_table = dynamodb_table
        self.remove_role_sqs_queue = remove_role_sqs_queue
