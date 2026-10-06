"""Stage-three permissions and durable orchestration in the synthesized template."""

import json

pytest_plugins = ["test_infrastructure"]


def test_standard_workflow_has_finite_task_and_no_private_execution_logs(resources):
    machine = next(
        v["Properties"]
        for v in resources.values()
        if v["Type"] == "AWS::StepFunctions::StateMachine"
    )
    assert machine["StateMachineType"] == "STANDARD"
    assert machine["LoggingConfiguration"]["IncludeExecutionData"] is False
    definition = json.dumps(machine["DefinitionString"])
    assert "CoordinateFiniteRun" in definition
    assert "TimeoutSeconds" in definition
    assert "Wait" not in definition and "Retry" not in definition


def test_planner_has_no_credentials_and_only_declared_model_and_calendar_reader(resources):
    functions = [
        v["Properties"] for v in resources.values() if v["Type"] == "AWS::Lambda::Function"
    ]
    coordinator = next(f for f in functions if f["Handler"].endswith(".coordinate"))
    env = coordinator["Environment"]["Variables"]
    assert env["KOYORI_PLANNING_MODE"] == "aws"
    assert "KOYORI_CALENDAR_READER_ARN" in env
    assert "KOYORI_TOKEN_KEY_ARN" not in env and "KOYORI_GOOGLE_CLIENT_SECRET_ARN" not in env
    assert "KOYORI_VECTOR_BUCKET" not in env
    role_id = coordinator["Role"]["Fn::GetAtt"][0]
    policies = [
        v["Properties"]
        for v in resources.values()
        if v["Type"] == "AWS::IAM::Policy" and {"Ref": role_id} in v["Properties"].get("Roles", [])
    ]
    text = json.dumps(policies)
    assert (
        "kms:Decrypt" not in text
        and "Connections" not in text
        and "secretsmanager:GetSecretValue" not in text
    )
    assert "bedrock:InvokeModel" in text and "nova-2-lite-v1:0" in text
    assert "lambda:InvokeFunction" in text
    assert "iam:PassRole" not in text and "scheduler:CreateSchedule" not in text


def test_scheduler_has_scoped_passrole_and_no_model_permissions(resources):
    group = next(
        v["Properties"] for v in resources.values() if v["Type"] == "AWS::Scheduler::ScheduleGroup"
    )
    assert group["Name"] == "koyori-dev-wakes"
    fn = next(
        v["Properties"]
        for v in resources.values()
        if v["Type"] == "AWS::Lambda::Function"
        and v["Properties"]["Handler"].endswith(".schedules")
    )
    role_id = fn["Role"]["Fn::GetAtt"][0]
    policies = [
        v["Properties"]
        for v in resources.values()
        if v["Type"] == "AWS::IAM::Policy" and {"Ref": role_id} in v["Properties"].get("Roles", [])
    ]
    text = json.dumps(policies)
    assert "iam:PassRole" in text and "iam:PassedToService" in text
    assert "scheduler:CreateSchedule" in text and "scheduler:DeleteSchedule" in text
    assert "bedrock:" not in text and "kms:Decrypt" not in text
