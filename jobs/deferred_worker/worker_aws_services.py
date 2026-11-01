# MIRROR: src/aws_services.py — keep in sync (independent Lambda packaging prevents imports)
class AWSServices:
    """Bundle of pre-built AWS resource handles (DynamoDB table, remove-role SQS queue)
    passed into command handlers."""

    def __init__(self, dynamodb_table, remove_role_sqs_queue):
        self.dynamodb_table = dynamodb_table
        self.remove_role_sqs_queue = remove_role_sqs_queue
