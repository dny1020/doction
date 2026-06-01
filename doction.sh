#!/usr/bin/env bash
# doction — shell CLI for the doction REST API
#
# Configuration (set in your shell or .env):
#   DOCTION_URL    base URL of the doction instance  (default: http://localhost:8000)
#   DOCTION_TOKEN  Bearer JWT from `doction login`
#   DOCTION_WS     workspace slug                    (default: personal)
#
# Usage:
#   ./doction.sh login <email> <password>
#   ./doction.sh pages
#   ./doction.sh get   <slug>
#   ./doction.sh raw   <slug>               # raw markdown to stdout
#   ./doction.sh create "<title>" [file]    # file or stdin
#   ./doction.sh update <slug>  [file]      # file or stdin
#   ./doction.sh delete <slug>
#   ./doction.sh search "<query>"
#   ./doction.sh workspaces
#   ./doction.sh ws-create "<name>"

set -euo pipefail

URL="${DOCTION_URL:-http://localhost:8000}"
TOKEN="${DOCTION_TOKEN:-}"
WS="${DOCTION_WS:-personal}"

_require_token() {
  if [[ -z "$TOKEN" ]]; then
    echo "Error: DOCTION_TOKEN not set. Run: eval \$(./doction.sh login <email> <pass>)" >&2
    exit 1
  fi
}

_curl() {
  curl -sf -H "Authorization: Bearer $TOKEN" "$@"
}

_ws_param() { echo "ws=${WS}"; }

cmd="${1:-help}"; shift || true

case "$cmd" in

  login)
    email="${1:?Usage: doction login <email> <password>}"
    pass="${2:?Usage: doction login <email> <password>}"
    token=$(curl -sf -X POST "${URL}/api/token" \
      -H "Content-Type: application/json" \
      -d "{\"email\":$(printf '%s' "$email" | jq -Rs .),\"password\":$(printf '%s' "$pass" | jq -Rs .)}" \
      | jq -r '.token')
    echo "export DOCTION_TOKEN=${token}"
    ;;

  pages)
    _require_token
    _curl "${URL}/api/pages?$(_ws_param)" | jq '.[] | "\(.depth * 2 | " " * .) \(.title)  \(.slug)"' -r
    ;;

  get)
    slug="${1:?Usage: doction get <slug>}"
    _require_token
    _curl "${URL}/api/pages/${slug}?$(_ws_param)" | jq
    ;;

  raw)
    slug="${1:?Usage: doction raw <slug>}"
    _require_token
    _curl "${URL}/api/pages/${slug}/raw?$(_ws_param)"
    ;;

  create)
    title="${1:?Usage: doction create \"<title>\" [file|-]}"
    src="${2:--}"
    _require_token
    content=$(cat "$src")
    _curl -X POST "${URL}/api/pages?$(_ws_param)" \
      -H "Content-Type: application/json" \
      -d "{\"title\":$(printf '%s' "$title" | jq -Rs .),\"content\":$(printf '%s' "$content" | jq -Rs .)}" \
      | jq
    ;;

  update)
    slug="${1:?Usage: doction update <slug> [file|-]}"
    src="${2:--}"
    _require_token
    content=$(cat "$src")
    _curl -X PUT "${URL}/api/pages/${slug}?$(_ws_param)" \
      -H "Content-Type: application/json" \
      -d "{\"content\":$(printf '%s' "$content" | jq -Rs .)}" \
      | jq
    ;;

  delete)
    slug="${1:?Usage: doction delete <slug>}"
    _require_token
    _curl -X DELETE "${URL}/api/pages/${slug}?$(_ws_param)"
    echo "Deleted: ${slug}"
    ;;

  search)
    query="${1:?Usage: doction search \"<query>\"}"
    _require_token
    q=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$query")
    _curl "${URL}/api/search?q=${q}&$(_ws_param)" | jq '.[] | "\(.title)  /pages/\(.slug)"' -r
    ;;

  workspaces)
    _require_token
    _curl "${URL}/api/workspaces" | jq '.[] | "\(.slug)  \(.name)"' -r
    ;;

  ws-create)
    name="${1:?Usage: doction ws-create \"<name>\"}"
    _require_token
    _curl -X POST "${URL}/api/workspaces" \
      -H "Content-Type: application/json" \
      -d "{\"name\":$(printf '%s' "$name" | jq -Rs .)}" \
      | jq
    ;;

  help|*)
    cat <<'EOF'
doction — CLI for the doction REST API

Setup:
  export DOCTION_URL=https://doction.danilocloud.me
  eval $(./doction.sh login you@example.com yourpassword)

Commands:
  login <email> <pass>       Authenticate; prints export DOCTION_TOKEN=...
  pages                      List all pages as an indented tree
  get   <slug>               Get page metadata + children (JSON)
  raw   <slug>               Print raw markdown to stdout
  create "<title>" [file]    Create page from file or stdin
  update <slug>  [file]      Replace page content from file or stdin
  delete <slug>              Delete a page
  search "<query>"           Full-text search
  workspaces                 List workspaces
  ws-create "<name>"         Create a workspace

Env vars:
  DOCTION_URL    instance URL    (default: http://localhost:8000)
  DOCTION_TOKEN  Bearer JWT      (set via login)
  DOCTION_WS     workspace slug  (default: personal)

Examples:
  # Dump a runbook to a file
  ./doction.sh raw k8s-runbook > k8s-runbook.md

  # Create a page from a local markdown file
  ./doction.sh create "Ansible Playbook Notes" playbook.md

  # Pipe terraform plan output into a page
  terraform plan 2>&1 | ./doction.sh create "Plan $(date +%F)"

  # Update from stdin
  echo "# Updated\nNew content" | ./doction.sh update my-page

  # Search and open in browser
  ./doction.sh search "kubernetes" | head -1 | awk '{print $2}' | xargs -I{} xdg-open "$DOCTION_URL{}"
EOF
    ;;

esac
