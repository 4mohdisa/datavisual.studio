"""Phase 0d — boot sweep flips restart-orphaned `running` pipelines to `error`
so their frontend pollers stop instead of spinning forever."""
import backend.main as main
from backend import storage


def _save(cid, status):
    storage.save_conversation({
        "id": cid, "created_at": "2026-01-01T00:00:00Z", "messages": [], "status": status,
    })


def test_sweep_flips_only_running_to_error():
    _save("run1", "running")
    _save("done1", "complete")
    _save("err1", "error")

    assert main._sweep_orphaned_jobs() == 1  # only the running one

    run1 = storage.get_conversation("run1")
    assert run1["status"] == "error"
    assert "restart" in run1["error_message"].lower()
    # terminal states are left untouched
    assert storage.get_conversation("done1")["status"] == "complete"
    assert storage.get_conversation("err1")["status"] == "error"


def test_sweep_noop_when_nothing_running():
    _save("done1", "complete")
    assert main._sweep_orphaned_jobs() == 0
