import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_source_fingerprint_is_portable_across_git_line_endings_and_path_order(
    tmp_path, monkeypatch
):
    spec = importlib.util.spec_from_file_location(
        "record_evidence", Path(__file__).resolve().parents[1] / "scripts/record_evidence.py"
    )
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    monkeypatch.setattr(script, "ROOT", tmp_path)
    upper, lower = tmp_path / "Dockerfile", tmp_path / "compose.yaml"
    upper.write_bytes(b"FROM example\n")
    lower.write_bytes(b"services: {}\n")
    expected = hashlib.sha256(b"Dockerfile\0FROM example\ncompose.yaml\0services: {}\n").hexdigest()
    assert script.tree_hash([lower, upper], normalize_text=True) == expected
    upper.write_bytes(b"FROM example\r\n")
    lower.write_bytes(b"services: {}\r\n")
    assert script.tree_hash([upper, lower], normalize_text=True) == expected
    # Bundle hashes remain hashes of exact bytes, including CRLF in binary artifacts.
    assert script.tree_hash([upper, lower]) != expected


@pytest.mark.parametrize("github_actions", [None, "false", "true"])
def test_evidence_identifies_github_actions(tmp_path, monkeypatch, github_actions):
    spec = importlib.util.spec_from_file_location(
        "record_evidence", Path(__file__).resolve().parents[1] / "scripts/record_evidence.py"
    )
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    files = {
        "artifacts/all-tests.xml": '<testsuites><testsuite tests="1"/></testsuites>',
        "artifacts/local-recovery.json": '{"result":"PASS","checks":[]}',
        "artifacts/stage2-recovery.json": '{"result":"PASS","checks":[]}',
        "artifacts/runtime-sbom.json": '{"vulnerabilities":[]}',
        "cdk.out/KoyoriFoundation.template.json": "{}",
        "src/koyori/example.py": "# synthetic test fixture\n",
        "artifacts/lambda/koyori/example.py": "# synthetic test fixture\n",
    }
    for name in (
        "Dockerfile",
        "compose.yaml",
        "pyproject.toml",
        "uv.lock",
        ".dockerignore",
        ".python-version",
    ):
        files[name] = ""
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (tmp_path / "docs/verification").mkdir(parents=True)
    monkeypatch.setattr(script, "ROOT", tmp_path)
    monkeypatch.setattr(
        script.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout="synthetic-image")
    )
    if github_actions is None:
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    else:
        monkeypatch.setenv("GITHUB_ACTIONS", github_actions)
    script.main()
    report = json.loads((tmp_path / "docs/verification/artifact-evidence.json").read_text())
    assert report["githubWorkflowExecuted"] is (github_actions == "true")
    script.check_source()
    (tmp_path / "src/koyori/example.py").write_bytes(b"# changed after verification\n")
    with pytest.raises(ValueError, match="source fingerprint differs"):
        script.check_source()
