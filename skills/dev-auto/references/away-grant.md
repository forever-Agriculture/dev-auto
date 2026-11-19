# MODULE: away-grant.md - collect the night's requests while getting ready, then read and use only the owner's answers
# Away grant

Read this when the owner says he is leaving or BMN says he is (BMN Epic 84), and at a
parked boundary while rounds remain. Only his own answer, in the BMN window
or on Telegram, makes a grant; it ends when he is back.

Routine BMN peer coordination with `bmn tell` or `bmn handoff` already has the owner's standing
authorization within existing task, provider and data limits. It needs no exact-text card,
Away grant or message reservation; it grants the receiver no work authority. The message
card and exact-text steps below apply to people and external destinations.

## Before he leaves

On his departure words to you, forward `bmn away --leaving` first. He is getting ready:
Away starts on his Go in the window or on Telegram, or by itself after 10 minutes without
an action of his on the list. Do not forward `bmn away` unless he says he is already gone.
On those words or on BMN's notice that he is getting ready or away, read
`bmn grant facts --run <Run id> --epic N --project P --json` and walk the remaining
stories and review boundaries. Ask once, within 3 minutes. Use only the work already
authorized and give a reason for each line.

- A limit needed by a remaining boundary may be raised within its existing ceiling
  through the ledger's usual `RAISE` path. Ask for a `limit` only when the remaining
  uses exceed what is left at the ceiling. Name its current value and the amount the
  remaining work needs.
- Rerun each Prepared check. If a login only the owner can do fails, add an `access`
  line with its name, exact login command and reason. Never include credentials or
  check output. On his Done, suppress the check's stdout and stderr and report only
  `bmn grant report --run ID --item I --attempt A --access works`, or `--access fails
  --cause not-signed-in|expired|no-access|network|other`, using the attempt BMN gave.
- Use the open PR's exact head and policy. Ask for a named merge, default-branch
  push or PR from the remaining work when its approval is needed. A PR whose
  checks are still pending under a policy that permits merging when green waits
  for its checks. Keep any planned exact commands or messages in their own lines.
- Epic 131's evidence gate dropped advance-choice lines. Reserved choices still
  wait on the ordinary workflow.

`scripts/night_card.py --run ID --epic N --project P --remaining FILE --key K` reads the
facts again, draws the needed lines and sends the card. Supply the remaining work
in JSON (run `--help` for fields). Without a recorded go, BMN provides PR facts only.
For a session without a planned epic, use its stable run id and ask for specific
authorized action targets directly. An empty answer needs `--nothing --reason TEXT`.
Name each contradictory fact in `--despite FACT` only when the reason explains why
it cannot stop the remaining work. If facts are unreadable, keep the checks in
the run log. No unreadable fact grants anything.

A message whose text you do not know yet goes as a draft on one non-blocking `bmn ask` card,
and the run continues. Before he leaves, run the go's `Prepared` checks again (SKILL.md, Owner
decisions).

Asking again for the same
run makes a new revision; his earlier answer holds until he answers it.

## Reading and using it

The base round count comes from the recorded allowance and its spend ledger. A night grant adds
temporary rounds. Spend the remaining base rounds first. A persistent limit raise follows
`bmn grant apply`, keeping earlier uses and the new total after Back.

For a held Git or GitHub command covered by an epic's go, bind the live conversation first.
The night card names its exact command, absolute folder, repository, ref and any file pin.
Reserve that action with `bmn grant use` and send the exact command through the harness.
BMN claims the same receipt for the matching tool call. Keep the receipt and report the outcome.

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

An approved limit raise is applied with `bmn grant apply --run ID --item I --use-id U`.
Keep its use id stable. The BMN-written source in the plan's allowance history
identifies the owner's answer. Read the new allowance before taking another use.
When a run parks with unfinished work while Away, log the boundary and send one
`bmn grant report --run ID --stopped --period DEPARTURE --cause CAUSE --text TEXT`. Pass the period id captured from BMN when the stop was observed. Use `limit:NAME`,
`action:merge|push|pr|command|message`, `access`, `decision`, `prompt` or `other`.
Describe the stop without secrets. If BMN is unavailable the local log still holds it.

After each step, report it for his morning summary: `bmn grant report --run
<Run id> --period <its period> --use-id <id> --result passed|failed|blocked` for a round,
`done`, `refused` (with `--text` saying why) or `uncertain` for an action; a granted action a
rule or GitHub stopped before any use is `--item <term id> --text <why>`. A report's
`--text` is at most 1,000 characters. A report grants nothing and is taken after Back too.

## A round at a parked boundary

A boundary parked by either brake takes one round at a time, the ledger's
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
