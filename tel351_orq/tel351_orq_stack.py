from pathlib import Path

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigatewayv2 as apigateway
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct


class Tel351OrqStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        table = dynamodb.Table(
            self,
            "StationsTable",
            partition_key=dynamodb.Attribute(name="sectorId", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="stationId", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        log_group = logs.LogGroup(
            self,
            "ApiLogs",
            retention=logs.RetentionDays.ONE_DAY,
            removal_policy=RemovalPolicy.DESTROY,
        )
        execution_role = iam.Role(
            self,
            "ApiExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )
        log_group.grant_write(execution_role)

        environment = {
            "SYSTEM_VERSION": "1.0",
            # EJERCICIO 1: Agregar TABLE_NAME utilizando la referencia a table.
        }

        api_function = lambda_.Function(
            self,
            "ApiFunction",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset(str(Path(__file__).resolve().parents[1] / "functions")),
            role=execution_role,
            log_group=log_group,
            environment=environment,
            timeout=Duration.seconds(10),
            memory_size=128,
        )

        # EJERCICIO 2: Agregar a execution_role una policy que permita consultar
        # y actualizar estaciones, restringida al ARN de table.
        # El apéndice muestra la estructura de add_to_policy y PolicyStatement.

        api = apigateway.HttpApi(self, "HttpApi", api_name="tel351-orq")
        integration = integrations.HttpLambdaIntegration("ApiIntegration", api_function)
        api.add_routes(
            path="/status",
            methods=[apigateway.HttpMethod.GET],
            integration=integration,
        )

        api.add_routes(
            path="/sectors/{sectorId}/stations",
            methods=[apigateway.HttpMethod.GET],
            integration=integration,
        )
        api.add_routes(
            path="/sectors/{sectorId}/stations/{stationId}",
            methods=[apigateway.HttpMethod.PATCH],
            integration=integration,
        )

        CfnOutput(self, "ApiUrl", value=api.api_endpoint)
        CfnOutput(self, "StationsTableName", value=table.table_name)
        CfnOutput(self, "ApiFunctionName", value=api_function.function_name)
