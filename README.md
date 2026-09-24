# dev-auto

Direct development from BMAD plans, with project-alignment checks, regression tests, independent reviews and useful model delegation. One shared skill for Codex and Claude Code; no custom orchestration engine.

Direct Codex/Claude implementation is the foundation. Dev-auto adds a thin layer
of proportionate quality, security, and recovery checks. Real runs inform the
ongoing search for the best balance of quality, total cost, elapsed time, and owner
attention; simplify when evidence shows overhead does not earn its cost.

Dev-auto owns the implementation workflow: consume BMAD plans directly, without
nesting another build workflow or introducing a second approval for authorized
work. Repeated failed outcomes trigger diagnosis of the shared boundary before
another repair, even when successive errors differ.

## Install

Requires Python 3 and the coding clients you intend to use. From this repository:

```bash
python3 scripts/install-dev-auto.py
python3 scripts/install-dev-auto.py --check
```

The installer links both clients to `skills/dev-auto` in this checkout and registers the compaction-recovery hook:

- Codex: `~/.agents/skills/dev-auto`; hook group in `~/.codex/hooks.json`
- Claude Code: `~/.claude/skills/dev-auto`; hook group in `~/.claude/settings.json`

The hook (`hooks/dev-auto-session-start.py`) runs on `SessionStart` with matcher `compact|resume`. It finds the nearest `.dev-auto/handoff.md` in the working directory or its ancestors, stopping at the first repository or home boundary. For an unfinished run it injects a reminder to reread the skill and complete handoff first, then the routing reference before dispatch. It includes the whole handoff up to 9,000 characters, preserving renamed fields and free text. Both hosts cap hook output: Claude Code injects only a 2 KB preview above 10,000 characters and Codex keeps about 2,500 tokens, so the reminder stays short enough (about 820 characters with paths) that a 9,000-character handoff fits under both, and the hook keeps its whole output under 9,950 characters, warning instead of letting a host cut a snapshot silently. An unusually token-dense handoff may still lose a visible middle piece in Codex, which the required full read covers. A larger handoff is omitted in full with an explicit incomplete warning that requires trimming until `check.py check` passes. The handoff can restore restrictions and progress, but cannot grant or expand permission; positive authorization must be reconciled with current owner instructions or established owner policy. The hook cannot enforce model compliance. It is silent when no handoff exists or when the handoff ends with a single `Status: COMPLETE` line and records no stop (a short note after `COMPLETE` or `none`, separated by punctuation, is fine), even above the 9,000-character snapshot limit (up to a 1 MB read cap), so a finished run never wakes an unrelated session in the same repository; it never writes and fails open. Codex requires trusting a new hook once through `/hooks`. Use `--links-only` to skip hook registration. Run the installer while no client is writing its settings; it replaces the file atomically but does not detect a concurrent edit. Start the client within the project you are developing; a nested repository has its own recovery boundary.

Keep the checkout in place. Both links use the same files, so edits stay synchronized. Existing conflicting files/links are preserved rather than overwritten. Start a fresh client session after installation or policy changes; already-loaded instructions may be stale.

## Claude Code

Start Claude Code in the project to develop, with the chosen lead model:

```bash
cd /path/to/your-project
claude --model opus --effort xhigh
```

Then:

```text
/dev-auto epics 1-3
/dev-auto project
/dev-auto status
/dev-auto resume
```

Use `epics` for selected epic numbers/ranges; `project` covers the planned project. Start one of these scopes, not both concurrently. Status reports current progress; resume continues the recorded scope.

Optional continuation in the same Claude session:

```text
/loop 20m /dev-auto resume
```

Start the initial dev-auto run first. The loop is a recovery wakeup if the agent stalls or a turn ends while work remains. Its interval does not limit the run: dev-auto keeps working until the selected scope is accepted. Scheduled prompts wait until the current turn is idle, so this cannot interrupt a hung tool or recover a closed client; the session must stay running. Cancel its associated job after COMPLETE or an explicit stop; on BLOCKED, resolve the named blocker and cancel the loop if repeated wakeups cannot help. Start with a supervised epic; scheduled execution has not yet been exercised by this project. `resume` reconciles actual progress and avoids restarting completed or still-active work. Do not create multiple development sessions for the same working tree.

