import json
from mypy_boto3_sqs.service_resource import Queue
from typing import List

def enqueue_remove_role_jobs(server_id: str, user_ids: List[str], role_id: str, sqs_queue: Queue):
    batch = []

    for idx, uid in enumerate(user_ids):  # enumerate to get index
        batch.append({
            "Id": str(idx),
            "MessageBody": json.dumps({
                "guild_id": server_id,
                "user_id": uid,
                "role_id": role_id
            })
        })

        if len(batch) == 10:  # SQS batch limit
            sqs_queue.send_messages(Entries=batch)
            batch = []

    if batch:
        sqs_queue.send_messages(Entries=batch)
