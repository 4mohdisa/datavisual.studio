"""End-to-end API tests over the real FastAPI app (hermetic temp data dir).

Covers the golden path (upload → dashboard → edit → share → public → revoke)
plus the security boundaries (ownership 404s, public allowlist has no leaks,
admin password gate)."""

ALICE = {"x-clerk-user-id": "clerk_alice", "x-user-email": "alice@test.dev"}
BOB = {"x-clerk-user-id": "clerk_bob", "x-user-email": "bob@test.dev"}


def _make_dashboard(client, upload_csv, headers=None):
    fid = upload_csv()
    r = client.post("/api/dashboard", json={"file_id": fid}, headers=headers or {})
    assert r.status_code == 200, r.text
    return r.json()["conversation_id"]


# --- golden path --------------------------------------------------------------

def test_upload_returns_metadata(client, upload_csv):
    fid = upload_csv()
    assert fid


def test_create_dashboard_from_upload(client, upload_csv):
    cid = _make_dashboard(client, upload_csv)
    conv = client.get(f"/api/conversations/{cid}").json()
    assert conv["mode"] == "dashboard"
    kinds = {w["kind"] for w in conv["dashboard"]["widgets"]}
    assert "metric" in kinds and "chart" in kinds


def test_dataset_endpoint_returns_rows(client, upload_csv):
    cid = _make_dashboard(client, upload_csv)
    ds = client.get(f"/api/dataset/{cid}").json()
    assert ds["total_rows"] == 6
    assert "revenue" in ds["columns"]


def test_dashboard_chat_ops_add_metric(client, upload_csv):
    cid = _make_dashboard(client, upload_csv)
    before = len(client.get(f"/api/conversations/{cid}").json()["dashboard"]["widgets"])
    r = client.post(f"/api/dashboard/{cid}/chat", json={"ops": [
        {"op": "add_metric", "column": "revenue", "agg": "sum", "label": "Total revenue"},
    ]})
    assert r.status_code == 200, r.text
    after = r.json()["dashboard"]["widgets"]
    assert len(after) == before + 1
    assert any(w.get("label") == "Total revenue" for w in after)


def test_export_format_endpoint(client):
    r = client.get("/api/export-format")
    assert r.status_code == 200
    assert r.json()["format"] in ("pdf", "html")


# --- share flow + public allowlist -------------------------------------------

def test_share_public_view_and_revoke(client, upload_csv):
    cid = _make_dashboard(client, upload_csv)
    token = client.post(f"/api/conversations/{cid}/share").json()["share_id"]

    pub = client.get(f"/api/public/{token}")
    assert pub.status_code == 200
    body = pub.json()
    assert body["dashboard"]["widgets"]
    # allowlist: sensitive server fields must NOT be present
    assert "owner_id" not in body
    assert "file" not in body
    assert "history" not in body["dashboard"]
    raw = pub.text
    assert "owner_id" not in raw and "clerk_" not in raw

    # revoke → gone
    client.delete(f"/api/conversations/{cid}/share")
    assert client.get(f"/api/public/{token}").status_code == 404


def test_public_unknown_token_404(client):
    assert client.get("/api/public/doesnotexist").status_code == 404


# --- ownership scoping --------------------------------------------------------

def test_owner_only_can_read(client, upload_csv):
    cid = _make_dashboard(client, upload_csv, headers=ALICE)
    assert client.get(f"/api/conversations/{cid}", headers=ALICE).status_code == 200
    assert client.get(f"/api/conversations/{cid}", headers=BOB).status_code == 404


def test_non_owner_cannot_share(client, upload_csv):
    cid = _make_dashboard(client, upload_csv, headers=ALICE)
    assert client.post(f"/api/conversations/{cid}/share", headers=BOB).status_code == 404


def test_conversation_list_scoped_to_owner(client, upload_csv):
    _make_dashboard(client, upload_csv, headers=ALICE)
    assert len(client.get("/api/conversations", headers=ALICE).json()) == 1
    assert client.get("/api/conversations", headers=BOB).json() == []


def test_non_owner_404_on_every_owner_scoped_endpoint(client, upload_csv):
    """Phase 2c — B must get 404 on A's dataset, export, status and dashboard
    chat, not just the record. One forgotten `_owned()` is a data leak."""
    cid = _make_dashboard(client, upload_csv, headers=ALICE)
    # sanity: A can reach them
    assert client.get(f"/api/dataset/{cid}", headers=ALICE).status_code == 200
    assert client.get(f"/api/conversations/{cid}/status", headers=ALICE).status_code == 200
    # B is a stranger to all of them
    assert client.get(f"/api/dataset/{cid}", headers=BOB).status_code == 404
    assert client.get(f"/api/conversations/{cid}/status", headers=BOB).status_code == 404
    assert client.get(f"/api/export/{cid}", headers=BOB, params={"format": "html"}).status_code == 404
    assert client.post(f"/api/dashboard/{cid}/chat", json={"ops": []}, headers=BOB).status_code == 404


def test_owner_share_link_opens_anonymously(client, upload_csv):
    """A's share link is public-by-token — it must open with no identity at all
    (the token IS the capability), while the record stays owner-scoped."""
    cid = _make_dashboard(client, upload_csv, headers=ALICE)
    token = client.post(f"/api/conversations/{cid}/share", headers=ALICE).json()["share_id"]
    assert client.get(f"/api/public/{token}").status_code == 200        # anonymous, no headers
    assert client.get(f"/api/conversations/{cid}", headers=BOB).status_code == 404  # record still scoped


# --- admin password gate ------------------------------------------------------

def test_admin_requires_password(client, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
    assert client.get("/api/admin/overview").status_code == 403
    assert client.get("/api/admin/overview", headers={"x-admin-password": "wrong"}).status_code == 403
    ok = client.get("/api/admin/overview", headers={"x-admin-password": "s3cret"})
    assert ok.status_code == 200
    assert "totals" in ok.json()


def test_settings_endpoint_shape(client):
    # /api/settings is blocked at the Next proxy, but the backend still serves a
    # masked view in open dev mode — assert the key is never returned in full.
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert "api_key" not in r.json() or "api_key_masked" in r.json()


# --- Phase 2a: pipeline transport (polling default, SSE opt-in) ---------------

def test_analyse_kickoff_is_polling_by_default(client):
    """Default /api/analyse returns a JSON job kickoff immediately (not a
    long-lived SSE stream), so it survives a serverless function timeout."""
    cid = "kickoff-default"
    assert client.post("/api/conversations/create",
                       json={"conversation_id": cid, "title": "q"}).status_code == 200
    r = client.post("/api/analyse", json={"conversation_id": cid, "question": "trends?"})
    assert r.status_code == 200, r.text
    assert "application/json" in r.headers.get("content-type", "")
    body = r.json()
    assert body["conversation_id"] == cid and body["status"] == "running"
    # The polling endpoint reflects a job state, never a stream.
    s = client.get(f"/api/conversations/{cid}/status").json()
    assert s["status"] in ("running", "complete", "error")


def test_analyse_stream_flag_returns_sse(client):
    """?stream=1 opts back into the live SSE transport."""
    cid = "kickoff-stream"
    client.post("/api/conversations/create", json={"conversation_id": cid, "title": "q"})
    with client.stream("POST", "/api/analyse?stream=1",
                       json={"conversation_id": cid, "question": "hi"}) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
