---
name: epic-lead-planning
description: Suggest an implementation lead when drafting or materially revising BMAD epics in any project, in the epic file and on its sprint-status row. Use during epic planning, not during implementation.
---

# Epic lead suggestions

A quick convenience hint for the owner, who picks the dev-auto lead. It selects nothing and changes no acceptance criteria.

For each new or materially revised epic, after checking the current [lead routes](../dev-auto/references/models.md), put one line right under the epic's heading (`## Epic N:` or `# Epic N — Title`), replacing any earlier one:

`**Suggested lead:** Sol — short reason tied to this epic`

If the project has a `sprint-status.yaml`, put the same hint at the start of that epic's `epic-N:` row comment and touch nothing else: `epic-N: backlog # Suggested lead: Sol — reason · <existing comment>`.

The configured providers are: Codex (Sol), Claude (Opus) and one other provider whose model changes over time; name whichever other lead the lead routes list now, never one from memory. Pick from scope and risk: the other lead for bounded routine work with clear patterns and tests, but not where the project keeps customer, production or personal data away from that provider; Sol or Opus for coupled systems, migration, concurrency, security, privacy or evidence-heavy acceptance. Flags mark provider origin, not capability. Keep epic headings intact and leave historical epics alone.
