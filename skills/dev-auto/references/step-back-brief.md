# MODULE: step-back-brief.md - BMN Story 106.7: the fixed brief for the big-picture look before a boundary's last round

# Step-back before the last round

Before a boundary's last round, save its failed-method record to a file (`.dev-auto/evidence/<boundary>/failed-methods.md`:
every method tried and what it established), then ask a different agent, the consultant role, read-only:

```bash
bmn team ask --role consultant --project "$PROJECT" --question-file "$BRIEF" --key "$(date -u +%Y%m%d)-<boundary>-step-back"
```

The brief is this text, filled in, with nothing else asked. Its line `Step-back: ...` is what `round` checks, so write it exactly,
with `sha256sum` of the record as it stands; change the record and the ask must be made again.

```text
Step-back: budget <the id `spend_ledger.py open` printed> boundary <N.M or epic> record sha256:<hash of the record file>

You are a fresh reader. This boundary has failed repeatedly and has one round left.
Goal: <the epic's outcome and this story's goal, in the plan's words>
Criteria: <the acceptance criteria, word for word, with the plan's file:line>
Failed methods: <the whole record: each method and what it established>
Evidence: <paths to read>

Answer in this order:
1. Is the goal or the criterion wrong, or misread? Say which, with evidence.
2. What is the real cause, as opposed to what we have been treating?
3. What would you drop: work the story does not ask for?
4. What different method would you try, and what would prove it worked? If none is different, say so.
Keep the requirements, the criteria and every limit; a change to them is for the owner's report, not this round.
```

Record the answer in the brake record, and choose. A different method: take the round with
`spend_ledger.py round --budget B --boundary <boundary> --use-id <boundary>:round-<n> --step-back <ask id> --record <file> --method "<the method>" --lead <your agent>`.
No different method: the story parks without using the round, with this answer as its evidence, and every other story continues.
