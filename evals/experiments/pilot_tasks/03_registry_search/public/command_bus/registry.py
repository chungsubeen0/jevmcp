"""Runtime command registry."""

from collections.abc import Callable

from . import handlers

Handler = Callable[[str], str]

COMMANDS: dict[str, Handler] = {
    "create": handlers.create,
    "preview": handlers.preview,
    "archive": handlers.preview,
}


def resolve(name: str) -> Handler:
    return COMMANDS[name]
