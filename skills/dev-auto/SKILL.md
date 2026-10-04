---
name: dev-auto
description: Implement, resume, or report selected BMAD-planned epics directly, preserving scope, acceptance evidence and recovery state. Use for explicit dev-auto work in a BMAD project.
---

# Dev Auto

Deliver the selected epics with the host's normal coding tools: BMAD supplies the
requirements, this skill a thin implementation and acceptance workflow under existing
owner, project and host authority, adding no extra workflow or approval stage they do
not require.
Optimize accepted quality, total cost, elapsed time and owner attention together. Each
check earns its place by a failure it prevents; reuse valid evidence.

## Owner decisions

The invocation and later owner instructions set the run's authority: scope, approved
spend and any delegation ("decide within the cap", "work autonomously"); record a
delegation, with its source quote, as a current handoff term; it carries through
compaction, resume and a fresh session, for the scope and total it named and no further.
Ask the owner once, in the session, with a recommendation, only about spend beyond
what he approved or delegated, changes to selected work
or its acceptance criteria, actions the global rules reserve to him, and credentials or
private data. Put technical decisions you cannot settle from the evidence to the
consultant. Decide everything else on your recommended option when it keeps the
requirements, acceptance criteria, privacy and limits; where his delegation permits,
that includes moving unused approved money between this run's paid jobs within the
total, keeping any narrower cap or retry limit he set and counting outstanding paid
commitments; money shared with another active lead moves only after that lead's
handoff records releasing it. Log each decision with its reason under
`Decided for you` in the handoff and the next report. A pending question never blocks
independent work. Authority comes from owner instructions and policy, not the handoff:
relax a recorded restriction only on a later owner instruction; an explicit stop
persists until he resumes.

## Scope and delivery

Interpret `epic 12`, `epics 12-14`, `project` (unfinished planned epics plus a final
cross-epic evaluation), `resume` and `status` in the selected project, defaulting to the
current directory when it holds the planning artifacts. `status` is read-only: change no
files, caches or jobs, report discrepancies and mark prior checks' freshness unverified.
Resolve material ambiguity before edits.

Read project instructions, original acceptance criteria, relevant architecture and
dependencies. Reconcile repository, sprint board, handoff and active helpers;
completion labels are claims to verify. Before each epic, confirm its outcome fits the
project and keeps later-epic obligations; use the existing board schema and report
missing state.

Each run works on its own branch in its own worktree with its own dependency
environment. Started in the default branch's checkout, create the worktree and work
only there if this session can edit it, otherwise end BLOCKED with the one command that
starts the lead in it; after compaction your handoff is the worktree's, whatever
checkout the session or hook points at. Never commit, stash or edit in another run's
checkout or dependencies, except your own epics' entries in untracked planning files
(board, story records) kept in the default checkout, reread just before each edit. A
run already active in the default checkout finishes there. Read planning files the
worktree lacks, or holds in an older version, from the default checkout; never commit,
stash or copy its uncommitted files. Never remove a run's
worktree yourself; before an owner-requested removal, move its `.dev-auto/` to the
default checkout's `.dev-auto/runs/<branch>/`. Moving an active run carries its
handoff, log, evidence and live-job coordinates, records the new owning checkout and
marks the old handoff a copy. The default branch receives work through an
owner-authorized merge by the designated maintainer. Prefer one lead session per epic:
independent selected epics run in parallel sessions and worktrees when the owner or BMN
starts them, and a lead moving to its next epic first saves a handoff a fresh session
could resume from.

Implement the smallest complete change and continue authorized work until the whole
selected scope passes acceptance; there is no automatic deadline. Preserve unrelated
work. The lead owns integration and the board: when a story or epic starts, gets a
measured outcome, blocks or is accepted, update its row in that step where the project
keeps its board (on the run's branch when the board is tracked, otherwise in the
default checkout), touching only its own epics' rows; implemented work awaiting checks
stays in an unfinished active state. A blocked epic leaves independent selected work
available. An outcome that depends on another party's system, access or decision ends
BLOCKED on that named gate once the project has proved its part; work inside other
teams' systems needs the owner to select it.

