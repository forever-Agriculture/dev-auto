---
name: dev-auto
description: Implement, resume, or report selected epics planned in BMN's plan format or BMAD's, directly, preserving scope, acceptance evidence and recovery state. Use for explicit dev-auto work in a planned project.
---
# MODULE: SKILL.md - direct implementation with bounded review, acceptance and recovery

# Dev Auto

Deliver the selected epics (BMN's plan or BMAD's) with host tools under existing authority, adding no
unnecessary approval stage.
Optimize accepted quality, total cost, elapsed time and owner attention together. Each
check earns its place by a failure it prevents; reuse valid evidence.

## Owner decisions

His standing consent for every dev-auto run (owner, 2026-11-04): A run also may move its own ticket to In progress, Blocked or In review, and publish its private reports and evidence to BMN's local file store; a recorded go authorizes the messages its Run needs name.

The invocation and later owner instructions set the run's authority: scope, approved
spend and delegation ("decide within the cap", "work autonomously"). Record each
delegation with its source quote as a handoff term, valid only for its named scope and
total. His go on a planned epic is one, day or night. At start and each resume run
`scripts/spend_ledger.py open --epic N` (it reads the go with `scripts/run_needs.py`), at start before
moving the epic's row past `ready`, and keep
what it prints in the handoff's `Go` field: the same go means its terms, rounds left and money
as printed, nothing to ask him. Take each extra round it printed with `spend_ledger.py round`
before using it; that ledger counts them for every lead, resume and worktree. A run has at least
4 per boundary, go or no go (his card, 2026-11-04), an allowance and never a target. On NO_GO_RECORD
go on under the invocation with what `open` printed and without deferrals; a withdrawn or
unconfirmed go prints no rounds, and his later narrower word is recorded with `spend_ledger.py
limit`. Approval evidence you find explains the missing
record in the handoff, grants nothing and never makes you ask him to restate or record a go.
Its Run needs may list `Prepared` (BMN Epic 103), printed by `run_needs.py`. At the run's start and at
his departure, run each `check:` yourself, as its own tool call under the app's and the guard's
rules (BMN never runs one), and write each result to the handoff. A failed need, or an owner step
not done, goes under `Needs your decision` with the stories that name it: those stories park and
every other story continues; at his departure say a step not done once, in one line.
A story you park gets the log line `<UTC stamp> parked N.M`, and `<UTC stamp> unparked N.M` when it resumes; `scripts/interruptions.py` counts those hours.
Reserved to him however sure you are: spend beyond what he approved or delegated, changes
to selected work or its acceptance criteria, actions the global rules reserve to him,
credentials or private data, owner-only acceptance checks and model choices; a broad "continue" or "work autonomously" answers none of these. His model choices live in his BMN team: a lasting
one for a project is a `## project-choices` entry he approves in BMN (if the host refuses
your write, give him the entry), a one-time pick goes as `--agent` (and `--effort`) on
the asks it covers, with his quote in the handoff. Decide a technical point only on
complete evidence with nothing against it, else ask the consultant and follow a confident
answer. A reserved point, or one the consultant cannot settle, goes at once under `Needs
your decision` in the handoff (evidence, missing decision, affected criteria, untouched
and remaining work);
continue every story it does not block, and ask him once, with a recommendation, only
when no work can proceed and he is not away. The final report lists open entries.
During a run, decide within your authority or park the story: rounds, retries, windows, one
more file, ticket status, labels and harness repairs are not questions. Ask him only when no
work can proceed, once, in one batch.
Decide everything else on your recommended option when it keeps the requirements,
acceptance criteria, privacy and limits. Log each
decision with its reason under `Decided for you` in the handoff and the next report
(on its page as "Choices you can reverse" in Next steps), away or back, as one line with the run's next unused entry id `[dN]`, never renumbered. While
BMN reports away, also record it with `bmn decision record --key dev-auto:<Run id>:<dN>`
where permitted and end the line with `(bmn: SESSION/KEY)`, the `sessionId` and `key` it returns;
never record an entry an earlier lead
logged. Authority comes from owner instructions
and policy, not the handoff: relax a recorded restriction only on a later owner
instruction; an explicit stop persists until he resumes.

