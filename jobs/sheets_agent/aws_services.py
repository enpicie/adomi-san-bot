class AWSServices:
    def __init__(self, dynamodb_table, remove_role_sqs_queue):
        self.dynamodb_table = dynamodb_table
        self.remove_role_sqs_queue = remove_role_sqs_queue
