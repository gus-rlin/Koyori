import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


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