Away: `away` as an invocation argument or a message of its own, or the owner saying he
is leaving now and unreachable even by phone ("going to bed"; still on his phone or Remote
Control is not away, owner 2026-10-17), starts away mode, a handoff term with his quote and
time, until he says he is back or cancels it; an explicit stop outranks it. Forward his
departure or return words once with `bmn away` or `bmn back --revision R`; activity is
never either. Run `scripts/check.py away` at invocation and resume and before an owner
question or an away-specific retry decision, and follow it (BMN's state notices count
between those reads): AWAY or BACK sets away mode and the `BMN away` field, an away
adopted from BMN with no departure statement or card; MISSING keeps the local mode;
UNAVAILABLE keeps the last confirmed state with every stop and limit, never back. On a
departure you handle, at once state in one short message the selected scope, what
proceeds and what waits; unless he forbade questions, add one card for the open Needs
your decision entries remaining work may need. Once per boundary, one further narrow repair and recheck may
follow a used review allowance; mark it used in the handoff first. When BMN says he is leaving
or away, follow [references/away-grant.md](references/away-grant.md).

## Scope and delivery

After a plan migration, the handover refreshes dev-auto tools before any run resumes or opens the
moved plan. Every later approval and ledger operation uses updated `run_needs.py` and
`spend_ledger.py`, even when a run retains its original budget ID. Untouched older script copies
are unsupported after cutover. Keep the original budget file and lock; never delete spending
history to make an open succeed.

Interpret `epic 12`, `epics 12-14`, `project` (unfinished planned epics plus a final
cross-epic evaluation), `resume` and `status` in the selected project, defaulting to the
current directory when it holds the planning artifacts. `status` is read-only: change no
files, caches or jobs, report discrepancies and mark prior checks' freshness unverified.

Find the plan with `bmn plan status --json` and report its format and paths; an undeclared pair of plans,
an unknown schema or a malformed BMN-format plan stops the run with that error named. A BMN board's
`bmad_board` declares the retained BMAD board; the canonical BMN plan wins from every worktree. In
BMN's format (BMN `docs/planning.md`) read `PLAN.md`, the selected epic files and their rows,
opening references, logs and evidence on demand; a legacy epic reads as its BMAD text, and an
epic's Truth impact is part of the outcome you verify. There `project` takes the unfinished
epics in `queue` order, then unqueued ones by number, skipping `paused` and `dropped`; an owner
stop sets the rows it stops `paused`, and a resumed run leaves them until he resumes them.
Change your rows with `bmn plan set` and the row's token, `done` meaning verified acceptance
as below; add one concise Log line with its evidence path to your epic file at acceptance and
one at delivery, as the default-checkout edit you make for your rows; commit nothing in
`plan/.git`. At each story's end on a tracked BMN plan, run `bmn plan publish`: it checkpoints only
planning paths, reads delivery policy, and publishes the plan difference without unrelated product work.
`unpublished N` or `PLAN_CONFLICT` leaves local commits and both conflicting values intact; record it
and continue unaffected epics, never ask for publication. The conflicted epic grants nothing through
`run_needs.py`. An ignored plan keeps its existing local history and is not published.
A BMAD project is read and updated as before this format existed: its epics
and story files, and the `sprint-status.yaml` board the status names.

Read project instructions, original acceptance criteria, relevant architecture and
dependencies. Reconcile repository, board, handoff and active helpers;
completion labels are claims to verify. Before each epic, confirm its outcome fits the
project and keeps later-epic obligations; use the existing board schema and report
missing state.

