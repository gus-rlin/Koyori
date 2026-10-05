"""API Gateway HTTP API adapter; authentication remains in the shared API."""

from mangum import Mangum

from koyori.control.app import create_app

_adapter = None


def handler(event, context):
    global _adapter
    if _adapter is None:
        _adapter = Mangum(create_app(), lifespan="off")
    return _adapter(event, context)
