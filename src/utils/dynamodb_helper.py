from mypy_boto3_dynamodb.service_resource import Table

import constants

def get_server_pk(server_id: str) -> str:
    """Constructs the partition key for a server."""
    return f"{constants.PK_SERVER_PREFIX}{server_id}"

def get_server_config(server_id: str, table: Table) -> dict | None:
    """
    Retrieves the CONFIG record for a given server from DynamoDB.
    Returns the item as a dictionary if found, otherwise None.
    """
    pk = get_server_pk(server_id)

    response = table.get_item(Key={"PK": pk, "SK": constants.SK_CONFIG})
    return response.get("Item")