Use a separate branch, worktree and dependency environment per run, created from the
default checkout; a run already active in the default checkout finishes there. After
compaction use that worktree's handoff, whatever checkout the session or hook points at.
Never commit, stash or edit another run's checkout or dependencies. From a separate
worktree, touch in the default checkout only your epics' board rows and untracked story records, rereading just before each edit and never
committing there; read missing or older planning files from it without copying its
uncommitted files. `scripts/check.py worktrees` lists each worktree's branch, run state,
ancestry, uncommitted count and disk bytes, read-only. Offer only finished, clean,
merged runs on one card; remove only the exact worktrees he names, with `git worktree
remove`, never `--force` without his word for that worktree. Log each size and removal
in `.dev-auto/log.md`;
preserve its needed evidence first. Prefer one lead session per
epic.

Implement the smallest complete change and continue authorized work until the whole
selected scope passes acceptance. The lead owns integration and the board: when a story
or epic starts, gets a measured outcome, blocks or is accepted, update its rows in that
step on the board in the default checkout, where the owner reads it; a canonical BMN plan is written
there even from a linked worktree. BMAD keeps its existing two-checkout convention. Touch only the
run's own epics' rows; implemented work
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
After every third failed agreed method at one boundary, take the rounds `open` printed,
then an Away grant's, as the away-grant reference runs them. Before the last one, a different
agent looks at the big picture ([references/step-back-brief.md](references/step-back-brief.md)):
`round` refuses it without that, and with no different method the story parks without using it.
With the rounds used, defer what Run needs lists as deferrable (other criteria pass; row `done`
noted `deferred: <N.M ACk>, <reason>`; Known limits; a new story proposed) and continue. Else
the story parks BLOCKED with its evidence and every other story continues: record the brake
record, the consultant's options and your recommendation in the report, and ask him for no round;
nothing lifts an authorization, spend, review allowance or acceptance gate.
A message the go's Run needs name (`run_needs.py` prints each) goes only to that person, destination
and purpose, only facts or access, no commitments, saying his agent wrote it. Before sending, `spend_ledger.py message reserve`
(refused past 2 per purpose, or for the same text); after, `message sent --receipt`. With no receipt, read the
destination and record `sent` or `unsent`, never send again. Anything else waits as a draft in the report, which lists every message.
Launch every paid job through `scripts/spend_ledger.py launch` against the go's money cap
or one he set (`none`: no paid launch); never raise a cap or the total yourself.
Before a paid or long run, use applicable evidence or the cheapest authorized check
to establish service access and launch/cleanup feasibility in its actual environment.
Preflight consumes the owner's applicable time, call and spend allowances; record
any required grant use before it. A denial parks that boundary; stubs do not prove
real-service access.

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
acceptance checks and the [manual QA phase](references/qa-brief.md) on its running interface;
QA findings join the same consolidated repair. Retest repaired flows in the existing recheck,
and affected flows after every later material repair; QA adds no round. A missing/invalid
report, mandatory verification gap or unachieved goal blocks acceptance unless approved Run
needs defer it. Without an interface record QA not applicable. Make one consolidated repair
and rerun affected checks, with no second pre-review. An independent strong
reviewer then checks the epic against original intent, architecture and goals with the
same brief, using the pre-review map and your dispositions as navigation, not proof:
one full review, consolidated repairs and one focused recheck, the candidate unedited
while a reviewer or gate reads it. Further review needs a named material risk or a consequential new
change or evidence, reusing unaffected results.

From the full review on, at one acceptance boundary: if a recheck finds a material
defect introduced by the previous repair, or a second recheck finds material defects
(any review of a repaired candidate is a recheck), stop repairing. Reread the original
acceptance criteria, substantiate each open finding with a reproduction or requirement
evidence, and put the design question once to the consultant, whose method must keep
the requirements, acceptance criteria and limits (removing work the story does not ask
for is a valid answer). One consolidated repair and recheck may follow; remaining
material defects take rounds or a deferral as the method brake does, else park that
boundary BLOCKED with the consultant's options. A new
reviewer, repair wave or resumed run does not reset this allowance; the pre-review,
owner-requested reviews and a project's own PR review sit outside it. That review runs
as the project's rules say, once, with one re-review only after a blocker or major fix;
its Do items join repair before merge and its fixes carry delta evidence. Project scope adds a quick project pre-review
before the final cross-epic evaluation; project-level reviews can cover the coincident
final epic.

## Acceptance

