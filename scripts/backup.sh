#!/usr/bin/env bash
# Back up data/ — the entire "database". There is NO other copy.
#
#   ./scripts/backup.sh                     # → ./backups/datavisual-YYYYmmdd-HHMMSS.tar.gz
#   BACKUP_DIR=/mnt/backups ./scripts/backup.sh
#   BACKUP_S3_URI=s3://my-bucket/dvs ./scripts/backup.sh   # also upload (needs awscli)
#   BACKUP_KEEP=14 ./scripts/backup.sh      # keep the last N local archives (default 7)
#
# Cron (daily 03:15, keep 14, offsite to S3) — see DEPLOY_RUNBOOK.md:
#   15 3 * * * cd /path/to/datavisual.studio && BACKUP_KEEP=14 \
#     BACKUP_S3_URI=s3://bucket/dvs ./scripts/backup.sh >> /var/log/dvs-backup.log 2>&1
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="${DATA_DIR:-$ROOT/data}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
KEEP="${BACKUP_KEEP:-7}"

if [ ! -d "$DATA_DIR" ]; then
  echo "backup: no data/ directory at $DATA_DIR — nothing to back up" >&2
  exit 0
fi

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
ARCHIVE="$BACKUP_DIR/datavisual-$STAMP.tar.gz"

# -C so the archive contains data/… not the absolute path.
tar -czf "$ARCHIVE" -C "$(dirname "$DATA_DIR")" "$(basename "$DATA_DIR")"
echo "backup: wrote $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"

# Optional offsite copy.
if [ -n "${BACKUP_S3_URI:-}" ]; then
  if command -v aws >/dev/null 2>&1; then
    aws s3 cp "$ARCHIVE" "$BACKUP_S3_URI/$(basename "$ARCHIVE")"
    echo "backup: uploaded to $BACKUP_S3_URI/$(basename "$ARCHIVE")"
  else
    echo "backup: BACKUP_S3_URI set but awscli not found — skipped upload" >&2
  fi
fi

# Prune: keep the newest $KEEP local archives.
ls -1t "$BACKUP_DIR"/datavisual-*.tar.gz 2>/dev/null | tail -n +"$((KEEP + 1))" | while read -r old; do
  rm -f "$old"
  echo "backup: pruned $old"
done
