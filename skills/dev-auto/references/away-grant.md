# Away grant

Read this when the owner says he is leaving or BMN says he is (BMN Epic 84), and at a
parked boundary while rounds remain. Only his own answer, in the BMN window
or on Telegram, makes a grant; it ends when he is back.

## Before he leaves

On his departure words to you, forward `bmn away --leaving` first. On those words or on
BMN's notice that he is leaving or away, ask once, before you forward `bmn away`, by piping
the card as JSON to `bmn grant ask --run <Run id> --card-file -` (`bmn grant --help` shows
its shape): the title, the remaining scope and only the terms that work needs, each with
its reason:

- with a go (`scripts/run_needs.py`), its Run needs' named actions with their targets and
  no rounds, an exact `command` or `message` included; with none, `bmn grant ask --run <Run id>
  --nothing`;
- without a go, no rounds (a run has its default rounds) and each reserved action you foresee
  with its target (a PR merge at its head
  SHA, a push to the default branch, a PR in another repository, one exact command with its
  folder, one exact message with its tool, target and whole text); `--nothing` when the work
  needs none.

A message whose text you do not know yet goes as a draft on one non-blocking `bmn ask` card,
and the run continues. Before he leaves, run the go's `Prepared` checks again (SKILL.md, Owner
decisions).

Asking again for the same
run makes a new revision; his earlier answer holds until he answers it.

## Reading and using it

Read `scripts/check.py grant` right before each step a grant would pay for, never the
handoff or memory; before each granted merge or push, also read `bmn policy --repo
OWNER/NAME` again. For a command or a message, run or send exactly the text `bmn grant use`
prints, and if the app prompts on it anyway, the step waits and the report says so. Record the use first, with an id stable across retries:
`bmn grant use --run <Run id> --boundary <boundary> --use-id <boundary>:round-<n>` for a
round, `--item <term id> --use-id <stable id>` for an action; keep the period it prints with
the use. A refused use waits as without a grant. After an uncertain
outcome, read the target's state first and retry only under the same use id when the action
did not happen; once he has answered a new revision, or is back, that retry is refused and
waits. A use id belongs to its run and away period, and his
answer to a new revision is a new grant, its actions counted afresh. A boundary is a story
(`96.3`) or `epic`, as the handoff's review allowance names it, so rounds used count across
resumes, leads, away periods and gos.

After each step, report it for his morning summary: `bmn grant report --run
<Run id> --period <its period> --use-id <id> --result passed|failed|blocked` for a round,
`done`, `refused` (with `--text` saying why) or `uncertain` for an action; a granted action a
rule or GitHub stopped before any use is `--item <term id> --text <why>`. A report's
`--text` is at most 1,000 characters. A report grants nothing and is taken after Back too.

## A round at a parked boundary

A boundary parked by either brake or the away repair takes one round at a time, the ledger's
first, without a card:

1. Record the new evidence and a consultant-agreed method in the brake record, and save the
   handoff in its own tool call.
2. Once that save succeeded, record the round: a ledger round with `scripts/spend_ledger.py round
   --budget B --boundary <boundary> --use-id <boundary>:round-<n>` (refused when none is left, and
   the last also needs its step-back, below), noted in the brake record with source `ledger`; a
   granted one with `bmn grant use`.
3. Make one consolidated repair and one focused recheck.

A third failed method within the rounds does not stop for a card. Before the last round,
ask the consultant for a step-back with [step-back-brief.md](step-back-brief.md) and record it;
pass it to `round` with `--step-back <ask id> --record <file> --method <text> --lead <you>`. For a granted round, report the chosen option with `bmn grant report --run
<Run id> --boundary <boundary> --step-back --text <option>` before its use. The last round
follows the recorded method, or the boundary parks BLOCKED with no round used when none is
different. With the rounds used, the skill's deferral or parking follows. While away no new allowance card is sent; an unforeseen YAML gap is recorded for Back, when the skill's amendment-card rule applies. Approval preserves prior usage and changes only the named terms. Back during a granted
round lets it finish; no new granted round starts.