Run required broad gates once at acceptance, reusing valid prior results. Schedule
heavy local gates one at a time, avoiding overlap with heavy work you control and
reducing concurrency when sharing the machine. Before a gate,
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

Keep QA's verdict, goal check, findings and their fate on the report page, with synthetic
or sanitized evidence only. A QA-focused epic may finish its planned audit/triage mission
while retaining the tested product's unresolved NO-GO; it never rewrites that product verdict.

As each epic is accepted (all before COMPLETE), deliver its report, including docs-only
or workflow changes. A report revision is the checked HTML page's SHA256.
1. Write, check and publish it privately as BMN's `report-artifact` skill says. Its
   second opinion is the full reviewer's opinion as the recheck refreshed it; a review
   output without one takes the skill's no-review route. With
   `bmn publish`, keep `.html` in any custom name and use `<epic>-owner-<first12sha>` as
   the key; changed bytes need a new key, an identical retry keeps its key.
2. Write one receipt beside the page immediately after each step returns: page path,
   SHA256, publisher, key if supported, id/link and browser result. Resume reuses successful
   delivery only when the page's SHA256 matches the receipt.
3. Open it once, as the skill's open rule says (a Claude Code Artifact publish opens it
   itself; otherwise the checked local page in his default browser), without another owner
   question (requested 2026-10-23). Host permission prompts still apply. Record `opened by
   publish` or `launched (exit 0)`, which does not mean the owner saw it; skip that launch on
   resume for the same recorded SHA256.
4. If publishing or opening is unavailable, refused, fails or returns an uncertain result,
   record UNAVAILABLE and the reason, give the checked local page path, and use no workaround
   or new-key retry. This presentation failure does not block product acceptance or COMPLETE.
5. Under `Reports` in the handoff, keep each receipt path, id/link and browser result; put
   the id/link in the epic's existing delivery Log line, and link every report in the final
   reply. Read-only `status` never creates, publishes or opens reports.

## Handoff and recovery

At each server, daemon or container launch, record its command and launch identity in
the handoff's `## Started` JSON bullets (template): PID and `/proc/PID/stat` start ticks,
or full container id and name. Before reporting COMPLETE, BLOCKED or PAUSED, run
`scripts/check.py leftovers CHECKOUT` for every run checkout. It lists identity-matching
Owned resources and path-matching Candidates without changing anything; exclude BMN,
the checker and its ancestors. Confirm a candidate belongs to this run before stopping
it; a path match grants no authority. Immediately before each stop, rerun the inventory
and check the recorded identity again. For a process, open a Linux pidfd, verify its
start ticks again, then signal through that pidfd, never a numeric PID susceptible to
reuse. For a container use its full recorded id, never its name alone. Stop owned resources
or record `keep` with its reason, then rerun: only deliberately kept resources may
remain. An incomplete inventory stays UNVERIFIED; report its limit.

Run state is local to each checkout and never committed; follow `scripts/check.py
check` notes about `.dev-auto/` and report tracked-state cleanup once. Keep receipts,
transcripts, screenshots and runtime dumps in `.dev-auto/evidence/`, cited by path and
hash, never in `/tmp` or session scratch; cite host records (`~/.claude/projects/`,
`~/.codex/sessions/`) in place by their real path.

Maintain `.dev-auto/handoff.md` from [assets/handoff.md](assets/handoff.md), its
fields current terms with source coordinates. Honor stops immediately; save each change
of scope, permission, blocker or stop and each helper dispatch and review outcome before
dependent work, and reconcile every section at acceptance and before pausing. Append
verbatim owner quotes, superseded terms, verbose results and failed attempts to the append-only
`.dev-auto/log.md`, never restated in `Status` or `Resume`; append what changed, never a
copy of the handoff.

Keep the handoff readable and within the recovery hook's 9,000-character snapshot:
move resolved history and verbose results to the log, preserving all unresolved
information and exact evidence paths. Keep one each of `Status` (label and short reason),
`Explicit user stop` (`none` when absent) and `Next safe action`; a finished run's last line is `- Status:
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
