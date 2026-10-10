"""One-use voice admission and bounded opaque internal authority, stored only as hashes."""

import secrets
import uuid
from dataclasses import replace

from koyori.domain import row, uid
from koyori.errors import Conflict, Problem, denied, missing
from koyori.security import digest
from koyori.store import Change, guard, put, revised

READ_TOOLS = {"get_daily_context", "recall_memories", "search_memories", "get_task_status"}
PERSONAL_TOOLS = READ_TOOLS | {
    "submit_goal",
    "amend_goal",
    "pause_goal",
    "resume_goal",
    "cancel_goal",
    "propose_calendar_event",
}


class Sessions:
    def __init__(self, domain):
        self.domain, self.store = domain, domain.store

    def _key(self, category, value):
        return f"{category}#{digest({'capability': value})}", "META"

    def _privacy(self, ctx):
        key = (f"H#{ctx.h}", f"PRIVACY#{ctx.actor}")
        fence = self.store.get("Domain", key)
        if fence and fence["status"] == "ERASING":
            raise denied()
        return (fence or {}).get("epoch", 0), guard("Domain", fence) if fence else Change(
            "Domain", key, None
        )

    def _authority(self, item):
        if item.get("expiresAt", 0) <= self.domain.now() or item.get("closed"):
            raise denied()
        ctx = self.domain.context(item["actor"], item["h"])
        if item["accessEpoch"] != ctx.member.get("accessEpoch", 1):
            raise denied()
        if item["profileEpoch"] != ctx.profile.get("accessEpoch", 1):
            raise denied()
        epoch, _ = self._privacy(ctx)
        if item.get("privacyEpoch", 0) != epoch:
            raise denied()
        if item["mode"] == "personal":
            self.domain.personal(ctx)
        else:
            # Authorization primitives already implement shared-mode restrictions.
            ctx = replace(ctx, profile={**ctx.profile, "kind": "shared"})
        return ctx

    def issue(self, ctx, body):
        fence = self.store.get("Sessions", ("RESTORE_FENCE", "META"))
        if fence and fence.get("blocked"):
            raise Problem(503, "RESTORE_OFFLINE", "Restored namespace is offline.")
        if self.domain.settings.speech_mode == "disabled":
            raise Problem(503, "VOICE_DISABLED", "Voice is not configured.")
        for _ in range(6):
            ctx = self.domain.context(ctx.actor, ctx.h)
            if body["mode"] == "personal":
                self.domain.personal(ctx)
            now = self.domain.now()
            privacy_epoch, privacy_check = self._privacy(ctx)
            conversation = body.get("conversationId")
            prior = (
                self.store.get("Sessions", (f"CONVERSATION#{conversation}", "META"))
                if conversation
                else None
            )
            if conversation and (
                not prior
                or (prior["actor"], prior["h"], prior["mode"], prior["accessEpoch"])
                != (ctx.actor, ctx.h, body["mode"], ctx.member.get("accessEpoch", 1))
            ):
                raise missing()
            conversation = conversation or uid()
            counter = self.store.get("Sessions", (f"VOICECAP#{ctx.h}", "META"))
            live = [
                entry for entry in (counter or {}).get("entries", []) if entry["expiresAt"] > now
            ]
            if len(live) >= 4 or sum(entry["actor"] == ctx.actor for entry in live) >= 2:
                raise Problem(
                    429, "VOICE_CAPACITY", "Interactive voice capacity is occupied.", True
                )
            usage_key = (f"VOICEUSAGE#{ctx.h}#{now // 86400}", "META")
            usage = self.store.get("Sessions", usage_key)
            used = (usage or {}).get("secondsReserved", 0)
            if used + 600 > self.domain.settings.voice_daily_seconds:
                raise Problem(429, "VOICE_BUDGET", "Daily voice ceiling reached.")
            ticket, sid = secrets.token_urlsafe(32), str(uuid.uuid4())
            binding = dict(
                actor=ctx.actor,
                h=ctx.h,
                mode=body["mode"],
                locale=body["locale"],
                conversationId=conversation,
                runtimeSessionId=sid,
                accessEpoch=ctx.member.get("accessEpoch", 1),
                profileEpoch=ctx.profile.get("accessEpoch", 1),
                privacyEpoch=privacy_epoch,
            )
            writes = [
                put(
                    "Sessions",
                    row(
                        *self._key("TICKET", ticket), **binding, expiresAt=now + 30, consumed=False
                    ),
                ),
                put(
                    "Sessions",
                    row(
                        f"VOICE#{sid}",
                        **binding,
                        expiresAt=now + 30,
                        state="ADMITTED",
                        closed=False,
                    ),
                ),
                put(
                    "Sessions",
                    row(
                        f"VOICECAP#{ctx.h}",
                        rev=(counter or {}).get("rev", 0) + 1,
                        entries=live + [dict(id=sid, actor=ctx.actor, expiresAt=now + 30)],
                    ),
                    counter,
                ),
                put(
                    "Sessions",
                    row(
                        *usage_key,
                        rev=(usage or {}).get("rev", 0) + 1,
                        secondsReserved=used + 600,
                        expiresAt=(now // 86400 + 2) * 86400,
                    ),
                    usage,
                ),
            ]
            if prior:
                writes.append(guard("Sessions", prior))
            else:
                writes.append(
                    put(
                        "Sessions",
                        row(
                            f"CONVERSATION#{conversation}",
                            **{k: v for k, v in binding.items() if k != "runtimeSessionId"},
                            createdAt=now,
                        ),
                    )
                )
            try:
                self.store.transact(ctx.guards() + [privacy_check] + writes)
                return dict(
                    schemaVersion="1.0",
                    ticket=ticket,
                    runtimeSessionId=sid,
                    conversationId=conversation,
                    expiresAt=now + 30,
                    connectionUrl=self.connection_url(sid),
                    mode=body["mode"],
                    inputFormat="pcm16-16000-mono",
                    outputFormat="pcm16-16000-mono",
                    simulation=self.domain.settings.speech_mode == "simulated",
                )
            except Conflict:
                continue
        raise Problem(503, "CONTENTION", "Retry admission.", True)

    def connection_url(self, sid):
        settings = self.domain.settings
        if settings.env == "local":
            return settings.voice_url
        if not settings.voice_runtime_arn:
            raise Problem(503, "VOICE_UNCONFIGURED", "Voice runtime is unavailable.")
        from bedrock_agentcore.runtime import AgentCoreRuntimeClient

        return AgentCoreRuntimeClient(region=settings.region).generate_presigned_url(
            runtime_arn=settings.voice_runtime_arn, session_id=sid, expires=30
        )

    def consume(self, ticket, sid):
        for _ in range(6):
            item = self.store.get("Sessions", self._key("TICKET", ticket))
            session = self.store.get("Sessions", (f"VOICE#{sid}", "META"))
            if (
                not item
                or item["consumed"]
                or item["runtimeSessionId"] != sid
                or not session
                or session["state"] != "ADMITTED"
            ):
                raise denied()
            ctx = self._authority(item)
            privacy_epoch, privacy_check = self._privacy(ctx)
            if item.get("privacyEpoch", 0) != privacy_epoch:
                raise denied()
            now = self.domain.now()
            counter = self.store.get("Sessions", (f"VOICECAP#{ctx.h}", "META"))
            entries = [
                entry
                for entry in counter["entries"]
                if entry["expiresAt"] > now and entry["id"] != sid
            ]
            if len(entries) >= 4 or sum(e["actor"] == ctx.actor for e in entries) >= 2:
                raise denied()
            new = revised(session, state="ACTIVE", expiresAt=now + 600, lastActivityAt=now)
            try:
                self.store.transact(
                    ctx.guards()
                    + [privacy_check]
                    + [
                        put("Sessions", revised(item, consumed=True), item),
                        put("Sessions", new, session),
                        put(
                            "Sessions",
                            revised(
                                counter,
                                entries=entries
                                + [dict(id=sid, actor=ctx.actor, expiresAt=now + 600)],
                            ),
                            counter,
                        ),
                    ]
                )
                return new
            except Conflict:
                continue
        raise Problem(503, "CONTENTION", "Retry connection.", True)

    def check(self, sid, *, activity=False):
        for _ in range(6):
            item = self.store.get("Sessions", (f"VOICE#{sid}", "META"))
            now = self.domain.now()
            if not item or item["state"] != "ACTIVE" or item["lastActivityAt"] + 60 <= now:
                raise denied()
            ctx = self._authority(item)
            privacy_epoch, privacy_check = self._privacy(ctx)
            if item.get("privacyEpoch", 0) != privacy_epoch:
                raise denied()
            # PCM frames need fresh authority, but at most one activity write per second.
            if not activity or item["lastActivityAt"] == now:
                return ctx, item
            new = revised(item, lastActivityAt=now)
            try:
                self.store.transact(ctx.guards() + [privacy_check, put("Sessions", new, item)])
                return ctx, new
            except Conflict:
                continue
        raise Problem(503, "CONTENTION", "Retry session activity.", True)

    def close(self, sid):
        for _ in range(6):
            session = self.store.get("Sessions", (f"VOICE#{sid}", "META"))
            if not session or session.get("closed"):
                return
            counter = self.store.get("Sessions", (f"VOICECAP#{session['h']}", "META"))
            changes = [put("Sessions", revised(session, closed=True, state="CLOSED"), session)]
            if counter:
                changes.append(
                    put(
                        "Sessions",
                        revised(counter, entries=[e for e in counter["entries"] if e["id"] != sid]),
                        counter,
                    )
                )
            try:
                self.store.transact(changes)
                return
            except Conflict:
                continue
        raise Problem(503, "CONTENTION", "Session close pending.", True)

    def grant(self, ctx, *, mode="personal", session_id=None, tools=None):
        if mode == "personal":
            self.domain.personal(ctx)
        allowed = PERSONAL_TOOLS if mode == "personal" else READ_TOOLS
        selected = allowed if tools is None else set(tools) & allowed
        privacy_epoch, privacy_check = self._privacy(ctx)
        secret = secrets.token_urlsafe(32)
        item = row(
            *self._key("CHANNELGRANT", secret),
            actor=ctx.actor,
            h=ctx.h,
            mode=mode,
            accessEpoch=ctx.member.get("accessEpoch", 1),
            profileEpoch=ctx.profile.get("accessEpoch", 1),
            privacyEpoch=privacy_epoch,
            expiresAt=self.domain.now() + 30,
            tools=sorted(selected),
            sessionId=session_id,
            closed=False,
        )
        checks = ctx.guards() + [privacy_check]
        if session_id:
            voice_ctx, session = self.check(session_id)
            if (voice_ctx.actor, voice_ctx.h, session["mode"]) != (ctx.actor, ctx.h, mode):
                raise denied()
            checks.append(guard("Sessions", session))
        self.store.transact(checks + [put("Sessions", item)])
        return secret

    def resolve(self, secret, tool=None):
        item = self.store.get("Sessions", self._key("CHANNELGRANT", secret))
        if not item or tool is not None and tool not in item["tools"]:
            raise denied()
        ctx = self._authority(item)
        privacy_epoch, privacy_check = self._privacy(ctx)
        if item.get("privacyEpoch", 0) != privacy_epoch:
            raise denied()
        checks = [guard("Sessions", item), privacy_check]
        if item["sessionId"]:
            _, session = self.check(item["sessionId"])
            checks.append(guard("Sessions", session))
        return ctx, checks
