"""AgentCore identity/data isolation, AppSync authorization and immutable image parameters."""

import json

from koyori.config import Settings

pytest_plugins = ["test_infrastructure"]


def test_every_deployed_lambda_environment_constructs_settings(resources, monkeypatch):
    def resolve(value):
        if isinstance(value, str):
            return value
        if "Fn::Join" in value:
            separator, parts = value["Fn::Join"]
            return separator.join(resolve(part) for part in parts)
        if value.get("Fn::GetAtt", [None, None])[1] == "ApiEndpoint":
            return "https://api.example.invalid"
        if value.get("Fn::GetAtt", [None, None])[1] == "ProviderURL":
            return "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_fixture"
        return "deployment-placeholder"

    for resource in resources.values():
        if resource["Type"] != "AWS::Lambda::Function":
            continue
        variables = resource["Properties"]["Environment"]["Variables"]
        assert "KOYORI_MCP_RESOURCE" in variables and "KOYORI_ALLOWED_ORIGINS" in variables
        with monkeypatch.context() as environment:
            for name, value in variables.items():
                environment.setenv(name, resolve(value))
            settings = Settings.from_env()
            assert settings.mcp_resource.startswith("https://")
            assert all(origin.startswith("https://") for origin in settings.allowed_origins)


def test_lambda_roles_can_read_restore_fence_and_connector_channel_authority(resources):
    sessions = next(
        key
        for key, resource in resources.items()
        if resource["Type"] == "AWS::DynamoDB::Table"
        and resource["Properties"]["TableName"].endswith("Sessions")
    )
    for resource in resources.values():
        if resource["Type"] != "AWS::Lambda::Function":
            continue
        function = resource["Properties"]
        role = function["Role"]["Fn::GetAtt"][0]
        statements = [
            statement
            for policy in resources.values()
            if policy["Type"] == "AWS::IAM::Policy"
            and {"Ref": role} in policy["Properties"].get("Roles", [])
            for statement in policy["Properties"]["PolicyDocument"]["Statement"]
            if statement["Effect"] == "Allow" and sessions in json.dumps(statement["Resource"])
        ]

        def actions(statement):
            return (
                statement["Action"]
                if isinstance(statement["Action"], list)
                else [statement["Action"]]
            )

        assert any(
            "dynamodb:GetItem" in actions(statement)
            and (
                not statement.get("Condition")
                or "RESTORE_FENCE" in json.dumps(statement["Condition"])
            )
            for statement in statements
        ), function["Handler"]
        if function["Handler"].endswith(".connectors"):
            assert any(
                {"dynamodb:GetItem", "dynamodb:ConditionCheckItem"} <= set(actions(statement))
                and all(key in json.dumps(statement) for key in ("CHANNELGRANT#*", "VOICE#*"))
                for statement in statements
            )


def test_runtime_protocols_roles_and_lifetimes(resources):
    runtimes = [
        r["Properties"] for r in resources.values() if r["Type"] == "AWS::BedrockAgentCore::Runtime"
    ]
    assert len(runtimes) == 2
    assert {r["ProtocolConfiguration"] for r in runtimes} == {"HTTP", "MCP"}
    for runtime in runtimes:
        assert runtime["LifecycleConfiguration"] == {
            "IdleRuntimeSessionTimeout": 60,
            "MaxLifetime": 600,
        }
        assert "Connections" not in json.dumps(runtime["EnvironmentVariables"])
        assert "KOYORI_TOKEN_KEY_ARN" not in runtime["EnvironmentVariables"]
        role = runtime["RoleArn"]["Fn::GetAtt"][0]
        policies = [
            r["Properties"]
            for r in resources.values()
            if r["Type"] == "AWS::IAM::Policy" and {"Ref": role} in r["Properties"].get("Roles", [])
        ]
        text = json.dumps(policies)
        assert "Connections" not in text and "kms:Decrypt" not in text
        if runtime["ProtocolConfiguration"] == "HTTP":
            assert "InvokeModelWithBidirectionalStream" in text and "polly:SynthesizeSpeech" in text
        else:
            assert "bedrock:Invoke" not in text and "polly:" not in text


def test_event_api_has_no_api_key_or_user_publish_auth(resources):
    api = next(r["Properties"] for r in resources.values() if r["Type"] == "AWS::AppSync::Api")
    assert api["EventConfig"]["DefaultPublishAuthModes"] == [{"AuthType": "AWS_IAM"}]
    assert api["EventConfig"]["DefaultSubscribeAuthModes"] == [{"AuthType": "AWS_LAMBDA"}]
    assert "API_KEY" not in json.dumps(api)
    auth = next(p for p in api["EventConfig"]["AuthProviders"] if p["AuthType"] == "AWS_LAMBDA")
    assert auth["LambdaAuthorizerConfig"]["AuthorizerResultTtlInSeconds"] == 0
    namespace = next(
        r["Properties"] for r in resources.values() if r["Type"] == "AWS::AppSync::ChannelNamespace"
    )
    assert namespace["Name"] == "activity"
