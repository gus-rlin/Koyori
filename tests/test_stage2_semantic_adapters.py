import io
import json
from dataclasses import replace

import pytest
from botocore.awsrequest import AWSResponse
from botocore.exceptions import ClientError
from stage2_helpers import memory

from koyori.semantic import Semantic


class BedrockFixture:
    def invoke_model(self, **kwargs):
        return {"body": io.BytesIO(json.dumps({"embedding": [0.1] * 512}).encode())}


@pytest.mark.parametrize("remove", [False, True])
@pytest.mark.parametrize(
    "crash,repair_before_reply", [(False, False), (True, False), (False, True)]
)
def test_late_external_put_rearms_completed_correction_or_erasure_after_restart(
    harness, remove, crash, repair_before_reply
):
    h = harness
    item = memory(h)
    key = (f"MEMINDEX#{item['id']}", "META")

    class WorkerKilled(BaseException):
        pass

    class Vectors:
        def __init__(self):
            self.data = {}

        def put_vectors(self, **args):
            vector = args["vectors"][0]
            if vector["metadata"]["revision"] == 1:
                if remove:
                    response = h.client.delete(
                        f"/v1/memories/{item['id']}", headers=h.headers(version=1)
                    )
                else:
                    response = h.client.patch(
                        f"/v1/memories/{item['id']}",
                        json={"text": "Corrected dinner"},
                        headers=h.headers(version=1),
                    )
                assert response.status_code == 200
                service.project(h.domain.store.get("Delivery", key))
                assert h.domain.store.get("Delivery", key)["status"] == "DONE"
                if repair_before_reply:
                    h.clock.advance(121)
                    restarted = Semantic(h.domain, bedrock=BedrockFixture(), vectors=self)
                    restarted.mode = "aws"
                    restarted.sweep()
                    assert h.domain.store.get("Delivery", key)["status"] == "DONE"
            self.data[vector["key"]] = vector
            if crash and vector["metadata"]["revision"] == 1:
                raise WorkerKilled()

        def delete_vectors(self, **args):
            self.data.pop(args["keys"][0], None)

    vectors = Vectors()
    service = Semantic(h.domain, bedrock=BedrockFixture(), vectors=vectors)
    service.mode = "aws"
    original = h.domain.store.get("Delivery", key)
    if crash:
        with pytest.raises(WorkerKilled):
            service.project(original)
        h.clock.advance(121)
    else:
        service.project(original)
        assert h.domain.store.get("Delivery", key)["status"] == "PENDING"
    restarted = Semantic(h.domain, bedrock=BedrockFixture(), vectors=vectors)
    restarted.mode = "aws"
    restarted.sweep()
    assert h.domain.store.get("Delivery", key)["status"] == "DONE"
    if remove:
        assert item["id"] not in vectors.data
    else:
        assert vectors.data[item["id"]]["metadata"]["revision"] == 2


@pytest.mark.parametrize("quota", [False, True])
def test_more_than_one_batch_of_failures_does_not_starve_other_households_and_retry_survives_restart(
    harness, quota
):
    h = harness
    blocked = [memory(h) for _ in range(25)]
    h.clock.advance(1)
    response = h.client.post(
        "/v1/memories",
        json={"kind": "exchange", "text": "Other household"},
        headers=h.headers("robin", h=h.h2),
    )
    assert response.status_code == 201
    other = response.json()

    class Bedrock(BedrockFixture):
        failed = not quota

        def invoke_model(self, **args):
            if self.failed and json.loads(args["body"])["inputText"] == "Breakfast tomorrow":
                raise RuntimeError("fixture outage")
            return super().invoke_model(**args)

    class Vectors:
        def put_vectors(self, **args):
            return {}

    h.domain.settings = replace(h.settings, embedding_daily_limit=1 if quota else 10000)
    bedrock, vectors = Bedrock(), Vectors()
    service = Semantic(h.domain, bedrock=bedrock, vectors=vectors)
    service.mode = "aws"
    if quota:
        service.charge(h.h)
    for _ in range(3):
        service.sweep()
    assert h.domain.store.get("Delivery", (f"MEMINDEX#{other['id']}", "META"))["status"] == "DONE"
    assert all(
        h.domain.store.get("Delivery", (f"MEMINDEX#{x['id']}", "META"))["dueAt"] > h.clock()
        for x in blocked
    )
    restarted = Semantic(h.domain, bedrock=bedrock, vectors=vectors)
    restarted.mode = "aws"
    assert restarted.sweep() == 0
    bedrock.failed = False
    h.clock.advance(86400 - h.clock() % 86400 if quota else 31)
    restarted.sweep()
    restarted.sweep()
    completed = sum(
        h.domain.store.get("Delivery", (f"MEMINDEX#{x['id']}", "META"))["status"] == "DONE"
        for x in blocked
    )
    assert completed == (1 if quota else 25)


