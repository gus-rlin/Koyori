"""Runs only inside the builder container with the explicit artifact mount."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

root = Path("/artifact").resolve()
target = (root / "lambda").resolve()
staging, previous = root / "lambda.staging", root / "lambda.previous"
if root != Path("/artifact") or any(
    not p.resolve().is_relative_to(root)
    or p.name not in {"lambda", "lambda.staging", "lambda.previous"}
    for p in (target, staging, previous)
):
    raise ValueError("Unexpected artifact destination")
if staging.exists():
    shutil.rmtree(staging)
staging.mkdir()
command = (
    [
        "uv",
        "--system-certs",
        "pip",
        "install",
        "--python",
        sys.executable,
        "--require-hashes",
        "--no-deps",
        "--target",
        str(staging),
        "-r",
        str(root / "runtime-requirements.txt"),
    ]
    if os.getenv("KOYORI_BUILD_WITH_UV") == "1"
    else [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--quiet",
        "--disable-pip-version-check",
        "--require-hashes",
        "--no-deps",
        "--no-compile",
        "--timeout",
        "60",
        "--retries",
        "3",
        "--target",
        str(staging),
        "-r",
        str(root / "runtime-requirements.txt"),
    ]
)
subprocess.run(command, check=True)
shutil.copytree("/src/koyori", staging / "koyori", ignore=shutil.ignore_patterns("__pycache__"))
if previous.exists():
    raise ValueError("Previous interrupted activation requires inspection")
if target.exists():
    target.rename(previous)
try:
    staging.rename(target)
except Exception:
    if previous.exists() and not target.exists():
        previous.rename(target)
    raise
if previous.exists():
    shutil.rmtree(previous)
print("Locked Linux Lambda artifact built.")
