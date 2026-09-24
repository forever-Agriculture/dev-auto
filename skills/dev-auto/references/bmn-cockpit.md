# Owner cockpit (BMN)

Read this only when the session runs inside BMN (`bmn` on PATH, `BMN_CONTROL_SOCKET`
and `BMN_TOKEN` set); then mirror the run for the owner. At each
`DEV-AUTO:` line run `bmn progress` with ACTIVE→`running`, PAUSED→`waiting`,
BLOCKED→`blocked`, COMPLETE→`claimed-done`; the label is the evidence for COMPLETE
and the next action otherwise; never `verified`, which is the owner's judgment. When
BLOCKED needs an owner decision, run `bmn ask dev-auto-<epic> "<decision needed>"`
with `--kind permission` for an action needing authorization and `--kind question`
otherwise; an external dependency needing no owner action stays a blocked progress
label. The ask never gates work: continue independent authorized work, and `bmn
withdraw` the request when you observe the decision in the session. An answered or
withdrawn request is not approval; only an attributable owner answer authorizes its
named action. At acceptance `bmn publish`
the handoff only, with receipts cited by path and hash; omit secrets. Never use
`bmn send`. Bound each call to two seconds (for example `timeout 2 bmn …`); after the
first failure skip mirroring for the rest of the run, without retries or repair, and
note it once at the next normal handoff update.
