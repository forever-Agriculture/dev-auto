# MODULE: review-brief.md - evidence and questions for independent reviews
# Independent review brief

Read this before dispatching a pre-review or the strong full review at an epic or
project boundary. Give a reviewer that can read this file its path; include its exact
text for reviewers without tools. Supply the original requirements, the baseline
(the revision before this scope's first change) and reviewed revisions or content
fingerprints with the diff between them (task-owned untracked content included),
the relevant source and tests, execution evidence, a risk map and test
instructions. Use exact paths within the reviewer's readable scope; attach authorized
task material outside it with `--file`, including required plans and checkpoints.
List every solo technical decision of the run with its one line of evidence from the
handoff and ask the reviewer to judge them; a run with none says so explicitly.
Implementation and test summaries are claims to check, not orientation. Exclude
credentials, raw private transcripts and unrelated files. Include the prior review and
disposition evidence still relevant to this scope.

## Quick pre-review

The pre-review needs the original requirements, the baseline and the diff. Map, do
not judge exhaustively. Return, in about one page: each story or acceptance criterion
with the files and tests that implement and cover it; criteria without a test or
evidence; the changed areas most worth the strong reviewer's attention, and why;
obvious defects and slop (question 4) with location and consequence. End with the
single line `RESULT: done`. The questions below are for the strong review.

## Questions for the reviewer

For a plan under review: does each answer in the epic's `## Challenges` hold (Scale, Origin, Verified, Exists, People)? Check it against the code and the people named.

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
   Does evidence exercise the affected owner path on the accepted candidate with
   representative state and, where relevant, viewport? Report gaps and limits.
4. Does the change add slop: complexity or leftovers no requirement asks for? Look
   for a second way of doing what the codebase already does one way (both sites);
   an abstraction, option or layer with no concrete purpose in the required design;
   a shim or fallback in place of the requested end state; replaced code left
   behind (its remaining callers, or evidence of none); a test that checks only
   its own mock; a simplified copy that bypasses the real component. These are
   signals: a finding is material only with evidence of a violated requirement or
   invariant or a consequential maintenance cost, allowing for required
   architecture, test seams and compatibility. Give file:line, the consequence
   and the simplest end state that keeps the requirements. Comments that restate
   the code and other cosmetic slop are optional polish: list them in one line
   for a repair already needed; alone they never justify a repair or recheck.
5. Which boundaries did you not examine? Say so explicitly.
6. Does any change work against a principle or a "We refuse" line of the project's
   vision? BMN attaches the project's `VISION.md` to `focused-reviewer`,
   `epic-reviewer`, `small-epic-reviewer` and `final-reviewer` asks; with none attached, answer "no vision
   given".

At project scope, also examine the aggregate multi-epic change for consequential
duplication, dependency or pattern drift and accumulated complexity, and verify
the obligations due within the selected scope.

## Findings

A finding names the violated requirement or invariant, a concrete location or
reproduction, the consequence, and a proposed verification. No finding quotas.
A vision finding (question 6) quotes the principle or refusal line, gives the code's
`file:line` and says the consequence.
Optional polish does not block acceptance. The lead records one line per full review
and recheck in the handoff: `review <ask id>: <n> findings, <r> repaired, <x> rejected,
<d> deferred`. Give findings stable names and dispositions so the counts can be
checked against evidence; a repeated finding is counted once in that review.

For a recheck or later evidence-triggered delta review, give each material finding
a disposition against the supplied final revision/fingerprint: closed with evidence,
rejected with the refutation, or unresolved with what would settle it. A changed
commit alone is not closure. Reuse unaffected evidence; remaining material gaps block
acceptance.

## Reviewer output

Examined scope, material findings, checks actually run, unreviewed areas,
limitations, and anything unverified. A full review also gives an opinion for the
report: a 1–4-word verdict and 2–3 plain sentences on worth, risk and what to watch.
A recheck, given the earlier review and the dispositions, refreshes that opinion
against the final revision. End with the single line `RESULT: done`.
