#!/usr/bin/env bash
# MODULE: luna-browse.sh - run one dev-auto Luna browser check through the Codex CLI
#
# luna-browse.sh PROJECT PROMPT OUTPUT ORIGIN [EFFORT]
# Luna (gpt-6-luna; max unless EFFORT names another) reads PROJECT read-only and drives a headless, isolated
# Playwright browser limited to ORIGIN, a loopback http origin the lead started.
# Only the listed browser tools are exposed (no script evaluation or file upload);
# they are pre-approved because approval_policy="never" refuses MCP calls otherwise.
# The origin filter misses redirects and page-initiated requests: synthetic data only.
# OUTPUT, a new file, receives Luna's answer; the ~/.codex/sessions rollout is the receipt.
# The owner's team is asked first (bmn roster check, models.md), from inside PROJECT as the
# check requires: OUTPUT.check.json, a new file too, keeps its answer, and a refusal launches
# nothing and exits with the check's own status.
set -euo pipefail
fail() { echo "luna-browse.sh: $*" >&2; exit 2; }
[[ $# -eq 4 || $# -eq 5 ]] || fail "usage: luna-browse.sh PROJECT PROMPT OUTPUT ORIGIN [EFFORT]"
project=$1 prompt=$2 output=$3 origin=$4 effort=${5:-max}
[[ $effort =~ ^(low|medium|high|xhigh|max)$ ]] || fail "EFFORT must be one the team lists for Luna, such as xhigh or max: $effort"
for path in "$project" "$prompt" "$output"; do [[ $path == /* ]] || fail "paths must be absolute: $path"; done
[[ -d $project && -f $prompt ]] || fail "PROJECT must be a directory and PROMPT a file"
[[ ! -e $output && ! -e $output.check.json ]] || fail "OUTPUT or its .check.json already exists; keep earlier receipts: $output"
# ORIGIN enters the TOML below unescaped: this pattern is what keeps quotes out.
[[ $origin =~ ^http://(127\.0\.0\.1|localhost|\[::1\]):([1-9][0-9]{0,4})$ ]] && (( BASH_REMATCH[2] <= 65535 )) \
  || fail "ORIGIN must be a loopback http origin such as http://127.0.0.1:3000: $origin"

tools=
for tool in navigate navigate_back snapshot click type fill_form select_option press_key \
            hover wait_for take_screenshot console_messages network_requests close; do
  tools+="${tools:+,}\"browser_$tool\""
done
server="{playwright={command=\"npx\",args=[\"--offline\",\"@playwright/mcp@0.0.75\",\"--headless\",\"--isolated\",\"--allowed-origins\",\"$origin\"],enabled_tools=[$tools],default_tools_approval_mode=\"approve\"}}"
command=(codex exec --skip-git-repo-check -C "$project" -m gpt-6-luna -c "model_reasoning_effort=$effort"
  -c "mcp_servers=$server" -c 'approval_policy="never"'
  --sandbox read-only --json -o "$output" -)
cd "$project"
status=0
bmn roster check --agent luna --role browser --workspace "$project" --data private --cwd "$project" \
  --stdin "$prompt" --json -- "${command[@]}" > "$output.check.json" || status=$?
if (( status != 0 )); then
  cat "$output.check.json" >&2
  echo "luna-browse.sh: the team check refused this run; nothing was launched" >&2
  exit "$status"
fi
exec "${command[@]}" < "$prompt" > /dev/null
