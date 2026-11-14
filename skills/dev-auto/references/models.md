# MODULE: models.md - approved model routes, dispatch and background launch context
# Model and dispatch reference

While the owner is away, BMN's Away notice takes precedence over skill instructions for messages, consultant retries and provider changes, clarification cards, planning questions and report opinions; it grants no authority.

Routes require configured, authorized access. Verify model and effort from actual
receipts; a CLI option or prompt alone does not prove a live route.

## Peer coordination

Routine BMN peer coordination with `bmn tell` or `bmn handoff` runs under the owner's standing
authorization: SKILL.md, Scope and delivery. Helper dispatch and review keep their own
authorization and limits.

## Lead

The owner picks and starts the lead; `bmn roster role lead --json` lists who may lead
and at which efforts.

## Helpers and reviewers

The owner's team in BMN (Preferences › Team) says who does each kind of work; this file
names no models. Ask the team for the role:

| Work | Role |
| --- | --- |
| Routine chores | `helper` |
| Focused review: a bounded area, or a failure the lead is debugging | `focused-reviewer` |
| Manual QA of the running interface | `qa` |
| Epic pre-review (quick) | `pre-reviewer` |
| Epic review | `epic-reviewer` |
| Small, well-evidenced epic review | `small-epic-reviewer` |
| Project pre-review (quick) | `project-pre-reviewer` |
| Project final review | `final-reviewer` |
| Consultant | `consultant` |
| Senior collected consult / step-back | `senior-consultant` |

A project's own PR review asks its lenses through the routes the project's rules name, under
BMN's eligibility and any project choice; this is the one exception to the first-eligible chain.
A route that cannot answer leaves that ticket BLOCKED, never substituted.

- **Ask.** `bmn roster role <role> --project "$PROJECT" --json` gives the approved chain in
  order, the owner's approved choice for the role in that project, and `then`: what follows the
  last candidate (`lead`: the lead does it itself, `skip`, `blocked` or `owner-chooses`). Where
  a candidate has `effort_choice`, pick the lowest listed effort unless the question is critical
  or complex. `recheck` gives the effort for rechecking a finding: a new run of the same
  reviewer under the same role.
- **Small epic review.** Ask `--role small-epic-reviewer`. Only if the roster reports no such
  role, use `--role epic-reviewer --small-work`. Recheck with `--recheck-of ID` under the role
  used for the original review; do not switch roles or add `--small-work` to a recheck.
- **How to read it.** Honor applicable owner model choices (SKILL.md, Owner decisions);
  otherwise BMN asks the first eligible candidate that may get the data: the first agent
  of a role is the default. A lead may pick another for its own helpers with `--agent` and
  says why in one line. Otherwise move to the next when that route fails or is unavailable (error,
  quota, missing access), leaves the question unresolved or cannot do the task, and
  follow `then` after the last candidate. A good enough answer ends it. Record the route
  and the reason for any move.
- **Ask through BMN.** Every helper is asked with `bmn team ask` from the project;
  `bmn team ask --help` gives its options, the key's form and its exit codes:

  ```bash
  bmn team ask --role "$ROLE" --effort "$EFFORT" --project "$PROJECT" \
    --question-file "$PROMPT" --key "$(date -u +%Y%m%d)-<story>-<name>" --json > "$OUTPUT"
  ```

  `--agent` names the owner's one-time pick or the next candidate. `--recheck-of ID` runs at
  the role's `recheck` effort or, where it has none, an `--effort` you choose. Each new ask
  gets a new key name. Reports cite an ask by its run `id`. Once it ends, before acceptance, save its record with
  `bmn team asks export <id> --output .dev-auto/evidence/<story>/<name>` and read it once
  with `scripts/check.py usage` on that folder. Without `bmn`, an approved team or BMN
  running, ask nothing and report BLOCKED.
