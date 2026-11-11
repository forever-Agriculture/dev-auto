# MODULE: consult-brief.md - Epic 118: one collected consult with epic context and an actionable answer
# Consult brief

Use this form for every ordinary or senior consult. Take the applicable ledger use first;
a refusal means no ask. Include every question open in the epic now in one collected
request, never one ask per question: at most five numbered questions, ranked by consequence,
grouping related issues when necessary. Do not wait for more questions before a consult
needed now. One question alone is right when the epic has no other open one.

Attach the epic's file with `--file "$EPIC_FILE"`. Give source and synthetic evidence only,
within existing provider/data permission. The consultant may explore the project, use its
helpers and search the web where its configured tools and existing permissions allow it;
this brief grants no extra access, spending or authority.

```text
Epic: <N; Outcome in the plan's words; epic file:line attached with --file>
Stories and criteria: <affected stories; original acceptance text and coordinates>
Limits left: <consults/senior uses, rounds, review/recheck counts, money, permissions and stops>
Solo decisions: <one line and evidence per relevant decision, or none>

1. <highest-ranked open question; boundary N.M or epic>
   Evidence: <exact source file:line and synthetic evidence paths; verify these coordinates>
   Tried and failed: <methods and what each established; no attempt history reset>
   Must settle: <the concrete decision or different method needed, keeping every criterion>
2. <next question, same fields; omit unused entries, maximum five questions>

Answer per numbered question:
- Verdict and confidence, with reason.
- Evidence actually read, citing file:line; separate facts from inference.
- For a stuck method question, up to three ranked, different evidence-backed methods,
  what would prove each worked, and any conditions that rule one out.
- What was not checked or remains uncertain. Say when no different method is justified.
You may explore the project, use helpers and search the web within your actual tools and
existing permissions. Do not edit files or change scope, criteria, privacy or limits.
End with RESULT: done, or RESULT: blocked and why.
```

For a first stuck-boundary ask use `--role consultant`. Keep its ranked methods in the
brake record; before each later attempt name the next unused method taken, without a new
consult. When it did not unblock development, its methods are exhausted or a step-back is
due, collect the epic's main open and most complex questions into a senior request with
this same form. Take `senior_consults` (or the approved file's exact `fable_consults` name
in Epics 114–117), then use `--role senior-consultant --time-limit 40`, or BMN's shorter
maximum. Without the role, use the consultant chain's next eligible agent other than its
first via `--role consultant --agent NAME`, still counted as a senior use. Refusals and
Away rules still hold. A step-back adds [step-back-brief.md](step-back-brief.md)'s exact
binding line and failed-method record; it remains one collected ask.

After acting on the answer, put its run id and `unblocked`, `partly` or `not`, with one
short reason, in the handoff; include those outcome lines in the final report.
