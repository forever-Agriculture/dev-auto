# MODULE: handoff.md - current run state, evidence and recovery template
# Dev Auto handoff

- Project / selected epics:
- Owning checkout and branch:
- Run id: branch-YYYYMMDD, set once at the start; every later lead keeps it
- Original request and intended outcomes:
- Mode: build | resume
- Stopping condition: selected scope accepted; no automatic time limit
- Explicit user stop (if any; only a later user instruction clears it):
- BMN away: none (`check.py away` keeps it: away|back since TIME revision R; never the note)
- Restrictions and authorization boundaries: current limits; source coordinates for approvals
- Decision and history log: .dev-auto/log.md (append-only; verbatim approval terms with source coordinates)
- Authorized provider routes:
- Lead host / requested model / observed model: from the Codex rollout or Claude receipt

## Progress

- Board (format and path from `bmn plan status --json`) and reconciled state: each selected epic; dependency or blocker
- Implemented:
- Associated loop (optional; host and native loop/task ID):
- Active helpers (ID, route, scope, ownership, state; finished ones go to the log):

## Decisions and findings

- Original or approved intent changes:
- Decided for you (decisions taken under the owner's delegation, for his review; one line each, `[dN]` first, `(bmn: SESSION/KEY)` last once BMN recorded it, as `bmn decision record` returned them):
- Material pending findings:
- Cross-epic obligations:

## Started

(Record each server, daemon or container immediately at launch, one JSON bullet per
identity. Use `none` when empty. Preserve entries after stopping for the audit trail.
Process: `{"kind":"process","pid":123,"start_ticks":"456","command":"synthetic server"}`;
`start_ticks` is field 22 of `/proc/PID/stat`. Container: `{"kind":"container","id":"FULL_64_HEX_ID","name":"run-fixture","command":"docker run …"}`.
An intentionally retained resource adds `"keep":"reason"`.)

- none

## Evidence

- Checks run and observed results: concise results; detailed receipt paths
- Tests: commands run and results; untested behavior (or `none`)
- Reviewed scope and route:
- Baseline and reviewed revisions / material finding dispositions / recheck or delta evidence:
- Review allowance per boundary, kept across leads: rechecks used / consultation used / final repair used / away repair used:
- Brake record per stuck outcome or gate, kept across leads (method history in the log): attempts / gate runs / harness rerun used per method / failed agreed methods / paid spend / latest usage per lead session / last brake card and answer, or pending:
- Unreviewed or unverified areas:

## Measurement

- Dispatches: one line each: purpose, observed model/effort, receipt path; the reason when a later route was used:
- Lead sessions: each lead session's ID or transcript path, one per lead or resume:

## Resume

(Only the two fields below; nothing else in this section.)

- Next safe action:
- Status: ACTIVE | PAUSED | BLOCKED | COMPLETE
