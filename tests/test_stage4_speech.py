"""Transaction truth and actual native SDK event classes with an explicit stream double."""

import asyncio
import json
from dataclasses import replace

import pytest

from koyori.config import Settings
from koyori.speech import NovaSpeech, Polly, RuntimeCredentials, narration


@pytest.mark.parametrize("locale", ["fr-FR", "en-US"])
@pytest.mark.parametrize("code", ["TOOL_FORBIDDEN", "CONTENTION"])
def test_tool_errors_never_announce_available_context_or_confirmed_work(locale, code):
    result = narration({"code": code, "retryable": code == "CONTENTION"}, locale)
    assert result["evidence"] == "tool_error" and result["code"] == code
    assert "disponible" not in result["text"] and "available" not in result["text"]
    assert "enregistrée" not in result["text"] and "recorded" not in result["text"]


@pytest.mark.parametrize("locale", ["fr-FR", "en-US"])
def test_goal_waiting_approval_is_spoken_before_its_proposed_action(locale):
    result = narration(
        {"id": "g", "rev": 3, "status": "WAITING_APPROVAL", "actions": [{"status": "PROPOSED"}]},
        locale,
    )
    assert "approbation" in result["text"].lower() or "approval" in result["text"].lower()
    assert "personnel" in result["text"] or "personal" in result["text"]
    assert result["status"] == "WAITING_APPROVAL" and result["sourceRevision"] == 3


def test_unknown_cancelled_goal_and_receipt_speech_are_distinct():
    unknown = narration({"id": "x", "status": "UNKNOWN", "receipt": None})
    assert "inconnu" in unknown["text"] and unknown["evidence"] == "canonical_state"
    goal = narration({"id": "g", "status": "CANCELLED"})
    assert "reste soumise" in goal["text"]
    confirmed = narration(
        {"id": "a", "status": "CONFIRMED", "receipt": {"status": "CONFIRMED", "totalMinor": 1234}}
    )
    assert "12,34" in confirmed["text"] and "pas encore attestée" in confirmed["text"]
    assert confirmed["evidence"] == "provider_receipt"
    unproven = narration({"id": "a", "status": "CONFIRMED", "receipt": None})
    assert "Commande confirmée" not in unproven["text"]


def test_polly_exact_template_text_and_pcm_configuration():
    import io

    class Client:
        def synthesize_speech(self, **values):
            self.values = values
            return {"AudioStream": io.BytesIO(b"\0\0" * 16)}

    client = Client()
    service = Polly(replace(Settings(), speech_mode="aws"), client)
    template = narration({"id": "g", "status": "WAITING_APPROVAL"})
    assert service.synthesize(template, "fr-FR") == b"\0\0" * 16
    assert client.values["Text"] == template["text"]
    assert client.values["SampleRate"] == "16000" and client.values["TextType"] == "text"


def test_memory_speech_in_both_languages_skips_missing_sources():
    value = {
        "items": [
            {"text": "Souvenir disponible", "sourceStatus": "available"},
            {"text": "Contenu retiré", "sourceStatus": "missing"},
        ]
    }
    for locale in ("fr-FR", "en-US"):
        result = narration(value, locale)
        assert "Souvenir disponible" in result["text"]
        assert "Contenu retiré" not in result["text"]
        assert result["evidence"] == "canonical_state"


def test_native_stream_api_and_wire_event_contract():
    class Input:
        def __init__(self):
            self.events = []

        async def send(self, chunk):
            self.events.append(json.loads(chunk.value.bytes_))

    class Stream:
        def __init__(self):
            self.input_stream = Input()

        async def close(self):
            pass

    class Client:
        def __init__(self):
            self.stream = Stream()

        async def invoke_model_with_bidirectional_stream(self, request):
            self.model = request.model_id
            return self.stream

        async def close(self):
            pass

    client = Client()

    async def run():
        service = NovaSpeech(Settings(), client=client)
        await service.open({"items": []}, {"get_task_status"})
        await service.audio(b"\0\0")
        await service.tool_result("one", {"status": "UNKNOWN"})
        await service.close()

    asyncio.run(run())
    assert client.model == "amazon.nova-2-sonic-v1:0"
    events = client.stream.input_stream.events
    assert "sessionStart" in events[0]["event"]
    assert any("audioInput" in event["event"] for event in events)
    assert any("toolResult" in event["event"] for event in events)


def test_native_identity_resolver_refreshes_temporary_execution_credentials():
    from types import SimpleNamespace

    class Session:
        def __init__(self):
            self.reads = 0

        def get_credentials(self):
            self.reads += 1
            return SimpleNamespace(
                get_frozen_credentials=lambda: SimpleNamespace(
                    access_key=f"fixture-{self.reads}",
                    secret_key="fixture-secret",
                    token="fixture-session",
                )
            )

    session = Session()
    resolver = RuntimeCredentials(session)

    async def run():
        first = await resolver.get_identity(properties={})
        second = await resolver.get_identity(properties={})
        assert first.access_key_id != second.access_key_id
        assert second.session_token == "fixture-session"

    asyncio.run(run())


def test_generative_audio_is_suppressed_and_only_final_user_is_emitted():
    service = NovaSpeech(Settings())
    assert service.decode({"audioOutput": {"content": "fake"}}) is None
    service.decode({"contentStart": {"contentName": "u", "role": "USER", "type": "TEXT"}})
    assert (
        service.decode({"textOutput": {"contentName": "u", "content": "Prépare le dîner"}}) is None
    )
    assert service.decode({"contentEnd": {"contentName": "u"}})["text"] == "Prépare le dîner"
    service.decode({"contentStart": {"contentName": "a", "role": "ASSISTANT", "type": "TEXT"}})
    service.decode({"textOutput": {"contentName": "a", "content": "The order is delivered"}})
    assert service.decode({"contentEnd": {"contentName": "a"}}) is None
