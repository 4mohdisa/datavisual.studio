"""Phase 1b — the public /demo endpoint: a prebuilt sample dashboard in the
read-only share shape, no auth, no owner-only fields leaked."""


def test_demo_returns_public_dashboard(client):
    r = client.get("/api/demo")
    assert r.status_code == 200
    data = r.json()
    assert data["is_demo"] is True
    assert data["shared"] is True
    assert data["dashboard"]["widgets"]  # a real, built dashboard


def test_demo_leaks_no_owner_only_fields(client):
    blob = str(client.get("/api/demo").json())
    for forbidden in ("owner_id", "history", "source", "alerts", "schedule", "clerk"):
        assert forbidden not in blob, f"demo payload leaked {forbidden!r}"


def test_demo_is_cached_stable(client):
    a = client.get("/api/demo").json()
    b = client.get("/api/demo").json()
    assert a["dashboard"]["title"] == b["dashboard"]["title"]
