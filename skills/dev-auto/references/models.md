# Model and dispatch reference

These identifiers, supported effort values, and CLI options were verified locally
on 2026-09-17 and 2026-09-18. That does not prove every route completed a live call. Recheck
availability and inspect the actual receipt when practical; never claim a route or
effort level from the prompt alone. External CLIs require configured, authorized
access.

## Capability routing

Keep a suitable lead on the work. Dispatch only for a concrete independent task.
Each row is an ordered tier: start with the first route, and move to the next only
for a specific failed or unavailable route, a result that leaves the question
unresolved, or a task the first route cannot do. Review and analysis rows use the
tools-disabled GLM command; Implement rows use the edit-capable GLM command below,
confined to the helper's project directory. A sufficient result at the
tier in use ends the dispatch; never run the next tier as a ceremony or pair
providers by default. Record the tier actually used and the reason for any escalation.

| Work | First route | Escalation, in order |
| --- | --- | --- |
| Codex lead | `gpt-5.6-sol`, `xhigh` | Keep the current lead when it is already suitable |
| Claude Code lead | `opus`, `xhigh` | Keep the current lead when it is already suitable |
| Routine: review, bounded tests, read-only analysis (most dispatches) | `GLM-5.3-Flash`, `max`, via the Claude GLM profile | `gpt-5.6-luna`, `max`; then `sonnet`, `low` or `medium` |
| Complex bounded: debugging, a hard focused review, one consequential boundary short of a whole epic | `GLM-5.3`, `max`, via the Claude GLM profile | `gpt-6-astra`, `low`; or the lead directly when dispatch adds no value |
| Implement: an easy isolated change that edits files | `GLM-5.3-Flash`, `max`, via the edit-capable GLM route | `gpt-5.6-luna`, `max`; then `sonnet`, `medium`; or the lead directly |
| Implement-complex: a consequential bounded change that edits files | `GLM-5.3`, `max`, via the edit-capable GLM route | `gpt-6-astra`, `low`; or the lead directly |
| Whole-epic important risks and project alignment | `gpt-6-astra`, `medium` | `fable`, `medium`. `gpt-6-astra`, `low` only for a focused follow-up on a well-evidenced question |
| Whole-project final evaluation or critical decision | `gpt-6-astra`, `high` | `fable`, `high` |

`fable` currently resolves to `claude-fable-5-1`. Codex currently supports Sol at
`xhigh`, Luna at `max`, and Astra at `low`, `medium`, or `high`. GLM routes run
through the Claude CLI with the configured GLM profile whichever host leads; that
is their normal path, not a fallback, and being absent from a host's native model
list does not make them unavailable. When Claude Code leads, strong reviews use
the Codex Astra CLI route below; Fable follows through the Claude CLI with explicit `--effort` only after the Astra
route has a recorded reason for escalation. Record requested and observed effort
separately.

Strong reviewers examine the original requirements, relevant source, raw evidence,
architecture, cross-story effects, omissions, and drift. Cheap helpers may collect
evidence or run routine checks, but their summaries are navigation aids rather than
acceptance proof.

## Delegation

Start a fresh bounded task; give it exact source coordinates, allowed write scope,
prohibited actions, expected checks, and a required concise result. Keep overlapping
writers serial. Host permissions remain authoritative. Do not use bypass-permissions modes or
claim that prompt restrictions enforce access.

Separate read-only review from implementation and safe test work. A reviewer can
use read tools or receive a deliberately prepared source packet. An implementation
helper uses suitably confined tools with only the workspace access required by its
owned files.

Observe the actual model, effort and usage from host records instead of guessing.
Codex writes every session, including `codex exec` runs and native helpers, to
`~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`, where `turn_context` payloads carry
`model` and `effort` and the last `token_count` payload carries cumulative
`total_token_usage`; Claude Code `-p --output-format json` receipts carry `modelUsage`
and `total_cost_usd`. Claude Code writes the lead session and each native helper as separate transcripts
under `~/.claude/projects/<project>/` (`<session>.jsonl`, `subagents/agent-*.jsonl`).
`scripts/check.py usage PATH` prints these fields from one rollout, transcript or
receipt: for a transcript it keeps the final usage of each API response and sums by
model; one session's counter is that session's usage, not the epic's total. Read
lead and helper files separately, and never add a session-cumulative cost record to
the worker costs it already includes. List helpers with no record under gaps. Record `unobservable` only when no
record exists, and never retry or dispatch another worker merely to discover it.

