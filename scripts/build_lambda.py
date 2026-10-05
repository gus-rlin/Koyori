"""Build a clean Linux Lambda bundle from the locked runtime dependencies."""

import os
import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    trusted_ca = os.getenv("KOYORI_BUILD_CA_FILE")
    ca_options = []
    if trusted_ca:
        ca_path = Path(trusted_ca).resolve(strict=True)
        if not ca_path.is_file():
            raise ValueError("Build CA must be a PEM file")
        ca_options = [
            "--mount",
            f"type=bind,source={ca_path},target=/trusted-ca.pem,readonly",
            "--env",
            "PIP_CERT=/trusted-ca.pem",
        ]
    subprocess.run(
        [
            "uv",
            "export",
            "--frozen",
            "--no-dev",
            "--no-emit-project",
            "--quiet",
            "--output-file",
            str(artifacts / "runtime-requirements.txt"),
        ],
        check=True,
        cwd=root,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            "--mount",
            "type=volume,source=koyori-lambda-build-cache,target=/root/.cache/pip",
            "--mount",
            f"type=bind,source={artifacts},target=/artifact",
            "--mount",
            f"type=bind,source={root / 'src'},target=/src,readonly",
            "--mount",
            f"type=bind,source={root / 'scripts' / 'lambda_build_inside.py'},target=/build.py,readonly",
            *ca_options,
            "python:3.12.13-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b",
            "python",
            "/build.py",
        ],
        check=True,
        cwd=root,
    )


if __name__ == "__main__":
    main()
