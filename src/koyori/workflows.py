"""Immutable Standard workflow starts with stable names and canonical run fencing."""

import json

from botocore.exceptions import ClientError

from koyori.domain import hkey, row
from koyori.errors import Conflict, Problem
from koyori.goals import Goals
from koyori.security import digest
from koyori.stage2 import Service
from koyori.store import guard, put


class Workflows(Service):
    def __init__(self, domain, client=None):
        super().__init__(domain)
        self.client = client or domain.settings.client("stepfunctions")
        self.goals = Goals(domain)

    def start_intent(self, run):
        input_text = json.dumps(
            {"householdId": run["PK"][2:], "taskId": run["id"], "runEpoch": run["runEpoch"]},
            sort_keys=True,
            separators=(",", ":"),
        )
        identifier = digest({"task": run["id"], "epoch": run["runEpoch"]})[:32]
        return row(
            f"WORKFLOWSTART#{identifier}",
            id=identifier,
            h=run["PK"][2:],
            taskId=run["id"],
            runEpoch=run["runEpoch"],
            name=f"{run['id']}-{run['runEpoch']}",
            input=input_text,
            status="PENDING",
            dueAt=self.domain.now(),
            GSI1PK=f"WORKFLOWSTART#{int(identifier[:8], 16) % self.domain.settings.shards}",
            GSI1SK=f"{self.domain.now():020d}#{identifier}",
        )

    def execution_arn(self, name):
        machine = self.domain.settings.coordinator_machine_arn
        if not machine:
            raise Problem(503, "WORKFLOW_UNAVAILABLE", "No Standard workflow configured.")
        return machine.replace(":stateMachine:", ":execution:") + ":" + name

    def start(self, candidate):
        intent = self.store.get("Delivery", (candidate["PK"], candidate["SK"]))
        if not intent or intent["status"] != "PENDING":
            return
        task = self.store.get("Domain", (hkey(intent["h"]), f"TASK#{intent['taskId']}"))
        if (
            not task
            or task["runEpoch"] != intent["runEpoch"]
            or task["leaseUntil"] <= self.domain.now()
        ):
            self.store.transact([put("Delivery", self.domain.done_intent(intent), intent)])
            return
        try:
            response = self.client.start_execution(
                stateMachineArn=self.domain.settings.coordinator_machine_arn,
                name=intent["name"],
                input=intent["input"],
            )
            execution = response["executionArn"]
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ExecutionAlreadyExists":
                raise
            execution = self.execution_arn(intent["name"])
            current = self.client.describe_execution(executionArn=execution)
            if current["input"] != intent["input"]:
                raise Problem(
                    409,
                    "WORKFLOW_INPUT_CONFLICT",
                    "Execution name has a different immutable input.",
                ) from exc
        new = self.domain.done_intent(intent)
        new.update(executionArn=execution, status="STARTED")
        self.store.transact([put("Delivery", new, intent)])

    def dispatch(self, candidate):
        task = self.store.get("Domain", (hkey(candidate["h"]), f"TASK#{candidate['taskId']}"))
        if task and task["leaseOwner"] and task["leaseUntil"] <= self.domain.now():
            # Lease expiry cannot take over a Standard execution that is still running.
            name = f"{task['id']}-{task['runEpoch']}"
            try:
                state = self.client.describe_execution(executionArn=self.execution_arn(name))
                if state["status"] == "RUNNING":
                    current = self.store.get("Delivery", (candidate["PK"], candidate["SK"]))
                    self.defer(current, self.domain.now() + 30)
                    return
            except ClientError as exc:
                if exc.response["Error"]["Code"] != "ExecutionDoesNotExist":
                    raise
        run = self.goals.acquire(candidate["h"], candidate["taskId"])
        if not run:
            return
        intent = self.start_intent(run)
        self.store.transact([guard("Domain", run), put("Delivery", intent)])
        self.start(intent)

    def sweep(self):
        candidates = self.pending("WORKFLOWSTART")
        for item in candidates:
            try:
                self.start(item)
            except Conflict:
                continue
            except Exception:
                current = self.store.get("Delivery", (item["PK"], item["SK"]))
                if current and current["status"] == "PENDING":
                    self.defer(current, self.domain.now() + 30)
        tasks = self.pending("GOALRUN")
        for item in tasks:
            try:
                self.dispatch(item)
            except Conflict:
                continue
            except Exception:
                current = self.store.get("Delivery", (item["PK"], item["SK"]))
                if current and current["status"] == "PENDING":
                    self.defer(current, self.domain.now() + 30)
        return len(candidates) + len(tasks)
