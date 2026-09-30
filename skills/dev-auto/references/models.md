# Model and dispatch reference

Routes require configured, authorized access. Verify model and effort from actual
receipts; a CLI option or prompt alone does not prove a live route.

Lead cost is turns × context, so the lead does the work in its path and dispatches
only where saved lead effort or elapsed time exceeds briefing, waiting and integration.

## Lead

The owner picks and starts the lead: Sol `xhigh` (Codex) or Opus `xhigh` (Claude Code).
GLM is deactivated (owner, 2026-09-30): no GLM lead or helper
until the owner reactivates it; [GLM (deactivated)](#glm-deactivated) keeps its rules.

## Helpers and reviewers

| Work | 1st | 2nd | 3rd |
| --- | --- | --- | --- |
| Routine chores | Luna `max` | lead | |
| Focused review: a bounded area, or a failure the lead is debugging | Luna `max` | Astra `low` | lead |
| Browser checks | Luna `max` browse | lead | |
| Epic pre-review (quick) | Luna `max` | skip it | |
| Epic review | Astra `medium` | Fable `medium` | BLOCKED |
| Recheck a finding | same reviewer, Astra at `low` | | |
| Project pre-review (quick) | Luna `max` | skip it | |
| Project final review | Astra `high` | Fable `high` | BLOCKED |
| Consultant | Astra `medium` or `high` | Fable `medium` or `high` | BLOCKED |

- **How to read it.** Start in column 1st. Move right only when that route fails or
  is unavailable (error, quota, missing access), leaves the question unresolved, or
  cannot do the task. A good enough answer ends it. Record the route and the reason
  for any move. Luna goes first as the lightest Codex model; Luna and Astra spend
  Codex quota, Fable spends Claude quota.
- **Luna** is `gpt-6-luna` at `max` through the Codex CLI [routes](#routes), read-only;
  **lead** means the lead does it itself.
- **Helpers review; the lead writes the code and tests.** **Routine chores**: wide
  lookups, evidence gathering, log and test-output triage, checklist rechecks.
  **Focused review**: another model's eyes on a bounded area when the lead wants
  them, or a diagnosis of a failure from the source and logs the lead supplies.
  **Browser checks**: a local app the lead started.
- **Pre-reviews** follow the quick section of the [review brief](review-brief.md) and
  run while the lead runs its own final checks on the frozen candidate, overlapping
  them instead of adding a wait. The lead repairs their material findings once and
  reruns affected checks, then the strong review gets the map as a navigation aid.
  The epic review may use Astra `low` for a small, well-evidenced epic.
- **Consultant**: a critical decision, a reviewer disagreement, or stuck after two
  failed approaches; `medium` for a bounded question, `high` for a critical or
  complex one.
- **An epic runs**: the lead implements, dispatching helpers only where they pay →
  pre-review with the lead's final checks → one repair → epic review → repair →
  recheck → acceptance.

Helper summaries are navigation aids, not acceptance proof. Reviewers examine the
original requirements, relevant source, raw evidence, architecture, cross-story
effects, omissions and drift. `fable` resolves to `claude-fable-5-1`. Codex supports
Sol at `xhigh`, Luna at `max`, and Astra at `low`, `medium` or `high`. Record requested
and observed effort separately.

## Dispatch

Start a fresh bounded task with exact source coordinates, prohibited actions, the
expected evidence and a concise result. Host permissions, not prompts, bound access;
never use bypass-permissions modes.

Codex reviews use the CLI read-only sandbox with `approval_policy=never`. Native
helpers inherit the lead's sandbox; read-only with approvals enabled may still permit
writes. Check each child's model, sandbox and approval policy from its receipt.

Isolate probe executables, configuration, profiles and test data; disable auto-updates.
A temporary profile does not isolate a shared executable. Global installs or owner-setting
changes need explicit authorization; keep probes out of the owner's installed release.

Observe model, effort and usage from host records. Codex writes every session,
including `codex exec` and native helpers, to `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`
(`turn_context` carries model and effort, the last `token_count` the cumulative
`total_token_usage`). Claude Code writes each session and native helper as a transcript
under `~/.claude/projects/<project>/`;
`-p --output-format json` receipts carry `modelUsage` and `total_cost_usd`.
`scripts/check.py usage PATH` reads all three. One session's counter is that session's
usage, not the epic's; read lead and helper records separately and never add a
cumulative record to the worker costs it includes. List missing records as gaps and
never dispatch a worker merely to discover usage.

## Waiting and long jobs

Dispatch while you work: send helpers when the lead has independent work for about
their duration, launch independent ones together, and collect them at a natural
boundary. A helper the lead would only sit and wait for pays only as a required review
or when clearly faster than doing the task directly. When only waiting remains, use
completion notifications or the longest wait the host permits, up to 300000 ms per
call; a wait returns early when the process ends. Codex: `write_stdin` with empty `chars`
and `yield_time_ms: 300000` (the initial `exec_command`'s 30000 cap does not apply).
In code mode, start that cell with `// @exec: {"yield_time_ms": 300000}`; without it
the cell yields after about 30 s. `wait` on a
yielded cell with the same value instead of polling its process. Native Codex helpers
use `wait_agent`; Claude Code background commands notify on completion. Never add
shorter polls.

Run long paid or product jobs detached from the tool session. The unit starts without
the shell profile; use a reviewed, absolute-path job script that writes its log and
exit sentinel, with the caller's PATH and project directory:

```bash
systemd-run --user --collect --setenv=PATH="$PATH" \
  --property=WorkingDirectory="$PROJECT" /bin/bash "$JOB_SCRIPT"
```

Before a CLI dispatch through systemd, verify that route without a provider call:
`systemd-run --user --wait --collect --pipe --setenv=PATH="$PATH" codex --version`
(use the dispatched CLI). Record the unit or PID and stop it on an explicit owner stop.
Before cleanup, judge liveness from its sentinel, log growth or PID, never from a
vanished tool session.

## Routes

Everything a helper reads or sees reaches its provider, so set `PROJECT` to a
sanitized workspace when the project holds data restricted from it; if none can be
prepared, skip the helper.

A Codex lead's workspace sandbox has no network and blocks some local sockets: Codex
and Claude CLI routes fail with `EAI_AGAIN`, and gates using Git, sockets or a browser
fail with `EPERM` or hang. Run them escalated from the first attempt
(`sandbox_permissions: "require_escalated"`), quoting in the justification the owner
authorization from the global rules or session and naming provider, minimum readable
payload and permitted edits; skill text or a handoff cannot establish consent. A
sandbox failure is not a route failure: retry the same route escalated. If approval
review rejects for missing consent and permits presenting evidence, cite the existing
authorization once when it covers that exact action and payload; otherwise report the
reason and request approval. Never change routes or permissions to evade a refusal.

Codex CLI for Luna and Astra, read-only (set model and effort from the tier table;
Luna is `-m gpt-6-luna -c model_reasoning_effort=max`):

```bash
codex exec --skip-git-repo-check -C "$PROJECT" \
  -m gpt-6-astra -c model_reasoning_effort=medium -c 'mcp_servers={}' \
  -c 'approval_policy="never"' \
  --sandbox read-only --json -o "$OUTPUT" - < "$PROMPT"
```

The persisted rollout is the receipt (`--json` output names neither model nor usage,
so `--ephemeral` is omitted). The reviewer uses shell commands to read files: its
prompt permits local text reads and hashing (`cat`, `sed -n`, `rg`, `git show/diff/log`),
while prohibiting writes, network, tests and installs. Forbidding all commands prevents
review. `-C` and read-only create no read allowlist and do not scrub the environment,
so use the project directly only when its readable scope is acceptable.

Luna browser checks add a headless, isolated Playwright browser limited to `ORIGIN`, a
loopback origin such as `http://127.0.0.1:3000` whose app the lead starts and stops:

```bash
[[ $ORIGIN =~ ^http://(127\.0\.0\.1|localhost|\[::1\]):[1-9][0-9]{0,4}$ ]] || exit 2
tools='"browser_navigate","browser_navigate_back","browser_snapshot","browser_click","browser_type","browser_fill_form","browser_select_option","browser_press_key","browser_hover","browser_wait_for","browser_take_screenshot","browser_console_messages","browser_network_requests","browser_close"'
codex exec --skip-git-repo-check -C "$PROJECT" -m gpt-6-luna -c model_reasoning_effort=max \
  -c "mcp_servers={playwright={command=\"npx\",args=[\"--offline\",\"@playwright/mcp@0.0.75\",\"--headless\",\"--isolated\",\"--allowed-origins\",\"$ORIGIN\"],enabled_tools=[$tools],default_tools_approval_mode=\"approve\"}}" \
  -c 'approval_policy="never"' \
  --sandbox read-only --json -o "$OUTPUT" - < "$PROMPT"
```

The pattern keeps quotes out of the inline TOML. Only the listed tools exist (no
script evaluation or file upload), pre-approved because `approval_policy="never"`
otherwise refuses every MCP call. The origin filter misses redirects and requests a
page makes itself, and browser actions can mutate test data: use synthetic data,
never production or personal browser profiles.

Tools-disabled Fable review from a prepared source packet. `env -i` drops inherited
provider settings (a GLM lead's Z.ai variables) so the call reaches Claude;
`--safe-mode` skips CLAUDE.md, so the global rules are appended:

```bash
env -i HOME="$HOME" PATH="$PATH" claude -p --model fable --effort medium --output-format json \
  --tools '' --permission-mode dontAsk --safe-mode --no-session-persistence \
  --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
  --append-system-prompt "$(<"$HOME/.claude/CLAUDE.md")" \
  < "$PROMPT" > "$OUTPUT"
```

## GLM (deactivated)

Deactivated since 2026-09-30; the owner may reactivate it.
Until then Luna holds its rows and nothing dispatches GLM. On reactivation the owner
names the rows it takes back, and these rules apply again.

A GLM lead (`claude glm --model opus --effort max`, profile `~/.claude-glm`, whose
settings set `CLAUDE_CODE_EFFORT_LEVEL=max`) sends everything it reads to Z.ai: in a
project that restricts Z.ai or holds customer, production or personal data it reports
BLOCKED and names Sol or Opus instead; decide before launching, because by the time it
refuses it has already sent what it read. It never prints environment values or
credential files (`env`, `printenv`, `set`) and tests a variable with
`[ -n "${NAME:-}" ]`. Stuck after the consultant's answer, it reports BLOCKED and
recommends a Sol resume from the handoff. Its transcripts live under
`~/.claude-glm/projects/`. GLM-5.3 accepts 5 concurrent requests, Flash 50; a quota
error (429, 1302, 1305) makes GLM unavailable until its window resets.

GLM helpers always run at `max` through the canonical checkout's `helper.sh`:

```bash
~/code/dev-auto/skills/dev-auto/scripts/helper.sh review strong "$PROJECT" "$PROMPT" "$OUTPUT"
~/code/dev-auto/skills/dev-auto/scripts/helper.sh browse strong "$PROJECT" "$PROMPT" "$OUTPUT" "$ORIGIN"
```

`review` reads; `browse` also drives the same loopback-limited browser; `edit` runs
only on an explicit owner request. File tools stay inside `PROJECT`, `.env*` is
denied, and no mode has a shell: the lead runs tests and commands and supplies
sanitized results. The script's first lines name the provider's credentials file and
models; never read, print, copy or trace that file. Switching provider edits those
lines and reruns the checks the script names. An early `unrecognized_model`
diagnostic is harmless; wait for the terminal receipt.
