import json
import logging
from dataclasses import replace

import boto3
import pytest
from botocore.awsrequest import AWSResponse
from botocore.exceptions import ClientError
from stage3_helpers import goals, submit, task

from koyori.errors import Conflict, Problem
from koyori.planner import StrandsPlanner
from koyori.scheduling import Scheduler, Wakes
from koyori.store import put
from koyori.workflows import Workflows


class Raw:
    def __init__(self, content):
        self.content = content

    def stream(self, amt=None, decode_content=False):
        yield self.content


class BedrockTransport:
    """Actual Strands/Botocore execution with HTTP intercepted before any network request."""

    def __init__(self, *, throttle=False):
        self.calls = []
        self.throttle = throttle

    def model(self, **kwargs):
        from strands.models import BedrockModel

        region = kwargs.pop("region_name")
        session = boto3.Session(
            region_name=region, aws_access_key_id="fixture", aws_secret_access_key="fixture"
        )
        model = BedrockModel(boto_session=session, **kwargs)

        def send(request):
            logging.getLogger("strands.event_loop.streaming").warning(
                "raw_input=<%s>", "PRIVATE_SYNTHETIC_MODEL_FRAGMENT"
            )
            payload = json.loads(request.body)
            self.calls.append(payload)
            if self.throttle:
                return AWSResponse(
                    request.url,
                    429,
                    {"x-amzn-errortype": "ThrottlingException"},
                    Raw(b'{"message":"fixture throttle"}'),
                )
            name = payload["toolConfig"]["tools"][0]["toolSpec"]["name"]
            plan = {
                "summary": "Consulter les souvenirs",
                "steps": [{"stepId": "memory", "capability": "memory.context", "arguments": {}}],
            }
            response = {
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"toolUse": {"toolUseId": "typed-plan", "name": name, "input": plan}}
                        ],
                    }
                },
                "stopReason": "tool_use",
                "usage": {"inputTokens": 100, "outputTokens": 50, "totalTokens": 150},
                "metrics": {"latencyMs": 1},
            }
            return AWSResponse(
                request.url,
                200,
                {"content-type": "application/json"},
                Raw(json.dumps(response).encode()),
            )

        model.client._endpoint.http_session.send = send
        return model


def test_actual_strands_converse_produces_validated_plan_without_execution_tools(harness):
    h = harness
    fixture = BedrockTransport()
    service = goals(h)
    service.planning = StrandsPlanner(h.settings, model_factory=fixture.model)
    tid = submit(h, "Consulte mes souvenirs")
    service.sweep()
    current = task(h, tid)
    assert current["plan"] and current["plan"]["steps"][0]["capability"] == "memory.context", (
        current
    )
    assert current["modelCalls"] == 1 and len(fixture.calls) == 1
    assert len(fixture.calls[0]["toolConfig"]["tools"]) == 1
    assert fixture.calls[0]["inferenceConfig"]["maxTokens"] == 4096


def test_strands_throttle_has_no_hidden_sdk_retries(harness):
    h = harness
    fixture = BedrockTransport(throttle=True)
    service = goals(h)
    service.planning = StrandsPlanner(h.settings, model_factory=fixture.model)
    tid = submit(h)
    service.sweep()
    assert task(h, tid)["status"] == "NEEDS_ATTENTION"
    assert task(h, tid)["modelCalls"] == len(fixture.calls) == 1


def test_sdk_warning_with_private_model_fragment_does_not_reach_application_logs(harness, caplog):
    h = harness
    fixture = BedrockTransport()
    service = goals(h)
    service.planning = StrandsPlanner(h.settings, model_factory=fixture.model)
    with caplog.at_level(logging.WARNING):
        tid = submit(h, "Consulte mes préférences")
        service.sweep()
    assert task(h, tid)["planRevision"] == 1
    assert "PRIVATE_SYNTHETIC_MODEL_FRAGMENT" not in caplog.text
    service.sweep()
    assert len(fixture.calls) == 1


class SchedulerFixture:
    def __init__(self):
        self.entries = {}

    def create_schedule(self, **kwargs):
        if kwargs["Name"] in self.entries:
            raise ClientError({"Error": {"Code": "ConflictException"}}, "CreateSchedule")
        self.entries[kwargs["Name"]] = kwargs
        return {}

    def get_schedule(self, **kwargs):
        return self.entries[kwargs["Name"]]

    def delete_schedule(self, **kwargs):
        if kwargs["Name"] not in self.entries:
            raise ClientError({"Error": {"Code": "ResourceNotFoundException"}}, "DeleteSchedule")
        del self.entries[kwargs["Name"]]


