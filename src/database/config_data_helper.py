from typing import Union
from mypy_boto3_dynamodb.service_resource import Table
import database.dynamodb_queries as db_helper
import database.server_config_keys as server_config_keys
from commands.models.response_message import ResponseMessage

def try_get_organizer_role(server_id: str, table: Table) -> Union[str, ResponseMessage]:
    existing_item = db_helper.get_server_config(server_id, table)
    if not existing_item:
        return ResponseMessage(
            content="This server is not set up! Run `/setup-server` first to get started. "
                    "You can set the organizer role there 👍"
        )

    return existing_item.get(server_config_keys.ORGANIZER_ROLE)
