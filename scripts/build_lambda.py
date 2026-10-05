"""Build a clean Linux Lambda bundle from the locked runtime dependencies."""

import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
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
            "--mount",
            "type=volume,source=koyori-lambda-build-cache,target=/root/.cache/pip",
            "--mount",
            f"type=bind,source={artifacts},target=/artifact",
            "--mount",
            f"type=bind,source={root / 'src'},target=/src,readonly",
            "--mount",
            f"type=bind,source={root / 'scripts' / 'lambda_build_inside.py'},target=/build.py,readonly",
            "python:3.12.13-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b",
            "python",
            "/build.py",
        ],
        check=True,
        cwd=root,
    )


if __name__ == "__main__":
    main()