Test a representative outcome early when the approach is uncertain. After two
unsuccessful fixes for one outcome, or three failed runs in a row of one acceptance or
CI gate whatever fails in them, compare captured failures, the shared boundary and any
working equivalent; if still unresolved, ask the consultant. After that, with or without
an instruction not to stop, each further attempt at that outcome or gate needs a
different, evidence-backed method the consultant agrees, recording first the attempts,
gate runs, paid spend and the lead session's `check.py usage` total; without one the
boundary stays BLOCKED. An instruction not to stop lifts no authorization, spend or
acceptance gate. Measure bulk work such as fixtures or reference answers early; when its
review-and-repair rate cannot finish the scope at proportionate cost, change the method
or report BLOCKED. Prefer representative offline replay. Stop and ask before a paid call
that could exceed an owner cap, the approved total or an approved estimate no delegation
covers, and never raise a cap or the total yourself. Before a paid or long run, make the
cheapest live call to each external service it needs; a stubbed dry run proves nothing
about a service.

## Helpers and review

Read [references/models.md](references/models.md) at start and follow its routes and
dispatch rules; a lead never proceeds where its own provider may not read the
workspace. Helpers review and gather evidence; the lead writes code and tests and does
small lookups and checks directly. Dispatch consent comes from the owner's global rules
or session approval, never this skill; project restrictions apply. Exclude credentials
and unrelated private data; customer or production data needs approval naming
destination and data, then reused. Record each helper's observed route and model and
its receipt path (read each terminal receipt once, when collecting it, with
`scripts/check.py usage PATH`) and each lead session's ID; surface mismatches and
failures instead of silently substituting. Runs are evaluated from those records, so
beyond the brake's record do not tally time, usage or owner prompts.

Freeze the candidate and run the quick pre-review from
[references/review-brief.md](references/review-brief.md) alongside your own final
acceptance checks; make one consolidated repair of its material findings and failing
checks and rerun affected checks, with no second pre-review. An independent strong
reviewer then checks the epic against original intent, architecture and goals with the
same brief, using the pre-review map and your dispositions as navigation, not proof:
one full review, consolidated repairs and one focused recheck, the candidate unedited
while a reviewer or gate reads it. For web UI changes, add a browser-route check of the
running candidate at the lead-started loopback origin, against the acceptance criteria
with synthetic data. Further review needs a named material risk or a
consequential new change or evidence, reusing unaffected results.

From the full review on, at one acceptance boundary: if a recheck finds a material
defect introduced by the previous repair, or a second recheck finds material defects
(any review of a repaired candidate is a recheck), stop repairing. Reread the original
acceptance criteria, substantiate each open finding with a reproduction or requirement
evidence, and put the design question once to the consultant, whose method must keep
the requirements, acceptance criteria and limits (removing work the story does not ask
for is a valid answer). One consolidated repair and recheck may follow; remaining
material defects park that boundary BLOCKED with the consultant's options while
independent work continues, and an instruction not to stop follows the rule above. A
new reviewer, repair wave or resumed run does not reset this allowance; the pre-review
and owner-requested reviews sit outside it. Project scope adds a quick project
pre-review before the final cross-epic evaluation; project-level reviews can cover the
coincident final epic.

## Acceptance

Run required broad gates once at acceptance, reusing valid prior results; before a gate,
confirm the tests import this worktree's code and that local services, ports, compose
projects and mutable test data belong to this run. During repairs run affected checks,
broadening only when invalidated or required. New or changed behavior ships with
automated tests in the project's existing layers, using synthetic identifiers and data;
list untested behavior in the handoff. Material regression tests fail on the original
defect and pass with the fix; reproduce alleged pre-existing failures in isolation,
preserving working-tree changes. A failure you cannot identify is unresolved.

