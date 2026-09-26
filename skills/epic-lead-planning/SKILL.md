---
name: epic-lead-planning
description: Suggest an implementation lead when drafting or materially revising BMAD epics in any project. Use during epic planning, not during implementation.
---

# Epic lead suggestions

Read project restrictions and the current [lead routes](../dev-auto/references/models.md) before naming a model. For each new or materially revised epic, place one advisory line immediately below its `## Epic N:` heading:

`**Suggested lead:** Sol — short reason tied to this epic`

Choose from the work's scope and risk, not the flag. GLM is a candidate for bounded routine work with clear patterns and tests. Sol or Opus is a stronger starting suggestion for coupled systems, migration, concurrency, security, privacy, or evidence-heavy acceptance. Suggest another model only after its route and a relevant implementation pilot are verified. Follow narrower project/provider restrictions.

Flags identify provider origin, not capability. The owner chooses the actual lead when implementation starts; the suggestion neither selects a model nor changes acceptance criteria. Keep existing epic headings intact for BMAD tracking, and leave historical epics alone unless the user asks to revise them.
