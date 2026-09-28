# dev-auto design proposal

Date: 2026-09-17. Status: design history; lean implementation complete. The owner's final simplification and current [IMPLEMENTATION.md](IMPLEMENTATION.md) take precedence over earlier proposals for custom mechanisms: nearly direct development, one shared skill, small routing reference and handoff. Reuse native tools and permissions; no new orchestration framework.

Owner correction after installation: dev-auto runs until the selected scope is accepted, with no automatic work deadline. Claude `/loop` is only a recovery wakeup. Earlier time-window proposals below are historical and superseded by the current skill and implementation specification.

## Purpose

Deliver accepted project outcomes with a direct coding lead, useful independent help, and proportionate verification. Optimize quality, total cost, elapsed time and owner attention together. BMAD remains the source of planning intent; its implementation workflow is not invoked.

## Evidence shaping this proposal

- ProjectQ demonstrated direct implementation across four epics. A late Astra/GLM audit found three material defects after the first close-out: prelaunch authority, capability pairing and migration rollback/reapply. Reviewer approval alone was insufficient.
- The same run lost the configured GLM route across compactions. Launch coordinates and owner decisions must survive independently of conversation memory.
- the earlier workflow records describe repeated review/repair loops, controller maintenance and source/installation drift. Preserve useful checks without copying its controller into a new project.
- The Epic 57 worker-isolation record documents production reads despite a local-only requirement. Worker access restrictions need enforceable permissions, not only prompt wording.
- Existing records do not establish a reliable overall cost/speed winner. Measure the next owner-selected real work; do not invent savings percentages.

Local source notes (historical evidence, not fresh replay of those runs):
- a retired project note
- a retired project note
- a retired project note
- a retired project note

## User experience

Proposed syntax; not yet available:

```text
Claude Code: /dev-auto epics 1-3 --for 3h
Codex:       $dev-auto epics 1-3 --for 3h
Either:      dev-auto project --for 3h   (through its native skill invocation)
Either:      dev-auto resume
Either:      dev-auto status
```

The lead works continuously while useful authorized work remains. The time budget is an upper bound, not a requirement to consume time. Stop early when accepted or externally blocked. Persist the original deadline on resume; a recurring trigger must not reset it. Reserve time for verification and a handoff. At expiry, checkpoint incomplete work rather than declare acceptance or launch new work. A prompt-only deadline is cooperative; a hard process cutoff would require a small supervisor and safe worker shutdown, which is a separate implementation decision.

Claude's native /loop interval is cadence, not run duration: /loop 3h repeats every three hours. Keep repeat scheduling outside the shared development policy. A recurring invocation must detect an active run and avoid duplicate workers, then stop scheduling once complete. Verify each host's actual invocation and continuation behavior before advertising parity.

## Shared installation

One canonical skills/dev-auto directory in this repository, linked from the personal Codex and Claude skill locations. Both tools read the same policy, model table and review guidance; host-specific adapters contain only invocation differences. No independently maintained copies.

Proposed installation locations: ~/.agents/skills/dev-auto and ~/.claude/skills/dev-auto. A check validates link targets and canonical revision. Each run records its policy revision, and resume detects changes rather than silently adopting a different policy mid-run. Live-session reload behavior requires verification in both clients.

Use one model registry with concrete model IDs, requested and supported effort, execution tool, configured profile/launcher, permissions and fallback order. Keep credentials out of the registry. Do not infer that GLM is unavailable from Codex's built-in model list. Inspect the configured Claude Code GLM route first.

## Model priorities

Superseded on 2026-09-25 by the tier table in `skills/dev-auto/references/models.md` (owner decision). The 2026-09-17 selection below is history.

The owner selected the roles and effort levels below on 2026-09-17. These are task priorities, not a measured pricing ranking. Exact identifiers, supported effort and available launch routes must be validated during implementation; no silent effort downgrade.