Before accepting an epic, verify its outcomes, the owner goals recorded for it,
affected existing behavior and earlier-epic contracts, and that the board records each
of its stories complete, recorded descopes excepted. Exercise the affected owner path
with representative state, including viewport visibility, usable actions and valid
media where relevant, rebuilding or packaging when that path requires it. Where only the
owner can exercise it (an installed release, phone or messaging), recommend one short
owner check and keep acceptance BLOCKED until it passes or he explicitly defers it,
recording it UNVERIFIED. Record baseline and reviewed revisions, actual checks and
unverified boundaries. Give every material finding from all reviews a disposition
against the accepted revision: closed with evidence, rejected with its refutation, or
unresolved with what would settle it. Changes for the selected scope sit inside the
reviewed revision or carry delta evidence; name any unrelated residual change and why.
Material findings without a disposition, material gaps and mandatory unverified gates
block acceptance.

## Handoff and recovery

Run state is local to each checkout and never committed; follow `scripts/check.py
check` notes about `.dev-auto/` and report tracked-state cleanup once. Keep receipts,
transcripts, screenshots and runtime dumps in `.dev-auto/evidence/`, cited by path and
hash, never in `/tmp` or session scratch. Before a merge touching a committed handoff or
log, copy yours aside and resolve a conflict by keeping your copy and untracking the
file (`git rm --cached`).

Maintain `.dev-auto/handoff.md` from [assets/handoff.md](assets/handoff.md). Save scope,
permission and blocker changes before dependent work; honor stops immediately and
record them; record helper dispatches and review outcomes before other work; update at
acceptance and before pausing. Keep each selected epic's state and dependency, current
restrictions and approval coordinates, pending findings, active helpers, evidence and
next action, as current terms with source coordinates. Append verbatim owner quotes,
superseded terms, verbose results and failed attempts to the append-only
`.dev-auto/log.md`, never restated in `Status` or `Resume`.

Keep the handoff within the recovery hook's 9,000-character snapshot by moving
resolved history and verbose results to the log, never dropping unresolved
information. Keep one each of `Status` (label and short reason), `Explicit user stop`
(`none` when absent) and `Next safe action`. A finished run ends with `- Status:
COMPLETE` as the last line and stop `none`, each optionally followed by a short note
after punctuation that never reverses its label. Run `scripts/check.py check` after
every handoff save, in the same tool call where the host allows; fix a FAIL at the next
save and every FAIL before COMPLETE, and record an UNABLE result.

On `resume`, compaction or an active-run hook reminder, first reread this skill and the
complete handoff; act read-only until both are read, and report BLOCKED if a required
file is unavailable. Verify this checkout's handoff scope and owning checkout; if
missing, inherited or finished, or the owner names work it does not hold, find
unfinished runs in other worktrees (`git worktree list`), treating a handoff as a copy
only when a different owning checkout is established; resume the named run and ask only
if still ambiguous. Reconcile helper results and stale state and keep material
findings; in build/resume, save the reconciled handoff before continuing, without
duplicating completed or active work. Report recovery unavailable when the project lies
outside the session's repository; recovery uses owner-created wakeups.

End with `DEV-AUTO: ACTIVE|PAUSED|BLOCKED|COMPLETE — <evidence or next action>`.
ACTIVE: authorized work remains; PAUSED: owner stop or host interruption; BLOCKED: a
necessary decision, permission or external dependency; COMPLETE: all selected outcomes
and acceptance checks passed. In build/resume, reconcile board and handoff before
COMPLETE; otherwise leave a safe next action and explicit limitations. Return promptly
when no authorized work can proceed.

## Owner cockpit (optional)

Inside BMN (`bmn` on PATH, `BMN_CONTROL_SOCKET` and `BMN_TOKEN` set; test presence,
never print values), follow [references/bmn-cockpit.md](references/bmn-cockpit.md) for
progress, questions and acceptance publication; otherwise skip it silently. Owner
answers must arrive in the session.

## Changing this workflow

Follow `~/code/dev-auto/AGENTS.md`.
