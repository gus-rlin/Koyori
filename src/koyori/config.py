"""Fail-closed configuration. Synthetic identity and custom AWS endpoints are local only."""

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.config import Config

SDK_CONFIG = Config(
    connect_timeout=3, read_timeout=10, retries={"mode": "standard", "max_attempts": 3}
)


@dataclass(frozen=True)
class Settings:
    env: str = "local"
    region: str = "eu-west-1"
    prefix: str = "KoyoriLocal"
    ddb_endpoint: str | None = "http://127.0.0.1:8800"
    sqs_endpoint: str | None = "http://127.0.0.1:9324"
    issuer: str = "https://koyori.invalid/local"
    client_id: str = "koyori-synthetic"
    audience: str = "koyori-control"
    key_dir: str = ".local/keys"
    cursor_secret_arn: str | None = None
    bus_name: str | None = None
    workflow_url: str | None = None
    activity_url: str | None = None
    lease_seconds: int = 30
    max_tasks: int = 32
    max_members: int = 8
    shards: int = 4
    semantic_mode: str = "disabled"
    vector_bucket: str | None = None
    vector_index: str = "memory-v1"
    google_client_id: str | None = None
    google_client_secret_arn: str | None = None
    google_config_file: str | None = None
    google_redirect_uri: str | None = None
    google_webhook_url: str | None = None
    token_key_arn: str | None = None
    token_key_file: str = ".local/oauth-envelope.key"
    embedding_daily_limit: int = 200

    def __post_init__(self):
        if self.env not in {"local", "dev", "prod"}:
            raise ValueError("Unsupported KOYORI_ENV")
        if not 1 <= self.shards <= 16 or not 5 <= self.lease_seconds <= 300:
            raise ValueError("Invalid operational limits")
        if self.semantic_mode not in {"disabled", "simulated", "aws"}:
            raise ValueError("Invalid semantic mode")
        if not 1 <= self.embedding_daily_limit <= 10000:
            raise ValueError("Invalid embedding call ceiling")
        if self.semantic_mode == "aws" and (self.env == "local" or not self.vector_bucket):
            raise ValueError("AWS semantic search requires an AWS environment and vector bucket")
        if self.env != "local" and self.semantic_mode == "simulated":
            raise ValueError("Simulated embedding is local only")
        if self.google_redirect_uri:
            redirect = urlparse(self.google_redirect_uri)
            if redirect.scheme != "https" and not (
                self.env == "local"
                and redirect.scheme == "http"
                and redirect.hostname in {"127.0.0.1", "localhost"}
            ):
                raise ValueError("Google callback requires HTTPS or local loopback")
        if self.google_webhook_url and urlparse(self.google_webhook_url).scheme != "https":
            raise ValueError("Google push requires HTTPS")
        if self.env != "local":
            host = urlparse(self.issuer)
            if self.ddb_endpoint or self.sqs_endpoint or self.client_id == "koyori-synthetic":
                raise ValueError("Local identity/endpoints prohibited outside local")
            if (
                host.scheme != "https"
                or host.hostname != f"cognito-idp.{self.region}.amazonaws.com"
            ):
                raise ValueError("Expected regional Cognito issuer")
            if not host.path.startswith(f"/{self.region}_") or not self.cursor_secret_arn:
                raise ValueError("Cognito pool and cursor secret required")

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.getenv("KOYORI_ENV", "local")
        local = env == "local"
        return cls(
            env=env,
            region=os.getenv("AWS_REGION", "eu-west-1"),
            prefix=os.getenv("KOYORI_TABLE_PREFIX", "KoyoriLocal"),
            ddb_endpoint=os.getenv("KOYORI_DDB_ENDPOINT", "http://127.0.0.1:8800" if local else "")
            or None,
            sqs_endpoint=os.getenv("KOYORI_SQS_ENDPOINT", "http://127.0.0.1:9324" if local else "")
            or None,
            issuer=os.getenv("KOYORI_ISSUER", "https://koyori.invalid/local" if local else ""),
            client_id=os.getenv("KOYORI_CLIENT_ID", "koyori-synthetic" if local else ""),
            audience=os.getenv("KOYORI_AUDIENCE", "koyori-control"),
            key_dir=os.getenv("KOYORI_KEY_DIR", ".local/keys"),
            cursor_secret_arn=os.getenv("KOYORI_CURSOR_SECRET_ARN"),
            bus_name=os.getenv("KOYORI_EVENT_BUS"),
            workflow_url=os.getenv("KOYORI_WORKFLOW_QUEUE_URL"),
            activity_url=os.getenv("KOYORI_ACTIVITY_QUEUE_URL"),
            semantic_mode=os.getenv("KOYORI_SEMANTIC_MODE", "simulated" if local else "disabled"),
            vector_bucket=os.getenv("KOYORI_VECTOR_BUCKET"),
            vector_index=os.getenv("KOYORI_VECTOR_INDEX", "memory-v1"),
            google_client_id=os.getenv("KOYORI_GOOGLE_CLIENT_ID"),
            google_client_secret_arn=os.getenv("KOYORI_GOOGLE_CLIENT_SECRET_ARN"),
            google_config_file=os.getenv("KOYORI_GOOGLE_CONFIG_FILE") if local else None,
            google_redirect_uri=os.getenv("KOYORI_GOOGLE_REDIRECT_URI"),
            google_webhook_url=os.getenv("KOYORI_GOOGLE_WEBHOOK_URL"),
            token_key_arn=os.getenv("KOYORI_TOKEN_KEY_ARN"),
            token_key_file=os.getenv("KOYORI_TOKEN_KEY_FILE", ".local/oauth-envelope.key"),
            embedding_daily_limit=int(os.getenv("KOYORI_EMBEDDING_DAILY_LIMIT", "200")),
        )

    def client(self, service: str):
        endpoint = (
            self.ddb_endpoint
            if service == "dynamodb"
            else self.sqs_endpoint
            if service == "sqs"
            else None
        )
        # Every billed model attempt needs its own durable quota reservation.
        config = (
            SDK_CONFIG.merge(Config(retries={"mode": "standard", "total_max_attempts": 1}))
            if service == "bedrock-runtime"
            else SDK_CONFIG
        )
        kwargs = {"region_name": self.region, "config": config}
        if self.env == "local":
            kwargs.update(aws_access_key_id="local", aws_secret_access_key="local")
        return boto3.client(service, endpoint_url=endpoint, **kwargs)

    def cursor_secret(self) -> bytes:
        if self.env == "local":
            value = Path(self.key_dir, "cursor.key").read_bytes()
        else:
            value = (
                self.client("secretsmanager")
                .get_secret_value(SecretId=self.cursor_secret_arn)["SecretString"]
                .encode()
            )
        if len(value) < 32:
            raise ValueError("Cursor signing key too short")
        return value