Wait for a helper with the longest timeout the host accepts (Codex accepted
360000 ms); a wait returns as soon as the helper finishes, and every timed-out wait
re-sends the lead context. Poll a running command the same way, with the longest
yield the host accepts (Codex accepted 30000 ms), never one-second polls. Do
independent work between waits.

## Direct CLI routes

Use these when the host's native interface cannot deliver the selected model,
effort or required access (every GLM route, and cross-provider routes), under
existing provider authorization. Set `PROJECT`, `PROMPT`, and `OUTPUT` to explicit,
task-specific paths. Use the project directly when its readable scope is appropriate;
otherwise set `PROJECT` to a prepared workspace containing only the required source
and evidence. Exclude credentials and unrelated private data, and keep `OUTPUT`
outside the tracked working tree.

A Codex lead's workspace sandbox has no network and blocks some local sockets:
Claude CLI and GLM routes fail with `EAI_AGAIN`, and test gates using Git, sockets or
a browser fail with `EPERM` or hang. Run those commands escalated from the first
attempt (`sandbox_permissions: "require_escalated"`), with a justification naming the
destination, the payload class and the owner's dev-auto request. A sandbox failure is
not a route failure: retry the same tier escalated, not the next tier. When the
approval reviewer refuses, never work around it; ask the owner as SKILL.md describes.

Read-only Codex review:

```bash
codex exec --skip-git-repo-check -C "$PROJECT" \
  -m gpt-6-astra -c model_reasoning_effort=medium -c 'mcp_servers={}' \
  --sandbox read-only --json -o "$OUTPUT" - < "$PROMPT"
```

`--ephemeral` is deliberately omitted: the `--json` output names neither model nor
usage, so the persisted rollout file is the receipt. Checked 2026-09-18 against
`codex exec --help` only, not a live run; confirm on the first live run that the
rollout appears with model and usage. The reviewer can still run read-only shell commands inside the sandbox; `-C` and
read-only do not create a read allowlist or scrub the environment. Use this route
only when its remaining host read scope is acceptable. The `mcp_servers={}`
override drops globally configured MCP servers for that run.

Authorized Codex implementation uses the real project path with the selected
model/effort and `--sandbox workspace-write`. The sandbox and host policy, not the
prompt, define its actual access.

Tools-disabled Claude review from a prepared source packet:

```bash
claude -p --model fable --effort medium --output-format json \
  --tools '' --permission-mode dontAsk --safe-mode --no-session-persistence \
  --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
  < "$PROMPT" > "$OUTPUT"
```

The configured GLM profile is `~/.claude-glm/env.sh`. It contains credentials: do
not read, print, copy, or trace it. The CLI accepts these provider model names
through Claude aliases, so set the non-secret alias values explicitly after sourcing
the profile and inspect the receipt for the actual model. A tools-disabled routine
review is:

```bash
(
  set +x
  source "$HOME/.claude-glm/env.sh" || exit 1
  export ANTHROPIC_DEFAULT_SONNET_MODEL=GLM-5.3-Flash
  claude -p --model sonnet --effort max --output-format json \
    --tools '' --permission-mode dontAsk --safe-mode --no-session-persistence \
    --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
  < "$PROMPT" > "$OUTPUT"
)
```

Wait for the terminal receipt: this route can emit an early
`unrecognized_model` diagnostic and still complete successfully.

For the complex bounded tier (debugging, a hard focused review), set
`ANTHROPIC_DEFAULT_OPUS_MODEL=GLM-5.3` after sourcing and use the `opus` alias at
`max` in the same command shape. Do not import legacy the earlier workflow wrappers or agent
definitions.

Edit-capable GLM implementation (the Implement rows; for Implement-complex use the
`opus` alias with `ANTHROPIC_DEFAULT_OPUS_MODEL=GLM-5.3`). Set `PROJECT` to the
directory the helper owns. Scope every file rule: unscoped `Read` or `Write` rules
reach any path, and on 2026-09-22 both GLM models wrote outside their folder until
the rules below replaced them. `Edit(...)` also governs `Write`, and `Read(...)`
also governs `Glob` and `Grep`. Deny the project's secret files explicitly, and
make the `Bash` rule the exact check the helper may run.

```bash
(
  set +x
  cd "$PROJECT" || exit 1
  source "$HOME/.claude-glm/env.sh" || exit 1
  export ANTHROPIC_DEFAULT_SONNET_MODEL=GLM-5.3-Flash
  claude -p --model sonnet --effort max --output-format json \
    --safe-mode --tools 'Read,Edit,Write,Glob,Grep,Bash' \
    --allowedTools 'Read(./**)' 'Edit(./**)' 'Bash(python3 -m unittest -q)' \
    --disallowedTools 'Read(./**/.env*)' 'Edit(./**/.env*)' \
    --permission-mode dontAsk --no-session-persistence \
    --strict-mcp-config --mcp-config '{"mcpServers":{}}' --max-turns 40 \
    --settings '{"sandbox":{"enabled":true,"failIfUnavailable":true,"allowUnsandboxedCommands":false,"network":{"allowedDomains":[]}}}' \
    < "$PROMPT" > "$OUTPUT"
)
```

