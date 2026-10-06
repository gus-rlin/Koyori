"""Google Calendar read-only OAuth, encrypted credentials and fenced incremental sync.

Push messages are authenticated hints. Event state comes exclusively from a fresh
Calendar API sync, so notification order/content never becomes provider evidence.
"""

import base64
import hashlib
import json
import logging
import os
import secrets
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote, urlencode

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from koyori.actions import Actions
from koyori.domain import active, hkey, projection, row, uid
from koyori.errors import Conflict, Problem, missing
from koyori.security import digest
from koyori.stage2 import Service
from koyori.store import Change, guard, put, revised

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
]
WATCH_TTL = 7200


def watch_deadlines(watch, expires_at):
    expires_at = min(watch["expiresAt"], expires_at)
    admitted_at = watch.get("admittedAt", watch["expiresAt"] - WATCH_TTL)
    lead = min(3600, max(0, (expires_at - admitted_at) // 2))
    return {"admittedAt": admitted_at, "expiresAt": expires_at, "renewAfter": expires_at - lead}


class Envelope:
    def __init__(self, settings):
        self.settings = settings

    def context(self, owner, cid):
        return {"env": self.settings.env, "owner": owner, "connection": cid}

    def local_key(self):
        path = Path(self.settings.token_key_file)
        if not path.exists():
            raise Problem(
                503, "TOKEN_KEY_UNAVAILABLE", "Configure the local provider encryption key."
            )
        key = path.read_bytes()
        if len(key) != 32:
            raise ValueError("Invalid provider envelope key")
        return key

    def seal(self, value, owner, cid):
        context = self.context(owner, cid)
        wrapped = None
        if self.settings.env == "local":
            key = self.local_key()
        else:
            if not self.settings.token_key_arn:
                raise Problem(503, "TOKEN_KEY_UNAVAILABLE", "Configure the provider KMS key.")
            result = self.settings.client("kms").generate_data_key(
                KeyId=self.settings.token_key_arn, KeySpec="AES_256", EncryptionContext=context
            )
            key, wrapped = result["Plaintext"], base64.b64encode(result["CiphertextBlob"]).decode()
        nonce = os.urandom(12)
        ciphertext = AESGCM(key).encrypt(
            nonce, json.dumps(value).encode(), json.dumps(context, sort_keys=True).encode()
        )
        return {
            "algorithm": "AES256-GCM-v1",
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "wrappedKey": wrapped,
        }

    def open(self, envelope, owner, cid):
        context = self.context(owner, cid)
        if envelope["algorithm"] != "AES256-GCM-v1":
            raise ValueError("Unknown provider envelope")
        if self.settings.env == "local":
            key = self.local_key()
        else:
            key = self.settings.client("kms").decrypt(
                KeyId=self.settings.token_key_arn,
                CiphertextBlob=base64.b64decode(envelope["wrappedKey"]),
                EncryptionContext=context,
            )["Plaintext"]
        return json.loads(
            AESGCM(key).decrypt(
                base64.b64decode(envelope["nonce"]),
                base64.b64decode(envelope["ciphertext"]),
                json.dumps(context, sort_keys=True).encode(),
            )
        )


class Google:
    def __init__(self, settings, transport=None):
        self.settings = settings
        # HTTPX INFO and httpcore DEBUG include private URLs/cursors and headers.
        for name in ("httpx", "httpcore"):
            logging.getLogger(name).setLevel(logging.WARNING)
        self.client = httpx.Client(timeout=10, follow_redirects=False, transport=transport)

    def config(self):
        if not self.settings.google_client_id or not self.settings.google_redirect_uri:
            raise Problem(
                503, "CALENDAR_UNAVAILABLE", "Configure Google OAuth before connecting a calendar."
            )
        if self.settings.env == "local":
            if not self.settings.google_config_file:
                raise Problem(
                    503, "CALENDAR_UNAVAILABLE", "Configure the local Google client secret file."
                )
            secret = json.loads(Path(self.settings.google_config_file).read_text(encoding="utf-8"))[
                "client_secret"
            ]
        else:
            if not self.settings.google_client_secret_arn:
                raise Problem(503, "CALENDAR_UNAVAILABLE", "Configure the Google client secret.")
            secret = self.settings.client("secretsmanager").get_secret_value(
                SecretId=self.settings.google_client_secret_arn
            )["SecretString"]
        return {
            "client_id": self.settings.google_client_id,
            "client_secret": secret,
            "redirect_uri": self.settings.google_redirect_uri,
        }

    def request(self, method, url, **kwargs):
        try:
            with self.client.stream(method, url, **kwargs) as response:
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > 1_000_000:
                        raise Problem(
                            502, "PROVIDER_RESPONSE_LIMIT", "Google response exceeds the bound."
                        )
                    chunks.append(chunk)
                raw = b"".join(chunks)
                try:
                    body = json.loads(raw) if raw else {}
                except (ValueError, UnicodeDecodeError):
                    body = None
                oauth = url == "https://oauth2.googleapis.com/token"
                if (
                    response.status_code == 400
                    and url == "https://oauth2.googleapis.com/revoke"
                    and isinstance(body, dict)
                    and body.get("error") == "invalid_token"
                ):
                    return {"alreadyRevoked": True}
                if oauth and response.status_code in {400, 401} and isinstance(body, dict):
                    if body.get("error") == "invalid_grant":
                        raise Problem(409, "OAUTH_REJECTED", "Google rejected the OAuth grant.")
                    if body.get("error") == "invalid_client":
                        raise Problem(
                            503,
                            "OAUTH_CLIENT_INVALID",
                            "Google OAuth client configuration is unavailable.",
                        )
                if not oauth and response.status_code in {401, 403}:
                    raise Problem(409, "PROVIDER_ACCESS_REVOKED", "Google access is unavailable.")
                if response.status_code == 410:
                    raise Problem(
                        409, "SYNC_TOKEN_EXPIRED", "Restart a full calendar synchronization."
                    )
                if response.status_code >= 300:
                    raise Problem(503, "PROVIDER_UNAVAILABLE", "Google request failed.", True)
                if not isinstance(body, dict):
                    raise Problem(502, "PROVIDER_RESPONSE_INVALID", "Google response is invalid.")
                return body
        except httpx.HTTPError:
            raise Problem(503, "PROVIDER_UNAVAILABLE", "Google request failed.", True) from None

    def exchange(self, code, verifier):
        return self.request(
            "POST",
            "https://oauth2.googleapis.com/token",
            data={
                **self.config(),
                "code": code,
                "code_verifier": verifier,
                "grant_type": "authorization_code",
            },
        )

    def refresh(self, token):
        config = self.config()
        return self.request(
            "POST",
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "refresh_token": token,
                "grant_type": "refresh_token",
            },
        )

    def calendars(self, token):
        result, page = [], None
        for _ in range(10):
            data = self.request(
                "GET",
                "https://www.googleapis.com/calendar/v3/users/me/calendarList",
                headers={"Authorization": f"Bearer {token}"},
                params={"maxResults": 100, **({"pageToken": page} if page else {})},
            )
            result.extend(data.get("items", []))
            page = data.get("nextPageToken")
            if not page:
                return result
        raise Problem(502, "CALENDAR_LIMIT", "Calendar inventory exceeds the supported bound.")

    def events(self, token, calendar, *, sync=None, page=None):
        params = {"maxResults": 50, "showDeleted": "true"}
        if sync:
            params["syncToken"] = sync
        if page:
            params["pageToken"] = page
        return self.request(
            "GET",
            f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar, safe='')}/events",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )

    def watch(self, token, calendar, channel, secret, *, expires_at):
        return self.request(
            "POST",
            f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar, safe='')}/events/watch",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "id": channel,
                "type": "web_hook",
                "address": self.settings.google_webhook_url,
                "token": secret,
                "expiration": str(expires_at * 1000),
                "params": {"ttl": str(WATCH_TTL)},
            },
        )

    def revoke(self, token):
        return self.request("POST", "https://oauth2.googleapis.com/revoke", data={"token": token})


