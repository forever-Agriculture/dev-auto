# dev-auto

Direct development from BMAD plans, with project-alignment checks, regression tests, independent reviews and useful model delegation. One shared skill for Codex and Claude Code; no custom orchestration engine.

Direct Codex/Claude implementation is the foundation. Dev-auto adds a thin layer
of proportionate quality, security, and recovery checks. Real runs inform the
ongoing search for the best balance of quality, total cost, elapsed time, and owner
attention; simplify when evidence shows overhead does not earn its cost.

## Install

Requires Python 3 and the coding clients you intend to use. From this repository:

```bash
python3 scripts/install-dev-auto.py
python3 scripts/install-dev-auto.py --check
```

The installer links both clients to `skills/dev-auto` in this checkout and registers the compaction-recovery hook:

- Codex: `~/.agents/skills/dev-auto`; hook group in `~/.codex/hooks.json`
- Claude Code: `~/.claude/skills/dev-auto`; hook group in `~/.claude/settings.json`

The hook (`hooks/dev-auto-session-start.py`) runs on `SessionStart` with matcher `compact|resume`. When the session's working directory holds an unfinished `.dev-auto/handoff.md`, it injects a reminder to reread the skill and complete handoff first, then the routing reference before dispatch. It includes the whole handoff up to 12,000 characters, preserving renamed fields and free text. Larger handoffs are omitted in full with an explicit incomplete warning. The snapshot is recovery data, not authorization or a substitute for rereading; the hook cannot enforce model compliance. It is silent when no handoff exists or completion is unambiguous, never writes, and fails open. Codex requires trusting a new hook once through `/hooks`. Use `--links-only` to skip hook registration. Run the installer while no client is writing its settings; it replaces the file atomically but does not detect a concurrent edit. The hook only sees the session's working directory, so start the client from the project root you are developing.

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
codex -m gpt-5.6-sol -c model_reasoning_effort=xhigh
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
5. Uses independent review for whole-epic correctness and project alignment; project scope also receives a cross-epic final evaluation.
6. Preserves pending findings, restrictions, routes, evidence and next actions in a short project handoff.

Reviewers run without tools by default. For a named UI acceptance question the lead may dispatch a browser-enabled review that uses the Playwright MCP against lead-supplied local URLs only; see the browser-enabled variants in the routing reference.

The lead can use GLM Flash/max or Luna/max when helpful and choose suitable models for independent parallel work. GLM/max is the debugging helper. Important epic reviews normally use Astra/medium, with Fable/medium as the next tier when needed; bounded cases can use low effort. Project final evaluation and critical decisions use Astra/high then Fable/high. Strong models focus on consequential judgments while economical helpers handle routine work. See the [routing reference](skills/dev-auto/references/models.md) for exact routes.

GLM runs through your configured Claude Code GLM profile, even when Codex is the lead. Credentials are never part of this repository. An unavailable route is reported; no silent model or effort substitution.

## Completion, permissions and limits

Dev-auto works until the selected scope passes its implementation, test and review requirements. There is no automatic time limit or need to renew a work window. A real blocker, explicit user stop, or host interruption leaves a resumable handoff. Tell the agent to stop when you want to stop; this also stops its identified recovery loop when the host supports cancellation. Scheduled wakeups cannot undo your stop. The skill cannot override host rate limits or keep a closed client running.

The skill uses native host tools and permissions. It does not create a sandbox or make concurrent sessions safe by itself. Helpers must have appropriate actual access restrictions, ownership and nonconflicting resources. Honor the owner's recorded authorization, including standing permission for local commits of ready, checked task changes. Preserve unrelated staged and unstaged work. Push, merge, deploy and production access require their own authorization; permission to commit does not grant them.

Independent review and green tests are evidence, not guarantees. Unverified flows and external acceptance gates remain explicit. A full real-project pilot is needed to establish unattended reliability and any cost advantage over direct development.

## Development

- [Verification evidence and limits](docs/verification.md)
- [Current implementation scope](IMPLEMENTATION.md)
- [Design decisions](DESIGN.md)
- [Lessons from earlier workflows](LESSONS.md)
- [Fable's design consultation](docs/reviews/2026-09-17-fable-high.md)

Repository: [forever-Agriculture/dev-auto](https://github.com/forever-Agriculture/dev-auto) (private).
