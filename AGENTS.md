# dev-auto project rules

Claude Code reads `CLAUDE.md`, a symlink to this file.

- Before discussing or changing this workflow, read the project's note in the owner's vault.
- Preserve safety and acceptance; remove demonstrated overhead; compare accepted outcomes by quality, cost and speed. Simplicity is an acceptance requirement.
- Change the workflow only for a serious incident, an owner request, or a verdict from real runs; collect other ideas for the next evaluation (owner 2026-09-28: 48 commits in 11 days left run-based judgments open).
- The owner does not use BMAD's build or loop workflows; dev-auto is his implementation path; plans come in BMN's plan format (BMN `docs/planning.md`, the `plan` skill); a project still on BMAD reads NEEDS_MOVE until it moves (BMN Epic 108).
- Canonical skill: `skills/dev-auto/SKILL.md`, installed into both clients by symlink. Run `python3 -m unittest discover -s tests` after changes.
