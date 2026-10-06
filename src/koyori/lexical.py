"""Derived lexical postings, resumable projection and opaque chronological search.

Postings contain references only. Canonical revisions, privacy and source authority
are checked again before disclosure. Projection never invokes an embedding model.
"""

import hashlib
import json
import re
import unicodedata

from koyori.domain import hkey, row
from koyori.errors import Conflict, Problem
from koyori.security import digest
from koyori.stage2 import Service
from koyori.store import guard, put, remove, revised

STOPWORDS = frozenset(
    "a au aux avec ce ces cette dans de des du en est et il je la le les leur ma mais me mes "
    "mon ne nos nous on ou par pas pour que qui sa se ses son sur ta te tes toi ton tu un "
    "une vos vous the a an and are as at be by for from i in is it my of on or that this "
    "to was we were what with you your".split()
)


def words(text):
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    return set(re.findall(r"[^\W_]{2,}", normalized, re.UNICODE)) - STOPWORDS


def query_terms(text):
    terms = sorted(words(text), key=lambda t: (-len(t), t))
    if not 1 <= len(terms) <= 8:
        raise ValueError("Search requires one to eight significant terms")
    return terms


def scope(h, owner, visibility):
    return f"{h}#shared" if visibility == "household" else f"{h}#private#{owner}"


def posting_pk(scope_key, term_hash):
    return f"LEX#{scope_key}#{term_hash}"


