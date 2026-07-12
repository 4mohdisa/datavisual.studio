"""Disk retention — uploads and exports grow forever otherwise.

A nightly sweep removes upload files that no conversation references AND are
older than N days, plus exports older than N days (they regenerate on demand).
It NEVER touches conversations — they are the database. Wire the cron in
DEPLOY_RUNBOOK.md; run manually with `python -m backend.gc`.
"""

import os
import time
from typing import Optional, Set

from . import storage


def referenced_upload_names() -> Set[str]:
    """Basenames of every upload file still referenced by a conversation."""
    names: Set[str] = set()
    for meta in storage.list_conversations():
        conv = storage.get_conversation(meta["id"])
        f = (conv or {}).get("file") or {}
        for key in ("save_name", "name"):
            if f.get(key):
                names.add(os.path.basename(f[key]))
        if f.get("path"):
            names.add(os.path.basename(f["path"]))
    return names


def sweep(uploads_dir: str, exports_dir: str, max_age_days: int = 30, now: Optional[float] = None) -> list[str]:
    """Remove orphaned old uploads + old exports. Returns the removed paths."""
    now = now if now is not None else time.time()
    cutoff = max_age_days * 86400
    removed: list[str] = []
    referenced = referenced_upload_names()

    if os.path.isdir(uploads_dir):
        for name in os.listdir(uploads_dir):
            if name in referenced:
                continue  # a conversation still points at this file
            p = os.path.join(uploads_dir, name)
            try:
                if os.path.isfile(p) and now - os.path.getmtime(p) > cutoff:
                    os.remove(p)
                    removed.append(p)
            except OSError:
                pass

    if os.path.isdir(exports_dir):
        for name in os.listdir(exports_dir):
            p = os.path.join(exports_dir, name)
            try:
                if os.path.isfile(p) and now - os.path.getmtime(p) > cutoff:
                    os.remove(p)
                    removed.append(p)
            except OSError:
                pass

    return removed


if __name__ == "__main__":  # pragma: no cover
    import backend.main as main
    days = int(os.getenv("GC_MAX_AGE_DAYS", "30"))
    gone = sweep(main.UPLOADS_DIR, main.EXPORTS_DIR, max_age_days=days)
    print(f"gc: removed {len(gone)} file(s) older than {days} days with no referencing conversation.")
