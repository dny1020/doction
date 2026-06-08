#!/usr/bin/env bash
# doction — shell CLI for the doction REST API. Run with no args for help.

set -euo pipefail

URL="${DOCTION_URL:-https://doction.danilocloud.me}"
TOKEN="${DOCTION_TOKEN:-}"
WS="${DOCTION_WS:-personal}"

_require_token() {
  if [[ -z "$TOKEN" ]]; then
    echo "Error: DOCTION_TOKEN not set. Run: eval \$(./doction.sh login <email> <pass>)" >&2
    exit 1
  fi
}

_curl() { curl -sf -H "Authorization: Bearer $TOKEN" "$@"; }

_urlencode() { jq -rn --arg v "$1" '$v | @uri'; }

cmd="${1:-help}"; shift || true

case "$cmd" in

  # ── Auth ────────────────────────────────────────────────────────────────────

  login)
    email="${1:?Usage: doction login <email> <password>}"
    pass="${2:?Usage: doction login <email> <password>}"
    response=$(curl -s -X POST "${URL}/api/token" \
      -H "Content-Type: application/json" \
      -d "{\"email\":$(printf '%s' "$email" | jq -Rs .),\"password\":$(printf '%s' "$pass" | jq -Rs .)}") || true
    if [[ -z "$response" ]]; then
      echo "Error: no response from ${URL} — is the server running? Set DOCTION_URL if needed." >&2
      exit 1
    fi
    token=$(printf '%s' "$response" | jq -r '.token // empty' 2>/dev/null) || true
    if [[ -z "$token" ]]; then
      detail=$(printf '%s' "$response" | jq -r '.detail // empty' 2>/dev/null) || true
      echo "Error: login failed — ${detail:-check credentials or server response}" >&2
      exit 1
    fi
    echo "export DOCTION_TOKEN=${token}"
    ;;

  # ── Workspaces ──────────────────────────────────────────────────────────────

  workspaces)
    _require_token
    _curl "${URL}/api/workspaces" | jq -r '.[] | "\(.slug)\t\(.name)"'
    ;;

  ws-create)
    name="${1:?Usage: doction ws-create \"<name>\"}"
    _require_token
    _curl -X POST "${URL}/api/workspaces" \
      -H "Content-Type: application/json" \
      -d "{\"name\":$(printf '%s' "$name" | jq -Rs .)}" | jq
    ;;

  # ── Pages ───────────────────────────────────────────────────────────────────

  pages)
    _require_token
    _curl "${URL}/api/pages?ws=${WS}" \
      | jq -r '.[] | ((" " * (.depth * 2)) + .title + "  [" + .slug + "]")'
    ;;

  get)
    slug="${1:?Usage: doction get <slug>}"
    _require_token
    _curl "${URL}/api/pages/${slug}?ws=${WS}" | jq
    ;;

  raw)
    slug="${1:?Usage: doction raw <slug>}"
    _require_token
    _curl "${URL}/api/pages/${slug}/raw?ws=${WS}"
    ;;

  create)
    title="${1:?Usage: doction create \"<title>\" [--parent <slug>] [file|-]}"
    shift
    parent=""
    src="-"
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --parent) parent="$2"; shift 2 ;;
        *)        src="$1";   shift   ;;
      esac
    done
    _require_token
    content=$(cat "$src")
    body=$(jq -n \
      --arg title   "$title" \
      --arg content "$content" \
      --arg parent  "$parent" \
      'if $parent != "" then {title: $title, content: $content, parent_slug: $parent}
       else {title: $title, content: $content} end')
    _curl -X POST "${URL}/api/pages?ws=${WS}" \
      -H "Content-Type: application/json" \
      -d "$body" | jq
    ;;

  update)
    slug="${1:?Usage: doction update <slug> [--title \"<title>\"] [file|-]}"
    shift
    new_title=""
    src="-"
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --title) new_title="$2"; shift 2 ;;
        *)       src="$1";       shift   ;;
      esac
    done
    _require_token
    content=$(cat "$src")
    body=$(jq -n \
      --arg content   "$content" \
      --arg new_title "$new_title" \
      'if $new_title != "" then {title: $new_title, content: $content}
       else {content: $content} end')
    _curl -X PUT "${URL}/api/pages/${slug}?ws=${WS}" \
      -H "Content-Type: application/json" \
      -d "$body" | jq
    ;;

  delete)
    slug="${1:?Usage: doction delete <slug>}"
    _require_token
    _curl -X DELETE "${URL}/api/pages/${slug}?ws=${WS}"
    echo "Deleted: ${slug}"
    ;;

  # ── Search ──────────────────────────────────────────────────────────────────

  search)
    query="${1:?Usage: doction search \"<query>\" [--mode fts|semantic|hybrid]}"
    shift
    mode="fts"
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --mode) mode="$2"; shift 2 ;;
        *)      shift ;;
      esac
    done
    _require_token
    q=$(_urlencode "$query")
    _curl "${URL}/api/search?q=${q}&mode=${mode}&ws=${WS}" \
      | jq -r '.[] | "\(.title)  [/pages/\(.slug)]"'
    ;;

  # ── Git versioning ──────────────────────────────────────────────────────────

  history)
    slug="${1:?Usage: doction history <slug>}"
    _require_token
    _curl "${URL}/api/pages/${slug}/history?ws=${WS}" \
      | jq -r '.[] | "\(.sha[0:7])  \(.timestamp)  \(.message)"'
    ;;

  at)
    slug="${1:?Usage: doction at <slug> <sha>}"
    sha="${2:?Usage: doction at <slug> <sha>}"
    _require_token
    _curl "${URL}/api/pages/${slug}/history/${sha}?ws=${WS}" | jq -r '.content'
    ;;

  # ── Help ────────────────────────────────────────────────────────────────────

  help|*)
    cat <<'EOF'
