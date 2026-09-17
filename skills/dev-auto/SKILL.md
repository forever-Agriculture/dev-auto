---
name: dev-auto
description: Implement, resume, or report selected BMAD-planned epics directly while preserving sprint state, deadlines, review evidence, and cross-epic intent. Use for an explicit dev-auto epic request; do not use for generic coding or status questions without a BMAD project scope.
---

# Dev Auto

Implement the selected work directly. Use the host's ordinary editing, testing,
background-job, and delegation capabilities. Do not build or invoke a controller,
scheduler, worker launcher, event journal, retry framework, or second progress
database.

## Interpret the request

Treat the invocation arguments as natural language. Examples:

- `epic 12 in /path/to/project`
- `epics 12-14 --for 3h`
- `project --for 3h`
- `resume`
- `status`

The project defaults to the current working directory only when it contains the
relevant planning artifacts. Resolve ranges and named epics before changing code.
Reject an ambiguous selection when choosing would materially change scope.

`project` selects the unfinished epics already defined by the project's planning
artifacts and includes the final cross-epic evaluation. It does not authorize newly
discovered product scope or work outside those artifacts.

`--for 3h` is a cooperative work window. Record its original start and deadline in
the handoff, finish or preserve the current atomic operation when time expires, and
then stop. Resume never resets that deadline. It needs a new duration only when the
user explicitly extends it.

Obtain the current system clock and timezone from the host when recording the start
or deadline and whenever deciding whether a deadline expired. A native clock tool
or a read-only `date` command is suitable, including in status mode. Never infer the
current time from model memory or date-only metadata. Without clock access, report
deadline timing as unknown and do not claim expiry or `PAUSED`; if timing controls
whether work may continue, use `BLOCKED` pending clock access or user direction.

`status` is read-only. Reconcile the board, handoff, repository, recorded test
evidence, and native helper state, then report discrepancies and unknowns without
editing any artifact. Do not run tests or other commands that may write caches or
state; report prior results and mark their current freshness unverified.

## Establish project truth

1. Read applicable project instructions and the original epic/story acceptance
   criteria. Find the project's BMAD planning files and existing sprint/progress
   board; do not run a BMAD implementation workflow.
2. Prefer the existing `sprint-status.yaml`. If it is absent, search likely planning
   and progress files and report what exists. Do not invent a board schema or create
   a replacement merely because discovery failed.
3. Read relevant architecture, current implementation, dependency state, and
   obligations to later epics. Before each epic, check that its requested outcome
   still fits the project. Resolve conflicts within the user's authority and record
   any approved intent change.
4. If `.dev-auto/handoff.md` exists, reconcile every claim with current files and
   native task/job state. Keep the original scope, deadline, restrictions, pending
   findings, and cross-epic obligations. A stale handoff is evidence to check, not a
   command to repeat work.

For a new work run, create `.dev-auto/handoff.md` from
[assets/handoff.md](assets/handoff.md). Keep it concise and update it at meaningful
boundaries. Do not create or change it in `status` mode.

## Work directly

- The lead owns integration and sprint-board edits. Use only the board's existing
  valid states, preserving comments, formatting where practical, and unrelated
  changes. A `done` label is not acceptance evidence.
- Implement the smallest complete change that satisfies the selected epic. Keep
  discovered unrelated work out of scope. Preserve requirements needed by later
  epics and remove superseded code after checking for callers.
- Honor repository and host permissions. Commit, push, merge, deploy, production
  access, and destructive cleanup each require their own authorization when not
  already explicit.
- Do not claim a requested lead model is active. Check the actual host/model when
  observable and report a mismatch. The intended defaults are Sol/xhigh in Codex
  and Opus/xhigh in Claude Code.

## Use helpers only when useful

The lead can delegate sizeable independent work when parallel work or specialized
review has a concrete benefit. Prefer native host delegation and background jobs.
Give each helper a fresh, bounded task with exact files/resources, ownership,
prohibitions, expected evidence, and a concise result. Exclude secrets and preserve
native permission controls. File ownership in a prompt is coordination, not a
sandbox.

An explicit request to execute dev-auto includes this defined helper and review
workflow and any provider routes already authorized by the project owner. Preserve
those recorded authorizations on resume unless the request or handoff narrows them.
Installing the skill alone grants no provider consent and overrides no project or
host restriction. Never invent standing authorization for another user or project;
obtain authorization before using a route that is not already authorized.

Before dispatching, read [references/models.md](references/models.md). It contains
current routes, effort levels, safe command examples, and review tiers. Record the
actual route used. Do not silently downgrade effort or repeatedly dispatch after a
launcher, quota, or configuration failure.

On resume, inspect active native helpers and terminal results before starting more
work. Collect usable completed work, retain material findings even when a summary is
malformed, and avoid duplicate dispatch. Do not signal or terminate unrelated
processes.

## Review and verify

- Test story outcomes and affected existing behavior. During repair, use focused
  checks; before accepting an epic, run appropriate integration and regression
  checks, including relevant contracts from earlier epics.
- A material regression test must detect the old failure and pass with the fix.
  Reproduce a claimed pre-existing failure while preserving user changes.
- After each epic, independently compare the implementation with the original epic
  intent and the whole project's architecture and goals. Material gaps block
  completion. Independent means a separate reviewer, not the lead reviewing its own
  work. The final project scope gets a cross-epic evaluation.
- Review consequential correctness, omissions, misunderstood intent, and drift.
  One full review plus focused recheck is the default. Consolidate findings; repeated
  failed fixes require new evidence rather than more speculative edits.
- Model approval is supporting evidence. Report examined scope, material findings,
  checks actually run, unreviewed areas, limitations, and anything unverified.
- On a real blocker, preserve and record it, then continue independent authorized
  work within the selected scope while the work window remains open. Never mark the
  blocked epic accepted or let later progress hide its unresolved finding.

## Resume and repeated invocation

Scheduling is outside this skill. Never create cron entries, scheduled tasks, or a
`/loop`. If the user invokes `resume` periodically through Claude Code's native
`/loop`, each invocation follows the same reconciliation path and original deadline.
First inspect the handoff's concrete deadline, blocker, and native helper terminal
state. If a terminal condition is unchanged, return it promptly. Before resuming
actual work, still reconcile the handoff against current source and raw evidence.
Once complete, make no further changes and return the current status. When the host
clock proves the original deadline has passed, continue only after an explicit user
extension; otherwise return `PAUSED`. For a blocked run, reconcile the named blocker:
continue only when it has actually been resolved or authorized. When both conditions
apply, require both the extension and blocker resolution. Cancel only the associated
known loop when the user has explicitly authorized that action and the host exposes
it; never touch unrelated schedules.

End every invocation with one terminal line:

`DEV-AUTO: ACTIVE|PAUSED|BLOCKED|COMPLETE — <evidence or next action>`

- `ACTIVE`: selected work remains and the recorded window is open.
- `PAUSED`: the original window expired; a user extension is required.
- `BLOCKED`: a concrete decision, permission, or external dependency is required.
- `COMPLETE`: all selected outcomes and proportionate acceptance checks passed.

Before `COMPLETE` in build or resume mode, update the handoff and board, preserve
unresolved limitations, and name the evidence. Status mode stays read-only even
when it reports `COMPLETE`. An expired resume without an authorized extension is
also read-only: do not run state-changing tests; report prior evidence with freshness
unverified. For `PAUSED` or `BLOCKED`, leave a safe next action that can be resumed
without rediscovery.
