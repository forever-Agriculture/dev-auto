# Model and dispatch reference

Routes require configured, authorized access. Verify model and effort from actual
receipts; a CLI option or prompt alone does not prove a live route.

## Lead

The owner picks and starts the lead; `bmn roster role lead --json` lists who may lead
and at which efforts.
GLM is deactivated (owner, 2026-09-30): no GLM lead or helper
until the owner reactivates it; [GLM (deactivated)](#glm-deactivated) keeps its rules.

## Helpers and reviewers

The owner's team in BMN (Preferences › Team) says who does each kind of work; this file
names no models. Ask the team for the role:

| Work | Role |
| --- | --- |
| Routine chores | `helper` |
| Focused review: a bounded area, or a failure the lead is debugging | `focused-reviewer` |
| Browser checks | `browser` |
| Epic pre-review (quick) | `pre-reviewer` |
| Epic review | `epic-reviewer` |
| Project pre-review (quick) | `project-pre-reviewer` |
| Project final review | `final-reviewer` |
| Consultant | `consultant` |

- **Ask.** `bmn roster role <role> --json` gives the approved chain: `candidates` in
  order, each with its `efforts` (with `effort_choice` the lead picks: the lowest listed
  unless the question is critical or complex), whether it is `eligible`,
  and the `context` items (`argv`, `env`) its command must carry. `then` says what
  follows the last candidate: `lead` (the lead does it itself), `skip`, `blocked` or
  `owner-chooses`. `recheck` gives the effort for rechecking a finding: a new run of the
  same reviewer under the same role. `small_work` is the candidate for a small,
  well-evidenced epic's review.
  `bmn team --all --json` gives each agent's app (`harness`) and `model` for the
  [routes](#routes).
- **How to read it.** Honor applicable owner model choices; otherwise start with the
  first eligible candidate. Move to the next only when that route fails or is
  unavailable (error, quota, missing access), leaves the question unresolved, cannot do
  the task, or the check answers `DATA_FORBIDDEN`. A candidate without a documented
  route for this work is unavailable: record why, continue in team order, and follow
  `then` after the last candidate; if the owner explicitly chose that candidate, report
  the missing route instead of substituting. A good enough answer ends it. Record the
  route and the reason for any move. Codex agents spend Codex quota, Claude Code agents
  Claude quota.
- **Check every helper command.** Just before it, in the same environment and from the
  folder it will run in (one inside the project), run `bmn roster check --agent <id>
  --role <role> --workspace "$PROJECT" --data private --cwd "$PWD" --stdin "$PROMPT"
  --json -- <the exact command, without its "< $PROMPT" redirect>`; `--data public` only
  where `bmn roster visibility "$PROJECT"` proves the workspace public. The answer is
  the receipt and only its `verdict` decides: save it in `.dev-auto/evidence/` beside
  the helper's prompt and answer, and for a Codex helper run `bmn roster bind --receipt
  <file> --session <id>` as soon as its rollout exists (BMN binds only within ten
  minutes of the check); check a resume with `--resume-of <receipt>`. Any refusal but `DATA_FORBIDDEN` stops that dispatch: report
  its line, since the owner changes the team or names another agent, and never reword a
  command to get past it. An owner's model choice is checked the same way. A wrapper
  script runs the check on its own inner command. Without `bmn` or an approved team,
  dispatch nothing and report BLOCKED. A native helper has no command to check, so it
  runs only as the lead's own model; work for any other model goes through a route and
  the check.
- **Helpers review; the lead writes the code and tests.** **Routine chores**: wide
  lookups, evidence gathering, log and test-output triage, checklist rechecks.
  **Focused review**: another model's eyes on a bounded area when the lead wants
  them, or a diagnosis of a failure from the source and logs the lead supplies.
  **Browser checks**: a local app the lead started.
- **Pre-reviews** follow the quick section of the [review brief](review-brief.md) and
  run while the lead runs its own final checks on the frozen candidate, overlapping
  them instead of adding a wait. The lead repairs their material findings once and
  reruns affected checks, then the strong review gets the map as a navigation aid.
- **Consultant**: a critical decision, a reviewer disagreement, or stuck after two
  failed approaches.
- **An epic runs**: the lead implements, dispatching helpers only where they pay →
  pre-review with the lead's final checks → one repair → epic review (for a web UI,
  plus a browser check of the running candidate against the acceptance criteria)
  → repair → recheck → acceptance.

Helper summaries are navigation aids, not acceptance proof. Reviewers examine the
original requirements, relevant source, raw evidence, architecture, cross-story
effects, omissions and drift. Record requested and observed effort separately.

## Dispatch

Dispatch for required review, bounded work whose saved lead effort or time justifies
coordination, or an unresolved decision. Use a native helper interface only when it
delivers the route with the required access. Start a fresh bounded task with exact
source coordinates, prohibited actions, the expected evidence and a concise result. Host permissions, not prompts, bound access;
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
`scripts/check.py usage PATH` reads all three; `usage --list PROJECT` lists a project's
Codex rollouts. One session's counter is that session's
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

Codex CLI, read-only (model and effort from the team; the example is Astra at medium):

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

Browser checks drive a headless Playwright browser limited to a loopback `ORIGIN`
whose app the lead starts; use synthetic data. The script is Luna's route: pass the
effort selected above as the fifth argument. It runs the team check itself (`browser`
role, receipt in `OUTPUT.check.json`); the caller finds the run's rollout with
`scripts/check.py usage --list "$PROJECT"` and binds that receipt to its session within
ten minutes of the check. Only Luna has a documented browser route here; skip other
candidates under the unavailable-route rule and follow the team's `then` action.

```bash
~/code/dev-auto/skills/dev-auto/scripts/luna-browse.sh "$PROJECT" "$PROMPT" "$OUTPUT" "$ORIGIN" "$EFFORT"
```

Tools-disabled Claude Code review from a prepared source packet (model and effort from
the team; the example is Opus at medium). `env -i` drops inherited provider settings so
the call reaches Claude, and a candidate's `context.env` items go after `PATH=`;
`--safe-mode` skips CLAUDE.md, so the global rules are appended:

```bash
env -i HOME="$HOME" PATH="$PATH" claude -p --model claude-opus-5-5 --effort medium --output-format json \
  --tools '' --permission-mode dontAsk --safe-mode --no-session-persistence \
  --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
  --append-system-prompt "$(<"$HOME/.claude/CLAUDE.md")" \
  < "$PROMPT" > "$OUTPUT"
```

## GLM (deactivated)

GLM is deactivated for now. Before owner-authorized reactivation, recover its routing
and safety instructions from commit `014f98c`, revalidate them, and make `helper.sh`
run the team check on its inner command.
