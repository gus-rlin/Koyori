"""Stable, public errors. Dependency messages must never cross this boundary."""


class Problem(Exception):
    def __init__(self, status: int, code: str, detail: str, retryable: bool = False):
        super().__init__(code)
        self.status, self.code, self.detail, self.retryable = status, code, detail, retryable


class Conflict(Exception):
    """A conditional transaction lost a race; callers must reload authority and state."""


def missing() -> Problem:
    return Problem(404, "NOT_FOUND", "Resource unavailable.")


def denied() -> Problem:
    return Problem(403, "FORBIDDEN", "Operation not permitted.")
