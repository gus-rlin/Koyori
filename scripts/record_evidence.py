"""Record reproducible artifact fingerprints and observed check results, without fixture data."""

import argparse
import hashlib
import json
import os
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def tree_hash(paths, *, normalize_text=False):
    """Source text uses LF and case-sensitive POSIX order; binary bundles stay exact."""
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.relative_to(ROOT).as_posix()):
        data = path.read_bytes()
        if normalize_text:
            data = data.replace(b"\r\n", b"\n")
        digest.update(path.relative_to(ROOT).as_posix().encode() + b"\0" + data)
    return digest.hexdigest()


def source_paths():
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
    return sources


def check_source():
    report = json.loads((ROOT / "docs/verification/artifact-evidence.json").read_text())
    if tree_hash(source_paths(), normalize_text=True) != report["sourceSha256"]:
        raise ValueError("Recorded source fingerprint differs from the checkout")
    print("Recorded source fingerprint matches the checkout")


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
    for source in (ROOT / "src/koyori").rglob("*.py"):
        bundled = ROOT / "artifacts/lambda/koyori" / source.relative_to(ROOT / "src/koyori")
        if bundled.read_bytes() != source.read_bytes():
            raise ValueError("Lambda source artifact differs from current code")
    sbom = json.loads((ROOT / "artifacts/runtime-sbom.json").read_text())
    if sbom.get("vulnerabilities"):
        raise ValueError("Runtime dependency findings must be resolved")
    image_id = subprocess.run(
        ["docker", "image", "inspect", "koyori-stage1:local", "--format", "{{.Id}}"],
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
        "scope": "stages-one-and-two-local-and-aws-preparation",
        "sourceSha256": tree_hash(source_paths(), normalize_text=True),
        "sourceHashFormat": "sha256(path + NUL + LF-text); case-sensitive POSIX path order",
        "lockSha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
        "lambdaBundleSha256": tree_hash(bundle_files),
        "templateSha256": hashlib.sha256(
            (ROOT / "cdk.out/KoyoriFoundation.template.json").read_bytes()
        ).hexdigest(),
        "runtimeImageId": image_id,
        "pytest": counts,
        "dockerRecovery": recovery["checks"],
        "stage2Recovery": stage2_recovery["checks"],
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-source", action="store_true")
    if parser.parse_args().check_source:
        check_source()
    else:
        main()