def test_scheduler_adapter_idempotence_immutable_payload_and_deletion(harness):
    h = harness
    settings = replace(
        h.settings,
        scheduler_group="fixture-group",
        scheduler_target_arn="arn:aws:lambda:eu-west-1:000000000000:function:fixture",
        scheduler_role_arn="arn:aws:iam::000000000000:role/fixture",
    )
    fixture = SchedulerFixture()
    scheduler = Scheduler(settings, fixture)
    tid = submit(h)
    writes = Wakes(h.domain).goal_wake(task(h, tid), h.clock() + 120)
    wake = writes[0].item
    scheduler.ensure(wake)
    scheduler.ensure(wake)
    assert len(fixture.entries) == 1
    entry = next(iter(fixture.entries.values()))
    assert json.loads(entry["Target"]["Input"]) == {"wakeId": wake["id"]}
    assert entry["ActionAfterCompletion"] == "DELETE"
    assert entry["FlexibleTimeWindow"] == {"Mode": "OFF"}
    fixture.entries[entry["Name"]]["Target"]["Input"] = '{"wakeId":"different"}'
    with pytest.raises(Problem, match="SCHEDULE_CONFLICT"):
        scheduler.ensure(wake)
    scheduler.remove(wake)
    scheduler.remove(wake)


class WorkflowFixture:
    def __init__(self):
        self.entries = {}
        self.names = []

    def start_execution(self, **kwargs):
        self.names.append(kwargs["name"])
        arn = (
            kwargs["stateMachineArn"].replace(":stateMachine:", ":execution:")
            + ":"
            + kwargs["name"]
        )
        if arn in self.entries:
            raise ClientError({"Error": {"Code": "ExecutionAlreadyExists"}}, "StartExecution")
        self.entries[arn] = {"status": "RUNNING", "input": kwargs["input"]}
        return {"executionArn": arn}

    def describe_execution(self, **kwargs):
        if kwargs["executionArn"] not in self.entries:
            raise ClientError({"Error": {"Code": "ExecutionDoesNotExist"}}, "DescribeExecution")
        return self.entries[kwargs["executionArn"]]


def test_workflow_crash_after_start_recovers_same_name_and_input(harness):
    h = harness
    h.domain.settings = replace(
        h.settings,
        coordinator_machine_arn="arn:aws:states:eu-west-1:000000000000:stateMachine:fixture",
    )
    fixture = WorkflowFixture()
    service = Workflows(h.domain, fixture)
    tid = submit(h)
    run = service.goals.acquire(h.h, tid)
    intent = service.start_intent(run)
    h.domain.store.transact([put("Delivery", intent)])
    original_transact = h.domain.store.transact

    def conflict(changes):
        if any(change.item and change.item.get("status") == "STARTED" for change in changes):
            raise Conflict
        original_transact(changes)

    h.domain.store.transact = conflict
    with pytest.raises(Conflict):
        service.start(intent)
    h.domain.store.transact = original_transact
    service.start(intent)
    assert fixture.names == [intent["name"], intent["name"]]
    assert len(fixture.entries) == 1
    stored = h.domain.store.get("Delivery", (intent["PK"], intent["SK"]))
    assert stored["status"] == "STARTED"
    assert set(json.loads(stored["input"])) == {"householdId", "taskId", "runEpoch"}


def test_workflow_still_running_after_lease_expiry_prevents_takeover(harness):
    h = harness
    h.domain.settings = replace(
        h.settings,
        coordinator_machine_arn="arn:aws:states:eu-west-1:000000000000:stateMachine:fixture",
    )
    fixture = WorkflowFixture()
    service = Workflows(h.domain, fixture)
    tid = submit(h)
    service.sweep()
    epoch = task(h, tid)["runEpoch"]
    h.clock.advance(121)
    service.sweep()
    assert task(h, tid)["runEpoch"] == epoch
    next(iter(fixture.entries.values()))["status"] = "TIMED_OUT"
    h.clock.advance(31)
    service.sweep()
    assert task(h, tid)["runEpoch"] == epoch + 1