| Role | Preferred model / effort | Alternatives and triggers |
| --- | --- | --- |
| Direct lead | Sol / xhigh in Codex OR Opus / xhigh in Claude Code | Owner selects the host; lead retains implementation and integration context |
| Routine review, bounded test work, easy isolated tasks | GLM Flash / max through Claude Code | Luna / max through Codex, then Sonnet / low or medium through Claude Code; adapt to task fit and available allowance |
| Debugging assistance | GLM / max through Claude Code | Supply the reproduction, relevant source and logs; the lead integrates the diagnosis and fix |
| Difficult implementation | Existing Sol / xhigh or Opus / xhigh lead | For a sizeable independent task with a concrete parallel benefit, the lead chooses whichever model is appropriate; no fixed Sol/Opus helper requirement |
| Whole-epic important risks and overall correctness | Astra / medium → Fable / medium; low for suitable bounded cases | Check intended outcomes and project alignment, architecture, cross-story behavior, misunderstood requirements and drift; economical models handle routine details and test work |
| Whole-project final evaluation | Astra / high → Fable / high | GLM / max assists with less consequential details, testing and evidence checks |
| Critical decisions or serious disagreements | Astra / high → Fable / high | Start with Astra; escalate to Fable when needed, bounded to the concrete decision and evidence |

GLM / max follows the owner's GLM preference; the exact configured GLM model/profile for these roles remains to be resolved during implementation. Do not silently equate it with the separate GLM Flash routine-task row.

Astra → Fable is an ordered tier, not a paired review requirement. Start with Astra at the effort specified for the task; use Fable as the next tier when escalation or fallback is warranted. Do not automatically dispatch Fable after a sufficient Astra result. The selected reviewer covers integrated correctness, important risks, intended outcomes, misunderstandings, omissions and architectural drift. Keep corrections and rechecks focused; escalation does not reset repair budgets.

The lead may dispatch GLM Flash/max or Luna/max at any point for a concrete, appropriate reason, including investigation, debugging support, testing, review or an implementation subtask. These helpers are not restricted to scheduled review boundaries or an exhaustive task list. The lead chooses the appropriate model for sizeable independent parallel work based on task fit, consequence, cost and availability. Keep each dispatch bounded and preserve existing ownership and access restrictions.

Reserve Astra/Fable time for consequential reasoning and judgment. Before a strong-model dispatch, the lead separates important questions from routine supporting work when that split saves meaningful effort. GLM Flash, Luna, Sonnet or another appropriate economical model can locate relevant files, collect and summarize logs, run established checks, map acceptance criteria to evidence, check mechanical consistency, reproduce a specified finding or prepare a bounded routine fix. Strong models focus on overall fidelity to intent, critical invariants, architectural tradeoffs, difficult interpretation and material disagreements.

Give the strong reviewer a concise brief with the questions, original requirements, source coordinates, exact reviewed revision or content fingerprint, raw evidence links, unresolved findings and helper limitations. Helper summaries are navigation aids, not acceptance proof: the strong reviewer retains access to relevant source and raw evidence and independently checks consequential claims. A routine-looking issue with high-consequence implications moves back to the strong reviewer. This division must not reduce whole-epic or whole-project review to an artificially narrow diff or hide omissions and drift.

The lead coordinates helper work before or alongside the strong review where independent. Astra/Fable can identify supporting work to delegate through the lead; avoid an automatic nested delegation layer. Do not dispatch a helper for a trivial lookup when the coordination would cost more than doing it directly. After fixes, ask the appropriate reviewer to recheck affected important conclusions rather than repeat routine evidence collection.

Tool/provider distinction: Codex runs configured OpenAI models; Claude Code runs configured Claude models and the GLM provider/profile. Read-only review and local test execution have different permission needs. A worker brief records allowed files/resources, provider route, explicit prohibitions and evidence required. Verify actual enforcement before unattended use.

A model limit is not evidence of implementation difficulty. First distinguish launcher/configuration failure, unavailable quota and a real reasoning failure. Do not respond to a broken dispatch by blindly buying a stronger model. Alternative routes preserve task restrictions and required independence.

## Development and sprint status

