# MODULE: qa-brief.md - manual QA inputs, retests and the product verdict in dev-auto
# Manual QA phase

Use BMN's shared `manual-qa` skill. Freeze the candidate and start its disposable running
interface before dispatch. The lead implements fixes; QA never edits the product or its test data
outside the UI. A candidate without a running interface records `QA: not applicable — <reason>`.

## Curate the brief

Write `.dev-auto/evidence/<epic>/qa/brief.json` using `manual-qa/schema.json`'s brief definition.
Supply the epic's Outcome, Why, included/excluded scope, applicable Decisions, numbered criteria
with their original mandatory flags, approved designs and the project's regression checklist.
Add the frozen revision, exact target, starting state, synthetic fixtures and time budget.
Do not supply the epic Log, diffs, implementation claims, lead test evidence, other reviewers'
conclusions, credentials or cookies. Derive the user's goal before looking at implementation.
Other projects keep their regression checklist in their plan; BMN uses `docs/qa-checklist.md`.
Run every gate that checklist requires (BMN: its desktop screen gate).

The brief is a testing contract, never account permission. A real account requires BMN's verified
owner grant for the named activities and limits; an agent-written plan or claim grants nothing.
Account-dependent criteria stay BLOCKED when that session/permission path is unavailable.

For account sessions, criteria must be observable through the permitted browser tools. The host
judges audit completeness from the sealed receipt independently of the agent's verdict. Never
ask the agent to certify the audit, request counts or absence of writes: the seal returns only
a receipt reference, not an audit it can inspect. For example, a look-only landing-page brief
asks “The expected list and statuses are visible” and “No loading error is visible”, with no
opened records or state-changing actions. The host still rejects an incomplete audit when the
agent reports GO.

## Dispatch and keep evidence

Read the approved `qa` role. For a signed-out loopback app, `mode` is `quick-web`, `accounts` is
empty, and `target` exactly matches the normalized origin:

```bash
bmn team ask --role qa --brief "$BRIEF" --origin "$ORIGIN" --disposable --key "$KEY" --background --json
bmn team asks wait "$ID" --timeout 300 --json
bmn team asks export "$ID" --output "$RECORD"
python3 "$SKILL/scripts/qa_gate.py" "$RECORD" --revision "$REVISION" --target "$ORIGIN"
```

`--disposable` states that the target and its services contain synthetic data and no production
backend or credentials. Read the native record and inspect
relevant screenshots before accepting its observations; a consistent report is not proof of a
working interface.

A QA session uses `bmn qa start --brief "$BRIEF" --key "$KEY"`, `bmn qa wait ID`, and `bmn qa stop ID`
only after that BMN build's session/relay path is verified. Save the JSON from `bmn qa wait ID --json`
as a local receipt, then pass its `folder` to the same gate:

```bash
python3 "$SKILL/scripts/qa_gate.py" "$QA_RECORD" --session-run "$WAIT_RECEIPT" --revision "$REVISION" --target "$TARGET"
```

An admitted receipt does not establish native tool confinement or account permission;
those remain separate BMN acceptance gates. V2 account sessions require the native result's
sealed host receipt. Missing, changed, foreign or unsealed receipts
block acceptance. A receipt proves neither native confinement nor service execution; reservation
and send-commitment counts overlap and never create fresh allowance. Use `mode: session`;
authenticated work requires approved aliases and local-only private evidence. Never substitute
a signed-out ask for an account criterion. The teammate's desktop `--bench` route remains refused.
An unavailable QA route is BLOCKED, with its named reason; silence or a failed launch is no pass.

## Lead-run desktop bench

When the owner selects lead-run desktop QA, follow the project's own bench route (BMN:
`docs/qa-checklist.md`, Lead-run desktop bench). It uses the same V1 manual-QA brief/report and
shared checker; it is not a teammate session or proof against a writer who can change the
record. Check its finalized receipt:

```bash
python3 "$SKILL/scripts/qa_gate.py" "$RECORD" --lead-bench --revision "$REVISION" --target "bmn-bench:$GENERATION"
```

An observed boundary escape is a finding; incomplete capture or cleanup blocks acceptance.
Inspect screenshots and exercise the goal before writing the verdict; an admitted receipt
alone proves no UI behaviour.

