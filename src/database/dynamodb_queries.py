import boto3
from boto3.dynamodb.conditions import Key, Attr
from mypy_boto3_dynamodb.service_resource import Table

import constants

def get_server_pk(server_id: str) -> str:
    return f"{constants.PK_SERVER_PREFIX}{server_id}"

def get_server_config(server_id: str, table: Table) -> dict | None:
    pk = get_server_pk(server_id)

    response = table.get_item(Key={"PK": pk, "SK": constants.SK_CONFIG})
    return response.get("Item")

def get_server_event_data(server_id: str, table: Table) -> dict | None:
    pk = get_server_pk(server_id)

    response = table.get_item(Key={"PK": pk, "SK": constants.SK_SERVER})
    return response.get("Item")

def query_items_by_sk(server_id: str, table: Table, sk_value: str):
    pk = get_server_pk(server_id)

    response = table.query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").eq(sk_value)
    )

    return response.get("Items", [])


def query_items_with_sk_prefix(server_id: str, table: Table, sk_prefix: str):
    """
    Returns all items for a server where SK begins with a prefix.
    Example: sk_prefix = "CHANNEL" → matches CHANNEL#123, CHANNEL#abc, etc.
    """
    pk = get_server_pk(server_id)

    response = table.query(
        KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with(sk_prefix)
    )

    return response.get("Items", [])
