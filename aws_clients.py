# -*- coding: utf-8 -*-
"""Clientes AWS con inicialización lazy (solo se crean cuando se necesitan)."""

import boto3

# ---------------------------------------------------------------------------
# Estado interno
# ---------------------------------------------------------------------------
_bedrock_agent_runtime = None
_dynamodb_resource = None
_secrets_client = None
_lambda_client = None


# ---------------------------------------------------------------------------
# Getters lazy
# ---------------------------------------------------------------------------


def get_bedrock_agent_runtime(region: str):
    """Cliente de Bedrock Agent Runtime (Knowledge Base, RAG)."""
    global _bedrock_agent_runtime
    if _bedrock_agent_runtime is None and region:
        _bedrock_agent_runtime = boto3.client(
            "bedrock-agent-runtime", region_name=region
        )
    return _bedrock_agent_runtime


def get_dynamodb_resource(region: str):
    """Recurso de DynamoDB (system prompt, tablas de configuración)."""
    global _dynamodb_resource
    if _dynamodb_resource is None and region:
        _dynamodb_resource = boto3.resource("dynamodb", region_name=region)
    return _dynamodb_resource


def get_secrets_client(region: str):
    """Cliente de Secrets Manager (tokens de API del Data Warehouse)."""
    global _secrets_client
    if _secrets_client is None and region:
        _secrets_client = boto3.client("secretsmanager", region_name=region)
    return _secrets_client


def get_lambda_client(region: str):
    """Cliente de Lambda (generación de reportes)."""
    global _lambda_client
    if _lambda_client is None and region:
        _lambda_client = boto3.client("lambda", region_name=region)
    return _lambda_client
