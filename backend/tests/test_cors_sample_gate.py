"""Phase 0j/0k — CORS preflight survives the guard middlewares on the direct-
upload carve-out, and the unauthenticated sample-dashboard endpoint is hard
rate-limited (no wildcard CORS anywhere)."""
import backend.main as main


# --- 0j: CORS preflight on /api/upload-direct ------------------------------

def test_no_wildcard_cors_origin():
    assert "*" not in main._allowed_origins


def test_upload_direct_preflight_not_swallowed(client, monkeypatch):
    # Even with the proxy-secret guard armed, the OPTIONS preflight for the
    # browser→backend upload carve-out must return CORS headers, not a 403/429.
    monkeypatch.setenv("PROXY_SHARED_SECRET", "s")
    r = client.options("/api/upload-direct", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "x-upload-ticket",
    })
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


# --- 0k: sample-dashboard is rate-limited ----------------------------------

def test_sample_dashboard_is_rate_limited(client):
    rl = main._rate_limiter
    rl.enabled = True
    rl.capacity = 1
    rl._tokens.clear()
    rl._last.clear()
    try:
        codes = [client.post("/api/sample-dashboard", json={"sample": "sales"}).status_code
                 for _ in range(6)]
    finally:
        rl.enabled = False
    assert 429 in codes  # an unauthenticated compute endpoint must throttle
