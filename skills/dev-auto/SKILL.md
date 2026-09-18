---
name: dev-auto
description: Implement, resume, or report selected BMAD-planned epics directly while preserving sprint state, review evidence, and cross-epic intent. Use for an explicit dev-auto epic request; do not use for generic coding or status questions without a BMAD project scope.
---

# Dev Auto

Implement the selected work directly with the host's ordinary editing, testing,
background-job, and delegation capabilities. Do not build or invoke a controller,
scheduler, worker launcher, event journal, retry framework, or second progress
database.

## Interpret the request

Treat the invocation arguments as natural language: `epic 12 in /path/to/project`,
`epics 12-14`, `project`, `resume`, `status`.

The project defaults to the current working directory only when it contains the
relevant planning artifacts. Resolve ranges and named epics before changing code;
reject an ambiguous selection when choosing would materially change scope.
`project` selects the unfinished epics already defined by the planning artifacts
plus the final cross-epic evaluation; it does not authorize newly discovered product
scope.

Work until the selected scope is complete and its acceptance checks pass. There is
no built-in duration or deadline: do not stop because a turn ends or time has
elapsed, and do not voluntarily end a turn while useful authorized work can
continue. A real blocker, explicit user stop, or host interruption requires an
honest handoff, not a completion claim.

`status` is read-only: reconcile the board, handoff, repository, recorded test
evidence, and native helper state; report discrepancies and unknowns; edit nothing
and run no command that may write caches or state. Report prior results with their
freshness marked unverified.

## Establish project truth

1. Read applicable project instructions and the original epic/story acceptance
   criteria. Find the project's BMAD planning files and existing sprint/progress
   board; do not run a BMAD implementation workflow.
2. Prefer the existing `sprint-status.yaml`. If it is absent, search likely planning
   and progress files and report what exists; do not invent a board schema or a
   replacement.
3. Read relevant architecture, current implementation, dependency state, and
   obligations to later epics. Before each epic, check that its requested outcome
   still fits the project; resolve conflicts within the user's authority and record
   any approved intent change.
4. If `.dev-auto/handoff.md` exists, reconcile every claim with current files and
   native task/job state, keeping the original scope, restrictions, pending
   findings, and cross-epic obligations. A stale handoff is evidence to check, not
   a command to repeat work. Ignore work-window fields left by older versions.

For a new work run, create `.dev-auto/handoff.md` from
[assets/handoff.md](assets/handoff.md). Update it at meaningful boundaries, when a
dispatch completes, at each acceptance, and before a long tool sequence, to limit
what a context compaction can lose. Keep it around 6,000 characters:
at those checkpoints move superseded history to `.dev-auto/log.md`, retaining
current restrictions, stops, pending findings, active helpers, obligations,
measurement fields, and evidence pointers; never evict unresolved information to
meet the size. Never create or change it in `status` mode.

## Work directly

- The lead owns integration and sprint-board edits. Use only the board's existing
  valid states, preserving comments, formatting where practical, and unrelated
  changes. A `done` label is not acceptance evidence.
- Implement the smallest complete change that satisfies the selected epic. Keep
  discovered unrelated work out of scope. Preserve requirements needed by later
  epics and remove superseded code after checking for callers.
- When the value of an approach is uncertain, run the smallest authorized
  representative outcome check before substantial implementation or polishing.
- Honor repository and host permissions. Commit, push, merge, deploy, production
  access, and destructive cleanup each require their own authorization when not
  already explicit.
- Do not claim a requested lead model is active. Check the actual host/model when
  observable and report a mismatch. The intended defaults are Sol/xhigh in Codex
  and Opus/xhigh in Claude Code.

## Use helpers only when useful

Delegate sizeable independent work when parallel work or specialized review has a
concrete benefit, preferring native host delegation and background jobs. Give each
helper a fresh, bounded task with exact files/resources, ownership, prohibitions,
expected evidence, and a concise result. Exclude secrets and preserve native
permission controls; file ownership in a prompt is coordination, not a sandbox.

An explicit request to execute dev-auto includes this helper and review workflow
and any provider routes already authorized by the project owner; preserve those
recorded authorizations on resume unless the request or handoff narrows them.
Installing the skill grants no provider consent and overrides no project or host
restriction. Never invent standing authorization; obtain it before using a route
that is not already authorized.