1. Read the selected BMAD plans, architecture, acceptance criteria, dependencies and repository instructions. Identify material ambiguities and existing changes. Build a short acceptance map referencing the original criteria rather than rewriting all planning documents.
2. Resolve the actual sprint-status.yaml and its documented status vocabulary. Treat it as the canonical story/epic progress board. Use existing transition semantics; do not invent new YAML states.
3. Mark a story in progress when implementation starts, review-ready when implementation and focused checks are ready, and done only after required evidence and applicable reviews are satisfied. Epic acceptance follows integrated verification. Maintain any project-specific retrospective semantics.
4. The lead owns status writes. Preserve unrelated entries, comments and order. Use guarded atomic writes, reread validation and stale-input detection so another actor's changes cannot be overwritten. Workers return evidence; they do not race to update the board.
5. When a material defect invalidates completed acceptance, reopen the affected story using a supported state and record why. If an epic/project gate is blocked, preserve that fact even when its individual stories passed.
6. After compaction/resume, reread the short run handoff, original owner restrictions, routes, board and pending findings. Reconcile recorded progress with actual files and evidence. Never infer acceptance merely from a status label.

Use direct development with coherent batches. For sizeable independent implementation tasks, the lead selects an appropriate model and supplies precise file ownership and resource boundaries. GLM Flash and Luna assistance remains available throughout development for appropriate bounded work. Separate test databases/ports where concurrent tests mutate shared state. Keep the lead productive while helpers work. Prefer a small number of useful workers over maximum fan-out.

## Verification and independent review

| Boundary | Required evidence | Review shape |
| --- | --- | --- |
| Story | Acceptance criteria mapped to meaningful focused tests; affected running flow and adjacent behavior where relevant | Independent review for consequential changes; routine changes may be covered by an explicitly scheduled epic review |
| Epic | Integrated user journeys, cross-story contracts, project-alignment evidence and an appropriate regression suite | Astra/medium first, Fable/medium as the next tier when needed; low for suitable bounded cases; assess the result against both epic intent and the project as a whole |
| Project | Cross-epic journeys, architecture consistency, failure/recovery paths and applicable full acceptance checks | Astra/high first, Fable/high as the next tier when needed; GLM/max handles less consequential supporting work; report what remains unverified |

Project regression checks are mandatory for every epic. Identify affected existing capabilities, earlier-epic contracts and shared components before development, and record a relevant baseline where practical. During implementation run focused regression checks; before epic acceptance run the appropriate broader integration/regression suite and drive affected existing user journeys. Include existing tests, not only newly written story tests, and add missing protection where a material uncovered risk is identified. Run a full project suite when the change impact or project policy requires it; do not substitute a narrow suite without an impact-based reason. Unexplained failures or unverified material affected flows block acceptance. Before labeling a failure pre-existing, reproduce it on an isolated baseline that preserves user changes, then report its impact on acceptance. Reuse only evidence still valid for the reviewed code, dependencies and environment.

Independent testing must include deriving missing cases and driving relevant behavior, not merely repeating the implementer's summary. For critical seams, frame adversarial tests from invariants: authorization pairs, cancellation/lease races, retries and effects, rollback/reapply, isolation and data boundaries. Use a different model family where available and useful.

Reviewers get requirements, risk map, exact reviewed revision or content fingerprint, test instructions and access to source. Findings need a violated requirement/invariant, concrete location or reproduction, consequence and proposed verification. No finding quotas. Optional polish does not block acceptance.

The lead triages findings against evidence. Material defects receive regressions that fail without the fix and pass with it, using an isolated baseline that preserves user work. If reviewer and lead disagree on a consequential issue, reproduce it or escalate the specific question.

Proposed default: one full review followed by one focused correction review at a boundary. A remaining material failure blocks that boundary; it does not become accepted because a budget expired. After two failed fixes of the same symptom, investigate with new evidence instead of another speculative patch. Continue unrelated authorized work where possible. A new scope or invalidated review may justify reopening, with the reason recorded.

Avoid duplicate broad reviews when the final epic and project boundary coincide: the selected strong reviewer's project-level high-effort pass may explicitly cover both required scopes. The Astra → Fable tier order still applies; combining boundaries does not require both reviewers. Reuse still-valid evidence for unchanged areas. Rerun affected checks after changes and the applicable integrated suite before acceptance; do not repeatedly run broad suites inside every repair loop.

