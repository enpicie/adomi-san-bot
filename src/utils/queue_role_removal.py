# MIRROR: jobs/sheets_agent/discord_api.enqueue_remove_roles — keep in sync (independent Lambda packaging prevents imports)
import json
from mypy_boto3_sqs.service_resource import Queue
from typing import List

def enqueue_remove_role_jobs(server_id: str, user_ids: List[str], role_id: str, sqs_queue: Queue):
    """Enqueue one role-removal SQS message per user, sending in batches of 10
    (the SQS send_messages batch limit)."""
    batch = []

    for idx, user_id in enumerate(user_ids):
        batch.append({
            "Id": str(idx),
            "MessageBody": json.dumps({
                "guild_id": server_id,
                "user_id": user_id,
                "role_id": role_id
            })
        })

        if len(batch) == 10:  # SQS batch limit
            sqs_queue.send_messages(Entries=batch)
            batch = []

    if batch:
        sqs_queue.send_messages(Entries=batch)
