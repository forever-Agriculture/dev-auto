---
name: dev-auto
description: Implement, resume, or report selected BMAD-planned epics directly, preserving scope, acceptance evidence and recovery state. Use for explicit dev-auto work in a BMAD project.
---

# Dev Auto

Deliver the selected BMAD epics with host tools under existing authority, adding no
unnecessary approval stage.
Optimize accepted quality, total cost, elapsed time and owner attention together. Each
check earns its place by a failure it prevents; reuse valid evidence.

## Owner decisions

The invocation and later owner instructions set the run's authority: scope, approved
spend and delegation ("decide within the cap", "work autonomously"). Record each
delegation with its source quote as a handoff term, valid only for its named scope and
total.
Ask the owner once, in the session, with a recommendation, only about spend beyond what
he approved or delegated, changes to selected work or its acceptance criteria, actions
the global rules reserve to him, credentials or private data, owner-only acceptance
checks and the brake's decision below. His model choices live in his BMN team: a lasting
one for a project is a `## project-choices` entry he approves in BMN (if the host refuses
your write, give him the entry), a one-time pick goes as `--agent` (and `--effort`) on
the asks it covers, with his quote in the handoff. Technical decisions the evidence
cannot settle go to the consultant.
Decide everything else on your recommended option when it keeps the requirements,
acceptance criteria, privacy and limits; where his delegation permits, that includes
moving unused approved money between this run's paid jobs within the total, keeping any
narrower cap or retry limit he set and counting outstanding paid commitments. Log each
decision with its reason under `Decided for you` in the handoff and the next report, away
or back, as one line with the run's next unused entry id `[dN]`, never renumbered. While
BMN reports away, also record it with `bmn decision record --key dev-auto:<Run id>:<dN>`
where permitted and end the line with `(bmn: SESSION/KEY)`, the `sessionId` and `key` it returns;
never record an entry an earlier lead
logged. A pending question never blocks independent work. Authority comes from owner instructions
and policy, not the handoff: relax a recorded restriction only on a later owner
instruction; an explicit stop persists until he resumes.

Away: `away` as an invocation argument or a message of its own, or the owner saying he
is leaving now ("going to bed"), starts away mode, a handoff term with his quote and
time, until he says he is back or cancels it; an explicit stop outranks it. Forward his
departure or return words once with `bmn away` or `bmn back --revision R`; activity is
never either. Run `scripts/check.py away` at invocation and resume and before an owner
question or an away-specific retry decision, and follow it (BMN's state notices count
between those reads): AWAY or BACK sets away mode and the `BMN away` field, an away
adopted from BMN with no departure statement or card; MISSING keeps the local mode;
UNAVAILABLE keeps the last confirmed state with every stop and limit, never back. On a
departure you handle, at once state in one short message the selected scope, what
proceeds and what waits; unless he forbade questions, add one card for unresolved
decisions reserved above that remaining work may need. Then record what waits instead of
asking; anything else reserved to him parks its own boundary. Once per boundary, one further narrow repair and recheck may
follow a used review allowance; mark it used in the handoff first.

## Scope and delivery

Interpret `epic 12`, `epics 12-14`, `project` (unfinished planned epics plus a final
cross-epic evaluation), `resume` and `status` in the selected project, defaulting to the
current directory when it holds the planning artifacts. `status` is read-only: change no
files, caches or jobs, report discrepancies and mark prior checks' freshness unverified.

Read project instructions, original acceptance criteria, relevant architecture and
dependencies. Reconcile repository, sprint board, handoff and active helpers;
completion labels are claims to verify. Before each epic, confirm its outcome fits the
project and keeps later-epic obligations; use the existing board schema and report
missing state.

Use a separate branch, worktree and dependency environment per run, created from the
default checkout; a run already active in the default checkout finishes there. After
compaction use that worktree's handoff, whatever checkout the session or hook points at.
Never commit, stash or edit another run's checkout or dependencies. From a separate
worktree, touch in the default checkout only your epics' board rows and untracked story records, rereading just before each edit and never
committing there; read missing or older planning files from it without copying its
uncommitted files. Never remove a run's worktree yourself. Prefer one lead session per
epic.

Implement the smallest complete change and continue authorized work until the whole
selected scope passes acceptance. The lead owns integration and the board: when a story
or epic starts, gets a measured outcome, blocks or is accepted, update its rows in that
step on the board in the default checkout, where the owner reads it, and on the run's
branch when the board is tracked, touching only its own epics' rows; implemented work
awaiting checks stays in an unfinished active state; record verified acceptance and its
branch using the board's convention; delivery is complete only once you confirm the work
is on the default branch. A blocked epic leaves independent selected work available. An
outcome that depends on another party's system, access or decision ends BLOCKED on that
named gate once the project has proved its part; work inside other teams' systems needs
the owner to select it.

Try an uncertain approach early on a representative sample, preferring offline replay.
After two unsuccessful fixes for one outcome, or three failed runs in a row of one
acceptance or CI gate whatever fails in them, compare captured failures, the shared
boundary and any working equivalent; if still unresolved, ask the consultant. After that,
even under an instruction not to stop, each further attempt at that outcome or gate
needs a different, evidence-backed method the consultant agrees, recorded first in the
handoff's brake record for that boundary, with what the failed methods established in
the log; later leads continue the record, never restart it. Without such a method the boundary
stays BLOCKED. Keep changes unrelated to the failure out of these attempts. Once per
method, a failure in your own harness before product execution counts as a gate run,
not a failed method: repair and rerun; a second such failure fails the method.
After every third failed agreed method at one boundary, ask the owner by card: that
record, the consultant's odds and cost to pass, and your recommendation among continue
within a usage budget, descope, report the cause upstream and leave the gate red, or
BLOCKED. Pause retries at that boundary until his answer authorizes them; inspect
existing evidence and continue independent work. Neither that card nor an instruction
not to stop lifts an authorization, spend, review allowance or acceptance gate.
Stop and ask before a paid call that could exceed an owner cap, the approved total or an
approved estimate no delegation covers, and never raise a cap or the total yourself.
Before a paid or long run, make the cheapest live call to each external service it
needs; a stubbed dry run proves nothing about a service.

