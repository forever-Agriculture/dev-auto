#!/usr/bin/env bash
# MODULE: helper.sh - run one dev-auto helper on the helper provider (currently Z.ai GLM)
#
# helper.sh review|edit fast|strong PROJECT PROMPT OUTPUT
#   review  reads files inside PROJECT (Read, Glob, Grep); never edits
#   edit    also edits files inside PROJECT
# The lead runs checks. Shell execution can read outside PROJECT and expose inherited
# environment values, even through an exact command in Claude's networkless sandbox.
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
[[ $# -eq 5 ]] || fail "usage: helper.sh review|edit fast|strong PROJECT PROMPT OUTPUT"
mode=$1 tier=$2 project=$3 prompt=$4 output=$5
case $mode in review|edit) ;; *) fail "mode must be review or edit: $mode" ;; esac
case $tier in fast) alias=sonnet ;; strong) alias=opus ;; *) fail "tier must be fast or strong: $tier" ;; esac
for path in "$project" "$prompt" "$output"; do [[ $path == /* ]] || fail "paths must be absolute: $path"; done
[[ -d $project && -f $prompt ]] || fail "PROJECT must be a directory and PROMPT a file"
[[ ! -e $output ]] || fail "OUTPUT already exists; keep earlier receipts: $output"

# Unscoped Read/Edit rules reach any path: on 2026-09-22 both GLM models wrote into
# another repository until every rule was scoped to the project and .env denied. A
# 2026-09-24 exact-check probe still read a sibling file and inherited environment
# values. File-tool rules do not constrain shell code; do not expose Bash here.
tools=Read,Glob,Grep allow=("Read(./**)") deny=("Read(./**/.env*)" "Edit(./**/.env*)")
if [[ $mode == edit ]]; then tools+=,Edit,Write; allow+=("Edit(./**)"); fi

cd "$project"
set +xu
. "$PROFILE" || exit 1
set -u
export ANTHROPIC_DEFAULT_SONNET_MODEL=$FAST ANTHROPIC_DEFAULT_OPUS_MODEL=$STRONG
exec claude -p --model "$alias" --effort max --output-format json --safe-mode \
  --tools "$tools" --allowedTools "${allow[@]}" --disallowedTools "${deny[@]}" \
  --permission-mode dontAsk --no-session-persistence --max-turns 80 \
  --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
  < "$prompt" > "$output"
