"""API del registro de estaciones de la HoloNet."""

import base64
import binascii
import json
import logging
import os
import re

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")
STATES = {"ACTIVE", "MAINTENANCE", "OFFLINE"}


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def error(status_code, code, message):
    return response(status_code, {"error": {"code": code, "message": message}})


def station_fields(item):
    return {field: item[field] for field in ("sectorId", "stationId", "name", "status")}


def list_stations(table, sector_id):
    # Query recupera solamente las estaciones de la partición solicitada.
    arguments = {
        "KeyConditionExpression": Key("sectorId").eq(sector_id),
        "ConsistentRead": True,
        "ScanIndexForward": True,
    }
    stations = []
    while True:
        result = table.query(**arguments)
        stations.extend(station_fields(item) for item in result.get("Items", []))
        if not result.get("LastEvaluatedKey"):
            break
        arguments["ExclusiveStartKey"] = result["LastEvaluatedKey"]
    return response(200, {"sectorId": sector_id, "stations": stations})


def update_station(table, sector_id, station_id, event):
    try:
        body = event.get("body") or ""
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body, validate=True).decode("utf-8")
        payload = json.loads(body)
    except (ValueError, TypeError, UnicodeError, binascii.Error):
        return error(400, "INVALID_BODY", "El body debe contener un objeto JSON válido.")

    if not isinstance(payload, dict) or set(payload) != {"status"}:
        return error(400, "INVALID_BODY", "El body debe contener solamente status.")
    state = payload["status"]
    if not isinstance(state, str) or state not in STATES:
        return error(400, "INVALID_STATUS", "El estado debe ser ACTIVE, MAINTENANCE u OFFLINE.")

    try:
        result = table.update_item(
            Key={"sectorId": sector_id, "stationId": station_id},
            UpdateExpression="SET #status = :status",
            ConditionExpression="attribute_exists(sectorId) AND attribute_exists(stationId)",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": state},
            ReturnValues="ALL_NEW",
        )
    except ClientError as exception:
        if exception.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return error(404, "STATION_NOT_FOUND", "La estación no existe en el sector indicado.")
        raise
    return response(200, station_fields(result["Attributes"]))


def lambda_handler(event, context):
    route = event.get("routeKey")
    if route == "GET /status":
        return response(200, {"status": "operational", "version": os.environ["SYSTEM_VERSION"]})

    routes = {
        "GET /sectors/{sectorId}/stations",
        "PATCH /sectors/{sectorId}/stations/{stationId}",
    }
    if route not in routes:
        return error(404, "ROUTE_NOT_FOUND", "La route solicitada no existe.")

    parameters = event.get("pathParameters") or {}
    sector_id = parameters.get("sectorId", "")
    station_id = parameters.get("stationId", "")
    if not isinstance(sector_id, str) or not IDENTIFIER.fullmatch(sector_id):
        return error(400, "INVALID_SECTOR_ID", "El identificador del sector no es válido.")
    if route.startswith("PATCH") and (
        not isinstance(station_id, str) or not IDENTIFIER.fullmatch(station_id)
    ):
        return error(400, "INVALID_STATION_ID", "El identificador de la estación no es válido.")

    try:
        table_name = os.environ.get("TABLE_NAME")
        if not table_name:
            return error(500, "CONFIGURATION_ERROR", "La función no tiene configurada TABLE_NAME.")
        table = boto3.resource("dynamodb").Table(table_name)
        if route.startswith("GET"):
            return list_stations(table, sector_id)
        return update_station(table, sector_id, station_id, event)
    except (ClientError, BotoCoreError):
        logger.exception("Station operation failed")
        return error(500, "SERVICE_ERROR", "No fue posible completar la operación.")
