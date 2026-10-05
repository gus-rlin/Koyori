"""Record reproducible artifact fingerprints and observed check results, without fixture data."""

import hashlib
import json
import os
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def tree_hash(paths):
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(ROOT).as_posix().encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def main():
    suites = ET.parse(ROOT / "artifacts/all-tests.xml").getroot()
    counts = {
        key: sum(int(s.attrib.get(key, "0")) for s in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    if counts["failures"] or counts["errors"] or counts["skipped"]:
        raise ValueError("Complete verification has not passed")
    recovery = json.loads((ROOT / "artifacts/local-recovery.json").read_text())
    if recovery["result"] != "PASS":
        raise ValueError("Docker recovery not verified")
    stage2_recovery = json.loads((ROOT / "artifacts/stage2-recovery.json").read_text())
    if stage2_recovery["result"] != "PASS":
        raise ValueError("Stage-two Docker recovery not verified")
    stage3_recovery = json.loads((ROOT / "artifacts/stage3-recovery.json").read_text())
    if stage3_recovery["result"] != "PASS":
        raise ValueError("Stage-three Docker recovery not verified")
    for source in (ROOT / "src/koyori").rglob("*.py"):
        bundled = ROOT / "artifacts/lambda/koyori" / source.relative_to(ROOT / "src/koyori")
        if bundled.read_bytes() != source.read_bytes():
            raise ValueError("Lambda source artifact differs from current code")
    sources = [
        p
        for folder in ("src", "tests", "scripts", "infrastructure", "local", ".github")
        for p in (ROOT / folder).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    ]
    sources += [
        ROOT / p
        for p in (
            "Dockerfile",
            "compose.yaml",
            "pyproject.toml",
            "uv.lock",
            ".dockerignore",
            ".python-version",
        )
    ]
    sbom = json.loads((ROOT / "artifacts/runtime-sbom.json").read_text())
    if sbom.get("vulnerabilities"):
        raise ValueError("Runtime dependency findings must be resolved")
    image_id = subprocess.run(
        [
            "docker",
            "image",
            "inspect",
            os.getenv("KOYORI_RUNTIME_IMAGE", "koyori-stage1:local"),
            "--format",
            "{{.Id}}",
        ],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    bundle_files = [
        p
        for p in (ROOT / "artifacts/lambda").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    ]
    report = {
        "schemaVersion": "1.0",
        "dateEuropeParis": datetime.now(ZoneInfo("Europe/Paris")).isoformat(),
        "scope": "stages-one-two-three-local-and-aws-preparation",
        "sourceSha256": tree_hash(sources),
        "lockSha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
        "lambdaBundleSha256": tree_hash(bundle_files),
        "templateSha256": hashlib.sha256(
            (ROOT / "cdk.out/KoyoriFoundation.template.json").read_bytes()
        ).hexdigest(),
        "runtimeImageId": image_id,
        "pytest": counts,
        "dockerRecovery": recovery["checks"],
        "stage2Recovery": stage2_recovery["checks"],
        "stage3Recovery": stage3_recovery["checks"],
        "liveNovaQualified": False,
        "googleQualified": False,
        "bedrockAndVectorsQualified": False,
        "runtimeDependencyAudit": "no known vulnerabilities found",
        "awsDeployedOrQualified": False,
        "githubWorkflowExecuted": os.getenv("GITHUB_ACTIONS") == "true",
    }
    output = ROOT / "docs/verification/artifact-evidence.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"sourceSha256": report["sourceSha256"], "pytest": counts, "dockerRecovery": "PASS"}
        )
    )


if __name__ == "__main__":
    main()
