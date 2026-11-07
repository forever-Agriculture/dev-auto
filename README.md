<!-- MODULE: README.md - what dev-auto is, how to install and run it, and what a run does -->
# dev-auto

A skill for Codex and Claude Code that implements planned epics directly and keeps going until they pass acceptance, with bounded reviews, manual QA, spend limits and recovery after compaction.

One lead agent writes the code. dev-auto adds only the checks that earn their cost, and judges itself by accepted outcomes: quality, total cost, elapsed time and owner attention together. It has no controller, scheduler or second approval stage. It is a skill, a few small scripts and one recovery hook, and it works from plans in [BMN](https://github.com/forever-Agriculture/BMN)'s format; a project still on BMAD is named for its move and runs nothing.

It is one person's working setup, not a packaged product: the text addresses "the owner", and it assumes his BMN team. The repository has no license yet, so you may read it but no reuse rights are granted.

## Requirements

- Python 3.10 or newer and Codex, Claude Code or both.
- BMN for finding the plan, helpers, QA, away grants and report publishing. Without `bmn`, an approved team or BMN running, a lead asks no helper and reports BLOCKED; local away mode still works.
- Linux for process inventories (`/proc`, pidfd) and detached paid jobs (`systemd-run --user`, or `--direct`).

## Install

```bash
python3 scripts/install-dev-auto.py
python3 scripts/install-dev-auto.py --check
```

The installer links each client to `skills/dev-auto` in this checkout and registers the recovery hook:

| Client | Skill link | Hook group |
| --- | --- | --- |
| Codex | `~/.agents/skills/dev-auto` | `~/.codex/hooks.json` |
| Claude Code | `~/.claude/skills/dev-auto` | `~/.claude/settings.json` |
| Claude Code on GLM, when `~/.claude-glm` exists | `~/.claude-glm/skills/dev-auto` | `~/.claude-glm/settings.json` |

GLM routes have been deactivated since 2026-09-30; the installer still maintains the profile if it exists.

Keep the checkout in place, because every link uses the same files. Existing conflicting files and links are preserved, and settings are replaced atomically, so run the installer while no client is writing them. `--links-only` skips the hook and `--target-root` installs below another directory. Codex asks you to trust a new hook once through `/hooks`. Start a fresh client session after installing or changing the skill.

Planning is BMN's `plan` skill, which BMN installs itself; `skills/epic-lead-planning` is only a pointer to it.

## Run

Start a client in the project to develop, with a lead the BMN team allows (`bmn roster role lead --json`):

```bash
claude --model <lead-model> --effort <effort>
codex -m <lead-model> -c model_reasoning_effort=<effort>
```

Then invoke the skill, with `/dev-auto` in Claude Code or `$dev-auto` in Codex:

```text
/dev-auto epics 1-3     selected epics
/dev-auto project       unfinished planned epics, then a final cross-epic evaluation
/dev-auto status        read-only report
/dev-auto resume        continue the recorded scope
```

Add `away`, or say you are leaving, when you will be unreachable. The skill does not switch the current model. Don't run two development sessions on one working tree.

Work continues until the selected scope is accepted, with no time limit. A real blocker, an explicit stop or a host interruption leaves a resumable handoff. In Claude Code, `/loop 20m /dev-auto resume` can wake a stalled session, but it cannot interrupt a hung tool or revive a closed client, and it never undoes a stop. Scheduled execution hasn't been exercised by this project.

## What a run does

1. **Finds the plan** with `bmn plan status --json`. Two undeclared plans, an unknown schema or a malformed BMN plan stop the run with that error named. `project` scope follows the plan's `queue`, skipping `paused` and `dropped` epics.
2. **Reads its authority.** `spend_ledger.py open` reads the owner's go on the epic, and the run keeps its terms, money cap and rounds. Prepared needs are checked at the start and again when the owner leaves.
3. **Checks fit**, then implements directly on its own branch, worktree and dependencies.
4. **Keeps the board current** at every state change: BMN rows with `bmn plan set`, always on the plan in the default checkout. `bmn plan publish` runs at each story's end on a tracked plan. Delivery counts only once the work is confirmed on the default branch.
5. **Tests behavior**: focused tests during repairs, required broad gates once at acceptance, and a regression test that fails on the original defect.
6. **Reviews a frozen candidate.** A quick pre-review and manual QA run alongside the lead's final checks, followed by one consolidated repair, then one full independent review with one focused recheck. Nothing edits a candidate while a reviewer reads it, and every material finding ends with a disposition. A project's own PR review runs as its rules say.
7. **Accepts** only after exercising the affected path the owner uses. A check only he can do keeps acceptance BLOCKED until he passes or defers it.
8. **Reports**: as each epic is accepted, it writes, checks and privately publishes an HTML page with BMN's `report-artifact` skill. A Claude Code Artifact publish opens the page itself; otherwise the lead launches the default browser once. A receipt with the page's SHA256 stops resume from repeating this, and a publishing failure doesn't block acceptance.
9. **Cleans up**: `check.py leftovers` inventories what the run started before it ends, and only finished, clean, merged worktrees are offered for removal.

Each run ends with `DEV-AUTO: ACTIVE|PAUSED|BLOCKED|COMPLETE`.

## Owner decisions

The lead asks only about what is reserved to the owner: spend beyond what he approved, changes to selected work or acceptance criteria, actions his global rules reserve, credentials or private data, owner-only checks and model choices. Method questions go to the consultant. Everything else is decided on the recommended option and listed under `Decided for you` in the handoff and report. A question normally goes out once, in one batch, only when no work can proceed; otherwise the affected story parks and the rest continues. Planning must cover foreseeable limits, permissions, money, commands, access, delivery and cleanup before the go so implementation is autonomous. For a genuinely unforeseen YAML gap, one amendment card may go out while the owner is present even if independent work remains: exact before/after, reason, cost/exposure and work unlocked. Only his approval permits the named change through `bmn plan allow --source`; usage stays counted. Until then only affected work parks. Existing delegated ceilings need no card; Away and external refusals still hold.

**Stuck work is bounded.** After two failed fixes, or three failed runs of one gate, the lead compares the failures and asks the consultant. Each further attempt needs a different method the consultant agrees, recorded first. Rounds come from the ledger with no card: at least 4 per boundary, as an allowance rather than a target, and the last needs a step-back by a different agent. After that, work the go lists as deferrable is deferred; otherwise the story parks BLOCKED and the rest continues.

**Away mode** lasts until the owner says he is back; inside BMN the lead follows BMN's away state (`bmn away`, `bmn back`, `check.py away`). Before he leaves, each run asks once on one card (`bmn grant ask`) for the named actions its night needs: a merge, a push, an exact command or an exact message. Only his answer, in BMN or on Telegram, grants them, and `check.py grant` reads the grant fresh before each use. See [away-grant.md](skills/dev-auto/references/away-grant.md).

**Spend and messages** go through `spend_ledger.py`. Every paid job launches through it against the go's cap, and a message the go's Run needs name is limited to 2 per person and purpose. No resume, new lead or worktree resets what was used.

## Helpers

The owner's BMN team says who does what, so the skill assigns no model to any role: the lead reads the chain with `bmn roster role <role>` and asks with `bmn team ask`, which runs the teammate read-only and keeps a record. An unavailable route is reported, never silently substituted. See [models.md](skills/dev-auto/references/models.md).

| Work | Role |
| --- | --- |
| Routine chores | `helper` |
| Bounded review or debugging look | `focused-reviewer` |
| Manual QA of the running interface | `qa` |
| Epic pre-review and review | `pre-reviewer`, `epic-reviewer` |
| Project pre-review and final review | `project-pre-reviewer`, `final-reviewer` |
| Method questions and step-backs | `consultant` |

Manual QA follows [qa-brief.md](skills/dev-auto/references/qa-brief.md). A missing report, mandatory verification gap or unachieved goal blocks acceptance unless approved Run needs defer it. Account-dependent criteria need BMN's verified owner grant and otherwise stay BLOCKED; a desktop candidate that can't be driven keeps its review with the gap stated.

## Run state and recovery

Run state lives in `.dev-auto/` in each checkout or worktree and is never committed; one line in the repository's shared `info/exclude` covers every worktree. It holds `handoff.md` (current terms, kept within 9,000 characters), the append-only `log.md`, and `evidence/` for receipts and raw records. The handoff restores restrictions and progress, but it can't grant permission.

`hooks/dev-auto-session-start.py` runs on `SessionStart` with matcher `compact|resume`. It finds the nearest handoff and, for an unfinished run, injects a reminder to reread the skill and the whole handoff, plus a short list of unfinished runs in the repository's other worktrees (up to 6). Its output stays under 9,950 characters to fit both hosts' caps, and a larger handoff is replaced by an explicit warning. An unusually token-dense handoff may still lose a visible middle piece in Codex, which the required full read covers. It stays silent when no run is unfinished, never writes and fails open. It guides the model but can't enforce anything.

## Scripts

All are under `skills/dev-auto/scripts/`. Only `spend_ledger.py` writes run state, in its own ledger under `$XDG_STATE_HOME/dev-auto/budgets/`; the rest only read.

| Script | Purpose |
| --- | --- |
| `check.py` | `check` lints the handoff, `usage` reads model and usage from host records, `away` and `grant` read BMN's state, `leftovers` and `worktrees` list what a run left |
| `run_needs.py` | Names the owner's go on an epic and the Run needs and Decisions it approved, from the plan's history |
| `spend_ledger.py` | Money caps, paid launches, repair rounds and named messages, shared by every resume, lead and worktree |
| `qa_gate.py` | Checks a QA report from a BMN ask's export |
| `interruptions.py` | Counts what asked the owner during named runs, plus rounds, parked hours and usage |
| `review_misses.py` | Per ticket, whether the agent review ran and what people or production flagged |
| `handoff_state.py`, `run_resources.py` | Libraries behind the hook and `check.py` |

## Limits

- The skill uses host tools and permissions. It creates no sandbox and doesn't make concurrent sessions safe.
- Read-only review limits writes, not reads, and a native helper's read-only mode with approvals enabled may still permit writes.
- Credentials are never part of this repository, and the owner's rules bound what may reach a provider.
- Pushes, merges and pull requests go only as far as `bmn policy --repo OWNER/NAME` authorizes.
- The skill can't override host rate limits or keep a closed client running.
- Reviews and green tests are evidence, not guarantees. Unverified flows, unattended reliability and external gates stay stated, and efficiency against plain direct development is still unmeasured.

## Development

```bash
python3 -m unittest discover -s tests
```

- [SKILL.md](skills/dev-auto/SKILL.md): the workflow itself, which wins over any summary here
- [DESIGN.md](DESIGN.md): why it is built this way
- [LESSONS.md](LESSONS.md): lessons from the workflow it replaced
