"""SSRF egress guard for user-supplied connector targets (Overnight Plan 2, 0a).

`POST /api/connect` fetches a user-supplied URL (REST) or connects to a
user-supplied DB host (SQL) *server-side*. Without an egress check a signed-in
user can point it at the cloud metadata endpoint (169.254.169.254), another
service on localhost, or anything on the private network.

The defence, applied at the single choke point every outbound connector request
passes through (`backend.main._run_source_import`):

- Resolve the hostname, then validate the *resolved IPs* — never the string.
- Refuse loopback / private / link-local / CGNAT / reserved / multicast and
  their IPv6 equivalents, including IPv4-mapped forms (`::ffff:127.0.0.1`).
- Re-validate after every redirect; cap the redirect count.
- Scheme allowlist: http/https only.
- Response size + read cap.

`SSRF_ALLOW_PRIVATE=1` is a dev-only escape hatch. It is auto-refused when
`PROXY_SHARED_SECRET` is set (the marker of a publicly reachable prod backend),
so a prod misconfig can't open egress.

Residual gap (logged in DECISIONS.md): we validate immediately before the
request but the HTTP/DB client re-resolves DNS itself, leaving a narrow TOCTOU
window against a same-host DNS-rebinding attacker. Pinning to the validated IP
isn't practical without breaking TLS SNI for legitimate https APIs.
"""
import ipaddress
import os
import socket
from urllib.parse import urlparse

import httpx

_MAX_REDIRECTS = 3
_MAX_BYTES = 50 * 1024 * 1024  # 50 MB — matches the upload cap.

# Belt-and-suspenders denylist: `not is_global` already covers these, but an
# explicit list makes the block version-robust across Python's periodic
# is_private/is_global registry revisions. Security control → redundancy earns
# its keep.
_BLOCKED = [ipaddress.ip_network(n) for n in (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8",
    "169.254.0.0/16", "172.16.0.0/12", "192.0.0.0/24", "192.168.0.0/16",
    "198.18.0.0/15", "224.0.0.0/4", "240.0.0.0/4",
    "::1/128", "::/128", "fc00::/7", "fe80::/10", "ff00::/8",
)]


class SSRFError(Exception):
    """A user-supplied URL/host that egress policy refuses to reach."""


def _allow_private() -> bool:
    return os.getenv("SSRF_ALLOW_PRIVATE") == "1" and not os.getenv("PROXY_SHARED_SECRET")


def _check_ip(ip_str: str) -> None:
    addr = ipaddress.ip_address(ip_str)
    # Unwrap IPv4-mapped IPv6 (::ffff:127.0.0.1) — a classic guard bypass.
    if addr.version == 6 and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    if _allow_private():
        return
    if not addr.is_global or any(addr in net for net in _BLOCKED):
        raise SSRFError(f"refusing to reach non-public address {addr}")


def validate_host(host: str | None, port: int = 0) -> None:
    """Resolve `host` and refuse if any resolved IP is non-public."""
    if not host:
        raise SSRFError("missing host")
    try:
        infos = socket.getaddrinfo(host, port or None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise SSRFError(f"could not resolve host {host!r}: {e}")
    for info in infos:
        _check_ip(info[4][0])


def validate_sql_host(connection_string: str) -> None:
    """Extract the host from a SQLAlchemy URL and validate it. Host-less
    drivers (sqlite) connect to a local file, not the network — that's a
    separate local-file concern, out of scope for the SSRF egress guard."""
    from sqlalchemy.engine import make_url
    try:
        url = make_url(connection_string)
    except Exception as e:
        raise SSRFError(f"unparseable connection string: {e}")
    if url.host is None:
        return  # ponytail: sqlite/local driver — see DECISIONS.md (LFI is separate).
    validate_host(url.host, url.port or 0)


def guarded_get(url: str, headers: dict | None = None, timeout: float = 30.0,
                transport: httpx.BaseTransport | None = None) -> httpx.Response:
    """GET with SSRF egress validation on the URL and every redirect hop.
    Redirects are followed manually so each Location is re-validated. Returns a
    fully-read httpx.Response (so `.raise_for_status()` / `.json()` work)."""
    headers = headers or {}
    hops = 0
    with httpx.Client(timeout=timeout, follow_redirects=False, transport=transport) as client:
        while True:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                raise SSRFError(f"scheme {parsed.scheme!r} not allowed (http/https only)")
            validate_host(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
            with client.stream("GET", url, headers=headers) as resp:
                if resp.is_redirect and resp.headers.get("location"):
                    hops += 1
                    if hops > _MAX_REDIRECTS:
                        raise SSRFError("too many redirects")
                    url = str(resp.url.join(resp.headers["location"]))
                    continue
                clen = resp.headers.get("content-length")
                if clen and clen.isdigit() and int(clen) > _MAX_BYTES:
                    raise SSRFError("response too large")
                total, chunks = 0, []
                for chunk in resp.iter_bytes():
                    total += len(chunk)
                    if total > _MAX_BYTES:
                        raise SSRFError("response too large")
                    chunks.append(chunk)
                return httpx.Response(resp.status_code, headers=resp.headers,
                                      content=b"".join(chunks), request=resp.request)
