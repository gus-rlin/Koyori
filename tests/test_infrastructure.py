"""Inspect the synthesized AWS deployment boundary without account access."""

import json
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def resources():
    path = Path("cdk.out/KoyoriFoundation.template.json")
    if not path.exists():
        pytest.skip("Build Lambda artifact and run python -m infrastructure.app first")
    return json.loads(path.read_text(encoding="utf-8"))["Resources"]


def test_tables_have_encryption_recovery_retention_and_bounded_indexes(resources):
    tables = [v for v in resources.values() if v["Type"] == "AWS::DynamoDB::Table"]
    assert len(tables) == 3
    for table in tables:
        properties = table["Properties"]
        assert properties["BillingMode"] == "PAY_PER_REQUEST"
        assert properties["DeletionProtectionEnabled"] is True
        assert properties["PointInTimeRecoverySpecification"]["PointInTimeRecoveryEnabled"]
        assert properties["SSESpecification"]["SSEEnabled"]
        assert table["DeletionPolicy"] == "Retain"
        assert len(properties["GlobalSecondaryIndexes"]) == 2


def test_lambda_separation_limits_partial_failure_and_identity(resources):
    functions = [
        v["Properties"] for v in resources.values() if v["Type"] == "AWS::Lambda::Function"
    ]
    assert len(functions) == 5
    for fn in functions:
        assert fn["Runtime"] == "python3.12"
        assert fn.get("Architectures", ["x86_64"]) == ["x86_64"]
        assert fn["Timeout"] == 30
        assert fn["ReservedConcurrentExecutions"] == 4
        assert fn["TracingConfig"]["Mode"] == "Active"
        environment = fn["Environment"]["Variables"]
        assert environment["KOYORI_ENV"] == "dev"
        assert "KOYORI_DDB_ENDPOINT" not in environment
        assert "KOYORI_SQS_ENDPOINT" not in environment
        assert "koyori-synthetic" not in json.dumps(environment)
    mappings = [
        v["Properties"]
        for v in resources.values()
        if v["Type"] == "AWS::Lambda::EventSourceMapping"
    ]
    assert len(mappings) == 3
    assert all(m["FunctionResponseTypes"] == ["ReportBatchItemFailures"] for m in mappings)


def test_queues_redrive_encryption_and_transport_security(resources):
    queues = [v["Properties"] for v in resources.values() if v["Type"] == "AWS::SQS::Queue"]
    assert len(queues) == 4
    assert all(q["SqsManagedSseEnabled"] for q in queues)
    primary = [q for q in queues if "RedrivePolicy" in q]
    assert len(primary) == 2
    assert all(
        q["RedrivePolicy"]["maxReceiveCount"] == 5 and q["VisibilityTimeout"] >= 180
        for q in primary
    )
    policies = [v["Properties"] for v in resources.values() if v["Type"] == "AWS::SQS::QueuePolicy"]
    assert len(policies) == 4
    assert all(
        any(
            s.get("Condition", {}).get("Bool", {}).get("aws:SecureTransport") == "false"
            and s["Effect"] == "Deny"
            for s in p["PolicyDocument"]["Statement"]
        )
        for p in policies
    )


def test_runtime_iam_has_no_scan_or_global_data_permissions(resources):
    policies = [v["Properties"] for v in resources.values() if v["Type"] == "AWS::IAM::Policy"]
    for policy in policies:
        for statement in policy["PolicyDocument"]["Statement"]:
            actions = (
                statement["Action"]
                if isinstance(statement["Action"], list)
                else [statement["Action"]]
            )
            assert "dynamodb:Scan" not in actions
            assert "dynamodb:*" not in actions and "sqs:*" not in actions
            if any(
                a.startswith(("dynamodb:", "sqs:", "secretsmanager:", "events:")) for a in actions
            ):
                # ListStreams cannot be resource-scoped; it reads stream metadata,
                # not private item values. All item/queue/secret operations are scoped.
                assert statement["Resource"] != "*" or actions == ["dynamodb:ListStreams"]


def test_managed_identity_uses_code_flow_and_mfa(resources):
    pool = next(
        v["Properties"] for v in resources.values() if v["Type"] == "AWS::Cognito::UserPool"
    )
    assert pool["MfaConfiguration"] == "ON"
    assert pool["AdminCreateUserConfig"]["AllowAdminCreateUserOnly"] is True
    assert pool["UserPoolTier"] == "ESSENTIALS"
    client = next(
        v["Properties"] for v in resources.values() if v["Type"] == "AWS::Cognito::UserPoolClient"
    )
    assert client["AllowedOAuthFlows"] == ["code"] and client["GenerateSecret"] is False
    server_id, server = next(
        (key, v["Properties"])
        for key, v in resources.items()
        if v["Type"] == "AWS::Cognito::UserPoolResourceServer"
    )
    assert server["Identifier"] == "koyori"
    assert server["Scopes"][0]["ScopeName"] == "control"
    assert {"Fn::Join": ["", [{"Ref": server_id}, "/control"]]} in client["AllowedOAuthScopes"]
    domain_id, domain = next(
        (key, v["Properties"])
        for key, v in resources.items()
        if v["Type"] == "AWS::Cognito::UserPoolDomain"
    )
    assert domain["ManagedLoginVersion"] == 2
    branding = next(
        v for v in resources.values() if v["Type"] == "AWS::Cognito::ManagedLoginBranding"
    )
    assert branding["Properties"]["UseCognitoProvidedValues"] is True
    assert branding["Properties"]["ClientId"] == {
        "Ref": next(k for k, v in resources.items() if v["Type"] == "AWS::Cognito::UserPoolClient")
    }
    assert domain_id in branding["DependsOn"]
    assert any(v["Type"] == "AWS::Backup::BackupPlan" for v in resources.values())
