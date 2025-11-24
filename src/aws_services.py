from mypy_boto3_dynamodb.service_resource import Table
from mypy_boto3_sqs.service_resource import Queue

class AWSServices:
    dynamotb_table: Table
    remove_role_sqs_queue: Queue

    def __init__(self, table: Table, remove_role_sqs_queue: Queue):
        self.dynamotb_table = table
        self.remove_role_sqs_queue = remove_role_sqs_queue
