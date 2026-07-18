# Security Policy

## Reporting a vulnerability

Please report security issues **privately** — do not open a public issue.

- Use GitHub's [private vulnerability reporting](https://github.com/4mohdisa/datavisual.studio/security/advisories/new)
  (Security tab → "Report a vulnerability"), or
- email **mohdisa233@gmail.com** with the details and, if possible, a proof of concept.

You'll get an acknowledgement within a few days. Please give a reasonable window to fix before any
public disclosure.

## Scope & known boundaries

The [README's "Known limitations"](README.md#known-limitations) and
[ARCHITECTURE.md](ARCHITECTURE.md) state the security model plainly, including boundaries that are
**by design** (single replica, `data/` is the only copy, `SECRET_KEY` travels with `data/`) and
known follow-ups (SQLite/file connector URLs, the SSRF guard's DNS-rebinding TOCTOU window). Reports
about those are welcome, but they're already documented rather than hidden.

Especially interested in: authentication/ownership bypass, the public share allowlist leaking an
owner-only field, path traversal via ids, SSRF through the connector, and anything that lets one
user reach another user's data.
