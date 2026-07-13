#!/usr/bin/env bash
# Restore drill (Overnight Plan 2, 0i). A backup you have never restored is a
# hypothesis. This proves the real thing end to end, hermetically:
#   synthetic data/ (a conversation + a REAL encrypted API key)
#     → scripts/backup.sh → tarball
#     → restore to a scratch dir
#     → boot the storage+crypto layer against it
#     → assert: conversations LOAD and encrypted keys still DECRYPT.
#
# The decrypt step is the point: it validates the "SECRET_KEY travels WITH data/"
# invariant. A restore with the wrong key would fail here, loudly, not in prod.
#
#   make restore-test   (or)   ./scripts/restore-test.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
export SECRET_KEY="restore-drill-fixed-key"

SRC="$WORK/data"
mkdir -p "$SRC/conversations"
cat > "$SRC/conversations/c_demo.json" <<'JSON'
{"id":"c_demo","created_at":"2026-07-14T00:00:00Z","messages":[],"status":"complete","title":"Restore drill"}
JSON

# Write a users.json whose API key is encrypted by the app's OWN crypto.
uv run python - "$SRC/users.json" <<'PY'
import sys, json, os
os.environ["SECRET_KEY"] = "restore-drill-fixed-key"
from backend import crypto
enc = crypto.encrypt("sk-or-secret-value-123")
json.dump({"clerk_x": {"id": "u_x", "settings": {"openrouter_api_key": enc}}}, open(sys.argv[1], "w"))
PY

# Back up, then restore to a fresh dir.
DATA_DIR="$SRC" BACKUP_DIR="$WORK/backups" BACKUP_KEEP=1 "$ROOT/scripts/backup.sh"
ARCHIVE="$(ls -1t "$WORK/backups"/datavisual-*.tar.gz | head -1)"
REST="$WORK/restore"
mkdir -p "$REST"
tar -xzf "$ARCHIVE" -C "$REST"   # → $REST/data/...

# Boot the storage + crypto layer against the restored data and verify.
uv run python - "$REST/data" <<'PY'
import sys, os, json, pathlib
os.environ["SECRET_KEY"] = "restore-drill-fixed-key"
data = sys.argv[1]
from backend import storage, users, crypto
storage.DATA_DIR = os.path.join(data, "conversations")
users.USERS_PATH = pathlib.Path(os.path.join(data, "users.json"))

convs = storage.list_conversations()
assert any(c["id"] == "c_demo" for c in convs), f"conversation did not load: {convs}"

crypto._secret_cache = None
crypto.verify_key_decryptable()  # boot guard — raises if keys can't decrypt

u = json.load(open(users.USERS_PATH))
dec = crypto.decrypt(u["clerk_x"]["settings"]["openrouter_api_key"])
assert dec == "sk-or-secret-value-123", f"decrypt mismatch after restore: {dec!r}"
print("restore-test: PASS — conversations load AND encrypted keys decrypt after restore")
PY