def test_botocore_model_transport_does_not_retry_unreserved_http_attempts(harness, monkeypatch):
    h = harness
    item = memory(h)
    client = h.settings.client("bedrock-runtime")
    attempts = []

    class Raw:
        def stream(self, **kwargs):
            yield b'{"message":"fixture unavailable"}'

    def send(request):
        attempts.append(request)
        return AWSResponse(request.url, 500, {"content-type": "application/json"}, Raw())

    monkeypatch.setattr(client._endpoint.http_session, "send", send)
    service = Semantic(h.domain, bedrock=client)
    service.mode = "aws"
    with pytest.raises(ClientError):
        service.project(h.domain.store.get("Delivery", (f"MEMINDEX#{item['id']}", "META")))
    assert len(attempts) == 1
    usage = [
        x
        for (table, (pk, _)), x in h.domain.store.rows.items()
        if table == "Domain" and pk.startswith(f"EMBEDUSE#{h.h}#")
    ]
    assert len(usage) == 1 and usage[0]["calls"] == 1


def test_s3_failures_preserve_exponential_retry_counter_across_workers(harness):
    h = harness
    item = memory(h)
    key = (f"MEMINDEX#{item['id']}", "META")

    class Vectors:
        calls = 0

        def put_vectors(self, **args):
            self.calls += 1
            if self.calls <= 3:
                raise RuntimeError("fixture S3 unavailable")

    vectors = Vectors()
    for retries, delay in enumerate((30, 60, 120), start=1):
        restarted = Semantic(h.domain, bedrock=BedrockFixture(), vectors=vectors)
        restarted.mode = "aws"
        restarted.sweep()
        intent = h.domain.store.get("Delivery", key)
        assert intent["retries"] == retries and intent["dueAt"] == h.clock() + delay
        assert restarted.sweep() == 0
        h.clock.advance(delay)
    restarted.sweep()
    assert vectors.calls == 4 and h.domain.store.get("Delivery", key)["status"] == "DONE"


def test_one_household_embedding_quota_does_not_block_other_projections(harness):
    h = harness
    a = memory(h)
    response = h.client.post(
        "/v1/memories",
        json={"kind": "exchange", "text": "Other household"},
        headers=h.headers("robin", h=h.h2),
    )
    assert response.status_code == 201
    b = response.json()

    class Bedrock:
        def invoke_model(self, **kwargs):
            return {"body": io.BytesIO(json.dumps({"embedding": [0.1] * 512}).encode())}

    class Vectors:
        def put_vectors(self, **kwargs):
            return {}

        def delete_vectors(self, **kwargs):
            return {}

    h.domain.settings = replace(h.settings, embedding_daily_limit=1)
    semantic = Semantic(h.domain, bedrock=Bedrock(), vectors=Vectors())
    semantic.mode = "aws"
    semantic.charge(h.h)
    semantic.sweep()
    assert h.domain.store.get("Delivery", (f"MEMINDEX#{a['id']}", "META"))["status"] == "PENDING"
    assert h.domain.store.get("Delivery", (f"MEMINDEX#{b['id']}", "META"))["status"] == "DONE"
    h.client.delete(f"/v1/memories/{a['id']}", headers=h.headers(version=1))
    semantic.sweep()
    assert h.domain.store.get("Delivery", (f"MEMINDEX#{a['id']}", "META"))["status"] == "DONE"


def test_real_embedding_and_vector_request_contracts_rehydrate_canonical_revision(harness):
    h = harness
    item = memory(h)
    seen = {}

    class Bedrock:
        def invoke_model(self, **args):
            seen["embedding"] = args
            return {"body": io.BytesIO(json.dumps({"embedding": [0.1] * 512}).encode())}

    class Vectors:
        def put_vectors(self, **args):
            seen["put"] = args

        def query_vectors(self, **args):
            seen["query"] = args
            return {"vectors": [{"metadata": seen["put"]["vectors"][0]["metadata"]}]}

        def delete_vectors(self, **args):
            seen["delete"] = args

    service = Semantic(h.domain, bedrock=Bedrock(), vectors=Vectors())
    service.mode = "aws"
    service.sweep()
    assert json.loads(seen["embedding"]["body"])["dimensions"] == 512
    assert seen["embedding"]["modelId"] == "amazon.titan-embed-text-v2:0"
    ctx = h.domain.context("alex", h.h)
    assert service.search(ctx, "Breakfast")[0]["id"] == item["id"]
    assert seen["query"]["topK"] == 20 and "filter" in seen["query"]
    assert "Breakfast" not in json.dumps(seen["put"])
    h.client.delete(f"/v1/memories/{item['id']}", headers=h.headers(version=1))
    assert service.search(ctx, "Breakfast") == []
    service.sweep()
    assert seen["delete"]["keys"] == [item["id"]]
