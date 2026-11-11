# MODULE: step-back-brief.md - BMN Stories 106.7 and 118.2: the collected big-picture look before a boundary's last round

# Step-back before the last round

Before a boundary's last round, save its failed-method record to
`.dev-auto/evidence/<boundary>/failed-methods.md`: every method tried and what it
established. Collect the epic's main open and most complex questions with their evidence
into one request using [consult-brief.md](consult-brief.md), at most five numbered
questions ranked by consequence, grouping related issues. Each gives its boundary, what
was tried and failed, and what the answer must settle; include the epic's Outcome, stories,
criteria and limits left. One question alone is right only if no other is open; do not
wait for more before a needed ask.

Take `senior_consults` first (`fable_consults` in Epics 114–117 whose approved file names
it so). Ask a different agent, read-only, attaching the epic with `--file`:

```bash
bmn team ask --role senior-consultant --time-limit 40 --project "$PROJECT" --file "$EPIC_FILE" --question-file "$BRIEF" --key "$(date -u +%Y%m%d)-<boundary>-step-back"
```

Use BMN's shorter maximum if it is below 40 minutes. Without that role in the team,
ask the consultant chain's next eligible agent other than its first with
`--role consultant --agent NAME`, still counted as a senior use. Do not change the team;
normal route/refusal and Away rules hold. A refused ledger use means no ask.

Add this exact binding line and the following step-back questions to the collected brief.
Use `sha256sum` of the record as it stands; a changed record needs a new counted ask.

```text
Step-back: budget <the id `spend_ledger.py open` printed> boundary <N.M or epic> record sha256:<hash of the record file>

You are a fresh reader. This boundary has failed repeatedly and has one round left.
Goal: <the epic's outcome and this story's goal, in the plan's words>
Criteria: <the acceptance criteria, word for word, with the plan's file:line>
Failed methods: <the whole record: each method and what it established>
Evidence: <paths to read>

For this boundary, settle these points in the numbered question's answer:
1. Is the goal or the criterion wrong, or misread? Which, with evidence?
2. What is the real cause, as opposed to what we have been treating?
3. What would you drop: work the story does not ask for?
4. What different method would you try, and what would prove it worked? If none is different, say so.
Use the consult brief's answer form: verdict, evidence read with file:line, confidence,
up to three ranked methods where asked, and what was not checked.
Keep requirements, criteria and every limit; changing them belongs in the owner's report.
```

Record the ask id, answer and ranked methods in the brake record, and choose a different
method. Take the round with
`spend_ledger.py round --budget B --boundary <boundary> --use-id <boundary>:round-<n> --step-back <ask id> --record <file> --method "<the method>" --lead <your agent>`.
The ledger accepts an answered `senior-consultant` or `consultant` ask by another agent;
all its other binding and reuse checks still hold. No different method: park without
using the round; independent stories continue. After acting, record the ask's outcome
(`unblocked`, `partly` or `not`, with why) in the handoff and report.
