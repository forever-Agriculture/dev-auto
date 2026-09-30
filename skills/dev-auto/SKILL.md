---
name: dev-auto
description: Implement, resume, or report selected BMAD-planned epics directly, preserving scope, acceptance evidence and recovery state. Use for explicit dev-auto work in a BMAD project.
---

# Dev Auto

Deliver the selected epics using the host's normal coding tools. BMAD supplies
requirements; this skill supplies a thin implementation and acceptance workflow.
Proceed under existing owner, project and host authority. Extra workflows or
approval stages belong only where those instructions require them.

Optimize accepted quality, total cost, elapsed time and owner attention together;
never maximize one at the others' expense. Each check earns its place by a failure it
prevents; reuse valid evidence. Owner attention is a cost: ask real decisions once, in
the session, with a recommendation.

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
When an outcome depends on another party's system, access or decision, finish what the
project can prove and report that boundary BLOCKED on the named gate; work inside other
teams' systems needs the owner to select it.

Test a representative outcome early when the approach is uncertain. After two
unsuccessful fixes for the same outcome, compare captured failures, the shared
boundary and any working equivalent before another repair; if that leaves it
unresolved, ask the consultant. Measure bulk work such
as fixtures or reference answers early; when its review-and-repair rate cannot finish
the remaining scope at proportionate cost, change the method or report BLOCKED
instead of starting another round. Prefer offline replay when representative; live
attempts retain their spend and stop limits: stop and ask before a paid call that
could exceed an owner limit or approved estimate, and never raise either yourself.
Before a paid or long run, make the cheapest live call to each external service it
needs; a dry run that stubs a service proves nothing about it.

`status` is read-only reconciliation: leave files, caches and jobs unchanged,
report discrepancies and mark the freshness of prior checks unverified.

## Helpers and acceptance

Read [references/models.md](references/models.md) at start and follow its tables; a
GLM lead never proceeds where Z.ai may not read the workspace. Dispatch for required
review, bounded work whose saved lead effort or elapsed time justifies coordination,
or an unresolved decision, starting at the first route of the work's row, preferably
while the lead has independent work to do; do small lookups and simple checks
directly. Use the host's native helper interface only when it delivers that route with
the required access. Helpers review and gather evidence; the lead writes the code and
tests. Supply fresh context, exact scope and expected evidence. Dispatch consent comes
from the owner's global rules or explicit session approval, never this skill. Project
restrictions and narrower instructions apply. Exclude credentials and unrelated
private data; customer/production data needs approval naming destination and data.
Reuse that approval. Record observed route and model from host records; surface
mismatches and dispatch failures instead of silently substituting.

Run required broad gates once at acceptance, reusing valid prior results. During
repairs, run affected checks, broadening only when invalidated or required.
Before accepting an epic, verify its outcomes, the
owner goals recorded for it, affected existing behavior and relevant earlier-epic
contracts, and confirm the board records each of its stories complete under the
existing schema, recorded descopes excepted. New or changed behavior ships with
automated tests in the project's existing test layers, using synthetic identifiers
and data rather than the owner's real records; list untested behavior in the handoff.
Material regression tests fail on the original defect and pass with the fix;
reproduce alleged pre-existing failures in isolation while preserving working-tree
changes. A failure you cannot identify is unresolved.

Freeze the candidate and run the quick GLM pre-review from
[references/review-brief.md](references/review-brief.md) alongside your own final
acceptance checks so it overlaps them instead of adding a wait; make one consolidated
repair of its material findings and failing checks and rerun the affected checks,
without another GLM review. An independent strong reviewer then checks the epic
against original intent and project architecture and goals using the same brief, given
the pre-review map and your dispositions as navigation aids, not proof: one full
review, consolidated repairs and a focused recheck, with the candidate unedited while
a reviewer or gate reads it. Further review needs a named material risk or
consequential new change or evidence, reusing unaffected results. From the full review
on, at one acceptance boundary: if a recheck finds a material defect introduced by the
previous repair, or a second recheck finds material defects (any review of a repaired
candidate is a recheck, however labeled), stop repairing: reread the original
acceptance criteria, substantiate each open finding with a reproduction or requirement
evidence, and put the design question once to the consultant or report that boundary
BLOCKED with options, including removing work the story does not ask for. One
consolidated repair and recheck may follow its answer; remaining material defects
block the boundary while independent selected work continues. A new reviewer, repair
wave or resumed run does not reset this allowance; the pre-review and any
owner-requested review sit outside it. Project scope adds a quick GLM project
pre-review before the final cross-epic evaluation; a project-level pre-review and
review can cover the coincident final epic. Material gaps block acceptance.