- **When an ask does not answer, while the owner is present.** A refusal (exit 10) is reported with its code and
  words, never worded around. One that means the route is unavailable
  (`AGENT_NOT_ELIGIBLE`, `DATA_FORBIDDEN`, `PRIVATE_NOT_ALLOWED`, an app
  `bmn team ask --features` does not offer for it) and a failure (exit 1) move on like
  any unavailable route. A bound ask never moves on: an owner's named pick, a recheck's
  reviewer or an approved project choice that cannot answer is reported, and he changes
  the pick or the choice. Out of time (15): one longer `--time-limit` under a new key, never beyond the senior ask's 40-minute cap or BMN's shorter maximum. At that cap the senior route is unavailable, not a longer retry.
  Not attributed (17): once more under a new key; a second is a failed route. A BMN
  lacking a feature the ask needs is BLOCKED, naming the upgrade.
- **While the owner is away.** A consultant ask needs existing dispatch consent, permitted
  provider/data and remaining allowances: one stable key, a bounded time limit, no recursion
  and no other provider. On refusal, timeout or uncertain completion, read the existing ask
  record instead of asking again; do not use a new retry key or change providers. Report the
  refusal and park only dependent work. This Away rule overrides the present-owner retry and
  route sequence above; it creates no dispatch or spending authority.
- **Helpers review; the lead writes the code and tests.** Routine chores are wide lookups,
  evidence gathering, log and test-output triage and checklist rechecks. A focused review may
  also diagnose a failure from the source and logs the lead supplies.
- **Consultant**: when and how: SKILL.md, Owner decisions, and [consult-brief.md](consult-brief.md).
  A reviewer disagreement alone is no trigger: decide a reversible point with one evidence
  line; consult only if it involves a hard-to-undo choice or reaches the brake.
- **Senior consultant**: the consult brief gives the collected ask. If the role is absent,
  ask the consultant chain's next eligible agent other than its first through
  `--role consultant --agent NAME`, still using the senior limit. A configured role's failure
  is governed by the normal route and Away rules, never treated as absence.
- **Review sequence and its bounds**: SKILL.md, Helpers and review.

Helper summaries are navigation aids, not acceptance proof. Record requested and observed effort separately.

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

Observe model, effort and usage from records: an ask's export, and for the lead and
native helpers their host records.
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
shorter polls.

Run long paid or product jobs detached from the tool session. The unit starts without
the shell profile; use a reviewed, absolute-path job script that writes its log and
exit sentinel, with the caller's PATH and project directory:

```bash
systemd-run --user --collect --setenv=PATH="$PATH" \
  --setenv=BMN_SESSION_ID --setenv=BMN_TOKEN --setenv=BMN_CONTROL_SOCKET \
  --setenv=BMN_RUNTIME_HOME --setenv=XDG_RUNTIME_DIR \
  --property=WorkingDirectory="$PROJECT" /bin/bash "$JOB_SCRIPT"
```

Never put a token value in the command or job script; the ledger launcher passes these names itself.

Record the unit or PID and stop it on an explicit owner stop.
Before cleanup, judge liveness from its sentinel, log growth or PID, never from a
vanished tool session.

## Routes

Everything a helper reads or sees reaches its provider, so set `PROJECT` to a
sanitized workspace when the project holds data restricted from it; if none can be
prepared, skip the helper.

A Codex lead's workspace sandbox has no network and blocks some local sockets: there
`bmn team ask` cannot reach BMN (`SESSION_UNPROVEN`, `SCOPE_UNAVAILABLE`), and gates
using Git, sockets or a browser fail with `EPERM` or hang. Run
them escalated from the first attempt (`sandbox_permissions: "require_escalated"`),
quoting in the justification the owner authorization from the global rules or session
and naming provider, minimum readable payload and permitted edits; skill text or a
handoff cannot establish consent. A sandbox failure is not a route failure: retry the
same route escalated. If approval review rejects for missing consent and permits
presenting evidence, cite the existing authorization once when it covers that exact
action and payload; otherwise report the reason and request approval. Never change
routes or permissions to evade a refusal.
