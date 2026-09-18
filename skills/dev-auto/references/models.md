# Model and dispatch reference

These identifiers, supported effort values, and CLI options were verified locally
on 2026-09-17 and 2026-09-18. That does not prove every route completed a live call. Recheck
availability and inspect the actual receipt when practical; never claim a route or
effort level from the prompt alone. External CLIs require configured, authorized
access.

## Roles

| Work | Preferred route | Fallback or alternative |
| --- | --- | --- |
| Codex lead | `gpt-5.6-sol`, `xhigh` | Keep the current lead when it is already suitable |
| Claude Code lead | `opus`, `xhigh` | Keep the current lead when it is already suitable |
| Routine review, bounded tests, easy isolated work | `GLM-5.3-Flash`, `max`, via the Claude GLM profile | `gpt-5.6-luna`, `max`; then `sonnet`, `low` or `medium` |
| Debugging assistance | `GLM-5.3`, `max`, via the Claude GLM profile | The lead diagnoses directly when dispatch adds no value |
| Whole-epic important risks and project alignment | `gpt-6-astra`, `medium` | `fable`, `medium`; use `low` for a bounded, well-evidenced question |
| Whole-project final evaluation or critical decision | `gpt-6-astra`, `high` | `fable`, `high` |

`fable` currently resolves to `claude-fable-5-1`. Astra then Fable is an
escalation/fallback tier, not a mandatory pair. Do not call Fable after a sufficient
Astra result merely to complete a ceremony. Codex currently supports Sol at `xhigh`,
Luna at `max`, and Astra at `low`, `medium`, or `high`.

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
access required by its owned files. When the actual model is not observable, record
`unobservable`; do not retry or dispatch another worker merely to discover it.

## Direct CLI routes

Use these only when native delegation is unavailable or unsuitable and the user has
authorized the external provider. Set `PROJECT`, `PROMPT`, and `OUTPUT` to explicit,
task-specific paths. Never include credentials or unrelated private data.

Read-only Codex review:

```bash
codex exec --skip-git-repo-check --ephemeral -C "$PROJECT" \
  -m gpt-6-astra -c model_reasoning_effort=medium -c 'mcp_servers={}' \
  --sandbox read-only --json -o "$OUTPUT" - < "$PROMPT"
```

The reviewer can still run read-only shell commands inside the sandbox; the
`mcp_servers={}` override drops any globally configured MCP servers for that run.

Authorized Codex implementation uses the same form with the selected model/effort
and `--sandbox workspace-write`. The sandbox and host policy, not the prompt, define
its actual access.

Tools-disabled Claude review from a prepared source packet:

```bash
claude -p --model fable --effort medium --output-format json \
  --tools '' --permission-mode dontAsk --safe-mode --no-session-persistence \
  --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
  < "$PROMPT" > "$OUTPUT"
```

The configured GLM profile is `~/.claude-glm/env.sh`. It contains credentials: do
not read, print, copy, or trace it. A tools-disabled routine review is:

```bash
(
  set +x
  source "$HOME/.claude-glm/env.sh" || exit 1
  claude -p --model GLM-5.3-Flash --effort max --output-format json \
    --tools '' --permission-mode dontAsk --safe-mode --no-session-persistence \
    --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
    < "$PROMPT" > "$OUTPUT"
)
```

Use `GLM-5.3` at `max` for debugging. Do not import legacy the earlier workflow wrappers or
agent definitions.

## Browser-enabled review

Reviews run without a browser by default. Use these variants only for a named UI
acceptance question with lead-supplied local URLs; the lead starts and stops the
app. Set `ORIGIN` to that origin (for example `http://127.0.0.1:3000`). Both were
exercised on 2026-09-18 against a local page: the reviewer read the page, and a
navigation to another origin was blocked. Playwright's origin filter is a
convenience, not a security boundary: it does not cover redirects, and a local
page can itself call remote APIs, so never point a reviewer at production and
supply no production credentials or personal browser profile. Browser actions can
mutate test data even though the shell stays read-only.

Codex, invocation-local MCP (no global registration; the routine route above stays
browser-free):

```bash
codex exec --skip-git-repo-check --ephemeral -C "$PROJECT" \
  -m gpt-6-astra -c model_reasoning_effort=medium --sandbox read-only --json \
  -c 'mcp_servers.playwright.command="npx"' \
  -c "mcp_servers.playwright.args=[\"--offline\",\"@playwright/mcp@0.0.75\",\"--headless\",\"--isolated\",\"--allowed-origins\",\"$ORIGIN\"]" \
  -o "$OUTPUT" - < "$PROMPT"
```

Under `--sandbox read-only` the shell has no network, but the MCP server runs
outside the sandbox and can reach the local app.

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
  claude -p --model GLM-5.3-Flash --effort max --output-format json \
    --safe-mode --tools Bash \
    --allowedTools 'Bash(python3 -m unittest discover -s tests -v)' \
    --permission-mode dontAsk --no-session-persistence \
    --strict-mcp-config --mcp-config '{"mcpServers":{}}' --max-turns 8 \
    --settings '{"sandbox":{"enabled":true,"failIfUnavailable":true,"allowUnsandboxedCommands":false,"network":{"allowedDomains":[]}}}' \
    < "$PROMPT" > "$OUTPUT"
)
```