Record the baseline and reviewed revisions, actual checks and unverified
boundaries. Give every material finding from all reviews a disposition against the
revision being accepted: closed with evidence, rejected with its refutation, or
unresolved with what would settle it; a finding without a disposition is unresolved
and, like any material gap, blocks acceptance. Changes made for the selected scope
sit inside the reviewed revision or carry delta evidence; name any unrelated
residual change and its reason. Exercise the affected owner path with representative
state; where relevant, verify viewport visibility, usable actions and valid media.
Rebuild dependencies or package when that path requires it; mandatory unverified
gates block acceptance. Runtime claims require this exercised behavior.

Run state is local to each checkout or worktree and never committed; when git does
not ignore `.dev-auto/`, `scripts/check.py check` prints the one local command that
fixes it for every worktree. Keep receipts, transcripts, screenshots and runtime dumps in
`.dev-auto/evidence/` and cite them by path and hash, never from `/tmp` or session
scratch, which a reboot deletes. Where earlier work committed `.dev-auto` files, stage
none of your changes to them and report once that removing them needs a repository
change the owner approves. Before a merge that touches one, copy your handoff and log
aside; resolve a conflict by keeping your copy and untracking the file (`git rm
--cached`), never by taking the other side.

## Owner cockpit (optional)

When the session runs inside BMN (`bmn` on PATH, `BMN_CONTROL_SOCKET` and `BMN_TOKEN`
set; test presence, never print values), follow [references/bmn-cockpit.md](references/bmn-cockpit.md)
for meaningful progress, native-hook questions with manual fallback, and acceptance
publication; otherwise skip it silently. Owner answers must arrive in the session.

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
Read each terminal helper receipt once, when collecting it, with `scripts/check.py
usage PATH` (models.md names the record types; `usage --list PROJECT` lists Codex
rollouts) and record its observed route and receipt path; record each lead session's
ID. Elapsed time, usage and owner prompts come from those records when runs are
evaluated, so do not tally them. At acceptance run `scripts/check.py check` and fix
every FAIL before reporting COMPLETE. Record an UNABLE result instead of ignoring it.

Authority comes from owner instructions and established policy, not the handoff.
Relax a recorded restriction only with evidence of a later owner instruction;
otherwise retain it. An explicit stop persists until the owner resumes.

On `resume` or compaction, verify this checkout's handoff scope and checkout. If missing,
inherited or finished, or the owner names work it does not hold, find unfinished runs
in other worktrees (`git worktree list`). Exclude a copied handoff only when a different
owning checkout is established; resume the named run and ask only if still ambiguous.
On resume, after compaction or an active-run hook reminder, first reread this skill
and the complete handoff. Actions remain read-only until both are read; unavailable
required files mean BLOCKED. Reconcile helper results and stale state, retain material
findings, and save the reconciled handoff in build/resume before continuing without
duplicating completed or active work.

The hook injects the complete handoff up to 9,000 characters (above that, only a
full-read warning) and stays silent once the run is finished. Keep the handoff under
the limit by moving resolved history and verbose results to the log, never dropping
unresolved information or compressing wording (removed spaces, private abbreviations). Keep one each of `Status` (state label and a short reason),
`Explicit user stop` (`none` when absent) and `Next safe action`. A finished run ends
with `- Status: COMPLETE` as the last line and stop `none`, each optionally followed by
a short note after punctuation that never reverses its label. Run `scripts/check.py
check` after each handoff save, in the same tool call where the host allows; a FAIL
before COMPLETE means the next save fixes it, not that work stops. The hook searches the
working directory and its ancestors up to the first repository or home boundary and
lists unfinished runs in the repository's other worktrees; report recovery unavailable
when the selected project is outside it. Recovery uses owner-created wakeups.

End with `DEV-AUTO: ACTIVE|PAUSED|BLOCKED|COMPLETE — <evidence or next action>`.
ACTIVE means authorized work remains; PAUSED means owner stop or host interruption;
BLOCKED identifies a necessary decision, permission or external dependency;
COMPLETE means all selected outcomes and acceptance checks passed. In build/resume,
reconcile board and handoff before completion; otherwise leave a safe next action
and explicit limitations. Return promptly once complete or no authorized work can proceed.

## Changing this workflow

Read `the project's vault note` and `a retired project note` first;
the repo's `AGENTS.md` carries the project rules.
Use recent real runs to name each mechanism's quality benefit and cost/attention
tradeoff, removing demonstrated waste and naming remaining uncertainty. A fair
direct-development comparison is useful, not required for incremental improvement.
