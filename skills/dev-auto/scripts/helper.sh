#!/usr/bin/env bash
# MODULE: helper.sh - run one dev-auto helper on the helper provider (Z.ai GLM, deactivated since 2026-09-30; see models.md)
#
# helper.sh review|edit fast|strong PROJECT PROMPT OUTPUT
# helper.sh browse fast|strong PROJECT PROMPT OUTPUT ORIGIN
#   review  reads files inside PROJECT (Read, Glob, Grep); never edits
#   edit    also edits files inside PROJECT
#   browse  reads files inside PROJECT and drives a headless, isolated Playwright
#           browser limited to ORIGIN, a loopback http origin the lead started
# No mode runs shell commands: the lead runs checks. Shell execution can read outside
# PROJECT and expose inherited environment values, even through an exact command in
# Claude's networkless sandbox. Paths are absolute. OUTPUT, a new file, receives the
# Claude `-p --output-format json` receipt; read it with `check.py usage OUTPUT`.
#
# Switching provider: point PROFILE at the new provider's Claude Code env file, set
# FAST and STRONG to its model names, run tests/test_helper.py and one live probe
# (docs/verification.md). PROFILE holds credentials: never read, print or trace it.
set -euo pipefail
PROFILE="$HOME/.claude-glm/env.sh"
FAST=GLM-5.3-Flash
STRONG=GLM-5.3

fail() { echo "helper.sh: $*" >&2; exit 2; }
usage="usage: helper.sh review|edit fast|strong PROJECT PROMPT OUTPUT, or browse fast|strong PROJECT PROMPT OUTPUT ORIGIN"
case ${1:-} in review|edit) want=5 ;; browse) want=6 ;; *) fail "$usage" ;; esac
[[ $# -eq $want ]] || fail "$usage"
mode=$1 tier=$2 project=$3 prompt=$4 output=$5 origin=${6:-}
case $tier in fast) alias=sonnet ;; strong) alias=opus ;; *) fail "tier must be fast or strong: $tier" ;; esac
for path in "$project" "$prompt" "$output"; do [[ $path == /* ]] || fail "paths must be absolute: $path"; done
[[ -d $project && -f $prompt ]] || fail "PROJECT must be a directory and PROMPT a file"
[[ ! -e $output ]] || fail "OUTPUT already exists; keep earlier receipts: $output"
# --safe-mode and --restricted skip CLAUDE.md, so pass the owner's global rules
# explicitly, as Codex helpers read them from AGENTS.md.
rules=$HOME/.claude/CLAUDE.md
[[ -r $rules ]] || fail "global rules unreadable: $rules"

# Unscoped Read/Edit rules reach any path: on 2026-09-22 both GLM models wrote into
# another repository until every rule was scoped to the project and .env denied. A
# 2026-09-24 exact-check probe still read a sibling file and inherited environment
# values. File-tool rules do not constrain shell code; do not expose Bash here.
tools=Read,Glob,Grep allow=("Read(./**)") deny=("Read(./**/.env*)" "Edit(./**/.env*)")
isolation=(--safe-mode --strict-mcp-config --mcp-config '{"mcpServers":{}}')
if [[ $mode == edit ]]; then tools+=,Edit,Write; allow+=("Edit(./**)"); fi
if [[ $mode == browse ]]; then
  # Loopback only: never point a helper at production or a remote site. The origin
  # filter misses redirects and page-initiated requests, so it is not a security
  # boundary. --safe-mode would disable MCP; --restricted ignores settings files,
  # removes code-running tools and confines file tools to the working directory.
  [[ $origin =~ ^http://(127\.0\.0\.1|localhost|\[::1\]):([1-9][0-9]{0,4})$ ]] && (( BASH_REMATCH[2] <= 65535 )) \
    || fail "ORIGIN must be a loopback http origin such as http://127.0.0.1:3000: $origin"
  # ORIGIN enters the JSON below unescaped: this pattern is what keeps quotes out.
  server="{\"mcpServers\":{\"playwright\":{\"command\":\"npx\",\"args\":[\"--offline\",\"@playwright/mcp@0.0.75\",\"--headless\",\"--isolated\",\"--allowed-origins\",\"$origin\"]}}}"
  isolation=(--restricted --strict-mcp-config --mcp-config "$server")
  for tool in navigate navigate_back snapshot click type fill_form select_option press_key \
              hover wait_for take_screenshot console_messages network_requests close; do
    allow+=("mcp__playwright__browser_$tool")
  done
fi

cd "$project"
set +xu
. "$PROFILE" || exit 1
set -u
export ANTHROPIC_DEFAULT_SONNET_MODEL=$FAST ANTHROPIC_DEFAULT_OPUS_MODEL=$STRONG
exec claude -p --model "$alias" --effort max --output-format json "${isolation[@]}" \
  --append-system-prompt "$(<"$rules")" \
  --tools "$tools" --allowedTools "${allow[@]}" --disallowedTools "${deny[@]}" \
  --permission-mode dontAsk --no-session-persistence --max-turns 80 \
  < "$prompt" > "$output"
