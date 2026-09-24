# Model and dispatch reference

These identifiers, supported effort values, and CLI options were verified locally
on 2026-09-17 and 2026-09-18, the `gpt-6` IDs on 2026-09-24. That does not prove
every route completed a live call. Recheck availability and inspect the actual
receipt when practical; never claim a route or effort level from the prompt alone.
External CLIs require configured, authorized access.

## Capability routing

Keep a suitable lead on the work. Dispatch only for a concrete independent task.
Each row is an ordered tier: start with the first route, and move to the next only
for a specific failed or unavailable route, a result that leaves the question
unresolved, or a task the first route cannot do. A sufficient result at the tier in
use ends the dispatch; never run the next tier as a ceremony. Record the route used
and the reason for any escalation.

Helper routes run on the helper provider through `scripts/helper.sh`
(below), with a `fast` or `strong` model, whichever host leads; that is their normal
path, not a fallback. Dispatch for required independent review, substantial bounded
work whose saved lead effort or elapsed time justifies coordination, or an unresolved
decision; each dispatch adds several lead turns over its current context. Do small
lookups and simple check commands directly, and overlap helpers with independent
work where possible.

| Work | First route | Escalation, in order |
| --- | --- | --- |
| Codex lead | `gpt-6-sol`, `xhigh` | Keep the current lead when it is already suitable |
| Claude Code lead | `opus`, `xhigh` | Keep the current lead when it is already suitable |
| Routine: evidence gathering, bounded test runs and triage, checklist rechecks | helper `fast` | `gpt-6-luna`, `max`; then `sonnet`, `low` or `medium` |
| Complex bounded: debugging, open-ended code, story or diff review, consequential boundary analysis | helper `strong` | `gpt-6-astra`, `low`; or the lead directly when dispatch adds no value |
| Implement: an easy isolated change that edits files | helper `fast`, `edit` mode | `gpt-6-luna`, `max`; then `sonnet`, `medium`; or the lead directly |
| Implement-complex: a consequential bounded change that edits files | helper `strong`, `edit` mode | `gpt-6-astra`, `low`; or the lead directly |
| Optional epic pre-review | helper `strong`, `review` mode | skip when unavailable or unjustified |
| Whole-epic important risks and project alignment | `gpt-6-astra`, `medium` | `fable`, `medium`. `gpt-6-astra`, `low` only for a focused follow-up on a well-evidenced question |
| Whole-project final evaluation or critical decision | `gpt-6-astra`, `high` | `fable`, `high` |

Use at most one helper pre-review before the full review, when it can overlap the
lead's own independent acceptance checks or a substantial change across several
stories warrants an extra defect-finding pass; skip small routine epics and areas
already adequately reviewed. It reuses passing checks on the unchanged candidate and
runs only missing or affected tests. Substantiate its findings, consolidate repairs,
then go to Astra/Fable without another helper round, giving them the report and your
dispositions as a navigation aid, not as proof.

`fable` currently resolves to `claude-fable-5-1`. Codex currently supports Sol at
`xhigh`, Luna at `max`, and Astra at `low`, `medium`, or `high`. When Claude Code
leads, strong reviews use the Codex Astra CLI route below; Fable follows through the
Claude CLI with explicit `--effort` only after the Astra route has a recorded reason
for escalation. Record requested and observed effort separately.

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

Launch independent helpers together and continue useful work; collect completed
results together. When only waiting remains, use completion notifications or the
longest wait the host and active instructions permit: every timed-out wait re-sends
the lead context. Observed Codex limits: running-cell `wait` with `yield_time_ms:
300000`; native `wait_agent` with `timeout_ms: 360000`. Claude Code background
commands notify on completion. Never poll merely to keep caches warm.

## Direct CLI routes

Use these when the host's native interface cannot deliver the selected model,
effort or required access (helper and cross-provider routes), under
existing provider authorization. Set `PROJECT`, `PROMPT`, and `OUTPUT` to explicit,
task-specific paths. Use the project directly when its readable scope is appropriate;
otherwise set `PROJECT` to a prepared workspace containing only the required source
and evidence. Exclude credentials and unrelated private data, and keep `OUTPUT`
outside the tracked working tree.

A Codex lead's workspace sandbox has no network and blocks some local sockets:
Claude CLI and helper routes fail with `EAI_AGAIN`, and test gates using Git, sockets or
a browser fail with `EPERM` or hang. Run those commands escalated from the first
attempt (`sandbox_permissions: "require_escalated"`), with a justification naming the
actual provider (not just the script), the readable payload and the owner's dev-auto
request. A sandbox failure is
not a route failure: retry the same tier escalated, not the next tier. When the
approval reviewer refuses, never work around it; ask the owner as SKILL.md describes.

Read-only Codex review:

```bash
codex exec --skip-git-repo-check -C "$PROJECT" \
  -m gpt-6-astra -c model_reasoning_effort=medium -c 'mcp_servers={}' \
  --sandbox read-only --json -o "$OUTPUT" - < "$PROMPT"
```

`--ephemeral` is deliberately omitted: the `--json` output names neither model nor
usage, so the persisted rollout file is the receipt (live 2026-09-24: the rollout
recorded `gpt-6-astra/high` and its token usage). The reviewer can still run read-only shell commands inside the sandbox; `-C` and
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

Helper routes, for any agent, through the canonical checkout (the installed skills
link to it):

```bash
~/code/dev-auto/skills/dev-auto/scripts/helper.sh review strong "$PROJECT" "$PROMPT" "$OUTPUT"
~/code/dev-auto/skills/dev-auto/scripts/helper.sh edit fast "$PROJECT" "$PROMPT" "$OUTPUT" 'python3 -m unittest -q'
```

`review` reads, `edit` also edits, and the optional last argument is the one exact
check command the helper may run. The script confines the file tools to `PROJECT`,
denies its `.env*` files and allows no other command than the check, which runs as
written in Claude's sandbox without network. Everything the helper reads reaches the
provider: set `PROJECT` to the directory the helper may read or own, and to a
sanitized workspace whenever the project holds data restricted from that provider
(customer text, production records); if none can be prepared, skip the helper and
recheck restrictions after a provider switch. Its first lines name the
provider's credentials file and `fast`/`strong` models (currently
`~/.claude-glm/env.sh`, GLM-5.3-Flash and GLM-5.3); never read, print, copy or trace
that file. Switching provider means editing those lines and rerunning the checks
the script names. Wait for the terminal receipt: the route can print an early
`unrecognized_model` diagnostic and still complete. Live probes: `docs/verification.md`.

## Browser-enabled review

Reviews run without a browser by default. For a named UI acceptance question with
lead-supplied local URLs, use [browser-review.md](browser-review.md).
