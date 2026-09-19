# Model and dispatch reference

These identifiers, supported effort values, and CLI options were verified locally
on 2026-09-17 and 2026-09-18. That does not prove every route completed a live call. Recheck
availability and inspect the actual receipt when practical; never claim a route or
effort level from the prompt alone. External CLIs require configured, authorized
access.

## Capability routing

Keep a suitable lead on the work. Dispatch only for a concrete independent task,
then choose one available route that meets its capability floor. The options in this
table are unordered: do not walk them as a ladder, pair providers by default, or
escalate after a sufficient result. Escalate only for a specific failed route,
unresolved uncertainty, or consequential risk.

| Work | Capability floor | Suitable routes (unordered) |
| --- | --- | --- |
| Codex lead | Strong implementation owner | `gpt-5.6-sol`, `xhigh` |
| Claude Code lead | Strong implementation owner | `opus`, `xhigh` |
| Routine review, bounded tests, easy isolated work | Reliable bounded worker | `GLM-5.3-Flash`, `max`; `gpt-5.6-luna`, `max`; `sonnet`, `low` or `medium` |
| Debugging assistance | Strong debugger with the relevant evidence | `GLM-5.3`, `max`; the lead directly |
| Whole-epic important risks and project alignment | Independent strong reasoner | `gpt-6-astra` or `fable`, `medium`; `low` for a bounded, well-evidenced question |
| Whole-project final evaluation or critical decision | Independent top-tier reasoner | `gpt-6-astra` or `fable`, `high` |

`fable` currently resolves to `claude-fable-5-1`. Codex currently supports Sol at
`xhigh`, Luna at `max`, and Astra at `low`, `medium`, or `high`.

Strong reviewers examine the original requirements, relevant source, raw evidence,
architecture, cross-story effects, omissions, and drift. Cheap helpers may collect
evidence or run routine checks, but their summaries are navigation aids rather than
acceptance proof.

## Native delegation

Prefer the host's native helper/task interface when available. Start a fresh bounded
task; give it exact source coordinates, allowed write scope, prohibited actions,
expected checks, and a required concise result. Keep overlapping writers serial.
Native permissions remain authoritative. Do not use bypass-permissions modes or
claim that prompt restrictions enforce access.

Separate read-only review from implementation and safe test work. A reviewer can
use native read tools or receive a deliberately prepared source packet. An
implementation helper uses native, suitably confined tools with only the workspace
access required by its owned files.

Observe the actual model, effort and usage from host records instead of guessing.
Codex writes every session, including `codex exec` runs and native helpers, to
`~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`, where `turn_context` payloads carry
`model` and `effort` and the last `token_count` payload carries cumulative
`total_token_usage`; Claude Code `-p --output-format json` receipts carry `modelUsage`
and `total_cost_usd`. `scripts/check.py usage PATH` prints these fields from one rollout or receipt; one
session's cumulative counter is that session's usage, not the epic's total. An
in-session helper with no receipt of its own is covered by the lead's record; list
the remainder under gaps. Record `unobservable` only when no
record exists, and never retry or dispatch another worker merely to discover it.

Wait for a helper with the longest timeout the host accepts (Codex accepted
360000 ms); a wait returns as soon as the helper finishes, and every timed-out wait
re-sends the lead context. Do independent work between waits.

## Direct CLI routes

Use these only when native delegation is unavailable or unsuitable and the user has
authorized the external provider. Set `PROJECT`, `PROMPT`, and `OUTPUT` to explicit,
task-specific paths. Use the project directly when its readable scope is appropriate;
otherwise set `PROJECT` to a prepared workspace containing only the required source
and evidence. Exclude credentials and unrelated private data, and keep `OUTPUT`
outside the tracked working tree.

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

For debugging, set `ANTHROPIC_DEFAULT_OPUS_MODEL=GLM-5.3` after sourcing and use
the `opus` alias at `max`. Do not import legacy the earlier workflow wrappers or agent
definitions.

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
