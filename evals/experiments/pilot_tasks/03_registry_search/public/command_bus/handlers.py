"""Command handlers."""


def create(payload: str) -> str:
    return f"created:{payload}"


def preview(payload: str) -> str:
    return f"preview:{payload}"


def archive(payload: str) -> str:
    return f"archived:{payload}"
