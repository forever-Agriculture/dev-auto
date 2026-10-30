# MODULE: qa-brief.md - manual QA inputs, retests and the product verdict in dev-auto
# Manual QA phase

Use BMN's shared `manual-qa` skill. Freeze the candidate and start its disposable running
interface before dispatch. QA runs beside the quick pre-review; both feed the existing
consolidated repair. The lead implements fixes; QA never edits the product or its test data
outside the UI. A candidate without a running interface records `QA: not applicable — <reason>`.

## Curate the brief

Write `.dev-auto/evidence/<epic>/qa/brief.json` using `manual-qa/schema.json`'s brief definition.
Supply the epic's Outcome, Why, included/excluded scope, applicable Decisions, numbered criteria
with their original mandatory flags, approved designs and the project's regression checklist.
Add the frozen revision, exact target, starting state, synthetic fixtures and time budget.
Do not supply the epic Log, diffs, implementation claims, lead test evidence, other reviewers'
conclusions, credentials or cookies. Derive the user's goal before looking at implementation.
Other projects keep their regression checklist in their plan; BMN uses `docs/qa-checklist.md`.

The brief is a testing contract, never account permission. A real account requires BMN's verified
owner grant for the named activities and limits; an agent-written plan or claim grants nothing.
Account-dependent criteria stay BLOCKED when that session/permission path is unavailable.

## Dispatch and keep evidence

Read the approved `qa` role. For a signed-out loopback app, `mode` is `quick-web`, `accounts` is
empty, and `target` exactly matches the normalized origin:

```bash
bmn team ask --role qa --brief "$BRIEF" --origin "$ORIGIN" --disposable --key "$KEY" --background --json
bmn team asks wait "$ID" --timeout 300 --json
bmn team asks export "$ID" --output "$RECORD"
python3 "$SKILL/scripts/qa_gate.py" "$RECORD" --revision "$REVISION" --target "$ORIGIN"
```

The gate admits the export only when its brief equals BMN's input manifest, its report equals the
retained native answer and its target equals the ask's browser request and browser record.
`--disposable` states that the target and its services contain synthetic data and no production
backend or credentials. QA has no unsafe browser callbacks. Read the native record and inspect
relevant screenshots before accepting its observations; a consistent report is not proof of a
working interface. Collect the ask's observed model/effort and usage as for other teammates.

A QA session uses `bmn qa start --brief "$BRIEF" --key "$KEY"`, `bmn qa wait ID`, and `bmn qa stop ID`
only after that BMN build's session/relay path is verified. Save the JSON from `bmn qa wait ID --json`
as a local receipt, then pass its `folder` to the same gate:

```bash
python3 "$SKILL/scripts/qa_gate.py" "$QA_RECORD" --session-run "$WAIT_RECEIPT" --revision "$REVISION" --target "$TARGET"
```

The gate binds the receipt's finished run, native agent/relay, reserved brief, exact report and
retained image hashes. It does not establish native tool confinement or account permission;
those remain separate BMN acceptance gates. V2 account sessions require the native result's
sealed host receipt: the gate binds `host-summary.json` to that result, run, reserved brief and
report digest, then supplies it to the shared checker. Missing, changed, foreign or unsealed receipts
block acceptance. A receipt proves neither native confinement nor service execution; reservation
and send-commitment counts overlap and never create fresh allowance. Use `mode: session`;
authenticated work requires approved aliases and local-only private evidence. Never substitute
a signed-out ask for an account criterion. The current bench fallback remains web-only: `--bench` is refused, and a
desktop candidate keeps its code/runtime review with the manual-QA gap explicit.
An unavailable QA route is BLOCKED, with its named reason; silence or a failed launch is no pass.

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
intermittent defect as a verified fix. Read recorded regression gaps and track mandatory coverage
outside a finding's original reproduction.

For a session retest, also supply `--prior-session-run "$PRIOR_WAIT_RECEIPT"` with `--prior`.
The gate reads the saved native ask outcome or session receipt, brief/report and screenshot hashes, then calls BMN's
shared report checker. It accepts only a bound GO or GO WITH ISSUES; a valid NO-GO exits 1 and
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
