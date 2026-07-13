"""Phase 0a — SSRF egress guard (hermetic: numeric IPs, monkeypatched DNS,
httpx.MockTransport — no network, no new deps)."""
import socket

import httpx
import pytest

from backend import ssrf
from backend.ssrf import SSRFError, guarded_get, validate_host, validate_sql_host


# --- IP classification: every row of the plan's threat table ----------------

@pytest.mark.parametrize("ip", [
    "169.254.169.254",   # AWS/GCP instance metadata
    "127.0.0.1", "127.0.0.53",  # loopback
    "10.1.2.3", "172.16.5.5", "172.31.255.255", "192.168.1.1",  # RFC1918
    "100.64.0.1",        # CGNAT / shared address space
    "0.0.0.0",           # unspecified
    "::1",               # IPv6 loopback
    "fc00::1", "fd00::1",  # IPv6 unique-local
    "fe80::1",           # IPv6 link-local
    "::ffff:127.0.0.1",  # IPv4-mapped loopback — classic bypass
    "::ffff:169.254.169.254",  # IPv4-mapped metadata
])
def test_blocked_addresses(ip):
    # host == literal IP → getaddrinfo returns it verbatim, no DNS.
    with pytest.raises(SSRFError):
        validate_host(ip)


@pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "93.184.216.34"])
def test_public_addresses_allowed(ip):
    validate_host(ip)  # must not raise


def test_hostname_resolving_to_private_is_blocked(monkeypatch):
    def fake_getaddrinfo(host, port, *a, **k):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", port or 80))]
    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(SSRFError):
        validate_host("metadata.evil.test")


def test_unresolvable_host_blocked(monkeypatch):
    def boom(*a, **k):
        raise socket.gaierror("nope")
    monkeypatch.setattr(socket, "getaddrinfo", boom)
    with pytest.raises(SSRFError):
        validate_host("does-not-exist.invalid")


def test_dev_escape_hatch(monkeypatch):
    monkeypatch.setenv("SSRF_ALLOW_PRIVATE", "1")
    monkeypatch.delenv("PROXY_SHARED_SECRET", raising=False)
    validate_host("127.0.0.1")  # allowed in dev
    # ...but refused in production (proxy secret present = publicly reachable).
    monkeypatch.setenv("PROXY_SHARED_SECRET", "x")
    with pytest.raises(SSRFError):
        validate_host("127.0.0.1")


# --- guarded_get: scheme allowlist + redirect revalidation ------------------

@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "gopher://x/", "ftp://x/", "data:text/plain,hi",
])
def test_scheme_allowlist(url):
    with pytest.raises(SSRFError):
        guarded_get(url)


def test_redirect_into_blocked_range_is_caught(monkeypatch):
    # first.test → public; the redirect target blocked.test → metadata IP.
    def fake_getaddrinfo(host, port, *a, **k):
        ip = "8.8.8.8" if host == "first.test" else "169.254.169.254"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port or 80))]
    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    def handler(request):
        if request.url.host == "first.test":
            return httpx.Response(302, headers={"location": "http://blocked.test/"})
        return httpx.Response(200, json=[{"a": 1}])

    with pytest.raises(SSRFError):
        guarded_get("http://first.test/", transport=httpx.MockTransport(handler))


def test_redirect_cap(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo",
                        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 80))])
    # Always redirects to another public host → must trip the redirect cap.
    handler = lambda request: httpx.Response(302, headers={"location": "http://loop.test/next"})
    monkeypatch.setattr(socket, "getaddrinfo",
                        lambda h, p, *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", p or 80))])
    with pytest.raises(SSRFError):
        guarded_get("http://loop.test/", transport=httpx.MockTransport(handler))


def test_happy_path_returns_json(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo",
                        lambda h, p, *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", p or 80))])
    handler = lambda request: httpx.Response(200, json=[{"a": 1}, {"a": 2}])
    resp = guarded_get("http://api.test/data", transport=httpx.MockTransport(handler))
    resp.raise_for_status()
    assert resp.json() == [{"a": 1}, {"a": 2}]


def test_oversize_response_rejected(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo",
                        lambda h, p, *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", p or 80))])
    monkeypatch.setattr(ssrf, "_MAX_BYTES", 10)
    handler = lambda request: httpx.Response(200, content=b"x" * 100)
    with pytest.raises(SSRFError):
        guarded_get("http://api.test/big", transport=httpx.MockTransport(handler))


# --- SQL connection-string host guard ---------------------------------------

@pytest.mark.parametrize("cs", [
    "postgresql://u:p@127.0.0.1:5432/db",
    "postgresql://u:p@localhost/db",
    "mysql://u:p@10.0.0.5/db",
    "postgresql://u:p@169.254.169.254/db",
])
def test_sql_host_blocked(cs, monkeypatch):
    # localhost must resolve to loopback deterministically.
    real = socket.getaddrinfo
    def fake(host, port, *a, **k):
        if host == "localhost":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port or 0))]
        return real(host, port, *a, **k)
    monkeypatch.setattr(socket, "getaddrinfo", fake)
    with pytest.raises(SSRFError):
        validate_sql_host(cs)


def test_sql_public_host_allowed():
    validate_sql_host("postgresql://u:p@8.8.8.8:5432/db")  # must not raise


def test_sqlite_has_no_host_and_is_skipped():
    validate_sql_host("sqlite:///./local.db")  # no network host → allowed here