## Settled decisions (2026-09-18)

Consultation briefs reference these instead of reopening them.

- No controller, scheduler, or worker framework; the host's native tools and permissions are the boundary.
- Reviewer tiers are escalation, not pairing: one strong full review, at most one justified second-family focused check, and focused rechecks within SKILL.md's convergence bound. Every epic and project gets a quick GLM pre-review that runs alongside the lead's final checks, one consolidated repair without a recheck round, then the strong review from which the bound counts; the pre-review sits outside it (2026-09-25, owner, replacing the optional pre-review of 2026-09-24). Escalation does not reset the allowance. (Amended 2026-09-22: the bound replaced a single consolidated recheck that the skill had stopped stating; BMN Epic 15 and ProjectB Epic 65 then looped through 15 and about 37 review dispatches.)
- Compaction recovery is a `SessionStart` hook plus a bounded handoff, not a custom context store; it is guidance, not enforcement, and each host's automatic case must be exercised before it is relied on.

## Small durable run record

Keep the existing sprint board plus one concise run handoff and referenced evidence files. Do not duplicate BMAD story state into a second competing board.

The handoff retains: selected scope and planning paths; original deadline; owner restrictions and action-specific permissions; policy revision; model routes; active worker identities; accepted evidence with source fingerprint; unresolved findings; cross-story obligations; next action and blockers. Update at meaningful transitions, before compaction and before yielding.

Minimal helpers are justified for synchronization checks, safe board edits, worker lifecycle/permissions and receipt collection where native tools cannot provide them. Start with native host capabilities and narrow helpers. Defer an event-sourced controller, custom task scheduler, elaborate scoring and automatic model tournaments until a demonstrated need exists.

## Acceptance, permissions and measurement

Report separately: implemented, verified locally, independently reviewed, blocked/unverified external gates and release status. Astra/Fable evaluate correctness evidence, goal satisfaction and proportionality; their approval is not a correctness guarantee.

Commit, push, merge and deploy remain separate permissions. A multi-hour development request does not authorize them. Workers inherit only explicitly allowed access; never silently switch to production credentials or services to make a local test pass.

Capture elapsed time through acceptance, provider/model usage including the lead, helpers and recovery, quota/cost when observable, meaningful defects found, escaped defects and owner interventions. Read them from host records (lead session IDs and receipt paths in the handoff) when runs are evaluated: lead-written tallies were wrong or missing in every run audited on 2026-09-28. Unknown usage stays unknown. Test count, token count or story count alone cannot establish efficiency.

## Small first implementation and pilot

Build one shared skill, a model table, short review/testing briefs, a run-handoff template, installation verification and only necessary host adapters/board helpers. Exercise discovery in both hosts, GLM launch through Claude Code, status updates, compaction/resume, duplicate invocation and enforcement of worker restrictions before unattended use.

Use one owner-selected real epic as the first development pilot, then evaluate its accepted outcome, total usage, elapsed time and owner attention. Expand to whole-project unattended work after that evidence. Do not run artificial product experiments merely to claim savings.


## Project alignment before and after every epic

Owner requirement, 2026-09-17: check project alignment before implementing an epic and again after implementation. Both checks are mandatory; integrate them into scope preparation and the existing epic acceptance review instead of adding automatic review rounds.

Before implementation, compare the epic and its stories with current project goals, requirements, architecture, established decisions, actual implementation and relevant completed/upcoming epics. Check whether the epic still serves the project goal, has the right scope and sequence, respects dependencies and existing contracts, avoids duplicated or contradictory work, and preserves obligations needed by later epics. Record a concise alignment conclusion, source references, material discrepancies and the expected integrated outcome in the existing run handoff. Do not mark implementation in progress until material alignment blockers affecting that work are resolved.

