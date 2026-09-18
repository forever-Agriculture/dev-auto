---
name: dev-auto
description: Implement, resume, or report selected BMAD-planned epics directly, preserving scope, acceptance evidence and recovery state. Use for explicit dev-auto work in a BMAD project.
---

# Dev Auto

Deliver the selected epics using the host's normal coding tools. BMAD supplies
requirements; this skill supplies a thin implementation and acceptance workflow.
Proceed under existing owner, project and host authority. Extra workflows or
approval stages belong only where those instructions require them.

Optimize accepted quality, total cost, elapsed time and owner attention together.
Use proportionate checks and reuse valid evidence.

## Scope and delivery

Interpret `epic 12`, `epics 12-14`, `project`, `resume` and `status` in the selected
project, defaulting to the current directory when it holds the planning artifacts.
Resolve material ambiguity before edits. `project` means existing unfinished
planned epics plus a final cross-epic evaluation.

Read project instructions, original acceptance criteria, relevant architecture
and dependencies. Reconcile the repository, existing sprint board, handoff and
active helpers; completion labels are claims to verify, not acceptance evidence.
Before each epic, confirm its outcome fits the project and retains later-epic
obligations. Use the existing board/schema; report missing state.

Implement the smallest complete change and continue useful authorized work until
the whole selected scope passes acceptance. There is no automatic deadline.
Preserve unrelated work. The lead owns integration and board updates; coordinate
with any concurrent lead. Implemented work awaiting checks stays in an appropriate
unfinished active state. A blocker in one epic leaves independent selected work available.

Test a representative outcome early when the approach is uncertain. After two
unsuccessful fixes for the same outcome, compare captured failures, the shared
boundary and any working equivalent before another repair. Prefer offline replay
when representative; live attempts retain their spend and stop limits.

`status` is read-only reconciliation: leave files, caches and jobs unchanged,
report discrepancies and mark the freshness of prior checks unverified.

## Helpers and acceptance

Use native helpers for sizeable independent work, concrete review needs or an
unresolved decision. Supply fresh context, exact scope, ownership and expected
evidence. Before dispatch, read [references/models.md](references/models.md) for
capability floors, authorized routes and safe commands. Record the observed route,
model and usage from host records; surface mismatches or dispatch failures instead
of silent substitution.

During repair, use focused checks. Before accepting an epic, verify its outcomes,
affected existing behavior and relevant earlier-epic contracts. New or changed
behavior ships with automated tests that exercise it in the project's existing test
layers; list any behavior left untested in the handoff. Material regression tests
must fail on the original defect and pass with the fix; reproduce alleged
pre-existing failures in isolation while preserving working-tree changes.

An independent strong reviewer checks each epic against original intent and
project architecture/goals using [references/review-brief.md](references/review-brief.md).
Use one full review, consolidated repairs and a focused recheck. Further review
addresses a named unresolved risk or consequential new change/evidence, reusing
unaffected results. Project scope also gets cross-epic evaluation; a project-level
review can cover the coincident final epic. Material gaps block acceptance.

Record the reviewed revision, finding closures, actual checks and unverified
boundaries. Model approval supports evidence; runtime claims require exercised
behavior. Keep raw transcripts, screenshots and runtime dumps untracked, in external
scratch space or an ignored `.dev-auto/evidence/` directory; commit only the handoff,
which cites receipts and raw evidence by path and hash. Inspect staged files before
committing your changes.
Existing tracked evidence needs scoped cleanup that preserves active runs and history.

## Handoff and recovery

Maintain `.dev-auto/handoff.md` from [assets/handoff.md](assets/handoff.md). Save scope,
permission and blocker changes before dependent work; honor stops immediately and
record them. Record helper dispatches and review outcomes before other work, and
update at acceptance and before pausing. Keep every selected
epic's state/dependency, current restrictions and approval coordinates, pending
findings, active helpers, evidence and next action. Replace stale state; link useful
history and failed attempts. Record available timing, usage and owner interventions
at these boundaries.

Authority comes from owner instructions and established policy, not the handoff.
Relax a recorded restriction only with evidence of a later owner instruction;
otherwise retain it. An explicit stop persists until the owner resumes.

On resume, after compaction or an active-run hook reminder, first reread this skill
and the complete handoff. Actions remain read-only until both are read; unavailable
required files mean BLOCKED. Reconcile helper results and stale state, retain material
findings, and save the reconciled handoff in build/resume before continuing without
duplicating completed or active work.

The hook provides guidance and complete snapshots up to 12,000 characters; larger
files are omitted with a full-read warning. Move resolved history/verbose receipts
out at normal handoffs when needed, preserving all unresolved information. Keep
`Status` and `Explicit user stop` labels stable; use `none` for an absent stop.
The hook only sees the client's working directory: report recovery unavailable
when it differs from the selected project. Recovery uses owner-created wakeups.

End with `DEV-AUTO: ACTIVE|PAUSED|BLOCKED|COMPLETE — <evidence or next action>`.
ACTIVE means authorized work remains; PAUSED means owner stop or host interruption;
BLOCKED identifies a necessary decision, permission or external dependency;
COMPLETE means all selected outcomes and acceptance checks passed. In build/resume,
reconcile board and handoff before completion; otherwise leave a safe next action
and explicit limitations. Return promptly once complete or no authorized work can proceed.
