# Lessons for dev-auto from the earlier workflow and direct development

Recorded 2026-09-17 from historical project notes, not a new replay of those runs. These are implementation lessons, not proof that dev-auto is more efficient. Keep the agreed model choices; historical model-routing prescriptions do not override current owner decisions.

## 1. Prove the approach serves the project before polishing it

Evidence: the September 13 diagnosis records Epic 64's content approach below the existing result on at least one dimension in 18/24 evaluated pairs, while additional extractor fix rounds continued.

Apply: before investing deeply in uncertain product behavior, run the smallest useful representative value/feasibility check. Fold it into the pre-epic alignment check. If the agreed approach fails its intended outcome, resolve that design question rather than keep polishing an implementation. Do not invent a paid or production experiment without authorization.

## 2. Coordination can cost more than the work it manages

Evidence: the same diagnosis attributes about 80% of list-price estimates across three historical nights to main agents. The September 14 issue record counts 274 hand-decision receipts out of 455; those receipts are not a count of owner interventions.

Apply: one direct lead, short state, compact returns, no repeated history reading or verbose polling. Add a helper only for a concrete benefit. Measure lead and coordination use alongside worker use; moving the same process to another provider alone does not remove overhead.

## 3. Recover completed work instead of replaying it

Evidence: the Epic 64 issue record describes a 61-minute worker whose reported completed work was rejected for result format, with full relaunch the supported recovery path. Other documented failures involved stale dependency holds, retry snapshots and a valid no-change investigation result being parked.

Apply: preserve artifacts and independently inspect their actual state. Distinguish implementation/test failure, launch failure, permission denial, quota, malformed return and required owner decision. Repair a result envelope or collect missing evidence when sufficient; do not automatically rerun implementation. A useful no-change/hypothesis-refuted result can satisfy the assigned task. Never infer acceptance merely from worker prose.

## 4. Reviews need a purpose and a stopping rule

Evidence: one troubled Epic 64 story accumulated 415 worker-minutes and about 21 review-lens dispatches; every story was classified high/critical. The diagnosis explicitly cautions that some late findings were real, so the lesson is not to dismiss them.

Apply: prioritize material requirements and consequential boundaries; keep Astra → Fable as a tier rather than a default pair; use focused corrections and explicit blocked outcomes. Reuse evidence only where semantically valid. A change in another part of the same file does not automatically require a full repeat review, but unchanged hunks can still be affected by changed shared contracts or dependencies. Do not replace semantic impact analysis with a hunk-only rule.

## 5. Runtime evidence and model diversity both matter

Evidence: ProjectQ passed 120 tests and an initial Astra review before a later audit found three material defects: prelaunch authority, unsafe capability pairing and migration rollback/reapply. GLM Flash found the migration defect. Six new regressions failed on the old implementation; the final aggregate passed 126 tests.

Apply: test important invariants, negative cases, races, rollback and existing user journeys. Independent testers derive missing cases. Preserve original requirements and source access for reviewers. A strong-model verdict, coverage percentage or test count cannot establish correctness by itself.

## 6. Use the right test scope at the right time

Evidence: Epic 64 repeatedly ran a roughly 12-minute full chain per story and again at epic acceptance. Load-sensitive timing tests required repeated adjudication. The direct run used targeted repair checks and reserved its roughly 107-second aggregate for acceptance boundaries.

Apply: affected tests during changes, integration/regression checks at epic boundaries, full project checks when impact or policy requires. Record useful baselines and suite durations. Investigate flaky/load-sensitive failures; serialize performance checks when needed. Reuse relevant unchanged evidence rather than rerun blindly; unexplained material failures block acceptance.

## 7. Continuity and synchronization prevent owner rework

Evidence: direct Codex lost GLM's Claude Code route across compaction; the owner had to correct it. the earlier workflow had distinct source and installed copies and required explicit hash verification.

Apply: canonical shared skill, concrete registry-backed routes and explicit owner restrictions. Persist unresolved findings, later-epic obligations and exact next action. Validate dispatch against current route/restriction files and restore state after compaction. Record policy revision so stale loaded instructions are detectable. Treat board status as progress metadata, not proof of acceptance.

## 8. Preserve useful parallelism with real boundaries

Evidence: the September 15 restoration note records parallelism as an established requirement that had been removed during simplification. It verifies overlap and conflict handling in local tests but explicitly does not prove an OS boundary or real model-run speedup.

Apply: keep useful independent implementation helpers, as the owner requested. Consider shared test databases, ports, fixtures and input dependencies as well as write files. Isolate or serialize conflicting resources. Do not describe file ownership prompts as a sandbox. Record actual overlap and integration outcome before claiming a speed benefit.

## 9. Permissions must work even when prompts are ignored

Evidence: the Epic 57 isolation record describes production reads after a worker unset emulator variables and loaded a repository environment file despite the intended local-only boundary.

Apply: enforce access through the host's sandbox/permissions, keep credentials out of tool environments and briefs, and test forbidden operations with harmless canaries. Missing isolation is a visible route limitation, not grounds to bypass restrictions. Actual behavior and receipts matter more than a worker's claim of compliance.

## 10. Define completion and count all delivery effort

Evidence: the earlier workflow acceptance/reporting repairs replaced reliance on done-board tokens with current evidence. Direct-development records distinguish controlled-local acceptance from unresolved production gates and record substantial usage gaps.

Apply: separate implemented, verified, reviewed and externally blocked states. Declare the intended acceptance boundary; avoid completed local work being described as deployed production. Include repair, review, waits, escaped defects and owner attention in comparisons. A quiet report, many tests or many completed stories is not proof of efficiency.

## Source records

- a retired project note
- a retired project note
- a retired project note
- a retired project note
- a retired project note
- a retired project note

## Using this during implementation

Sol/xhigh implements dev-auto when implementation starts. GLM Flash/max through Claude Code then performs routine review and driven testing. Give both this note and IMPLEMENTATION.md; verify their findings against artifacts. These assignments are for building dev-auto itself and do not restrict its future lead's choice of helpers. Runtime product work has not started in this design discussion.