class Lexical(Service):
    def state_key(self, h):
        return hkey(h), "LEXSTATE"

    def enqueue(self, item):
        key = (f"LEXRUN#{item['id']}", "META")
        old = self.store.get("Delivery", key)
        state = self.store.get("Domain", self.state_key(item["PK"][2:]))
        due = self.domain.now()
        intent = row(
            *key,
            rev=(old or {}).get("rev", 0) + 1,
            h=item["PK"][2:],
            memoryId=item["id"],
            memoryRev=item["rev"],
            status="PENDING",
            phase="PURGE",
            position=0,
            dueAt=due,
            GSI1PK=f"LEXRUN#{int(item['id'][:8], 16) % self.domain.settings.shards}",
            GSI1SK=f"{due:020d}#{item['id']}",
        )
        values = dict(
            pending=(state or {}).get("pending", 0) + int(not old or old["status"] != "PENDING"),
            backfilled=state["backfilled"]
            if state
            else not self.store.query("Domain", hkey(intent["h"]), prefix="MEMORY#", limit=1)[0],
        )
        updated = revised(state, **values) if state else row(*self.state_key(intent["h"]), **values)
        return [put("Delivery", intent, old), put("Domain", updated, state)]

    def project(self, candidate):
        intent = self.store.get("Delivery", (candidate["PK"], "META"))
        if not intent or intent["status"] != "PENDING":
            return
        item = self.store.get("Domain", (hkey(intent["h"]), f"MEMORY#{intent['memoryId']}"))
        if not item:
            raise Problem(503, "LEXICAL_SOURCE_MISSING", "Projection source is unavailable.", True)
        if item["rev"] != intent["memoryRev"]:
            self.store.transact([guard("Domain", item), *self.enqueue(item)])
            return
        from koyori.store import Change

        fence_key = (hkey(intent["h"]), f"PRIVACY#{item['owner']}")
        fence = self.store.get("Domain", fence_key)
        checks = [guard("Domain", item), guard("Delivery", intent)]
        checks.append(guard("Domain", fence) if fence else Change("Domain", fence_key, None))
        manifest_pk = f"LEXDOC#{intent['h']}#{item['id']}"
        if intent["phase"] == "PURGE":
            page, _ = self.store.query("Domain", manifest_pk, limit=32)
            for entry in page:
                posting = self.store.get("Domain", (entry["postingPK"], entry["postingSK"]))
                if posting:
                    checks.append(remove("Domain", posting))
                checks.append(remove("Domain", entry))
            checks.append(
                put("Delivery", revised(intent, phase="PURGE" if page else "BUILD"), intent)
            )
        else:
            erased = item["deleted"] or bool(fence and fence["status"] == "ERASING")
            erased |= bool(item.get("validUntil") and item["validUntil"] <= self.domain.now())
            hashes = (
                []
                if erased
                else sorted(hashlib.sha256(w.encode()).hexdigest() for w in words(item["text"]))
            )
            position = intent["position"]
            batch = hashes[position : position + 32]
            scoped = scope(intent["h"], item["owner"], item["visibility"])
            sk = f"{item['occurredAt']:020d}#{item['id']}"
            for term in batch:
                pk = posting_pk(scoped, term)
                checks.extend(
                    [
                        put(
                            "Domain",
                            row(
                                pk,
                                sk,
                                memoryId=item["id"],
                                memoryRev=item["rev"],
                                privacyEpoch=item["privacyEpoch"],
                                scope=scoped,
                            ),
                        ),
                        put("Domain", row(manifest_pk, term, postingPK=pk, postingSK=sk)),
                    ]
                )
            if position + len(batch) < len(hashes):
                checks.append(
                    put("Delivery", revised(intent, position=position + len(batch)), intent)
                )
            else:
                state = self.store.get("Domain", self.state_key(intent["h"]))
                checks.extend(
                    [
                        put("Delivery", self.domain.done_intent(intent), intent),
                        put("Domain", revised(state, pending=state["pending"] - 1), state),
                    ]
                )
        self.store.transact(checks)

    def sweep(self):
        attempted = 0
        for intent in self.pending("LEXRUN"):
            try:
                self.project(intent)
                attempted += 1
            except Conflict:
                continue
        return attempted

    def repair_expired(self, ctx, mid):
        item = self.store.get("Domain", (hkey(ctx.h), f"MEMORY#{mid}"))
        if (
            not item
            or item["deleted"]
            or not item.get("validUntil")
            or item["validUntil"] > self.domain.now()
        ):
            return
        old = self.store.get("Delivery", (f"LEXRUN#{mid}", "META"))
        if old and old["status"] == "PENDING":
            return
        try:
            self.store.transact(ctx.guards() + [guard("Domain", item), *self.enqueue(item)])
        except Conflict:
            pass  # Renewal or another cleanup already owns the canonical revision.

    def backfill(self, h, *, drain=False):
        """Operator-driven, paginated and idempotent; never schedules model learning."""
        state = self.store.get("Domain", self.state_key(h))
        after = (state or {}).get("backfillAfter")
        page, last = self.store.query("Domain", hkey(h), prefix="MEMORY#", after=after, limit=20)
        for item in page:
            old = self.store.get("Delivery", (f"LEXRUN#{item['id']}", "META"))
            if not old or old["memoryRev"] != item["rev"]:
                self.store.transact([guard("Domain", item), *self.enqueue(item)])
            if drain:
                # Offline rebuild reads each intent consistently, without relying on GSI lag.
                while True:
                    current = self.store.get("Delivery", (f"LEXRUN#{item['id']}", "META"))
                    if current["status"] != "PENDING":
                        break
                    self.project(current)
        state = self.store.get("Domain", self.state_key(h))
        values = dict(backfillAfter=last, backfilled=last is None)
        updated = (
            revised(state, **values) if state else row(*self.state_key(h), pending=0, **values)
        )
        self.store.transact([put("Domain", updated, state)])
        return {"count": len(page), "more": last is not None}

    def search(self, ctx, body):
        from koyori.memory import Memory

        memory = Memory(self.domain)
        terms = query_terms(body["query"])
        fingerprint = digest({k: v for k, v in body.items() if k != "cursor"})
        route = "memory-search:" + fingerprint
        saved = self.domain.cursors.decode(body.get("cursor"), ctx.actor, ctx.h, route)
        scopes = [scope(ctx.h, ctx.actor, "household")]
        if ctx.profile["kind"] == "personal":
            scopes.insert(0, scope(ctx.h, ctx.actor, "private"))
        term_hash = hashlib.sha256(terms[0].encode()).hexdigest()
        positions = (saved or {}).get("positions", [None] * len(scopes))
        if len(positions) != len(scopes):
            raise Problem(400, "INVALID_CURSOR", "Search authority changed.")
        buffers, more = [[] for _ in scopes], [True] * len(scopes)
        scanned, selected, checks, used, skipped = 0, [], [], 0, False
        start, end, zone = memory.day_range(ctx, body.get("day"))
        while scanned < 500 and len(selected) < body["limit"]:
            for i, scoped in enumerate(scopes):
                if not buffers[i] and more[i]:
                    page, last = self.store.query(
                        "Domain",
                        posting_pk(scoped, term_hash),
                        after=positions[i],
                        limit=50,
                        descending=True,
                    )
                    buffers[i], more[i] = page, last is not None
            heads = [(b[0]["SK"], i) for i, b in enumerate(buffers) if b]
            if not heads:
                break
            _, index = max(heads)
            posting = buffers[index][0]
            item = None
            try:
                item = memory.get(ctx, posting["memoryId"])
            except Problem as exc:
                if exc.status != 404:
                    raise
                self.repair_expired(ctx, posting["memoryId"])
            eligible = bool(
                item
                and not item["deleted"]
                and item["rev"] == posting["memoryRev"]
                and item["privacyEpoch"] == posting["privacyEpoch"]
                and scope(ctx.h, item["owner"], item["visibility"]) == scopes[index]
                and set(terms) <= words(item["text"])
                and (not body.get("kinds") or item["kind"] in body["kinds"])
                and (not body.get("key") or item.get("key") == body["key"])
                and (start is None or start <= item["occurredAt"] < end)
            )
            if eligible:
                value, authority = memory.context_value(ctx, item)
                size = len(json.dumps(value, ensure_ascii=False))
                if used + size > body["maxCharacters"] and size <= body["maxCharacters"]:
                    break  # This candidate belongs to the next page, not to this cursor.
                if size <= body["maxCharacters"]:
                    selected.append(value)
                    checks.extend(authority)
                    used += size
                else:
                    skipped = True
            positions[index] = {k: posting[k] for k in ("PK", "SK")}
            buffers[index].pop(0)
            scanned += 1
        continuation = any(buffers) or any(more)
        self.store.transact(ctx.guards() + memory.disclosure_fence() + checks)
        state = self.store.get("Domain", self.state_key(ctx.h))
        incomplete = (
            not state.get("backfilled") or state.get("pending", 0) > 0
            if state
            else bool(self.store.query("Domain", hkey(ctx.h), prefix="MEMORY#", limit=1)[0])
        )
        return dict(
            items=selected,
            nextCursor=self.domain.cursors.encode(ctx.actor, ctx.h, route, {"positions": positions})
            if continuation
            else None,
            truncated=continuation or skipped or bool(incomplete),
            indexIncomplete=bool(incomplete),
            characters=used,
            timeZone=str(zone),
            range={"start": start, "end": end},
        )