The lead owns this preparation and may use economical helpers to gather evidence. Important ambiguity or architectural conflict goes to Astra at appropriate effort, then Fable if needed; critical decisions retain the high-effort tier. Do not automatically buy a strong-model call for every routine precheck. If resolution changes project intent, public contracts or material scope, obtain the owner's decision rather than silently rewriting the plan. An alignment check does not authorize unrelated project cleanup or implementation outside the selected scope.

After implementation, the existing independent whole-epic reviewer compares the actual result against both the epic's intended outcome and the project as a whole. Inspect integration with existing capabilities and cross-epic contracts, consistency with architecture and user journeys, regressions, omissions, scope drift and effects on upcoming epics. Use driven integration evidence and direct source inspection; passing story tests alone does not establish project alignment. Check actual alignment anew rather than merely confirming the precheck's conclusion.

Record the result and outstanding project obligations alongside epic acceptance evidence. Material misalignment blocks epic completion and reopens affected completed work when necessary; optional improvements stay separate. Revisit the relevant precheck if requirements, architecture or dependencies materially change during implementation. Retain the original intent and explicit approved changes so it cannot be rewritten merely to match the result.

## Agreed efficiency and effort policy

Owner accepted the efficiency suggestions and adaptive use of Astra/low or Fable/low on 2026-09-17. Lower total delivery effort than plain direct implementation is an agreed objective to validate, not a demonstrated advantage.

Use low effort for: narrow, well-specified questions; focused rechecks of a bounded fix; small epic evaluations with clear requirements, limited interactions and strong running evidence. Keep medium as the default for broad whole-epic synthesis, ambiguous intent and multiple interacting changes. Retain high for whole-project final evaluation and critical decisions/serious disagreements. Astra → Fable remains the model tier order. Effort and model escalation are separate decisions; do not mechanically call every model/effort combination.

Efficiency target: lower total effort to an accepted outcome at comparable scope and risk, including the lead, helpers, reviews, repair, escaped defects and owner intervention. Extra process can make straightforward work slower and more expensive. The skill should retain direct development's productive path and add assistance only where its expected benefit exceeds dispatch, context-transfer, waiting and integration cost.

Agreed practical rules: keep one lead; delegate only useful bounded work; reserve strong calls for judgments that affect acceptance; prepare concise briefs with raw evidence access; reuse valid evidence; use focused correction reviews; batch independent checks; avoid idle polling and repeated context reconstruction. Every dispatch should have a concrete question/output and a reason that doing it separately is worthwhile. This should be a short judgment, not a new scoring system. Required quality gates remain binding; improve their scope and execution rather than silently omit them.

Evaluate on owner-selected real work against a clearly described direct-development baseline with comparable quality requirements. Record total usage/cost when available, elapsed time through acceptance, material/escaped defects and owner interventions. Do not manufacture reruns or claim an exact saving from incomparable projects. If overhead dominates without better accepted outcomes, simplify the workflow.

## Accepted consultation follow-up

On 2026-09-17 the owner accepted the lead's qualified Fable/high recommendations: retain the agreed workflow and model tiers; add enforceable route/restriction and sprint safeguards, concrete escalation reasons, explicit review limitations, independent testing of consequential changes, preserved original project intent and a small attended pilot. Baseline evidence may be reused when valid; preserve dirty starting state; keep useful implementation delegation; do not reduce review effort merely because reviews found nothing. Missing external evidence is not a model-escalation trigger. The full consultation remains historical evidence, not blanket approval of every suggestion.

See [IMPLEMENTATION.md](IMPLEMENTATION.md) for the concise v0 specification and verification requirements. Command behavior remains unimplemented and unverified.

## Decisions still open

- Default allowance for strong calls and optional helper concurrency; avoid invented numeric cost budgets before real telemetry.
- Exact deadline enforcement and host continuation behavior; shared policy does not imply identical host scheduling features.

## Documentation checked

- Codex skill discovery and symlink support: https://learn.chatgpt.com/docs/build-skills
- Claude skill discovery and symlink support: https://code.claude.com/docs/en/skills
- Claude loop cadence: https://code.claude.com/docs/en/scheduled-tasks

The documented installation mechanism is supported; dev-auto itself and its live synchronization behavior remain UNVERIFIED until implemented and exercised.
