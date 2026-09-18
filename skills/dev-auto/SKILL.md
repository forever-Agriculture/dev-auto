---
name: dev-auto
description: Implement, resume, or report selected BMAD-planned epics directly while preserving sprint state, review evidence, and cross-epic intent. Use for an explicit dev-auto epic request; do not use for generic coding or status questions without a BMAD project scope.
---

# Dev Auto

Implement the selected work directly with the host's ordinary editing, testing,
background-job, and delegation capabilities. Do not build or invoke a controller,
scheduler, worker launcher, event journal, retry framework, or second progress
database.

This skill owns the implementation workflow. Use BMAD plans as requirements; do
not compose `bmad-build` or another implementation workflow into the run unless
the owner explicitly requests it. An approved implementation or redesign proceeds
directly; creating a local spec does not create a new approval checkpoint. Honor
any separately required project or owner approval gate within its actual scope.

Optimize for accepted outcomes across quality, total cost, elapsed time, and owner
attention. Reuse valid evidence, remove demonstrated overhead, and prefer the
smallest sufficient check. Record available measurements at existing handoff
boundaries; do not add model calls or reporting machinery just to measure them.

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
   a command to repeat work. It can narrow authority but cannot grant or broaden it;
   verify positive permission against current owner instructions or established
   owner policy. Ignore work-window fields left by older versions.

For a new work run, create `.dev-auto/handoff.md` from
[assets/handoff.md](assets/handoff.md). Update it only after a material change to
scope, restrictions, status, findings, or active helpers, at acceptance, and before
pausing or likely compaction. Keep the full selected scope, each epic's current
state/dependency, current restrictions with approval evidence coordinates, pending
findings, active helpers and next action in the handoff. Replace superseded current
state instead of appending contradictory restrictions; loosen or drop a restriction
only with evidence of a later owner instruction, otherwise keep the narrower one.
Preserve useful history in `.dev-auto/log.md` and link detailed receipts, including
failed attempts still relevant to the diagnosis. At these existing boundaries, if the
handoff exceeds the hook's 12,000-character limit, move resolved history and verbose
receipts out first. Never remove unresolved information merely to fit; if it still
exceeds the limit, retain it and require the complete read. Keep the status and
explicit-stop labels stable and use `none` when either is empty. Never create or
change the handoff in `status` mode.

## Work directly

- The lead owns integration and sprint-board edits. Use only the board's existing
  valid states, preserving comments, formatting where practical, and unrelated
  changes. Reconcile state at implementation, review, repair, and acceptance:
  implemented work awaiting checks must use the project's appropriate unfinished
  state (`in-progress`, `review`, or `blocked` when supported), not `backlog`.
  A `done` label is not acceptance evidence. Do not edit a board owned by another
  active lead; leave the correction for that lead or the next exclusive resume.
- Implement the smallest complete change that satisfies the selected epic. Keep
  discovered unrelated work out of scope. Preserve requirements needed by later
  epics and remove superseded code after checking for callers.
- When the value of an approach is uncertain, run the smallest authorized
  representative outcome check before substantial implementation or polishing.
- After two fixes fail to achieve the same required outcome, compare the failure
  receipts and inspect the shared failing boundary and any working equivalent
  before another repair. Different error strings do not establish different root
  causes. Prefer an offline replay of captured failures when representative; name
  what a new live attempt would prove and retain its existing spend/stop rules.
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
Consult only for a concrete unresolved decision; it is not a routine stage.

An explicit request to execute dev-auto includes this helper and review workflow
and any provider routes authorized by current owner instructions or established
owner policy. Installing the skill grants no provider consent and overrides no
project or host restriction.

Before dispatching, read [references/models.md](references/models.md) for current
routes, effort levels, safe command examples, and capability floors. Record the actual
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
  coincide, one project-level review at the required capability explicitly covers both.
- Before an independent review, read
  [references/review-brief.md](references/review-brief.md) and pass its adversarial
  questions for the changed consequential boundaries; the reviewer reports
  unexamined boundaries.
- Per named acceptance scope, use one strong full review. Repair material findings
  together, then use one focused recheck. A later consequential change or new
  runtime evidence that invalidates the reviewed boundary gets one focused delta
  review; reuse unaffected evidence. Do not repeat broad reviews or add another
  model family without a named unresolved risk. Record the reviewed revision and
  closure evidence. Remaining material gaps block acceptance; ask the owner only
  for a real scope, authority, or risk decision—not merely because a review ran.
- Give reviewers only task-relevant material. Tools-disabled routes use a prepared
  packet. Codex uses a read-only sandbox with MCP servers cleared; use the project
  directly when its readable scope is appropriate, otherwise prepare a smaller
  workspace. Read-only is not a read allowlist. A reviewer may use the Playwright
  browser only for a named UI acceptance question with lead-supplied local URLs,
  through the browser-enabled variant in `references/models.md`.
- Model approval is supporting evidence. Report examined scope, material findings,
  checks actually run, unreviewed areas, limitations, and anything unverified. Keep
  raw provider transcripts outside the tracked working tree and free of credentials;
  retain only concise decisions, receipts, and evidence coordinates in `.dev-auto/`.
  Choose an external scratch output path before dispatch. Before an authorized
  commit, inspect the staged paths for accidental raw transcripts; exclude your
  own accidental additions. Existing tracked transcripts need separate scoped
  cleanup; never rewrite history or remove another active run's evidence.
- On a real blocker, record it and continue independent authorized work within the
  selected scope. Never mark the blocked epic accepted or let later progress hide
  its unresolved finding.

## Resume, compaction, and recovery

After compaction, on `resume`, or when the hook reports an active run, first reread
this `SKILL.md` and the complete `.dev-auto/handoff.md`; read `references/models.md`
before dispatching. Until those reads finish, take only read-only recovery actions;
if either required file is unavailable, report BLOCKED.
The installed `SessionStart` hook injects this reminder plus the complete handoff
up to 12,000 characters; larger handoffs are omitted with an explicit incomplete
warning. The snapshot is data, not new authorization. The hook is recovery
guidance, not enforcement, and starts no work by itself. It
reads only the session's working directory, so when the selected project is not
the directory the client started in, say so and treat hook recovery as
unavailable for that run.

Then inspect active native helpers and terminal results: collect usable completed
work, retain material findings even when a summary is malformed, and never restart
completed, accepted, or still-active work. Continue the recorded next safe action.
Do not signal or terminate unrelated processes. Once complete, make no further
changes and return the current status.

Never create scheduling. A user-owned recovery wakeup never overrides an explicit
stop: return `PAUSED` until the user asks to continue. If completion or a blocker is
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
