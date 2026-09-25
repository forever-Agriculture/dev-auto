# Independent review brief

Read this before dispatching a pre-review or the strong full review at an epic or
project boundary. Give a reviewer with read tools this brief by path; otherwise
include its exact text with the source packet. Supply the original requirements, the baseline
(the revision before this scope's first change) and reviewed revisions or content
fingerprints with the diff between them (task-owned untracked content included),
the relevant source and tests, execution evidence, a risk map and test
instructions. Implementation and test summaries are claims to check, not
orientation. Exclude credentials and unrelated files. Include the prior review and
disposition evidence still relevant to this scope.

## Quick pre-review

The pre-review needs the original requirements, the baseline and the diff. Map, do
not judge exhaustively. Return, in about one page: each story or acceptance criterion
with the files and tests that implement and cover it; criteria without a test or
evidence; the changed areas most worth the strong reviewer's attention, and why;
obvious defects with location and consequence. End with the single line
`RESULT: done`. The questions below are for the strong review.

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
   - isolation and data boundaries: tenant, user, environment;
   - adoption and deletion: where replacement is intended, sibling sites sharing
     the contract; behavior removed without either replacement or intentional
     retirement.
3. For changed consequential behavior, read the relevant tests and execution
   evidence: would a realistic regression at its use site fail an assertion?
   Report gaps and evidence limits.
4. Which boundaries did you not examine? Say so explicitly.

At project scope, also examine the aggregate multi-epic change for consequential
duplication, dependency or pattern drift and accumulated complexity, and verify
the obligations due within the selected scope.

## Findings

A finding names the violated requirement or invariant, a concrete location or
reproduction, the consequence, and a proposed verification. No finding quotas.
Optional polish does not block acceptance.

For a recheck or later evidence-triggered delta review, give each material finding
a disposition against the supplied final revision/fingerprint: closed with evidence,
rejected with the refutation, or unresolved with what would settle it. A changed
commit alone is not closure. Reuse unaffected evidence; remaining material gaps block
acceptance.

## Reviewer output

Examined scope, material findings, checks actually run, unreviewed areas,
limitations, and anything unverified. End with the single line `RESULT: done`.
