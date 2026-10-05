"""Credential-free CDK synthesis. Deployment is a separately authorized action."""

import os

import aws_cdk as cdk

from infrastructure.stack import FoundationStack


def build(outdir="cdk.out"):
    app = cdk.App(outdir=outdir)
    FoundationStack(
        app,
        "KoyoriFoundation",
        stage=os.getenv("KOYORI_STAGE", "dev"),
        callback_url=os.getenv("KOYORI_CALLBACK_URL", "https://example.invalid/oauth/callback"),
        google_client_id=os.getenv("KOYORI_GOOGLE_CLIENT_ID"),
    )
    return app.synth()


if __name__ == "__main__":
    build()
