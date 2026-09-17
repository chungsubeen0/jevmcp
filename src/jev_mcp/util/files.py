from __future__ import annotations

import os
from pathlib import Path


def secure_data_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass


def secure_data_file(path: Path) -> None:
    secure_data_dir(path.parent)
    if path.exists():
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    for suffix in ("-wal", "-shm"):
        sibling = Path(str(path) + suffix)
        if sibling.exists():
            try:
                os.chmod(sibling, 0o600)
            except OSError:
                pass
