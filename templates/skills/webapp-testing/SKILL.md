---
name: webapp-testing
allowed-tools: Bash, Read, Write
description: |
  Optional skill for frontend-coder. Provides Playwright-based UI verification:
  screenshots, browser console-log capture, and click/type interactions. Installed
  by the /onboard wizard when the user opts in.

  Load this skill AFTER making UI changes to verify the result before signing off.
  Returns a screenshot path, console-log summary, and a pass/fail verdict.

  Antigravity adopters: SKIP this skill. Antigravity provides its own browser
  verification. Do not invoke this skill in an Antigravity environment.
---

# webapp-testing

> **Antigravity adopters — skip this skill.** Antigravity provides its own
> browser verification pipeline. If the `ANTIGRAVITY` environment variable is set,
> do not execute any step below. Exit immediately with a one-line note:
> `webapp-testing skipped — Antigravity provides its own browser.`

This is an optional skill for `frontend-coder`. It provides Playwright-based UI
verification after UI changes are made. Invoke it as the final step before signing
off, to confirm the rendered output looks correct and has no console errors.

---

## §1 Prerequisites Check

Before executing any Playwright command, verify Playwright is available:

```bash
npx playwright --version 2>/dev/null || echo "PLAYWRIGHT_NOT_INSTALLED"
```

If the output contains `PLAYWRIGHT_NOT_INSTALLED`, log a one-line warning and
exit gracefully:

```
webapp-testing: Playwright is not installed in this environment. Skipping browser verification.
```

**Do NOT block the agent sign-off.** The absence of Playwright is not a failure —
it means the adopter has not installed it. The agent should still sign off and note
the absence in its response payload.

---

## §2 Input Contract

The calling agent (`frontend-coder`) passes the following context when loading
this skill:

| Field | Type | Description |
|---|---|---|
| `url_or_command` | string | Either a URL to open (e.g. `http://localhost:3000`) or a shell command to start the app (e.g. `npm run dev`). |
| `test_steps` | list | An ordered list of interaction steps to perform before capturing. Can be empty (`[]`) for a static screenshot only. |

**Example call context:**

```
url_or_command: http://localhost:3000/dashboard
test_steps:
  - click: "#submit-button"
  - type: "[name=email]" value="test@example.com"
  - wait: 1000
```

If `url_or_command` starts with `http://` or `https://`, open the URL directly.
Otherwise, treat it as a startup command: run it in the background, wait 3 seconds
for the server to start, then open `http://localhost:3000` (or the port specified
in the command, if determinable).

---

## §3 Operations

### §3.1 Screenshot

Capture a screenshot of the current page state:

```bash
npx playwright screenshot \
  --browser chromium \
  "<url>" \
  "<output_path>.png"
```

Store the screenshot at `tmp_webapp_testing_<timestamp>.png` (use `mktemp` or
a timestamp-based name). Return the absolute path in the output contract.

### §3.2 Console-log capture

Use a Playwright Node.js script to capture console output:

```bash
node -e "
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const logs = [];
  page.on('console', msg => logs.push({ type: msg.type(), text: msg.text() }));
  await page.goto('$URL');
  // wait for network idle
  await page.waitForLoadState('networkidle');
  console.log(JSON.stringify(logs));
  await browser.close();
})();
" 2>/dev/null
```

If the script fails (Playwright not available as a Node module), fall back to the
CLI screenshot only and report console logs as `unavailable`.

### §3.3 Interactions (click / type / wait)

For each step in `test_steps`:

- **click `<selector>`**: `page.click('<selector>')`
- **type `<selector>` value `<text>`**: `page.fill('<selector>', '<text>')`
- **wait `<ms>`**: `page.waitForTimeout(<ms>)`

Implement interactions inside the Node.js script from §3.2 before the screenshot.

---

## §4 Output Contract

After running, return the following structured block to the calling agent
(`frontend-coder`). Include it verbatim in the agent's response payload.

```
webapp-testing-result:
  screenshot: <absolute-path-to-screenshot.png or "none">
  console_logs:
    errors: <count>
    warnings: <count>
    sample: <first 3 error/warning messages, or "none">
  verdict: pass | warn | fail
  notes: <one sentence — e.g. "No console errors. Screenshot captured." or "Playwright not installed — browser verification skipped.">
```

**Verdict rules:**

| Condition | Verdict |
|---|---|
| No console errors, screenshot captured | `pass` |
| Console warnings present but no errors | `warn` |
| Console errors present | `fail` |
| Playwright not installed | `pass` (graceful skip — not a test failure) |
| URL unreachable / server failed to start | `fail` |

---

## §5 Playwright-Not-Installed Fallback

When Playwright is not installed (detected in §1), return:

```
webapp-testing-result:
  screenshot: none
  console_logs:
    errors: 0
    warnings: 0
    sample: none
  verdict: pass
  notes: "Playwright not installed in this environment — browser verification skipped. Install with: npm install -D playwright @playwright/test && npx playwright install chromium"
```

This fallback ensures the agent pipeline is not blocked by a missing optional
dependency. The adopter can install Playwright separately and re-run if needed.

---

## §6 Constraints

- Do NOT modify any source files while running this skill.
- Do NOT commit screenshots to the repository — they are temporary verification artifacts.
- Do NOT block the agent sign-off if Playwright is unavailable or the URL is unreachable.
- Run only in the context of `frontend-coder`. Do not invoke this skill from other agents.
- If running in an Antigravity environment (`ANTIGRAVITY` env var set), skip all steps and return the Antigravity-skip message.
