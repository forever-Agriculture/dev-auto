# Away grant

Read this when the owner says he is leaving or BMN says he is (BMN Epic 84), and at a
parked boundary while a grant may cover it. Only his own answer, in the BMN window or on
Telegram, makes a grant; it ends when he is back. With no grant, nothing here applies.

## Before he leaves

On his departure words to you, forward `bmn away --leaving` first. On those words or on
BMN's notice that he is leaving or away, ask once, before you forward `bmn away`:

- pipe the card as JSON to `bmn grant ask --run <Run id> --card-file -` (`bmn grant --help`
  shows its shape): the title, the remaining scope, and only the terms that work needs,
  each with its reason;
- extra repair rounds per boundary (2, 3 or 4), only when a review or gate boundary is ahead;
- each reserved action you foresee, with its target: merge a PR (at its head SHA, or up to
  N of this run's PRs when their required checks are green), push a branch to the default
  branch, or open or update a PR in another repository (its branch or PR number);
- `bmn grant ask --run <Run id> --nothing` when the remaining work needs none of these.

Other reserved decisions still go on the one departure card the skill describes. Asking
again for the same run makes a new revision; his earlier answer holds until he answers it.

## Reading and using it

Read `scripts/check.py grant` right before each step a grant would pay for, never the
handoff or memory. Record the use first, with an id that stays the same on a retry:
`bmn grant use --run <Run id> --boundary <boundary> --use-id <boundary>:round-<n>` for a
round, `--item <term id> --use-id <stable id>` for an action. A refused use means the step
waits as it would without a grant. After an uncertain outcome, read the target's state
first and retry only under the same use id when the action did not happen; once he is
back, that retry is refused and waits. A use id belongs to its run and away period, and his
answer to a new revision is a new grant, its actions counted afresh. The boundary
name is the one the handoff's review allowance uses, so rounds used count across resumes,
leads and away periods.

After each step, report what it did for his morning summary: `bmn grant report --run
<Run id> --use-id <id> --result passed|failed|blocked` for a round, `done`, `refused` (with
`--text` saying why) or `uncertain` for an action; a granted action a rule or GitHub stopped
before any use is `--item <term id> --text <why>`. A report grants nothing.

## A granted round at a parked boundary

A boundary parked by the review brake or the away repair takes one granted round at a time:

1. Record the new evidence and a consultant-agreed method in the brake record first.
2. Record the round with `bmn grant use`.
3. Make one consolidated repair and one focused recheck.

A third failed method within the granted rounds does not stop for his card. Before the
last granted round, ask the consultant for a step-back consult and record it: the original intent and acceptance
criteria, the architecture, and every failed method with what it established; its options
keep the requirements and include a different design, descoping work the story does not
ask for, and BLOCKED; report the chosen option with `bmn grant report --run <Run id>
--boundary <boundary> --step-back --text <option>`. The last round follows the recorded option, or the boundary parks
BLOCKED when that option is to stop. With the rounds used, the boundary parks BLOCKED with
the consult's options and the third-method card waits for him, as without a grant. Back
during a round lets it finish; no new round starts.
