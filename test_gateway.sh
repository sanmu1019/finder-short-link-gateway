#!/usr/bin/env bash
set -euo pipefail

api_key="${FINDER_API_KEY:-}"
object_id="${1:-}"
nonce_id="${2:-}"
base_url="${FINDER_BASE_URL:-http://127.0.0.1:8790}"

if [[ -z "${api_key}" ]]; then
  echo "Set FINDER_API_KEY before running this script." >&2
  exit 1
fi
if [[ -z "${object_id}" || -z "${nonce_id}" ]]; then
  echo "Usage: FINDER_API_KEY=... $0 OBJECT_ID NONCE_ID" >&2
  exit 1
fi

curl --fail --silent --get \
  -H "X-API-Key: ${api_key}" \
  --data-urlencode "object_id=${object_id}" \
  --data-urlencode "object_nonce_id=${nonce_id}" \
  --data-urlencode "scene=40" \
  "${base_url}/api/v1/finder/share-url"
echo
