# Independent review brief

Read this before dispatching the strong full review at an epic or project
boundary, and pass its questions to the reviewer. Supply the reviewer with the
original requirements, the exact reviewed revision or content fingerprint, the
changed files or a prepared source packet, a risk map, and test instructions.
Include the handoff's rounds used for this scope and prior closure evidence.

## Questions for the reviewer

1. Does the implementation satisfy the original epic intent and the project's
   architecture and goals? Name omissions, misunderstood intent, and drift.
2. For each changed consequential boundary, derive adversarial cases from its
   invariants and check them against the relevant source and, where available,
   running behavior:
   - authority and capability pairs: who may do what, with which credential;
   - cancellation and lease races;
   - retry effects: idempotency, double effects, partial completion;
   - rollback and reapply: migrations, partial failure, replay;
   - isolation and data boundaries: tenant, user, environment.
3. Which boundaries did you not examine? Say so explicitly.

## Findings

A finding names the violated requirement or invariant, a concrete location or
reproduction, the consequence, and a proposed verification. No finding quotas.
Optional polish does not block acceptance.

For a recheck, name each material finding as open or closed with evidence against
the supplied final revision/fingerprint. A changed commit alone is not closure.
The one supplemental delta check allowed by `SKILL.md` must name its trigger,
previous unresolved findings, changed boundaries, and reused evidence. It does
not restart the full review allowance; remaining material gaps block acceptance.

## Second-family check

Use the existing strong review for the questions above. Request at most one
bounded second-family focused check (for example GLM Flash on migration
rollback/reapply) only when a named consequential invariant merits independent
testing; specify its question and the expected evidence. Do not repeat the
whole review, and do not pair reviewers by default.

## Reviewer output

Examined scope, material findings, checks actually run, unreviewed areas,
limitations, and anything unverified. End with the single line `RESULT: done`.
