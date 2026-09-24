#!/usr/bin/env bash
# MODULE: helper.sh - run one dev-auto helper on the helper provider (currently Z.ai GLM)
#
# helper.sh review|edit fast|strong PROJECT PROMPT OUTPUT [CHECK]
#   review  reads files inside PROJECT (Read, Glob, Grep); never edits
#   edit    also edits files inside PROJECT
#   CHECK   the one exact shell command the helper may run in PROJECT, sandboxed without
#           network, e.g. 'python3 -m unittest -q'; it runs as written and may write
#           inside PROJECT
# Paths are absolute. OUTPUT, a new file, receives the Claude `-p --output-format json`
# receipt; read it with `check.py usage OUTPUT`.
#
# Switching provider: point PROFILE at the new provider's Claude Code env file, set
# FAST and STRONG to its model names, run tests/test_helper.py and one live probe
# (docs/verification.md). PROFILE holds credentials: never read, print or trace it.
set -euo pipefail
PROFILE="$HOME/.claude-glm/env.sh"
FAST=GLM-5.3-Flash
STRONG=GLM-5.3

fail() { echo "helper.sh: $*" >&2; exit 2; }
[[ $# -eq 5 || $# -eq 6 ]] || fail "usage: helper.sh review|edit fast|strong PROJECT PROMPT OUTPUT [CHECK]"
mode=$1 tier=$2 project=$3 prompt=$4 output=$5 check=${6:-}
case $mode in review|edit) ;; *) fail "mode must be review or edit: $mode" ;; esac
case $tier in fast) alias=sonnet ;; strong) alias=opus ;; *) fail "tier must be fast or strong: $tier" ;; esac
for path in "$project" "$prompt" "$output"; do [[ $path == /* ]] || fail "paths must be absolute: $path"; done
[[ -d $project && -f $prompt ]] || fail "PROJECT must be a directory and PROMPT a file"
[[ ! -e $output ]] || fail "OUTPUT already exists; keep earlier receipts: $output"
[[ $check != *$'\n'* && $check != *")"* ]] || fail "CHECK must be one line without ')'"

# Unscoped Read/Edit rules reach any path: on 2026-09-22 both GLM models wrote into
# another repository until every rule was scoped to the project and .env denied. The
# sandbox auto-approves any sandboxed command unless told not to: on 2026-09-24 a probe
# ran `cat ../outside.txt` past the one allowed check until autoAllowBashIfSandboxed
# was set to false.
tools=Read,Glob,Grep allow=("Read(./**)") deny=("Read(./**/.env*)" "Edit(./**/.env*)") extra=()
if [[ $mode == edit ]]; then tools+=,Edit,Write; allow+=("Edit(./**)"); fi
if [[ -n $check ]]; then
  tools+=,Bash; allow+=("Bash($check)")
  extra=(--settings '{"sandbox":{"enabled":true,"failIfUnavailable":true,"autoAllowBashIfSandboxed":false,"allowUnsandboxedCommands":false,"network":{"allowedDomains":[]}}}')
fi

cd "$project"
set +xu
. "$PROFILE" || exit 1
set -u
export ANTHROPIC_DEFAULT_SONNET_MODEL=$FAST ANTHROPIC_DEFAULT_OPUS_MODEL=$STRONG
exec claude -p --model "$alias" --effort max --output-format json --safe-mode \
  --tools "$tools" --allowedTools "${allow[@]}" --disallowedTools "${deny[@]}" \
  --permission-mode dontAsk --no-session-persistence --max-turns 80 \
  --strict-mcp-config --mcp-config '{"mcpServers":{}}' "${extra[@]}" \
  < "$prompt" > "$output"
