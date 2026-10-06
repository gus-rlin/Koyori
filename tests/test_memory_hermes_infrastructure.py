"""Memory projection and learning have separate model/delete permissions."""

import json
from pathlib import Path

import pytest

pytest_plugins = ["test_infrastructure"]


def policies(resources, function):
    role = function["Role"]["Fn::GetAtt"][0]
    return [
        r["Properties"]
        for r in resources.values()
        if r["Type"] == "AWS::IAM::Policy" and {"Ref": role} in r["Properties"].get("Roles", [])
    ]


def test_learning_is_disabled_by_default_without_credential_or_execution_authority(resources):
    function = next(
        r["Properties"]
        for r in resources.values()
        if r["Type"] == "AWS::Lambda::Function" and r["Properties"]["Handler"].endswith(".learn")
    )
    assert function["Environment"]["Variables"]["KOYORI_LEARNING_MODE"] == "disabled"
    assert function["Timeout"] == 60
    text = json.dumps(policies(resources, function))
    assert "bedrock:InvokeModel" in text and "nova-2-lite-v1:0" in text
    assert "RESTORE_FENCE" in text and "dynamodb:ConditionCheckItem" in text
    assert not any(
        s in text
        for s in (
            "kms:Decrypt",
            "Connections",
            "secretsmanager:GetSecretValue",
            "iam:PassRole",
            "s3vectors:",
            "lambda:InvokeFunction",
        )
    )


def test_projection_delete_is_limited_to_lexical_derivatives(resources):
    function = next(
        r["Properties"]
        for r in resources.values()
        if r["Type"] == "AWS::Lambda::Function"
        and r["Properties"]["Handler"].endswith(".projections")
    )
    deletes = [
        s
        for p in policies(resources, function)
        for s in p["PolicyDocument"]["Statement"]
        if "dynamodb:DeleteItem" in s["Action"]
    ]
    assert len(deletes) == 1
    assert deletes[0]["Condition"]["ForAllValues:StringLike"]["dynamodb:LeadingKeys"] == [
        "LEX#*",
        "LEXDOC#*",
    ]


@pytest.mark.parametrize("value, mode", [(True, "aws"), ("true", "aws"), ("yes", "disabled")])
def test_learning_activation_accepts_explicit_boolean_and_cli_context(
    tmp_path, monkeypatch, value, mode
):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    import aws_cdk as cdk
    from aws_cdk.assertions import Template

    from infrastructure.stack import FoundationStack

    app = cdk.App(outdir=str(tmp_path / "cdk"), context={"learningEnabled": value})
    stack = FoundationStack(
        app, "MemoryActivation", stage="dev", callback_url="https://example.invalid/callback"
    )
    functions = [
        r["Properties"]
        for r in Template.from_stack(stack).to_json()["Resources"].values()
        if r["Type"] == "AWS::Lambda::Function"
    ]
    assert len(functions) == 14
    assert all(f["Environment"]["Variables"]["KOYORI_LEARNING_MODE"] == mode for f in functions)