## Repairs and retests

FAILs and blocker/major findings join the pre-review's consolidated repair. Minor issues outside
scope go to the follow-up list. Retest repaired flows during the existing recheck. Every later
material repair, including a full-review fix, re-runs its affected goal, criteria and adjacent
flows. A new material defect from that retest follows dev-auto's existing brake; QA adds no round.

For a recheck, supply the original findings and neutral repair dispositions; a disposition is
navigation, never evidence. Copy facts from the earlier admitted QA report into `prior_findings`.
Earlier screenshot paths belong to that prior record. Preserve the textual finding facts, but
replace its evidence list with screenshots captured in the current run (or capture those filenames
again); an old screenshot is never current retest evidence.
Bind each required retest to that record and a repaired revision, and keep every original finding
and verdict visible. Run the gate with `--prior "$PRIOR_RECORD" --retest FINDING_ID` (repeat for
additional repaired findings). Every prior open finding, including a minor left for follow-up, needs current original-repro
steps and observations; merely remaining open proves no retest. An unchanged candidate may confirm
that it remains open. A repeat of the unchanged candidate cannot close an
intermittent defect as a verified fix. The revision label is the gate's only candidate identity:
give a new candidate a new label, and never relabel an unchanged one to pass this rule.

One bounded exception covers a prior run on the same label that reopened a finding only because its
reproduction was not assigned: no evidence, no linked criterion, facts unchanged from the earlier
admitted resolution it was handed. Supply that finding with a mandatory `retest:ID` criterion that
carries every original step, reuse the prior's exact label, and pass `--history EARLIER_RECORD` and
`--history-review REVIEW` beside `--prior`, never with `--retest`. REVIEW is an independent
reviewer's native ask export that read the whole prior report and the chain between the records. Its
answer holds the line `HISTORY REVIEW: history-report <sha256 of EARLIER_RECORD/qa/report.json>;
prior-report <sha256 of PRIOR/qa/report.json>; revision <label>; target <target>` and exactly
`ID: NO RECURRENCE` for each finding it clears. Any other line for that ID blocks. The review proves
provenance, not truth; read it and the new run's evidence before accepting.
Read recorded regression gaps and track mandatory coverage
outside a finding's original reproduction.

For a session retest, also supply `--prior-session-run "$PRIOR_WAIT_RECEIPT"` with `--prior`.
For a lead-run bench retest, use `--lead-bench` and add `--prior-lead-bench` with `--prior`.
The gate accepts only a bound GO or GO WITH ISSUES; a valid NO-GO exits 1 and
keeps that verdict. Missing/invalid records, mandatory FAIL/BLOCKED/NOT RUN, an unachieved or
uncertain goal, and unresolved blocker/major findings block acceptance. Only an explicit deferral
in the epic's approved Run needs may waive that acceptance criterion; record it and its follow-up
without rewriting QA's report or treating its checker's exit 0 as release approval.

A manual-QA epic retains an implementing lead. Planning names what it may fix and what it may
defer. The lead dispatches QA, triages reproducible findings, fixes within that scope, records
permitted difficult/large deferrals with follow-up coordinates, retests repairs, then obtains
the normal whole-epic reviews. Its audit/triage mission can be complete while the tested product
remains NO-GO; report those two outcomes separately.

## Report and evaluation

The epic report shows QA's verdict, goal check, findings and their fate, and remaining coverage
gaps. Only synthetic or sanitized evidence may reach the report page or another teammate;
real-account screenshots, pages and responses stay in the QA's local BMN record. For V2 account
sessions, show the host receipt's sanitized account/site/activity totals and audit completeness
beside the verdict, goal, findings and dispositions. Never copy raw requests or model-authored
counter claims. A host audit gap or uncertain activity keeps NO-GO visible.

After the first three real epics with a running interface, use existing host/ask records to count
material findings unique to QA, later defects QA missed, coverage, blocked/missing passes apart
from clean passes, false findings, time and known usage. Send the owner one keep/change/remove
verdict with these counts; nothing switches off automatically. Rehearsals verify the integration
and do not count as real-epic effectiveness evidence. No new tracking service or benchmark.