class Calendar(Service):
    def __init__(self, domain, google=None, envelope=None):
        super().__init__(domain)
        self.google = google or Google(domain.settings)
        self.envelope = envelope or Envelope(domain.settings)

    def get(self, ctx, cid, *, inactive=False):
        connection = Actions(self.domain).get(ctx, "CONNECTION", cid, inactive=inactive)
        if connection["provider"] != "google-calendar":
            raise missing()
        return connection

    @staticmethod
    def token_key(connection):
        return (
            f"H#{connection['PK'][2:]}#OWNER#{connection['owner']}",
            f"TOKEN#{connection['id']}",
        )

    def authorize(self, ctx, body):
        self.google.config()
        cid, state, verifier = uid(), secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        params = {
            "client_id": self.domain.settings.google_client_id,
            "redirect_uri": self.domain.settings.google_redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "code_challenge": base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("="),
            "code_challenge_method": "S256",
        }
        item = row(
            f"OAUTH#{digest({'state': state})}",
            h=ctx.h,
            owner=ctx.actor,
            connectionId=cid,
            memberEpoch=ctx.member.get("accessEpoch", 1),
            calendarIds=body["calendarIds"],
            expiresAt=self.domain.now() + 600,
            status="PENDING",
            verifier=self.envelope.seal({"verifier": verifier}, ctx.actor, cid),
        )
        # The callback state is a one-use secret; only its digest is persisted.
        return (
            {
                "id": cid,
                "authorizationUrl": "https://accounts.google.com/o/oauth2/v2/auth?"
                + urlencode(params),
            },
            [put("Connections", item)],
            True,
        )

    def callback(self, state, code):
        item = self.store.get("Connections", (f"OAUTH#{digest({'state': state})}", "META"))
        if not item or item["status"] != "PENDING" or item["expiresAt"] <= self.domain.now():
            raise Problem(409, "OAUTH_STATE_INVALID", "OAuth state is expired or already consumed.")
        ctx = self.domain.context(item["owner"], item["h"])
        self.domain.personal(ctx)
        if ctx.member.get("accessEpoch", 1) != item["memberEpoch"]:
            raise Problem(403, "OAUTH_AUTHORITY_CHANGED", "Restart authorization.")
        processing = revised(item, status="PROCESSING")
        self.store.transact(ctx.guards() + [put("Connections", processing, item)])
        credentials = self.google.exchange(
            code,
            self.envelope.open(item["verifier"], item["owner"], item["connectionId"])["verifier"],
        )
        scopes = set(credentials.get("scope", "").split())
        if not set(SCOPES) <= scopes or not credentials.get("refresh_token"):
            raise Problem(
                403,
                "OAUTH_SCOPE_MISSING",
                "Google did not grant the requested offline read access.",
            )
        available = {
            c["id"]
            for c in self.google.calendars(credentials["access_token"])
            if c.get("accessRole") in {"reader", "writer", "owner"} and not c.get("deleted")
        }
        if not set(item["calendarIds"]) <= available:
            raise Problem(403, "CALENDAR_NOT_AUTHORIZED", "A selected calendar is unavailable.")
        ctx = self.domain.context(item["owner"], item["h"])
        if ctx.member.get("accessEpoch", 1) != item["memberEpoch"]:
            raise Problem(403, "OAUTH_AUTHORITY_CHANGED", "Restart authorization.")
        cid = item["connectionId"]
        connection = row(
            hkey(ctx.h),
            f"CONNECTION#{cid}",
            id=cid,
            owner=ctx.actor,
            provider="google-calendar",
            mode="real",
            active=True,
            epoch=1,
            memberEpoch=ctx.member.get("accessEpoch", 1),
            capabilities=["calendar.read"],
            calendarIds=item["calendarIds"],
            createdAt=self.domain.now(),
            revokePending=False,
        )
        credentials["expiresAt"] = self.domain.now() + int(credentials["expires_in"])
        secret_row = row(
            *self.token_key(connection),
            envelope=self.envelope.seal(credentials, ctx.actor, cid),
            leaseUntil=0,
        )
        completed = revised(processing, status="DONE", verifier=None)
        self.store.transact(
            ctx.guards()
            + [
                put("Domain", connection),
                put("Connections", secret_row),
                put("Connections", completed, processing),
                put("Delivery", self.intent(connection)),
                self.domain.event(ctx, cid, 1, kind="connection", mode="real"),
            ]
        )
        return {"id": cid, "rev": 1, "mode": "real", "provider": "google-calendar"}

    def intent(self, connection, old=None, due=None):
        due = self.domain.now() if due is None else due
        return row(
            f"CALRUN#{connection['id']}",
            rev=old["rev"] + 1 if old else 1,
            h=connection["PK"][2:],
            owner=connection["owner"],
            connectionId=connection["id"],
            dueAt=due,
            status="PENDING",
            GSI1PK=f"CALRUN#{int(connection['id'][:8], 16) % self.domain.settings.shards}",
            GSI1SK=f"{due:020d}#{connection['id']}",
        )

    def access_token(self, ctx, connection):
        self.get(ctx, connection["id"])
        if connection["memberEpoch"] != ctx.member.get("accessEpoch", 1):
            raise Problem(403, "CONNECTION_AUTHORITY_CHANGED", "Reconnect the account.")
        secret_row = self.store.get("Connections", self.token_key(connection))
        credentials = self.envelope.open(secret_row["envelope"], ctx.actor, connection["id"])
        if credentials["expiresAt"] > self.domain.now() + 30:
            return credentials["access_token"]
        if secret_row["leaseUntil"] > self.domain.now():
            raise Problem(503, "REFRESH_IN_PROGRESS", "OAuth refresh is already running.", True)
        leased = revised(secret_row, leaseUntil=self.domain.now() + 30)
        self.store.transact(
            ctx.guards() + [guard("Domain", connection), put("Connections", leased, secret_row)]
        )
        try:
            refreshed = self.google.refresh(credentials["refresh_token"])
        except Problem as exc:
            if exc.code in {"OAUTH_REJECTED", "PROVIDER_ACCESS_REVOKED"}:
                self.store.transact(
                    [
                        put(
                            "Domain",
                            revised(connection, active=False, epoch=connection["epoch"] + 1),
                            connection,
                        ),
                        put("Connections", revised(leased, leaseUntil=0), leased),
                    ]
                )
            raise
        refreshed = {
            **credentials,
            **refreshed,
            "expiresAt": self.domain.now() + int(refreshed["expires_in"]),
        }
        self.store.transact(
            ctx.guards()
            + [
                guard("Domain", connection),
                put(
                    "Connections",
                    revised(
                        leased,
                        envelope=self.envelope.seal(refreshed, ctx.actor, connection["id"]),
                        leaseUntil=0,
                    ),
                    leased,
                ),
            ]
        )
        return refreshed["access_token"]

    def sync(self, ctx, cid):
        connection = self.get(ctx, cid)
        token = self.access_token(ctx, connection)
        allowed = {
            c["id"]
            for c in self.google.calendars(token)
            if c.get("accessRole") in {"reader", "writer", "owner"} and not c.get("deleted")
        }
        for calendar_id in connection["calendarIds"]:
            if calendar_id not in allowed:
                self.store.transact(
                    ctx.guards()
                    + [
                        put(
                            "Domain",
                            revised(connection, active=False, epoch=connection["epoch"] + 1),
                            connection,
                        )
                    ]
                )
                raise Problem(
                    409, "CALENDAR_ACCESS_REVOKED", "A selected calendar is no longer authorized."
                )
            self._sync_calendar(ctx, connection, token, calendar_id)
        return projection(self.get(ctx, cid))

    def _sync_calendar(self, ctx, connection, token, calendar_id):
        key = (connection["PK"], f"CALSYNC#{connection['id']}#{digest({'calendar': calendar_id})}")
        old = self.store.get("Domain", key)
        if old and old.get("leaseUntil", 0) > self.domain.now():
            return
        sync = old.get("syncToken") if old else None
        generation = old.get("generation", 0) if old else 0
        page = old.get("pageToken") if old else None
        full = not sync
        if full and not page:
            generation += 1
        state = row(
            *key,
            rev=old["rev"] + 1 if old else 1,
            owner=ctx.actor,
            connectionId=connection["id"],
            calendarId=calendar_id,
            syncToken=sync,
            pageToken=page,
            generation=generation,
            leaseUntil=self.domain.now() + 30,
            complete=False,
        )
        self.store.transact(ctx.guards() + [guard("Domain", connection), put("Domain", state, old)])
        try:
            data = self.google.events(token, calendar_id, sync=sync, page=page)
        except Problem as exc:
            if exc.code == "SYNC_TOKEN_EXPIRED":
                self.store.transact(
                    [
                        guard("Domain", connection),
                        put(
                            "Domain",
                            revised(
                                state, syncToken=None, pageToken=None, leaseUntil=0, complete=False
                            ),
                            state,
                        ),
                    ]
                )
                return
            raise
        if len(data.get("items", [])) > 50:
            raise Problem(502, "PROVIDER_RESPONSE_LIMIT", "Calendar page exceeds the contract.")
        next_page = data.get("nextPageToken")
        next_sync = data.get("nextSyncToken")
        if not next_page and not next_sync:
            raise Problem(502, "INVALID_SYNC_RESPONSE", "Google omitted the sync cursor.")
        writes = [guard("Domain", connection)]
        content_changed = False
        for event in data.get("items", []):
            event_key = (
                connection["PK"],
                f"CALEVENT#{connection['id']}#{digest({'calendar': calendar_id, 'event': event['id']})}",
            )
            previous = self.store.get("Domain", event_key)
            # Google notifications are unordered; the fenced sync cursor supplies ordering.
            item = row(
                *event_key,
                rev=previous["rev"] + 1 if previous else 1,
                owner=ctx.actor,
                connectionId=connection["id"],
                calendarId=calendar_id,
                id=event["id"],
                etag=event.get("etag"),
                generation=generation,
                deleted=event.get("status") == "cancelled",
                summary=str(event.get("summary", ""))[:1000],
                start=event.get("start"),
                end=event.get("end"),
                updated=event.get("updated"),
                mode="real",
            )
            content_changed = (
                content_changed
                or not previous
                or any(
                    previous.get(field) != item.get(field)
                    for field in ("summary", "start", "end", "deleted", "generation")
                )
            )
            writes.append(put("Domain", item, previous))
        updated = revised(
            state,
            pageToken=next_page,
            syncToken=sync if next_page else next_sync,
            complete=not bool(next_page),
            leaseUntil=0,
            lastSyncedAt=self.domain.now(),
            completedGeneration=generation
            if not next_page
            else (old or {}).get("completedGeneration", 0),
        )
        writes.append(put("Domain", updated, state))
        version_key = (connection["PK"], f"CALVERSION#{connection['id']}")
        previous_version = self.store.get("Domain", version_key)
        content_changed = (
            content_changed
            or not next_page
            and updated["completedGeneration"] != (old or {}).get("completedGeneration", 0)
        )
        if content_changed or not previous_version:
            content_version = revised(previous_version) if previous_version else row(*version_key)
            writes.append(put("Domain", content_version, previous_version))
            writes.append(
                self.domain.event(
                    ctx, connection["id"], content_version["rev"], kind="calendar", mode="real"
                )
            )
        else:
            writes.append(guard("Domain", previous_version))
        self.store.transact(ctx.guards() + writes)

    def events(self, ctx, cid, cursor=None):
        connection = self.get(ctx, cid)
        if ctx.member.get("accessEpoch", 1) != connection["memberEpoch"]:
            raise missing()
        token = self.access_token(ctx, connection)
        allowed = {
            c["id"]
            for c in self.google.calendars(token)
            if c.get("accessRole") in {"reader", "writer", "owner"} and not c.get("deleted")
        }
        if not set(connection["calendarIds"]) <= allowed:
            self.store.transact(
                ctx.guards()
                + [
                    put(
                        "Domain",
                        revised(connection, active=False, epoch=connection["epoch"] + 1),
                        connection,
                    )
                ]
            )
            raise Problem(
                409, "CALENDAR_ACCESS_REVOKED", "A selected calendar is no longer authorized."
            )
        after = self.domain.cursors.decode(cursor, ctx.actor, ctx.h, f"calendar/{cid}")
        rows, last = self.store.query(
            "Domain", hkey(ctx.h), prefix=f"CALEVENT#{cid}#", after=after, limit=50
        )
        items = []
        for event in rows:
            state = self.store.get(
                "Domain",
                (hkey(ctx.h), f"CALSYNC#{cid}#{digest({'calendar': event['calendarId']})}"),
            )
            if (
                state
                and state["complete"]
                and event["generation"] == state["completedGeneration"]
                and not event["deleted"]
                and event["calendarId"] in connection["calendarIds"]
            ):
                items.append(projection(event))
        return {
            "items": items,
            "nextCursor": self.domain.cursors.encode(ctx.actor, ctx.h, f"calendar/{cid}", last)
            if last
            else None,
            "mode": "real",
            "source": "google-calendar",
            "freshness": "last successful sync; synchronize to revalidate provider access",
        }

    def revoke(self, ctx, cid, version):
        connection = self.get(ctx, cid, inactive=True)
        self.domain.require_version(connection, version)
        secret_row = self.store.get("Connections", self.token_key(connection))
        if connection.get("revokePending") or (
            not connection["active"] and secret_row["envelope"] is None
        ):
            return (
                {"id": cid, "rev": connection["rev"]},
                [guard("Domain", connection), guard("Connections", secret_row)],
                False,
            )
        new = revised(connection, active=False, epoch=connection["epoch"] + 1, revokePending=True)
        intent = self.store.get("Delivery", (f"CALRUN#{cid}", "META"))
        return (
            {"id": cid, "rev": new["rev"]},
            [
                put("Domain", new, connection),
                put("Delivery", self.intent(new, intent), intent),
                self.domain.event(ctx, cid, new["rev"], kind="connection", mode="real"),
            ],
            False,
        )

    def register_watch(self, ctx, cid):
        connection = self.get(ctx, cid)
        if not self.domain.settings.google_webhook_url:
            return 0
        token = self.access_token(ctx, connection)
        count = 0
        for calendar_id in connection["calendarIds"]:
            key = (f"WATCH#{cid}", digest({"calendar": calendar_id}))
            old = self.store.get("Connections", key)
            if old:
                deadline = (
                    old["expiresAt"]
                    if old.get("status") == "PENDING"
                    else old.get("renewAfter", old["expiresAt"] - 3600)
                )
                if deadline > self.domain.now():
                    continue
            channel, secret = uid(), secrets.token_urlsafe(32)
            # Persist the admission before the non-idempotent provider effect. If its
            # response is lost, an authenticated hint can recover it; otherwise wait for expiry.
            admitted_at = self.domain.now()
            item = row(
                *key,
                rev=old["rev"] + 1 if old else 1,
                channelId=channel,
                tokenHash=digest({"token": secret}),
                resourceId=None,
                admittedAt=admitted_at,
                expiresAt=admitted_at + WATCH_TTL,
                renewAfter=admitted_at + WATCH_TTL // 2,
                status="PENDING",
                connectionId=cid,
                h=ctx.h,
                owner=ctx.actor,
                lastMessage=0,
            )
            channel_key = (f"CHANNEL#{channel}", "META")
            self.store.transact(
                ctx.guards()
                + [
                    guard("Domain", connection),
                    put("Connections", item, old),
                    put("Connections", row(*channel_key, watchPK=key[0], watchSK=key[1])),
                ]
            )
            result = self.google.watch(
                token, calendar_id, channel, secret, expires_at=item["expiresAt"]
            )
            for _ in range(6):
                latest = self.store.get("Connections", key)
                if latest["channelId"] != channel:
                    break  # The admitted channel already expired and was replaced.
                if latest["resourceId"] and latest["resourceId"] != result["resourceId"]:
                    raise Problem(502, "INVALID_WATCH_RESPONSE", "Google channel identity changed.")
                completed = revised(
                    latest,
                    status="ACTIVE",
                    resourceId=result["resourceId"],
                    **watch_deadlines(latest, int(result["expiration"]) // 1000),
                )
                try:
                    # Only admission metadata is finalized, including after revocation;
                    # it cannot reactivate the connection or overwrite a newer hint.
                    self.store.transact([put("Connections", completed, latest)])
                    break
                except Conflict:
                    continue
            else:
                raise Conflict("Concurrent channel admission finalization")
            count += 1
        return count

    def webhook(self, headers):
        channel = headers.get("x-goog-channel-id", "")
        locator = self.store.get("Connections", (f"CHANNEL#{channel}", "META"))
        if not locator:
            return
        watch = self.store.get("Connections", (locator["watchPK"], locator["watchSK"]))
        if (
            watch["channelId"] != channel
            or watch["expiresAt"] <= self.domain.now()
            or not secrets.compare_digest(
                watch["tokenHash"], digest({"token": headers.get("x-goog-channel-token", "")})
            )
            or not headers.get("x-goog-resource-id")
            or watch["resourceId"]
            and watch["resourceId"] != headers.get("x-goog-resource-id")
        ):
            raise Problem(403, "WEBHOOK_INVALID", "Calendar notification identity is invalid.")
        try:
            sequence = int(headers.get("x-goog-message-number", ""))
        except ValueError:
            raise Problem(422, "WEBHOOK_INVALID", "Calendar message number is invalid.") from None
        if sequence <= watch["lastMessage"]:
            return
        expires_at = watch["expiresAt"]
        if headers.get("x-goog-channel-expiration"):
            try:
                expiry = parsedate_to_datetime(headers["x-goog-channel-expiration"])
                if expiry.tzinfo is None:
                    raise ValueError("Missing expiration timezone")
                expires_at = int(expiry.timestamp())
            except (ValueError, TypeError, OverflowError, OSError):
                raise Problem(422, "WEBHOOK_INVALID", "Calendar expiration is invalid.") from None
        connection = self.store.get(
            "Domain", (hkey(watch["h"]), f"CONNECTION#{watch['connectionId']}")
        )
        if not active(connection, self.domain.now()):
            return
        intent = self.store.get("Delivery", (f"CALRUN#{connection['id']}", "META"))
        self.store.transact(
            [
                guard("Domain", connection),
                put(
                    "Connections",
                    revised(
                        watch,
                        lastMessage=sequence,
                        status="ACTIVE",
                        resourceId=headers["x-goog-resource-id"],
                        **watch_deadlines(watch, expires_at),
                    ),
                    watch,
                ),
                put("Delivery", self.intent(connection, intent), intent),
            ]
        )

    def sweep(self):
        items = self.pending("CALRUN")
        for intent in items:
            try:
                self.run_intent(intent)
            except Conflict:
                continue
            except Exception as exc:
                logging.getLogger("koyori.calendar").warning(
                    json.dumps(
                        {
                            "event": "calendar_retry",
                            "errorClass": type(exc).__name__,
                            "code": exc.code
                            if isinstance(exc, Problem)
                            else "DEPENDENCY_UNAVAILABLE",
                        }
                    )
                )
                self.defer(
                    intent,
                    self.domain.now() + min(3600, 30 * 2 ** min(intent.get("retries", 0), 7)),
                )
        return len(items)

    def run_intent(self, intent):
        connection = self.store.get(
            "Domain", (hkey(intent["h"]), f"CONNECTION#{intent['connectionId']}")
        )
        if not connection:
            return
        if connection.get("revokePending"):
            secret_row = self.store.get("Connections", self.token_key(connection))
            if secret_row["envelope"] is not None:
                credentials = self.envelope.open(
                    secret_row["envelope"], connection["owner"], connection["id"]
                )
                self.google.revoke(credentials["refresh_token"])
            self.store.transact(
                [
                    put("Domain", revised(connection, revokePending=False), connection),
                    put(
                        "Connections", revised(secret_row, envelope=None, leaseUntil=0), secret_row
                    ),
                    put("Delivery", self.domain.done_intent(intent), intent),
                ]
            )
            return
        if self.revoke_lost_authority(connection, intent):
            return
        if not active(connection, self.domain.now()):
            self.store.transact(
                [
                    guard("Domain", connection),
                    put("Delivery", self.domain.done_intent(intent), intent),
                ]
            )
            return
        ctx = self.domain.context(connection["owner"], intent["h"])
        self.sync(ctx, connection["id"])
        self.register_watch(ctx, connection["id"])
        current = self.store.get("Delivery", (intent["PK"], intent["SK"]))
        if current["rev"] == intent["rev"]:
            self.store.transact(
                [put("Delivery", self.intent(connection, current, self.domain.now() + 60), current)]
            )

    def revoke_lost_authority(self, connection, intent):
        keys = [
            (hkey(intent["h"]), "META"),
            (hkey(intent["h"]), f"MEMBER#{connection['owner']}"),
            (f"P#{connection['owner']}", "PROFILE"),
        ]
        snapshots = [self.store.get("Domain", key) for key in keys]
        household, member, profile = snapshots
        if (
            household
            and active(member, self.domain.now())
            and active(profile, self.domain.now())
            and profile["kind"] == "personal"
            and member.get("accessEpoch", 1) == connection["memberEpoch"]
        ):
            return False
        revoked = revised(
            connection, active=False, epoch=connection["epoch"] + 1, revokePending=True
        )
        # Cleanup is system work. Lost owner authority must not prevent revoking its
        # credential, but a concurrent restoration must invalidate this decision.
        checks = [
            Change("Domain", key, value["rev"] if value else None)
            for key, value in zip(keys, snapshots, strict=True)
        ]
        self.store.transact(
            checks
            + [
                put("Domain", revoked, connection),
                put("Delivery", self.intent(revoked, intent), intent),
            ]
        )
        return True
