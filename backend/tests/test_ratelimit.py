"""Phase 0b/0c — rate limiter must not throttle the status poller, and must key
on the real client IP (X-Forwarded-For), not the shared proxy socket."""
import backend.main as main
from backend.main import _client_ip


class _Req:
    """Minimal stand-in for a Starlette Request (headers.get + client.host)."""
    def __init__(self, xff=None, socket="203.0.113.9"):
        self.headers = {"x-forwarded-for": xff} if xff else {}
        self.client = type("C", (), {"host": socket})()


# --- 0c: X-Forwarded-For keying -------------------------------------------

def test_xff_rightmost_is_authoritative(monkeypatch):
    monkeypatch.setattr(main, "_TRUSTED_PROXY_HOPS", 1)
    assert _client_ip(_Req(xff="1.2.3.4", socket="10.0.0.1")) == "1.2.3.4"


def test_spoofed_xff_prefix_does_not_bypass(monkeypatch):
    monkeypatch.setattr(main, "_TRUSTED_PROXY_HOPS", 1)
    # Same real client behind the proxy, attacker varies the forgeable prefix →
    # must resolve to the SAME key, so the spoof can't dodge the bucket.
    a = _client_ip(_Req(xff="9.9.9.9, 1.2.3.4"))
    b = _client_ip(_Req(xff="6.6.6.6, 1.2.3.4"))
    assert a == b == "1.2.3.4"


def test_distinct_real_clients_get_distinct_keys(monkeypatch):
    monkeypatch.setattr(main, "_TRUSTED_PROXY_HOPS", 1)
    assert _client_ip(_Req(xff="1.2.3.4")) != _client_ip(_Req(xff="5.6.7.8"))


def test_no_xff_falls_back_to_socket(monkeypatch):
    monkeypatch.setattr(main, "_TRUSTED_PROXY_HOPS", 1)
    assert _client_ip(_Req(xff=None, socket="10.0.0.1")) == "10.0.0.1"


def test_hops_zero_ignores_xff(monkeypatch):
    # No trusted proxy in front → XFF is fully client-controlled, trust the socket.
    monkeypatch.setattr(main, "_TRUSTED_PROXY_HOPS", 0)
    assert _client_ip(_Req(xff="1.2.3.4", socket="10.0.0.1")) == "10.0.0.1"


def test_two_hops(monkeypatch):
    monkeypatch.setattr(main, "_TRUSTED_PROXY_HOPS", 2)
    assert _client_ip(_Req(xff="client, cf")) == "client"
    assert _client_ip(_Req(xff="spoof, client, cf")) == "client"


# --- 0b: the poller is exempt (the suspected product-breaking bug) ---------

def _enable_limiter(capacity=3):
    rl = main._rate_limiter
    rl.enabled = True
    rl.capacity = capacity
    rl._tokens.clear()
    rl._last.clear()


def _disable_limiter():
    main._rate_limiter.enabled = False


def test_status_polling_never_429s(client):
    """A 5-minute pipeline polls /status ~200 times. With the limiter ON and a
    tiny bucket, every one of those GETs must pass — else long analyses
    self-throttle in production."""
    _enable_limiter(capacity=3)
    try:
        codes = [client.get(f"/api/conversations/poll{i}/status").status_code for i in range(200)]
    finally:
        _disable_limiter()
    assert 429 not in codes  # exempt: GET + not in the limited set


def test_limiter_actually_fires_on_limited_post(client):
    """Positive control — proves the limiter is genuinely on above, so the
    exemption test means something. Repeated limited POSTs DO hit 429."""
    _enable_limiter(capacity=3)
    try:
        codes = [client.post("/api/connect", json={"type": "bogus"}).status_code for _ in range(10)]
    finally:
        _disable_limiter()
    assert 429 in codes
