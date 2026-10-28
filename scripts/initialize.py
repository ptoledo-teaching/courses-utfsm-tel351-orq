"""Inicialización del catálogo de estaciones desde los outputs de CloudFormation."""

import argparse
import json
from pathlib import Path
import re
import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError


CATALOG = Path(__file__).resolve().parents[1] / "data" / "stations.json"


def load_catalog(path):
    with path.open(encoding="utf-8") as source:
        stations = json.load(source)
    if not isinstance(stations, list) or not stations:
        raise ValueError("El catálogo debe contener una lista de estaciones.")
    identifiers = set()
    for station in stations:
        if not isinstance(station, dict) or set(station) != {"sectorId", "stationId", "name", "status"}:
            raise ValueError("Cada estación debe contener sectorId, stationId, name y status.")
        for key in ("sectorId", "stationId"):
            value = station[key]
            if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", value):
                raise ValueError(f"Identificador no válido: {key}.")
        if not isinstance(station["name"], str) or not station["name"].strip():
            raise ValueError("El nombre de la estación no puede estar vacío.")
        if station["status"] != "ACTIVE":
            raise ValueError("Las estaciones del catálogo deben comenzar en ACTIVE.")
        identifier = (station["sectorId"], station["stationId"])
        if identifier in identifiers:
            raise ValueError("El catálogo contiene una estación repetida.")
        identifiers.add(identifier)
    return stations


def discover_resources(stack_name):
    cloudformation = boto3.client("cloudformation")
    response = cloudformation.describe_stacks(StackName=stack_name)
    stack = response["Stacks"][0]
    outputs = {}
    for output in stack.get("Outputs", []):
        outputs[output["OutputKey"]] = output["OutputValue"]

    for name in ("ApiUrl", "StationsTableName"):
        if not outputs.get(name):
            raise ValueError(f"El stack no publica el output {name}.")
    return {"api_url": outputs["ApiUrl"], "table_name": outputs["StationsTableName"]}


def initialize_stations(table_name, stations):
    table = boto3.resource("dynamodb").Table(table_name)
    counts = {"created": 0, "existing": 0}
    for station in stations:
        try:
            # EJERCICIO 3: Escribir station con put_item y una condición que
            # impida reemplazar un item con la misma primary key.
            raise NotImplementedError("Completar la escritura condicional")
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                counts["existing"] += 1
            else:
                raise
        else:
            counts["created"] += 1
    return counts


def main():
    parser = argparse.ArgumentParser(description="Preparar el catálogo inicial de estaciones.")
    parser.add_argument("--stack-name", required=True, help="Nombre del stack de CloudFormation")
    args = parser.parse_args()

    try:
        stations = load_catalog(CATALOG)
        resources = discover_resources(args.stack_name)
        counts = initialize_stations(resources["table_name"], stations)
    except (BotoCoreError, ClientError, OSError, ValueError, NotImplementedError) as exception:
        print(f"No se completó la inicialización: {exception}", file=sys.stderr)
        return 1

    print(f"API: {resources['api_url']}")
    print(f"Tabla: {resources['table_name']}")
    print(f"Estaciones creadas: {counts['created']}")
    print(f"Estaciones existentes: {counts['existing']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
