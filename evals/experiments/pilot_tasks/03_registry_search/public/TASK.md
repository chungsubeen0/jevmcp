# Correct the command registry

One command name resolves to the wrong handler. Find the active command
registry and correct the single bad registration.

Requirements:

- `resolve("archive")` must return the archive handler;
- all other command registrations must remain unchanged;
- unknown commands must continue to raise `KeyError`.

This package contains historical and generated-looking modules that are not
used by `resolve`. Avoid unrelated cleanup or refactoring.
