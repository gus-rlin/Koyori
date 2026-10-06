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
    planning_mode: str = "disabled"
    planning_region: str = "us-east-1"
    planning_model: str = "us.amazon.nova-2-lite-v1:0"
    planning_daily_limit: int = 200
    reasoning_task_limit: int = 16
    learning_mode: str = "disabled"
    learning_daily_limit: int = 20
    coordinator_machine_arn: str | None = None
    scheduler_group: str | None = None
    scheduler_role_arn: str | None = None
    scheduler_target_arn: str | None = None
    calendar_reader_arn: str | None = None
    speech_mode: str = "disabled"
    speech_region: str = "us-east-1"
    speech_model: str = "amazon.nova-2-sonic-v1:0"
    voice_runtime_arn: str | None = None
    mcp_runtime_arn: str | None = None
    voice_url: str = "ws://127.0.0.1:8099/ws"
    mcp_resource: str = "http://127.0.0.1:8088/mcp"
    allowed_origins: tuple[str, ...] = ("http://127.0.0.1:5173",)
    voice_daily_seconds: int = 3600
    realtime_url: str | None = None
    realtime_api_id: str | None = None

    def __post_init__(self):
        if self.learning_mode not in {"disabled", "simulated", "aws"}:
            raise ValueError("Invalid learning mode")
        if self.env != "local" and self.learning_mode == "simulated":
            raise ValueError("Simulated learning is local only")
        if not 1 <= self.learning_daily_limit <= 20:
            raise ValueError("Invalid learning call ceiling")
        if self.speech_mode not in {"disabled", "simulated", "aws"}:
            raise ValueError("Invalid speech mode")
        if self.env != "local" and self.speech_mode == "simulated":
            raise ValueError("Synthetic speech is local only")
        if self.speech_model != "amazon.nova-2-sonic-v1:0" or self.speech_region not in {
            "us-east-1",
            "us-west-2",
            "eu-north-1",
        }:
            raise ValueError("Unsupported speech locality/model")
        if not 600 <= self.voice_daily_seconds <= 86400:
            raise ValueError("Invalid voice daily ceiling")
        if self.env != "local" and (
            urlparse(self.mcp_resource).scheme != "https"
            or any(urlparse(origin).scheme != "https" for origin in self.allowed_origins)
        ):
            raise ValueError("Deployed channel endpoints require HTTPS")
        if self.env not in {"local", "dev", "prod"}:
            raise ValueError("Unsupported KOYORI_ENV")
        if not 1 <= self.shards <= 16 or not 5 <= self.lease_seconds <= 300:
            raise ValueError("Invalid operational limits")
        if self.semantic_mode not in {"disabled", "simulated", "aws"}:
            raise ValueError("Invalid semantic mode")
        if not 1 <= self.embedding_daily_limit <= 10000:
            raise ValueError("Invalid embedding call ceiling")
        if self.planning_mode not in {"disabled", "simulated", "aws"}:
            raise ValueError("Invalid planner mode")
        if self.env != "local" and self.planning_mode == "simulated":
            raise ValueError("Simulated planner is local only")
        if (
            self.planning_region not in {"us-east-1", "us-east-2", "us-west-2"}
            or self.planning_model != "us.amazon.nova-2-lite-v1:0"
        ):
            raise ValueError("Only the supported planning profile configuration is accepted")
        if not 1 <= self.planning_daily_limit <= 10000 or not 2 <= self.reasoning_task_limit <= 64:
            raise ValueError("Invalid reasoning call ceilings")
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
            planning_mode=os.getenv("KOYORI_PLANNING_MODE", "simulated" if local else "disabled"),
            planning_region=os.getenv("KOYORI_PLANNING_REGION", "us-east-1"),
            planning_model=os.getenv("KOYORI_PLANNING_MODEL", "us.amazon.nova-2-lite-v1:0"),
            planning_daily_limit=int(os.getenv("KOYORI_PLANNING_DAILY_LIMIT", "200")),
            reasoning_task_limit=int(os.getenv("KOYORI_REASONING_TASK_LIMIT", "16")),
            learning_mode=os.getenv("KOYORI_LEARNING_MODE", "disabled"),
            learning_daily_limit=int(os.getenv("KOYORI_LEARNING_DAILY_LIMIT", "20")),
            coordinator_machine_arn=os.getenv("KOYORI_COORDINATOR_MACHINE_ARN"),
            scheduler_group=os.getenv("KOYORI_SCHEDULER_GROUP"),
            scheduler_role_arn=os.getenv("KOYORI_SCHEDULER_ROLE_ARN"),
            scheduler_target_arn=os.getenv("KOYORI_SCHEDULER_TARGET_ARN"),
            calendar_reader_arn=os.getenv("KOYORI_CALENDAR_READER_ARN"),
            speech_mode=os.getenv("KOYORI_SPEECH_MODE", "simulated" if local else "disabled"),
            speech_region=os.getenv("KOYORI_SPEECH_REGION", "us-east-1"),
            speech_model=os.getenv("KOYORI_SPEECH_MODEL", "amazon.nova-2-sonic-v1:0"),
            voice_runtime_arn=os.getenv("KOYORI_VOICE_RUNTIME_ARN"),
            mcp_runtime_arn=os.getenv("KOYORI_MCP_RUNTIME_ARN"),
            voice_url=os.getenv("KOYORI_VOICE_URL", "ws://127.0.0.1:8099/ws"),
            mcp_resource=os.getenv("KOYORI_MCP_RESOURCE", "http://127.0.0.1:8088/mcp"),
            allowed_origins=tuple(
                filter(
                    None, os.getenv("KOYORI_ALLOWED_ORIGINS", "http://127.0.0.1:5173").split(",")
                )
            ),
            voice_daily_seconds=int(os.getenv("KOYORI_VOICE_DAILY_SECONDS", "3600")),
            realtime_url=os.getenv("KOYORI_REALTIME_URL"),
            realtime_api_id=os.getenv("KOYORI_REALTIME_API_ID"),
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
