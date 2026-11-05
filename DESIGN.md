<!-- MODULE: DESIGN.md - why dev-auto is built the way it is today -->
# dev-auto design

`skills/dev-auto/SKILL.md` is the workflow; this file says why it has that shape. Earlier proposals and the v0 specification are in git history.

## Purpose

Deliver accepted project outcomes with a direct coding lead. Optimize accepted quality, total cost, elapsed time and owner attention together, never one at the others' expense. The plan, in BMN's format or BMAD's, is the source of planning intent; BMAD's implementation workflow isn't invoked.

## Principles

1. **A thin layer over direct development.** The lead implements. dev-auto adds proportionate tests, independent review, safety and recovery. It isn't a code factory.
2. **Every safeguard earns its cost** by a concrete failure it prevents. A mechanism that shows no benefit in real runs is removed. More checks, agents or tests aren't more quality.
3. **The quality floor holds:** original requirements, privacy and authorization, no lost work, and completion verified by exercised behavior on the path the owner uses. Cost or speed never excuses a breach.
4. **Effort is bounded.** Attempts and review repairs are allowances per boundary. A stuck boundary goes to a consultant and then parks BLOCKED. Work ends at the owner's project boundary: an outcome that depends on another team's system ends BLOCKED on that gate unless he selects the integration.
5. **Owner attention is a cost.** Real decisions are asked once with a recommendation, stops are honored, and he never repeats an instruction.
6. **Evidence comes from real work.** Accepted outcomes are read from host records when runs are evaluated, unknown measurements stay unknown, and there are no artificial runs.
7. **Simplicity is an acceptance requirement.** The workflow changes only for a serious incident, an owner request or a verdict from real runs.
8. **Local by default.** Run state stays with the checkout and is never committed. Product repositories get product changes, at most an ignore line and, where the project tracks its plan, planning commits.
9. **One team, one behavior.** Codex and Claude Code read the same files; providers and models change, the principles don't.

## Decisions

**No controller.** The host's tools and permissions are the boundary. There is no scheduler, worker framework, event journal or progress database. The code a run uses answers a demonstrated gap: read-only lints and inventories, the recovery hook and one ledger.

**The ledger is the one script a run uses that keeps state.** Lead-kept tallies were wrong or missing, and a resume or new lead could reset them. Money caps, repair rounds and named messages therefore live in a locked file outside every worktree, so no resume, lead or worktree can refill what was used. A go is read from the plan's history, not from a handoff, so a lead's notes can't grant anything.

**The team, not the skill, names models.** Routes change often and are the owner's choice, so `references/models.md` holds roles and `bmn team ask` checks each ask against his approved team, keeping its record. A route that fails is reported and the next candidate is named, never silently substituted.

**One review shape.** A quick pre-review and manual QA run beside the lead's final checks, followed by one consolidated repair, then one full independent review and one focused recheck. Reviewers are a chain to escalate along, not a pair. The bound counts from the full review, and a new reviewer, repair wave or resume doesn't reset it. It exists because an unbounded loop once took one epic through 15 rechecks over about 12 hours. Helper summaries are navigation, not proof: the reviewer keeps access to source and raw evidence.

**A failure gets a different method, not another try.** After two failed fixes or three failed gate runs, the lead compares failures and asks the consultant, and each further attempt needs a different agreed method recorded first. This also counts failures across different symptoms at one boundary, since successive errors can share one cause. A failure in the lead's own harness counts once as a gate run, not a failed method.

**Rounds and parking replace waiting.** A run has at least 4 rounds per boundary, taken without a card, and the last needs a step-back from a different agent. After that, work is deferred if the go allows it or the story parks, and everything else continues. Nights were being lost to a single stuck story or an unanswered question.

**Questions are rare and batched.** Everything not reserved to the owner is decided on the recommended option and listed where he can reverse it. A broad "continue" answers no reserved point.

**Away is a state, not a guess.** His words, or the away state in BMN, start and end it; activity never does. Only his answer makes a grant, read fresh before each use.

**Acceptance is separate from delivery.** Implemented, verified, reviewed, externally blocked and delivered are reported apart. A board label is a claim to verify, and a row is delivered only once the work is confirmed on the default branch. A check only the owner can do keeps acceptance BLOCKED until he passes or defers it.

**Each run has its own worktree.** Each run gets its own branch, worktree and dependencies, created from the default checkout. Board rows are the exception: the owner reads them in the default checkout, so they are written there.

**Recovery is a hook and a bounded handoff.** Compaction is the common failure, and hosts cut long hook output, which sets the 9,000-character handoff and the 9,950-character output ceiling. The hook is guidance, not enforcement. The handoff restores restrictions and progress but can't grant permission, so authority always comes from owner instructions and policy.

**Every accepted epic ends in a report.** The owner reads a checked HTML page, not a terminal scrollback. Publishing failure is reported with the local path and doesn't block acceptance.

## Host documentation checked

- Codex skill discovery and symlink support: https://learn.chatgpt.com/docs/build-skills
- Claude skill discovery and symlink support: https://code.claude.com/docs/en/skills
- Claude `/loop` cadence: https://code.claude.com/docs/en/scheduled-tasks

## Open questions

- Whether dev-auto is more efficient than plain direct development is unmeasured; a fair comparison is a check, not a gate.
- Unattended reliability remains unproven and stays stated in reports.
