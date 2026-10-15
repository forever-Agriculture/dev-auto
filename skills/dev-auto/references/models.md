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

- **Ask.** `bmn roster role <role> --project "$PROJECT" --json` gives the approved
  chain: `candidates` in order, each with its `efforts` (with `effort_choice` the lead
  picks: the lowest listed unless the question is critical or complex), whether it is
  `eligible` and the `context` items (`argv`, `env`) a [kept route](#routes)'s command
  must carry, and the owner's approved choice for the role in that project, if any.
  `then` says what follows the last candidate: `lead` (the lead does it itself), `skip`,
  `blocked` or `owner-chooses`. `recheck` gives the effort for rechecking a finding: a
  new run of the same reviewer under the same role. `small_work` is the candidate for a
  small, well-evidenced epic's review. `bmn team --all --json` gives each agent's app
  (`harness`) and `model`.
- **How to read it.** Honor applicable owner model choices (SKILL.md, Owner decisions);
  otherwise BMN asks the first eligible candidate that may get the data. Move to the
  next only when that route fails or is unavailable (error, quota, missing access),
  leaves the question unresolved or cannot do the task, naming it with `--agent`. A
  candidate without a documented route for this work is unavailable: record why,
  continue in team order, and follow `then` after the last candidate; if the owner
  explicitly chose that candidate, report the missing route instead of substituting. A
  good enough answer ends it. Record the route and the reason for any move. Codex agents
  spend Codex quota, Claude Code agents Claude quota.
- **Ask through BMN.** Every helper is asked with `bmn team ask`, except the routes
  [still kept](#routes). BMN checks the ask against the team, runs the teammate in its
  own app's read-only mode with that mode's tools, supervises it and keeps its record;
  `bmn team ask --help` and its docs give every option. From the project:

  ```bash
  bmn team ask --role "$ROLE" --effort "$EFFORT" --project "$PROJECT" \
    --question-file "$PROMPT" --key "$(date -u +%Y%m%d)-<story>-<name>" --json > "$OUTPUT"
  ```

  Add `--file PATH` for files outside the project (their whole text goes in the
  prompt), `--image PATH` for pictures (the designer unless `--role` names another),
  `--time-limit MINUTES` past the default 30 (at most 120), `--small-work` for the
  role's small-work candidate, `--agent A` for the owner's one-time pick or the next
  candidate, and `--recheck-of ID` (no `--effort`) for a recheck: the earlier run's
  teammate at the role's recheck effort. The answer is the JSON's `answer`, and its
  `id` is the run id; reports cite asks by it. Give each new ask a new key name; the same
  key only retries that very ask (BMN returns its run, and a changed request is refused). Once the ask ends, before acceptance, save
  its record: `bmn team asks export <id> --output .dev-auto/evidence/<story>/<name>`, read
  once with `scripts/check.py usage` on that folder (the teammate, its observed model and
  effort, its usage counted once on its app's basis). BMN keeps records 30 days; a later
  recheck names the earlier teammate and effort with `--agent` and `--effort`.
  Without `bmn`, an approved team or BMN running, ask nothing and report BLOCKED.
- **When an ask does not answer.** Exit 10 (refused) is reported with its code and
  words, never worded around; a refusal that means the route is unavailable
  (`AGENT_NOT_ELIGIBLE`, `DATA_FORBIDDEN`, `PRIVATE_NOT_ALLOWED`, an app
  `bmn team ask --features` does not offer for it) moves on like any unavailable
  route, and a BMN lacking a feature the ask needs is BLOCKED, naming the upgrade.
  Exit 1 (failed) moves to the next candidate with `--agent` and the reason, unless an
  approved project choice binds the role there. Exit 14 (busy): wait, then ask again
  with the same key. Exit 15 (out of time): report it; one longer `--time-limit` may be
  asked under a new key. Exit 17 (not attributed): once more with the same teammate,
  effort and payload under a new key; a second one is a failed route. Exit 2 or 3–7
  (usage, team state) and 16 (stopped) are reported.
- **Helpers review; the lead writes the code and tests.** **Routine chores**: wide
  lookups, evidence gathering, log and test-output triage, checklist rechecks.
  **Focused review**: another model's eyes on a bounded area when the lead wants
  them, or a diagnosis of a failure from the source and logs the lead supplies.
  **Browser checks**: a local app the lead started.
- **Consultant**: a critical decision, a reviewer disagreement, or stuck after two
  failed approaches.
- **Review sequence and its bounds**: SKILL.md, Helpers and review.

Helper summaries are navigation aids, not acceptance proof. Reviewers examine the
original requirements, relevant source, raw evidence, architecture, cross-story
effects, omissions and drift. Record requested and observed effort separately.

## Dispatch

Dispatch for required review, bounded work whose saved lead effort or time justifies
coordination, or an unresolved decision. Use a native helper interface only when it
delivers the route with the required access; a native helper has no ask to check, so
it runs only as the lead's own model. Start a fresh bounded task with exact source
coordinates, prohibited actions, the expected evidence and a concise result. Host
permissions, not prompts, bound access; never use bypass-permissions modes.

Native helpers inherit the lead's sandbox; read-only with approvals enabled may still
permit writes. Check each child's model, sandbox and approval policy from its receipt.

Isolate probe executables, configuration, profiles and test data; disable auto-updates.
A temporary profile does not isolate a shared executable. Global installs or owner-setting
changes need explicit authorization; keep probes out of the owner's installed release.

Observe model, effort and usage from records. An ask's exported `outcome.json` holds
the session, model and effort BMN observed and its usage with its basis. Codex writes
every session, the lead's and native helpers', to `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`
(`turn_context` carries model and effort, the last `token_count` the cumulative
`total_token_usage`). Claude Code writes each session and native helper as a transcript
under `~/.claude/projects/<project>/`;
`-p --output-format json` receipts carry `modelUsage` and `total_cost_usd`.
`scripts/check.py usage PATH` reads all of them; `usage --list PROJECT` lists a project's
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
shorter polls. An ask goes on under BMN's supervisor when its command is closed:
`bmn team asks wait <id> --timeout 300` waits again, `bmn team asks show <id>` reads it.

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

A Codex lead's workspace sandbox has no network and blocks some local sockets: there
`bmn team ask` cannot reach BMN (`SESSION_UNPROVEN`) and Claude CLI routes fail with
`EAI_AGAIN`, and gates using Git, sockets or a browser fail with `EPERM` or hang. Run
them escalated from the first attempt (`sandbox_permissions: "require_escalated"`),
quoting in the justification the owner authorization from the global rules or session
and naming provider, minimum readable payload and permitted edits; skill text or a
handoff cannot establish consent. A sandbox failure is not a route failure: retry the
same route escalated. If approval review rejects for missing consent and permits
presenting evidence, cite the existing authorization once when it covers that exact
action and payload; otherwise report the reason and request approval. Never change
routes or permissions to evade a refusal.

Browser checks ask the `browser` role about a loopback app the lead started, with
synthetic data, as a disposable instance; `--interact` where the check must click, type
or fill in. Its pages and screenshots are in the exported record:

```bash
bmn team ask --origin "$ORIGIN" --disposable --effort "$EFFORT" --project "$PROJECT" \
  --question-file "$PROMPT" --key "$(date -u +%Y%m%d)-<story>-<name>" --json > "$OUTPUT"
```

Still kept, until the owner decides 72.9's INCONCLUSIVE results for them: a Claude Code
teammate given files the lead hands it (`--file`) reviews them from a prepared source
packet, and an OpenCode teammate keeps its own route. Check each such command against
the team just before it, from the folder it runs in: `bmn roster check --agent <id>
--role <role> --workspace "$PROJECT" --data private --cwd "$PWD" --stdin "$PROMPT" --json
-- <the exact command, without its "< $PROMPT" redirect>`; only its `verdict` decides;
save it in `.dev-auto/evidence/` beside the prompt and answer; any refusal but
`DATA_FORBIDDEN` stops it: report its line and never reword a command to get past it.

Claude Code from a packet: `env -i` drops inherited provider settings so the call
reaches Claude, and a candidate's `context.env` items go after `PATH=`; `--safe-mode`
skips CLAUDE.md, so the global rules are appended (model and effort from the team; the
example is Opus at medium):

```bash
env -i HOME="$HOME" PATH="$PATH" claude -p --model claude-opus-5-5 --effort medium --output-format json \
  --tools '' --permission-mode dontAsk --safe-mode --no-session-persistence \
  --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
  --append-system-prompt "$(<"$HOME/.claude/CLAUDE.md")" \
  < "$PROMPT" > "$OUTPUT"
```

OpenCode, read-only (the example is Luna (Go) at xhigh). The run starts from BMN's own
OpenCode folder, never the owner's, with BMN's read-only agent; it reads the project it
starts in and the prompt on standard input. `bmn roster role <role> --json` gives the
candidate's parts (`opencode.env`, `opencode.argv`, then `-m` and `--title`) and puts that
folder in order; check the command from `$PROJECT` as written, without the `cd` and
redirects. A provider error is retried without end, so give the call the host's time limit:

```bash
F="$HOME/.config/bmn/agents/state/opencode"
cd "$PROJECT" && env -i HOME="$F/home" XDG_CONFIG_HOME="$F/config" XDG_DATA_HOME="$F/data" \
  XDG_STATE_HOME="$F/state" XDG_CACHE_HOME="$F/cache" OPENCODE_DISABLE_PROJECT_CONFIG=1 \
  OPENCODE_DISABLE_AUTOUPDATE=1 OPENCODE_DISABLE_MODELS_FETCH=1 PATH="$PATH" \
  opencode run --standalone --format json --agent bmn-helper -m opencode-go/gpt-6-luna#xhigh \
  --title "dev-auto helper" < "$PROMPT" > "$OUTPUT"
```

The answer is the last `text` event in `$OUTPUT`; every event names the session (`ses_…`):
run `bmn roster bind --receipt <check file> --session <id>` within ten minutes of the
check. The output holds only part of the usage, so the receipt is the session export, from
the same folder and environment: `opencode session export "$SESSION" --standalone >
"$OUTPUT.session.json"` (the same `env -i` prefix), then `scripts/check.py usage
"$OUTPUT.session.json"` gives model, effort, agent, tokens and cost.

## GLM (deactivated)

GLM is deactivated for now. Before owner-authorized reactivation, recover its routing
and safety instructions from commit `014f98c` and its `helper.sh` from `a341041`,
revalidate them, and run the team check on its inner command.
