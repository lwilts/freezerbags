#!/usr/bin/env bash
# Restore FreezerBags' database from a daily backup.
#
#   ./restore.sh 2026-08-13
#
# Overwrites the LIVE database with that day's backup. Fetches the
# restore token live from the cluster (never stored in this repo), so
# this only works from a machine with kubectl access to the cluster.
set -euo pipefail

NAMESPACE="freezerbags"
SECRET_NAME="freezerbags-secrets"
URL="https://freezer.lab.lkwt.dev/internal/restore"

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 YYYY-MM-DD" >&2
  exit 1
fi
DATE="$1"

if ! [[ "$DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  echo "Error: date must be in YYYY-MM-DD form, got: $DATE" >&2
  exit 1
fi

TOKEN=$(kubectl -n "$NAMESPACE" get secret "$SECRET_NAME" -o jsonpath='{.data.RESTORE_TOKEN}' | base64 -d)
if [[ -z "$TOKEN" ]]; then
  echo "Error: could not fetch RESTORE_TOKEN from secret $SECRET_NAME in namespace $NAMESPACE" >&2
  exit 1
fi

echo "This will OVERWRITE the live FreezerBags database with the backup from $DATE."
read -p "Continue? [y/N] " -r REPLY
if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 1
fi

HTTP_CODE=$(curl -s -o /tmp/freezerbags-restore-response.json -w '%{http_code}' \
  -X POST "$URL" \
  -H "X-Restore-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"date\": \"$DATE\"}")

BODY=$(cat /tmp/freezerbags-restore-response.json)
rm -f /tmp/freezerbags-restore-response.json

if [[ "$HTTP_CODE" == "200" ]]; then
  echo "Restored: $BODY"
else
  echo "Restore failed (HTTP $HTTP_CODE): $BODY" >&2
  exit 1
fi