## Helpers and review

Read [references/models.md](references/models.md) at start and follow it; a lead never
proceeds where its own provider may not read the workspace. Dispatch consent and its data limits (no credentials or unapproved private data) come
from the owner's global rules or session approval, never this skill; project
restrictions apply. Record each ask's run id and exported record, or a native helper's
session record, and each lead session's ID; surface mismatches and failures instead of
silently substituting. Runs are evaluated from those records, so beyond the brake's
record do not tally time, usage or owner prompts.

Freeze the candidate and run the quick pre-review from
[references/review-brief.md](references/review-brief.md) alongside your own final
acceptance checks; make one consolidated repair of its material findings and failing
checks and rerun affected checks, with no second pre-review. An independent strong
reviewer then checks the epic against original intent, architecture and goals with the
same brief, using the pre-review map and your dispositions as navigation, not proof:
one full review, consolidated repairs and one focused recheck, the candidate unedited
while a reviewer or gate reads it. For web UI changes, add a browser check of the
running candidate at the lead-started loopback origin, against the acceptance criteria
with synthetic data. Further review needs a named material risk or a consequential new
change or evidence, reusing unaffected results.

From the full review on, at one acceptance boundary: if a recheck finds a material
defect introduced by the previous repair, or a second recheck finds material defects
(any review of a repaired candidate is a recheck), stop repairing. Reread the original
acceptance criteria, substantiate each open finding with a reproduction or requirement
evidence, and put the design question once to the consultant, whose method must keep
the requirements, acceptance criteria and limits (removing work the story does not ask
for is a valid answer). One consolidated repair and recheck may follow; remaining
material defects park that boundary BLOCKED with the consultant's options. A new
reviewer, repair wave or resumed run does not reset this allowance; the pre-review and
owner-requested reviews sit outside it. Project scope adds a quick project pre-review
before the final cross-epic evaluation; project-level reviews can cover the coincident
final epic.

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
story's acceptance and delivery state, recorded descopes excepted. Exercise the affected owner path
with representative state, including viewport visibility, usable actions and valid
media where relevant, rebuilding or packaging when that path requires it; check each
consequential fake once against the real contract, and recommend delivery only after
its own path (packaged build, update or deploy) passes. Where only the
owner can exercise it (an installed release, phone or messaging), recommend one short
owner check and keep acceptance BLOCKED until it passes or he explicitly defers it,
recording it UNVERIFIED. Record baseline and reviewed revisions, actual checks and
unverified boundaries. Give every material finding from all reviews a disposition
against the accepted revision, as the review brief defines. Changes for the selected
scope sit inside the reviewed revision or carry delta evidence, including commits added
after acceptance; name any unrelated residual change and why. Material findings without
a disposition, material gaps and mandatory unverified gates block acceptance.

## Handoff and recovery

Run state is local to each checkout and never committed; follow `scripts/check.py
check` notes about `.dev-auto/` and report tracked-state cleanup once. Keep receipts,
transcripts, screenshots and runtime dumps in `.dev-auto/evidence/`, cited by path and
hash, never in `/tmp` or session scratch; cite host records (`~/.claude/projects/`,
`~/.codex/sessions/`) in place by their real path.

Maintain `.dev-auto/handoff.md` from [assets/handoff.md](assets/handoff.md), its
fields current terms with source coordinates. Honor stops immediately; save each change
of scope, permission, blocker or stop and each helper dispatch and review outcome before
dependent work, and update at acceptance and before pausing. Append verbatim owner quotes,
superseded terms, verbose results and failed attempts to the append-only
`.dev-auto/log.md`, never restated in `Status` or `Resume`; append what changed, never a
copy of the handoff.

Keep the handoff within the recovery hook's 9,000-character snapshot by moving
resolved history and verbose results to the log, never dropping unresolved
information. Keep one each of `Status` (label and short reason), `Explicit user stop`
(`none` when absent) and `Next safe action`; a finished run's last line is `- Status:
COMPLETE` with stop `none`, a short note after punctuation reversing neither. Run `scripts/check.py check` after
every handoff save, in the same tool call where the host allows; fix a FAIL at the next
save and every FAIL before COMPLETE, and record an UNABLE result.

On `resume`, compaction or an active-run hook reminder, first reread this skill and the
complete handoff; act read-only until both are read, and report BLOCKED if a required
file is unavailable. Verify this handoff's scope and owning checkout, treating it as a
copy only when another owning checkout is established; if missing, inherited or
finished, or the owner names work it does not hold, find unfinished runs in other
worktrees (`git worktree list`) and resume the named run, asking only if still
ambiguous. Reconcile helper results and stale state and keep material findings; in
build/resume, save the reconciled handoff before continuing, without duplicating
completed or active work. Recovery uses owner-created wakeups.

End with `DEV-AUTO: ACTIVE|PAUSED|BLOCKED|COMPLETE — <evidence or next action>`:
ACTIVE while authorized work remains, PAUSED on an owner stop or host interruption,
BLOCKED on a necessary decision, permission or external dependency, COMPLETE once all
selected outcomes and acceptance checks passed and, in build/resume, board and handoff
are reconciled. Otherwise leave a safe next action and explicit limitations. Return
promptly when no authorized work can proceed.

## Changing this workflow

Follow `~/code/dev-auto/AGENTS.md`.
