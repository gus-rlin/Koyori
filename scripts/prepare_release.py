"""Generate a compatible artifact manifest without claiming deployment or ARM64 qualification."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from koyori.release import CONTRACTS, RECOVERY, compatible

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--voice-image")
    parser.add_argument("--mcp-image")
    args = parser.parse_args()
    for image in (args.voice_image, args.mcp_image):
        if image and not re.fullmatch(
            r"[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/koyori-[a-z0-9/_-]+@sha256:[a-f0-9]{64}",
            image,
        ):
            parser.error("Runtime images require an immutable digest in an approved ECR repository")
    evidence = json.loads((ROOT / "docs/verification/artifact-evidence.json").read_text())
    manifest = {
        "schemaVersion": "1.0",
        "state": "PREPARED_NOT_DEPLOYED",
        "contracts": CONTRACTS,
        "restoration": RECOVERY,
        "backendRegion": "eu-west-1",
        "speechRegion": "eu-north-1",
        "speechModel": "amazon.nova-2-sonic-v1:0",
        "voiceImage": args.voice_image,
        "mcpImage": args.mcp_image,
        "requiredArchitecture": "arm64",
        "runtimeArchitectureQualified": False,
        "sourceSha256": evidence["sourceSha256"],
        "lambdaBundleSha256": evidence["lambdaBundleSha256"],
        "templateSha256": evidence["templateSha256"],
        "localRuntimeImageId": evidence["runtimeImageId"],
        "lockSha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
        "cloudQualification": "NOT_RUN",
        "observedAwsCost": None,
        "awsResourcesCreated": [],
    }
    compatible(json.loads(args.previous.read_text()) if args.previous else None, manifest)
    (ROOT / "docs/verification/deployment-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print("Prepared compatible release manifest; no deployment performed")


if __name__ == "__main__":
    main()
