#!/bin/bash

# Send a write request to the API signed with WEBHOOK_SHARED_SECRET.
#
# The review write endpoints accept either a user token or a request whose body
# is signed with the shared secret, so a machine caller with no user account
# uses this instead of a bare `curl`.
#
# usage: webhook_curl.sh <METHOD> <PATH> [JSON_BODY]
#
# environment:
#   WEBHOOK_SHARED_SECRET  secret configured on the server (required)
#   API_BASE               default http://127.0.0.1:8000
#
# example:
#   WEBHOOK_SHARED_SECRET=... ./scripts/webhook_curl.sh POST /api/v1/reviews '{
#     "pull_request_id": "PR-1",
#     "project_key": "PROJ",
#     "repository_slug": "my-repo",
#     "source_branch": "feature/x",
#     "target_branch": "main"
#   }'

set -euo pipefail

if [ $# -lt 2 ]; then
  echo "usage: $(basename "$0") <METHOD> <PATH> [JSON_BODY]" >&2
  exit 2
fi

method=$1
path=$2
body=${3:-}

: "${WEBHOOK_SHARED_SECRET:?set WEBHOOK_SHARED_SECRET to the secret configured on the server}"
api_base=${API_BASE:-http://127.0.0.1:8000}

# The server signs "<timestamp>.<raw body>" with HMAC-SHA256. Keep the body byte
# for byte: --data-binary sends it unchanged, so a trailing newline added by a
# shell variable would invalidate the signature.
timestamp=$(date +%s)
signature=$(
  printf '%s' "$timestamp.$body" |
    openssl dgst -sha256 -hmac "$WEBHOOK_SHARED_SECRET" |
    awk '{print $NF}'
)

payload=()
if [ -n "$body" ]; then
  payload=(--data-binary "$body")
fi

curl -sS -X "$method" "${api_base}${path}" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Timestamp: $timestamp" \
  -H "X-Webhook-Signature: sha256=$signature" \
  ${payload[@]+"${payload[@]}"}