doction — CLI for the doction REST API

Structure: workspace → page → subpage

Setup:
  eval $(./doction.sh login you@example.com yourpassword)
  export DOCTION_WS=personal   # optional, default: personal

Commands:
  login <email> <pass>                     Authenticate; prints export DOCTION_TOKEN=...
  workspaces                               List workspaces
  ws-create "<name>"                       Create a workspace

  pages                                    List all pages as an indented tree
  get     <slug>                           Get page metadata + children (JSON)
  raw     <slug>                           Print raw markdown to stdout
  create  "<title>" [--parent <slug>] [file|-]   Create page from file or stdin
  update  <slug>    [--title "<title>"] [file|-]  Replace content (optionally rename)
  delete  <slug>                           Delete a page

  search  "<query>" [--mode fts|semantic|hybrid]  Search pages (default: fts)

  history <slug>                           Show git history for a page
  at      <slug> <sha>                     Print page content at a specific commit

Env vars:
  DOCTION_URL    instance URL     (default: https://doction.danilocloud.me)
  DOCTION_TOKEN  Bearer JWT       (set via login)
  DOCTION_WS     workspace slug   (default: personal)

Examples:
  # Dump a runbook to a file
  ./doction.sh raw k8s-runbook > k8s-runbook.md

  # Create a page from a local markdown file
  ./doction.sh create "Ansible Playbook Notes" playbook.md

  # Create a subpage under an existing page
  ./doction.sh create "BGP Tuning" --parent network-runbook bgp.md

  # Rename a page and update its content
  ./doction.sh update my-page --title "New Title" updated.md

  # Pipe terraform plan output into a page
  terraform plan 2>&1 | ./doction.sh create "Plan $(date +%F)"

  # Semantic search (uses local embeddings)
  ./doction.sh search "kubernetes deploy rollback" --mode hybrid

  # Show git history for a page
  ./doction.sh history k8s-runbook

  # Read the page as it was at a specific commit
  ./doction.sh at k8s-runbook a1b2c3d

  # Switch workspace
  DOCTION_WS=work ./doction.sh pages
EOF
    ;;

esac
