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

    def __post_init__(self):
        if self.env not in {"local", "dev", "prod"}:
            raise ValueError("Unsupported KOYORI_ENV")
        if not 1 <= self.shards <= 16 or not 5 <= self.lease_seconds <= 300:
            raise ValueError("Invalid operational limits")
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
        )

    def client(self, service: str):
        endpoint = (
            self.ddb_endpoint
            if service == "dynamodb"
            else self.sqs_endpoint
            if service == "sqs"
            else None
        )
        kwargs = {"region_name": self.region, "config": SDK_CONFIG}
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
