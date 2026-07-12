"""Crash-safe JSON writes.

`data/` is the database and there is no other copy, so a kill / OOM / disk-full
in the middle of a write must never leave a truncated file — a torn
`conversations/<id>.json` 500s the whole list endpoint, and a torn `users.json`
loses every user's saved API keys. Every persistent state writer goes through
`atomic_write_json`: write to a unique temp file in the same directory, fsync,
then `os.replace` (atomic on POSIX) onto the target. On any failure the temp
file is unlinked and the original is left untouched.
"""

import json
import os
import uuid


def atomic_write_json(path, obj, *, indent: int = 2) -> None:
    path = os.fspath(path)
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    # Temp file in the SAME directory so os.replace is a same-filesystem rename.
    tmp = f"{path}.tmp.{os.getpid()}.{uuid.uuid4().hex}"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        # Present only if json.dump or os.replace raised (a successful replace
        # renames tmp away). Best-effort cleanup so failures don't litter.
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            pass