Exercised 2026-09-22 on a synthetic project with both GLM models: each fixed the
defect and ran its test, and writes, reads and greps outside
`PROJECT` plus reads and edits of its `.env` were denied and listed in the
receipt's `permission_denials`. Real-project implementation quality is not yet
measured.

## Browser-enabled review

Reviews run without a browser by default. Use these variants only for a named UI
acceptance question with lead-supplied local URLs; the lead starts and stops the
app. Set `ORIGIN` to that origin (for example `http://127.0.0.1:3000`). Earlier variants
were exercised on 2026-09-18: the reviewer read a local page and another origin was
blocked. The subsequent Codex server-clearing change has configuration-only proof;
its live browser dispatch remains UNVERIFIED (see `docs/verification.md` in the checkout).
Playwright's origin filter is a
convenience, not a security boundary: it does not cover redirects, and a local
page can itself call remote APIs, so never point a reviewer at production and
supply no production credentials or personal browser profile. Browser actions can
mutate test data even though the shell stays read-only.

Codex, invocation-local MCP (no global registration; the routine route above stays
browser-free):

```bash
codex exec --skip-git-repo-check -C "$PROJECT" \
  -m gpt-6-astra -c model_reasoning_effort=medium --sandbox read-only --json \
  -c 'mcp_servers={}' \
  -c 'mcp_servers.playwright.command="npx"' \
  -c "mcp_servers.playwright.args=[\"--offline\",\"@playwright/mcp@0.0.75\",\"--headless\",\"--isolated\",\"--allowed-origins\",\"$ORIGIN\"]" \
  -o "$OUTPUT" - < "$PROMPT"
```

Under `--sandbox read-only` the shell has no network, but the MCP server runs
outside the sandbox and can reach the local app. Clear configured servers before
adding Playwright. On first use or after integration changes, inspect the reviewer's
available tools, including plugins; only the intended MCP tools should be available.

Claude (`--tools ''` keeps built-ins off but leaves MCP tools available; do not
add `--safe-mode`, which disables MCP servers):

```bash
claude -p --model fable --effort medium --output-format json \
  --tools '' --permission-mode dontAsk --no-session-persistence \
  --strict-mcp-config --mcp-config "{\"mcpServers\":{\"playwright\":{\"command\":\"npx\",\"args\":[\"--offline\",\"@playwright/mcp@0.0.75\",\"--headless\",\"--isolated\",\"--allowed-origins\",\"$ORIGIN\"]}}}" \
  --allowedTools 'mcp__playwright__browser_navigate,mcp__playwright__browser_snapshot,mcp__playwright__browser_click,mcp__playwright__browser_type,mcp__playwright__browser_fill_form,mcp__playwright__browser_take_screenshot,mcp__playwright__browser_console_messages,mcp__playwright__browser_close' \
  < "$PROMPT" > "$OUTPUT"
```

`--allowedTools` is variadic: keep it before the stdin redirection and never
follow it with a positional prompt. Inspect the response/receipt for the actual model, effort, errors,
and limitations, and record those facts in the handoff.

For bounded test work, this route was exercised with a scoped working directory,
Claude's native sandbox, no network, and one exact allowed command. Keep `PROJECT`,
`PROMPT`, and `OUTPUT` absolute; change the command only when that different check
falls within the authorized task, and make `--allowedTools` match it exactly.

```bash
(
  set +x
  cd "$PROJECT" || exit 1
  source "$HOME/.claude-glm/env.sh" || exit 1
  export ANTHROPIC_DEFAULT_SONNET_MODEL=GLM-5.3-Flash
  claude -p --model sonnet --effort max --output-format json \
    --safe-mode --tools Bash \
    --allowedTools 'Bash(python3 -m unittest discover -s tests -v)' \
    --permission-mode dontAsk --no-session-persistence \
    --strict-mcp-config --mcp-config '{"mcpServers":{}}' --max-turns 8 \
    --settings '{"sandbox":{"enabled":true,"failIfUnavailable":true,"allowUnsandboxedCommands":false,"network":{"allowedDomains":[]}}}' \
    < "$PROMPT" > "$OUTPUT"
)
```
