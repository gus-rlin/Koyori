"""Explicit synthetic issuer and bootstrap. Refuses every non-local environment."""

import argparse
import json
import os
import time
import urllib.request
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from koyori.config import Settings
from koyori.contracts import HouseholdCreate, MemberCreate
from koyori.domain import Domain
from koyori.security import Cursors, request_hash
from koyori.store import DynamoStore


def issuer_dir(settings: Settings) -> Path:
    return Path(os.getenv("KOYORI_ISSUER_DIR", ".local/issuer"))


def initialize_keys(settings: Settings) -> None:
    if settings.env != "local":
        raise ValueError("Synthetic identity only exists locally")
    public_dir, private_dir = Path(settings.key_dir), issuer_dir(settings)
    public_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    private_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    private_path = private_dir / "jwt-private.pem"
    if not private_path.exists():
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        value = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        with private_path.open("xb") as output:
            output.write(value)
        private_path.chmod(0o600)
    key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    public_path = public_dir / "jwt-public.pem"
    if public_path.exists() and public_path.read_bytes() != public:
        raise ValueError("Identity keys inconsistent; do not overwrite active identities")
    if not public_path.exists():
        public_path.write_bytes(public)
    cursor = public_dir / "cursor.key"
    if not cursor.exists():
        with cursor.open("xb") as output:
            output.write(os.urandom(48))
        cursor.chmod(0o600)


def token(
    settings: Settings, principal: str, *, nonce=None, now=None, expires=600, mcp=False
) -> str:
    if settings.env != "local":
        raise ValueError("Synthetic issuer forbidden outside local")
    current = int(time.time()) if now is None else now
    claims = dict(
        iss=settings.issuer,
        sub=principal,
        iat=current,
        auth_time=current,
        exp=current + expires,
        token_use="id" if nonce else "access",
    )
    if nonce:
        claims.update(nonce=nonce, aud=settings.client_id)
    else:
        claims.update(
            client_id=settings.client_id,
            scope="koyori/mcp" if mcp else "koyori/control",
            aud=settings.mcp_resource if mcp else settings.audience,
        )
    return jwt.encode(
        claims,
        (issuer_dir(settings) / "jwt-private.pem").read_bytes(),
        algorithm="RS256",
        headers={"kid": "synthetic-local"},
    )


def seed(settings: Settings) -> dict:
    if settings.env != "local":
        raise ValueError("Synthetic bootstrap forbidden outside local")
    initialize_keys(settings)
    store = DynamoStore(settings)
    store.create_tables()
    sqs = settings.client("sqs")
    urls = {}
    for kind in ("workflow", "activity"):
        dlq = sqs.create_queue(QueueName=f"koyori-{kind}-dlq")["QueueUrl"]
        arn = sqs.get_queue_attributes(QueueUrl=dlq, AttributeNames=["QueueArn"])["Attributes"][
            "QueueArn"
        ]
        urls[kind] = sqs.create_queue(
            QueueName=f"koyori-{kind}",
            Attributes={
                "VisibilityTimeout": "60",
                "RedrivePolicy": json.dumps({"deadLetterTargetArn": arn, "maxReceiveCount": "5"}),
            },
        )["QueueUrl"]
    domain = Domain(store, settings, Cursors(settings.cursor_secret()))
    first = domain.create_household(
        "alex",
        HouseholdCreate(name="Foyer synthétique A").model_dump(),
        "00000000000040008000000000000001",
    )
    second = domain.create_household(
        "robin",
        HouseholdCreate(name="Foyer synthétique B").model_dump(),
        "00000000000040008000000000000002",
    )
    ctx = domain.context("alex", first["id"])
    # Upgrade initial local fixture metadata without changing any member right.
    for actor, hid in (("alex", first["id"]), ("robin", second["id"])):
        context = domain.context(actor, hid)
        if "memberIds" not in context.household:
            from koyori.store import put, revised

            members, _ = store.query("Domain", context.household["PK"], prefix="MEMBER#", limit=50)
            ids = [m["principalId"] for m in members if m["active"]]
            if len(ids) != context.household["memberCount"]:
                raise ValueError("Membership metadata inconsistent; explicit repair required")
            store.transact(
                [put("Domain", revised(context.household, memberIds=ids), context.household)]
            )
    ctx = domain.context("alex", first["id"])
    for principal, kind in (("sam", "personal"), ("speaker", "shared")):
        if store.get("Domain", (ctx.household["PK"], f"MEMBER#{principal}")):
            continue  # Never restore revoked rights or replace an existing membership.
        body = MemberCreate(principalId=principal, kind=kind).model_dump()
        _, changes, _ = domain.add_member(ctx, body)
        store.transact(ctx.guards() + changes)
        ctx = domain.context("alex", first["id"])
    return {
        "households": {"alex": first["id"], "robin": second["id"]},
        "queues": urls,
        "mode": "synthetic-local",
    }


def step_up(
    settings: Settings,
    principal: str,
    household: str,
    operation: str,
    body: dict,
    version: int | None,
    base_url: str,
) -> dict:
    from uuid import uuid4

    access = token(settings, principal)

    def post(path, payload):
        req = urllib.request.Request(
            base_url.rstrip("/") + path,
            data=json.dumps(payload).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {access}",
                "Content-Type": "application/json",
                "X-Household-Id": household,
                "Idempotency-Key": str(uuid4()),
            },
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.load(response)

    challenge = post(
        "/v1/auth/step-up", {"operation": operation, "requestHash": request_hash(body, version)}
    )
    return post(
        f"/v1/auth/step-up/{challenge['id']}/complete",
        {"identityProof": token(settings, principal, nonce=challenge["nonce"])},
    )


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed")
    tok = sub.add_parser("token")
    tok.add_argument("principal")
    tok.add_argument("--mcp", action="store_true", help="Resource-bound local MCP access token")
    step = sub.add_parser("step-up")
    step.add_argument("principal")
    step.add_argument("household")
    step.add_argument("operation")
    step.add_argument(
        "body_file", help="Normalized JSON body, including schemaVersion and defaults"
    )
    step.add_argument("--version", type=int)
    step.add_argument("--url", default="http://127.0.0.1:8088")
    args = parser.parse_args()
    settings = Settings.from_env()
    if settings.env != "local":
        parser.error("Synthetic CLI is local only")
    if args.command == "seed":
        print(json.dumps(seed(settings), ensure_ascii=False))
    elif args.command == "token":
        print(token(settings, args.principal, mcp=args.mcp))
    else:
        print(
            json.dumps(
                step_up(
                    settings,
                    args.principal,
                    args.household,
                    args.operation,
                    json.loads(Path(args.body_file).read_text(encoding="utf-8")),
                    args.version,
                    args.url,
                )
            )
        )


if __name__ == "__main__":
    main()
