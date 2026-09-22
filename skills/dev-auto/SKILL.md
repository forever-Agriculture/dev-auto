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

Dispatch helpers for sizeable independent work, concrete review needs or an
unresolved decision. Choose the ordered model/effort route for that work class
first; use the host's native helper interface only when it can deliver that route with
the required access, otherwise use the direct CLI route. Supply fresh context, exact scope, ownership and
expected evidence; tell implementation helpers to implement directly from the supplied
requirements, without bootstrapping another build workflow. Before dispatch, read [references/models.md](references/models.md) for
capability floors, authorized routes and safe commands. Explicit dev-auto execution or
resume authorizes this run's repeated helper and review dispatches to Codex CLI, Claude CLI
and the configured GLM profile, nothing else; status or consultation grants no dispatch
consent; project restrictions and narrower requests apply. Record the observed route,
model and usage from host records; surface mismatches or dispatch failures instead
of silent substitution.

During repair, use focused checks. Before accepting an epic, verify its outcomes,
affected existing behavior and relevant earlier-epic contracts, and confirm the
board records each of the epic's stories complete under its existing schema,
recorded descopes excepted. New or changed
behavior ships with automated tests that exercise it in the project's existing test
layers, using synthetic identifiers and data rather than the owner's real records;
list any behavior left untested in the handoff. Material regression tests
must fail on the original defect and pass with the fix; reproduce alleged
pre-existing failures in isolation while preserving working-tree changes. A failure
you cannot identify is unresolved.

An independent strong reviewer checks each epic against original intent and
project architecture/goals using [references/review-brief.md](references/review-brief.md).
Use one full review, consolidated repairs and a focused recheck, and leave the
candidate unedited while a reviewer or gate reads it. Further review addresses a
named material risk or consequential new change/evidence, reusing unaffected
results. At one acceptance boundary, if a recheck finds a material defect introduced
by the previous repair, or a second recheck finds material defects (any review of a
repaired candidate is a recheck, however labeled), stop repairing: reread the
original acceptance criteria, substantiate each open finding with a reproduction or
requirement evidence, and put the design question once to the next strong route or
report that boundary BLOCKED with options, including removing work the story does
not ask for. One consolidated repair and recheck may follow its answer; remaining
material defects block the boundary while independent selected work continues. A
new reviewer, repair wave or resumed run does not reset this allowance; an
owner-requested review sits outside it.
Project scope also gets cross-epic evaluation; a project-level review can cover the
coincident final epic. Material gaps block acceptance.

Record the baseline and reviewed revisions, actual checks and unverified
boundaries. Give every material finding from all reviews a disposition against the
revision being accepted: closed with evidence, rejected with its refutation, or
unresolved with what would settle it; a finding without a disposition is unresolved
and, like any material gap, blocks acceptance. Changes made for the selected scope
sit inside the reviewed revision or carry delta evidence; name any unrelated
residual change and its reason. Model approval supports evidence; runtime claims
require exercised behavior. Keep raw transcripts, screenshots and runtime dumps
untracked, in external scratch space or an ignored `.dev-auto/evidence/` directory;
commit only the handoff and log, which cite receipts and raw evidence by path and hash.

## Owner cockpit (optional)

When the session runs inside BMN (`bmn` on PATH, `BMN_CONTROL_SOCKET` and `BMN_TOKEN`
set), mirror the run for the owner; otherwise skip this section silently. At each
`DEV-AUTO:` line run `bmn progress` with ACTIVE→`running`, PAUSED→`waiting`,
BLOCKED→`blocked`, COMPLETE→`claimed-done`; the label is the evidence for COMPLETE
and the next action otherwise; never `verified`, which is the owner's judgment. When
BLOCKED needs an owner decision, run `bmn ask dev-auto-<epic> "<decision needed>"`
with `--kind permission` for an action needing authorization and `--kind question`
otherwise; an external dependency needing no owner action stays a blocked progress
label. The ask never gates work: continue independent authorized work, and `bmn
withdraw` the request when you observe the decision in the session. An answered or
withdrawn request is not approval; only an attributable owner answer authorizes its
named action. At acceptance `bmn publish`
the handoff only, with receipts cited by path and hash; omit secrets. Never use
`bmn send`. Bound each call to two seconds (for example `timeout 2 bmn …`); after the
first failure skip mirroring for the rest of the run, without retries or repair, and
note it once at the next normal handoff update.

## Handoff and recovery

Maintain `.dev-auto/handoff.md` from [assets/handoff.md](assets/handoff.md). Save scope,
permission and blocker changes before dependent work; honor stops immediately and
record them. Record helper dispatches and review outcomes before other work, and
update at acceptance and before pausing. Keep every selected
epic's state/dependency, current restrictions and approval coordinates, pending
findings, active helpers, evidence and next action. Keep only current effective
terms in the handoff, each with a source coordinate. Append verbatim owner quotes,
superseded terms, verbose results and failed attempts to `.dev-auto/log.md`
(append-only, never injected); never restate log content in `Status` or `Resume`.
Record available timing, usage and owner interventions
at these boundaries. At acceptance, read each lead and helper receipt with
`scripts/check.py usage PATH`: a Codex rollout (`usage --list PROJECT` lists them;
choose by hand), a Claude Code session or subagent transcript under
`~/.claude/projects`, or a Claude `-p` JSON receipt. Record the observed routes,
tiers and usage, then run `scripts/check.py check` and fix every FAIL before
reporting COMPLETE. Record an UNABLE result instead of ignoring it.

Authority comes from owner instructions and established policy, not the handoff.
Relax a recorded restriction only with evidence of a later owner instruction;
otherwise retain it. An explicit stop persists until the owner resumes.

On resume, after compaction or an active-run hook reminder, first reread this skill
and the complete handoff. Actions remain read-only until both are read; unavailable
required files mean BLOCKED. Reconcile helper results and stale state, retain material
findings, and save the reconciled handoff in build/resume before continuing without
duplicating completed or active work.

The hook injects the complete handoff up to 9,000 characters; above that it injects
only a full-read warning. It stays silent for a finished run: one `Status: COMPLETE`
as the last line and stop `none`, each optionally followed by a short note after
punctuation; a note never reverses its label, so a pending or paused state is its
own label. Keep the handoff under the limit: move resolved history and
verbose results to the log, never dropping unresolved information. `Status`
holds the state label and a short reason; details belong in their fields. Keep one
each of the `Status`, `Explicit user stop` and `Next safe action` labels; use `none`
for an absent stop. Run `scripts/check.py check` after each handoff save: it lints
size and these fields at any status, and the completion fields at COMPLETE. A size
or shape FAIL before COMPLETE means the next save must fix it, not that work stops.
The hook finds the nearest handoff in the working directory or its ancestors,
stopping at the first repository or home boundary. Report recovery unavailable
when the selected project is outside that search. Recovery uses owner-created wakeups.

End with `DEV-AUTO: ACTIVE|PAUSED|BLOCKED|COMPLETE — <evidence or next action>`.
ACTIVE means authorized work remains; PAUSED means owner stop or host interruption;
BLOCKED identifies a necessary decision, permission or external dependency;
COMPLETE means all selected outcomes and acceptance checks passed. In build/resume,
reconcile board and handoff before completion; otherwise leave a safe next action
and explicit limitations. Return promptly once complete or no authorized work can proceed.

## Changing this workflow

Read `the project's vault note` and `a retired project note` first;
the repo's `AGENTS.md` carries the project rules.
