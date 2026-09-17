# dev-auto v0 implementation specification

Status: initial version published and installed; current owner correction removes automatic work deadlines. Earlier review reports describe the version they examined. The owner's latest clarification supersedes the earlier controller-shaped specification: this is almost direct development, with shared instructions for review, tests, sprint tracking and useful delegation. Historical mechanisms are not implementation requirements. [DESIGN.md](DESIGN.md) records policy history; [LESSONS.md](LESSONS.md) informs judgment, not a checklist of machinery to rebuild.

## What to build

- One canonical `skills/dev-auto/SKILL.md` usable by Codex and Claude Code.
- A small supporting model-routing reference, loaded when dispatching, with real configured routes and effort levels.
- A short handoff template for `.dev-auto/handoff.md` in the target project. The existing `sprint-status.yaml` remains its progress board.
- A small install/check helper only to link both clients to the canonical skill without overwriting existing content. Use native host execution, permissions, background jobs and delegation.

No controller, scheduler, worker launcher framework, event journal, custom retry state machine, automatic review fan-out or redundant progress database. Add any further code only for a concrete demonstrated gap. The skill does not create a security boundary: the host's actual tools/permissions must provide the access required by a delegated task. If they cannot, constrain or defer that dispatch rather than invent bypasses.

## Required behavior

1. Accept selected epic numbers/ranges, project, resume and status; work until the selected scope passes acceptance, without an automatic time limit. Use the native invocation on each host. Scheduling stays outside the skill.
2. Read BMAD planning artifacts and project instructions. Implement directly, without BMAD implementation workflows. Before each epic, check its fit with project goals, architecture, dependencies, current code and obligations to later epics. Resolve material conflicts within authority; preserve original intent.
3. Lead defaults: Sol/xhigh in Codex or Opus/xhigh in Claude Code. The skill cannot magically switch the current model; verify the actual host selection and report a mismatch rather than claiming the requested model is running.
4. Lead may dispatch any appropriate model for sizeable independent work and GLM Flash/max or Luna/max whenever useful. Debugging assistance: GLM/max. Routine alternative: Sonnet/low or medium. Retain useful safe parallelism with explicit file/resource ownership.
5. Whole-epic important review and overall project alignment: Astra/medium then Fable/medium as an escalation/fallback tier, not a mandatory pair. Low is appropriate for bounded questions or small well-evidenced epics. Project final evaluation and critical decisions: Astra/high then Fable/high. GLM supports routine work. Record actual routes; GLM is available through Claude Code.
6. Strong reviewers assess consequential correctness, omissions, misunderstood intent and drift, using original criteria, source and raw evidence. Cheap helpers can collect evidence and run routine checks. Review outputs name material findings, examined scope, unreviewed/unverified areas and limitations.
7. Update the project's existing sprint board during work using its valid states; preserve comments and unrelated changes. The lead owns these edits. Never manufacture acceptance from a done label.
8. Test story outcomes and affected existing behavior. Independently test consequential boundaries. During repair use focused checks; before epic acceptance run appropriate integration/regression checks, including earlier-epic contracts. Reproduce claimed pre-existing failures without losing user changes. Material regressions require evidence that tests detect the old failure and pass with the fix.
9. After each epic, independently check actual implementation against both epic intent and the project as a whole. Material gaps block completion. Project scope includes a final cross-epic evaluation. No guarantee of correctness from model approval alone.
10. Keep a short durable handoff: scope, stopping condition, restrictions, model routes, active helpers, original/approved intent changes, findings, evidence, cross-epic obligations and next action. Resume restores these and reconciles actual work; never blindly starts duplicate work. Use native lifecycle tools and don't signal unrelated processes.
11. Bound correction work: consolidate findings, one full review plus focused recheck by default; repeated failed fixes call for new evidence. Preserve work and continue independent authorized work on a real blocker. Preserve authorization boundaries on resume or model escalation. A malformed worker summary is not a reason to repeat completed implementation.
12. Honor host permissions and owner restrictions. No implicit commit/push/merge/deploy or production access. Do not claim effective worker confinement from a prompt or file-ownership list.

## Implementation and verification assignments

Sol/xhigh implements the skill, references and justified install helper. GLM Flash/max through Claude Code independently reviews and exercises it. The coordinating assistant verifies results and integration, then Fable/medium assesses final artifacts, complexity and evidence. The assistant gives its own final verdict after material findings are addressed. These are the build assignments, not the future runtime tier policy.

## Prove the small thing actually works

- Validate the skill's format and references.
- Exercise safe installation/check: both hosts point to identical canonical files; existing files and conflicting links are preserved; reinstall is idempotent.
- Exercise real skill discovery/invocation in Codex and Claude Code using a disposable tiny project. Show at least status/resume and an affected development/test/sprint flow; no production or user project experiments.
- Verify concrete Claude-hosted GLM dispatch at requested effort and inspect the actual model receipt. Evaluate behavior with GLM Flash, not just static word matching.
- Exercise preservation of a material pending finding and selected scope on resume. Verify reported acceptance limitations and project regression checks against actual artifacts.
- Host permission/lifecycle behavior is reused, not reimplemented. Test any claimed new mechanism at its real boundary; explicitly label unexercised compaction, concurrent multi-session behavior and broader unattended reliability as unverified.
- Whole-project production readiness, lower real-world cost and unattended reliability need an owner-selected real pilot. Do not manufacture those claims from a fixture or review verdict.

Keep brief instructions, meaningful evidence and low owner burden. Review needless complexity as a defect. No model call should exist merely to satisfy a ceremonial stage.
