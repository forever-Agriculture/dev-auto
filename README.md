# dev-auto

Direct development from BMAD plans, with project-alignment checks, regression tests, independent reviews and useful model delegation. One shared skill for Codex and Claude Code; no custom orchestration engine.

## Install

Requires Python 3 and the coding clients you intend to use. From this repository:

```bash
python3 scripts/install-dev-auto.py
python3 scripts/install-dev-auto.py --check
```

The installer links both clients to `skills/dev-auto` in this checkout:

- Codex: `~/.agents/skills/dev-auto`
- Claude Code: `~/.claude/skills/dev-auto`

Keep the checkout in place. Both links use the same files, so edits stay synchronized. Existing conflicting files/links are preserved rather than overwritten. Start a fresh client session after installation or policy changes; already-loaded instructions may be stale.

## Claude Code

Start Claude Code in the project to develop, with the chosen lead model:

```bash
cd /path/to/your-project
claude --model opus --effort xhigh
```

Then:

```text
/dev-auto epics 1-3 --for 3h
/dev-auto project --for 3h
/dev-auto status
/dev-auto resume
```

Use `epics` for selected epic numbers/ranges; `project` covers the planned project. Start one of these scopes, not both concurrently. Status reports current progress; resume continues the recorded scope.

Optional continuation in the same Claude session:

```text
/loop 20m /dev-auto resume
```

Start the initial dev-auto run first. The loop interval is a wakeup cadence, not the work duration. Scheduled prompts wait until the current turn is idle, and the session must stay running. A fixed loop keeps firing until canceled; cancel its associated job when the run reports COMPLETE, PAUSED or BLOCKED. Start with a supervised epic; scheduled execution has not yet been exercised by this project. `resume` must preserve the original deadline and avoid restarting completed or still-active work. Do not create multiple development sessions for the same working tree.

Claude documents skill composition with `/loop` in [scheduled tasks](https://code.claude.com/docs/en/scheduled-tasks). This skill provides no independent scheduler or hard timeout.

## Codex

Start Codex in the project with the chosen lead model:

```bash
cd /path/to/your-project
codex -m gpt-5.6-sol -c model_reasoning_effort=xhigh
```

Then invoke the shared skill:

```text
$dev-auto epics 1-3 --for 3h
$dev-auto project --for 3h
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

The lead can use GLM Flash/max or Luna/max when helpful and choose suitable models for independent parallel work. GLM/max is the debugging helper. Important epic reviews normally use Astra/medium, with Fable/medium as the next tier when needed; bounded cases can use low effort. Project final evaluation and critical decisions use Astra/high then Fable/high. Strong models focus on consequential judgments while economical helpers handle routine work. See the [routing reference](skills/dev-auto/references/models.md) for exact routes.

GLM runs through your configured Claude Code GLM profile, even when Codex is the lead. Credentials are never part of this repository. An unavailable route is reported; no silent model or effort substitution.

## Duration, permissions and limits

`--for 3h` is a cooperative upper bound. The agent should finish early when accepted, stop launching work near the deadline, and leave a resumable handoff if incomplete. It is not an OS-enforced timeout; resume does not grant a new time budget. Explicitly extend the deadline when you want more work.

The skill uses native host tools and permissions. It does not create a sandbox or make concurrent sessions safe by itself. Helpers must have appropriate actual access restrictions, ownership and nonconflicting resources. Commit, push, merge, deploy and production access require their own authorization; a development request alone does not grant them.

Independent review and green tests are evidence, not guarantees. Unverified flows and external acceptance gates remain explicit. A full real-project pilot is needed to establish unattended reliability and any cost advantage over direct development.

## Development

- [Verification evidence and limits](docs/verification.md)
- [Current implementation scope](IMPLEMENTATION.md)
- [Design decisions](DESIGN.md)
- [Lessons from earlier workflows](LESSONS.md)
- [Fable's design consultation](docs/reviews/2026-09-17-fable-high.md)

Repository: [forever-Agriculture/dev-auto](https://github.com/forever-Agriculture/dev-auto) (private).