Claude documents skill composition with `/loop` in [scheduled tasks](https://code.claude.com/docs/en/scheduled-tasks). This skill provides no independent scheduler or hard timeout.

## Codex

Start Codex in the project with the chosen lead model:

```bash
cd /path/to/your-project
codex -m gpt-6-sol -c model_reasoning_effort=xhigh
```

Then invoke the shared skill:

```text
$dev-auto epics 1-3
$dev-auto project
$dev-auto status
$dev-auto resume
```

Codex's native skill picker may also expose it. The skill does not switch the current model itself. Resume manually or through the host's supported continuation features; Claude's `/loop` is not installed as a Codex command by this project.

## What it does

1. Reads project instructions and BMAD requirements, architecture, epics/stories and acceptance criteria.
2. Checks the selected epic against the project before implementing it directly.
3. Maintains the existing `sprint-status.yaml`, preserving unrelated entries and comments.
4. Uses focused story tests and appropriate project regression/integration checks; checks existing behavior, not just new tests.
5. Uses one independent whole-epic review, followed only by a focused recheck or evidence-triggered delta when needed, and never edits a candidate while a reviewer reads it. When a recheck finds a defect introduced by the previous repair, or a second recheck still fails, the lead stops repairing, rereads the acceptance criteria, substantiates each open finding and asks the next strong route once (or reports BLOCKED with options, including removing work the story does not ask for); after one more repair and recheck, remaining defects block the boundary. A new reviewer, repair wave or resumed run does not reset that allowance. Project scope also receives a cross-epic final evaluation. Reviewers get the baseline-to-reviewed diff and the [review brief](skills/dev-auto/references/review-brief.md); every material finding ends with a disposition (closed with evidence, rejected with refutation, or unresolved), and acceptance confirms each in-scope story's board completion.
6. Preserves pending findings, restrictions, routes, evidence and next actions in a short project handoff.

The handoff keeps every selected epic and its dependency visible. At material
updates, replace stale state and link detailed receipts; append owner quotes,
superseded terms and history to the append-only `.dev-auto/log.md` so the handoff stays within the hook's 9,000-character snapshot limit. Never drop
unresolved restrictions or findings to fit; move resolved material instead. Owner-effort records separate
corrections, necessary approvals and avoidable repeated requests.

Mechanical handoff rules are checked by a read-only helper instead of prose. `skills/dev-auto/scripts/check.py check` fails any handoff over the 9,000-character snapshot limit, with a Status longer than 200 characters, or without exactly one Status, Explicit user stop and Next safe action field; at COMPLETE it also fails model/usage placeholder text and any tracked `.dev-auto` file other than the committed handoff and log. `-h` prints its help. `check.py usage PATH` prints model, effort and usage from a Codex rollout, a Claude Code session or subagent transcript, or a Claude JSON receipt. The lead runs `check` after each handoff save (a FAIL before COMPLETE means the next save fixes it) and `usage` at acceptance; the helper never writes, launches or decides, and it is not a hook.

When the session runs inside BMN (the owner's terminal cockpit), the skill mirrors each status line with `bmn progress`, raises `bmn ask` when BLOCKED needs an owner decision and publishes the handoff at acceptance; outside BMN it skips this silently, each call is bounded to two seconds, and after one failure it stops mirroring for the run. It never marks progress `verified` and never uses `bmn send`.

Reviewers run without a browser by default. For a named UI acceptance question the lead may dispatch a browser-enabled review that uses the Playwright MCP against lead-supplied local URLs only; see the [browser review reference](skills/dev-auto/references/browser-review.md).

The lead dispatches helpers only for required independent review or substantial bounded work that saves it real effort or elapsed time, and does small lookups itself; each dispatch costs the lead several turns over its whole context. Evidence gathering, test runs and checklist rechecks start on the helper provider's fast model; debugging and open-ended code review on its strong model; then Codex Luna/max or Astra/low. Small implementations start there too, in an edit mode confined to the helper's directory. An optional helper pre-review may precede the strong full review of a larger epic, which stays Astra/medium then Fable/medium; project evaluation is Astra/high then Fable/high. A sufficient result ends the dispatch; escalate only after a specific failure, an unresolved question or a task the first route cannot do. See the [routing reference](skills/dev-auto/references/models.md) for exact routes.

Helper routes run through `skills/dev-auto/scripts/helper.sh`, even when Codex is the lead; its first lines name the provider's Claude Code env file and fast/strong models (currently Z.ai GLM-5.3-Flash and GLM-5.3), so switching provider is a three-line change. Credentials are never part of this repository. An unavailable route is reported; no silent model or effort substitution.

## Completion, permissions and limits

Dev-auto works until the selected scope passes its implementation, test and review requirements. There is no automatic time limit or need to renew a work window. A real blocker, explicit user stop, or host interruption leaves a resumable handoff. Tell the agent to stop when you want to stop; this also stops its identified recovery loop when the host supports cancellation. Scheduled wakeups cannot undo your stop. The skill cannot override host rate limits or keep a closed client running.

The skill uses native host tools and permissions. It does not create a sandbox or make concurrent sessions safe by itself. Helpers must have appropriate actual access restrictions, ownership and nonconflicting resources. Read-only review prevents writes, not arbitrary reads; use the project directly only when its readable scope is appropriate, otherwise prepare a smaller workspace. Raw provider transcripts, screenshots and runtime dumps stay untracked, in external scratch space or an ignored `.dev-auto/evidence/` directory; the handoff cites them by path and hash. Codex rollout files, Claude Code transcripts and Claude JSON receipts supply the observed model, effort and usage recorded in the handoff. Honor the owner's standing permission for local commits of ready, checked task changes while preserving unrelated work. Push, merge, deploy and production access require separate authorization.

Independent review and green tests are evidence, not guarantees. Unverified flows and external acceptance gates remain explicit. A full real-project pilot is needed to establish unattended reliability and any cost advantage over direct development.

## Development

- [Verification evidence and limits](docs/verification.md)
- [Current implementation scope](IMPLEMENTATION.md)
- [Design decisions](DESIGN.md)
- [Lessons from earlier workflows](LESSONS.md)
- [Fable's design consultation](docs/reviews/2026-09-17-fable-high.md)

Repository: [forever-Agriculture/dev-auto](https://github.com/forever-Agriculture/dev-auto) (private).
