# Browser-enabled review

Reviews run without a browser by default. Use these variants only for a named UI
acceptance question with lead-supplied local URLs; the lead starts and stops the
app. Set `ORIGIN` to that origin (for example `http://127.0.0.1:3000`). Earlier variants
were exercised on 2026-09-18: the reviewer read a local page and another origin was
blocked. The subsequent Codex server-clearing change has configuration-only proof;
its live browser dispatch remains UNVERIFIED (see `docs/verification.md` in the checkout).
Playwright's origin filter is a
convenience, not a security boundary: it does not cover redirects, and a local
page can itself call remote APIs, so never point a reviewer at production and
supply no production credentials or personal browser profile. Browser actions can
mutate test data even though the shell stays read-only.

Codex, invocation-local MCP (no global registration; the normal review routes
stay browser-free):

```bash
codex exec --skip-git-repo-check -C "$PROJECT" \
  -m gpt-6-astra -c model_reasoning_effort=medium --sandbox read-only --json \
  -c 'mcp_servers={}' \
  -c 'mcp_servers.playwright.command="npx"' \
  -c "mcp_servers.playwright.args=[\"--offline\",\"@playwright/mcp@0.0.75\",\"--headless\",\"--isolated\",\"--allowed-origins\",\"$ORIGIN\"]" \
  -o "$OUTPUT" - < "$PROMPT"
```

Under `--sandbox read-only` the shell has no network, but the MCP server runs
outside the sandbox and can reach the local app. Clear configured servers before
adding Playwright. On first use or after integration changes, inspect the reviewer's
available tools, including plugins; only the intended MCP tools should be available.

Claude (`--tools ''` keeps built-ins off but leaves MCP tools available; do not
add `--safe-mode`, which disables MCP servers):

```bash
claude -p --model fable --effort medium --output-format json \
  --tools '' --permission-mode dontAsk --no-session-persistence \
  --strict-mcp-config --mcp-config "{\"mcpServers\":{\"playwright\":{\"command\":\"npx\",\"args\":[\"--offline\",\"@playwright/mcp@0.0.75\",\"--headless\",\"--isolated\",\"--allowed-origins\",\"$ORIGIN\"]}}}" \
  --allowedTools 'mcp__playwright__browser_navigate,mcp__playwright__browser_snapshot,mcp__playwright__browser_click,mcp__playwright__browser_type,mcp__playwright__browser_fill_form,mcp__playwright__browser_take_screenshot,mcp__playwright__browser_console_messages,mcp__playwright__browser_close' \
  < "$PROMPT" > "$OUTPUT"
```

`--allowedTools` is variadic: keep it before the stdin redirection and never
follow it with a positional prompt. Inspect the response/receipt for the actual model, effort, errors,
and limitations, and record those facts in the handoff.
