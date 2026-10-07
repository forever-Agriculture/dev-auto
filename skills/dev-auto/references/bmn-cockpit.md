# Owner cockpit (BMN)

Inside BMN (`bmn` on PATH, `BMN_CONTROL_SOCKET`/`BMN_TOKEN` set; test with
`[ -n "${BMN_TOKEN:-}" ]`, never print values), BMN handles native cards and conversation resume.
Dev-auto's handoff preserves task state.

Run `bmn progress` when the state, blocker or next action materially changes, and
at COMPLETE: ACTIVE→`running`, PAUSED→`waiting`, BLOCKED→`blocked`,
COMPLETE→`claimed-done`. Label COMPLETE with evidence, other states with the next
action. Never use `verified`, which is the owner's judgment.

Use selectable native question cards per global rules. If unavailable, keep the
decision unresolved and state the limitation; do not ask in plain text.
Rely on BMN's native question and permission cards; do not mirror them with manual
`bmn ask` requests. Do not add polling or withdraw hook-managed cards. External dependencies needing no owner action
stay blocked progress. Continue independent authorized work while answers are pending.

Only an attributable in-session owner answer authorizes its named action; card
resolution/withdrawal is not approval, tool permission covers only that call.
Remote answers require correlated producer receipts; unsupported routes stay unfinished.
Keep unresolved questions through compaction without duplicating them.

At acceptance `bmn publish` only the handoff, citing receipts by path/hash; omit
secrets. Never use `bmn send`. Bound manual calls with `timeout 2 bmn …`; after
one failure skip them for the run without retries/repair; note it at the next
normal handoff update.