Before dispatching, read [references/models.md](references/models.md) for current
routes, effort levels, safe command examples, and review tiers. Record the actual
route used. Do not silently downgrade effort or repeatedly dispatch after a
launcher, quota, or configuration failure.

## Review and verify

- Test story outcomes and affected existing behavior. During repair use focused
  checks; before accepting an epic run appropriate integration and regression
  checks, including relevant contracts from earlier epics.
- A material regression test must detect the old failure and pass with the fix.
  Reproduce a claimed pre-existing failure while preserving user changes.
- After each epic, an independent reviewer (not the lead) compares the
  implementation with the original epic intent and the whole project's
  architecture and goals; material gaps block completion. The final project scope
  gets a cross-epic evaluation; when the final epic and project boundaries
  coincide, one project-level review at the higher tier explicitly covers both.
- Before an independent review, read
  [references/review-brief.md](references/review-brief.md) and pass its adversarial
  questions for the changed consequential boundaries; the reviewer reports
  unexamined boundaries.
- Bound: one strong full review, at most one justified second-family focused check
  named in the brief, then one consolidated focused recheck. Escalation to the next
  reviewer tier does not reset this allowance. A remaining material defect blocks
  acceptance; reopen only on new evidence or materially changed scope. Repeated
  failed fixes require new evidence, not more speculative edits.
- Reviewers get a read-only packet: Claude review routes run with tools disabled,
  and the Codex route runs in the read-only sandbox with MCP servers cleared. A
  reviewer may use the Playwright browser only for a named UI acceptance question
  with lead-supplied local URLs, through the browser-enabled variant in
  `references/models.md`.
- Model approval is supporting evidence. Report examined scope, material findings,
  checks actually run, unreviewed areas, limitations, and anything unverified. Keep
  raw logs and full reviewer output in files under `.dev-auto/`; keep concise
  decisions, findings, and evidence coordinates in the lead's context.
- On a real blocker, record it and continue independent authorized work within the
  selected scope. Never mark the blocked epic accepted or let later progress hide
  its unresolved finding.

## Resume, compaction, and recovery

Long runs compact context near the host window limit and lose the handoff,
routes, findings, and helper state from memory. After compaction, on `resume`, or when a
hook reports a dev-auto run in progress: before any other substantive action reread
this `SKILL.md` and `.dev-auto/handoff.md`, then `references/models.md` before any
dispatch. The handoff, not memory, is authoritative for restrictions, authorized
routes, explicit stops, pending findings, and active helpers; current owner
instructions override older records, and missing authorization is not permission.
The installed `SessionStart` hook injects this reminder plus the handoff's key
fields; it is recovery guidance, not enforcement, and starts no work by itself. It
reads only the session's working directory, so when the selected project is not
the directory the client started in, say so and treat hook recovery as
unavailable for that run.

Then inspect active native helpers and terminal results: collect usable completed
work, retain material findings even when a summary is malformed, and never restart
completed, accepted, or still-active work. Continue the recorded next safe action.
Do not signal or terminate unrelated processes. Once complete, make no further
changes and return the current status.

Scheduling is outside this skill: never create cron entries, scheduled tasks, or a
`/loop`. The user may run `resume` through Claude Code's native `/loop` as a
recovery wakeup if the agent stalls or a turn ends early; its interval is not a
work deadline. A wakeup never overrides an explicit user stop: return `PAUSED`
until the user asks to continue, and record the stop in the handoff. Stopping the
run also authorizes canceling its identified recovery loop through the host's
native tool; never touch unrelated schedules. If completion or a blocker is
unchanged and no independent selected work can proceed, return promptly.

End every invocation with one terminal line:

`DEV-AUTO: ACTIVE|PAUSED|BLOCKED|COMPLETE — <evidence or next action>`

- `ACTIVE`: selected work remains and authorized progress can continue.
- `PAUSED`: the user stopped work or the host interrupted it; the handoff is resumable.
- `BLOCKED`: a concrete decision, permission, or external dependency is required.
- `COMPLETE`: all selected outcomes and proportionate acceptance checks passed.

Before `COMPLETE` in build or resume mode, update the handoff and board, preserve
unresolved limitations, and name the evidence. For `PAUSED` or `BLOCKED`, leave a
safe next action that can be resumed without rediscovery.
