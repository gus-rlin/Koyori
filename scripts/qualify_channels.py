"""Explicit cloud preflight; no success is claimed without the deployed end-to-end recipe."""

import argparse
import json
import os
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    reason = "live_not_requested"
    if args.live:
        try:
            # This read does not invoke a service or infer permission from credential presence.
            credentials = boto3.Session().get_credentials()
            available = bool(credentials and credentials.get_frozen_credentials().access_key)
        except (BotoCoreError, OSError):
            available = False
        reason = (
            "deployed_fixture_and_channel_recipe_required"
            if available
            else "aws_credentials_unavailable"
        )
    report = {
        "schemaVersion": "1.0",
        "result": "NOT_RUN",
        "reason": reason,
        "testsExecuted": 0,
        "facturableModelCalls": 0,
        "observedAwsCost": None,
        "awsResourcesCreated": [],
        "requiredEvidence": [
            "Cognito PKCE and resource-bound MCP",
            "AgentCore ARM64 image and IAM denial",
            "French and English Nova finalized PCM turns",
            "Polly exact templates and interruption",
            "AppSync subscription isolation and reconnect",
            "three concept journeys with Google calendar",
            "offline restore and key rotation",
            "client voice p95 and measured billing units",
        ],
        "environment": {
            "region": os.getenv("AWS_REGION", "eu-west-1"),
            "speechRegion": os.getenv("KOYORI_SPEECH_REGION", "eu-north-1"),
        },
    }
    (ROOT / "docs/verification/channel-qualification.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"result": report["result"], "reason": reason, "facturableModelCalls": 0}))


if __name__ == "__main__":
    main()
