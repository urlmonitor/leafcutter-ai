## Sign-off (when ticket_path is provided)

If you were invoked with a `ticket_path` argument:

1. **Resolve and load the `signoff` skill.** Read it in full before editing anything.
   - Consumer project (after `build.py`): `.claude/skills/signoff/SKILL.md`
   - leafcutter-ai source repo / epic worktree: `templates/skills/signoff/SKILL.md`

   Do not proceed from memory if the skill cannot be loaded — return
   `{status: "failed", payload: {blocker_summary: "signoff-skill-unreadable"}}`.
2. **Atomic sign-off (signoff §2) — all edits in one pass:**
   a. Frontmatter: set `agents.<your-name>: signed_off`.
   b. Sign-offs checkbox: `- [ ] <agent>` → `- [x] <agent> — YYYY-MM-DD HH:MM`.
      The separator is an em-dash (`—`, U+2014), **not** a hyphen; the timestamp is
      required. The parity guard rejects a hyphen or a missing timestamp.
   c. If a `## Implementation Tasks` section exists, flip every `- [ ]` under
      `### <your-name>` to `- [x]`.
3. **Comment heading (signoff §3):** append a `## Comments` entry whose heading is
   exactly `### YYYY-MM-DD HH:MM — <your-name> (status: ok)` (em-dash U+2014). The
   parser regex rejects any other punctuation.
4. **submit_feedback (signoff §2a):** run each of these as its own single Bash call.
   `<ticket_basename>` is the ticket file's name and `<agent_name>` is your agent name.
   ```bash
   python3 scripts/feedback/submit_feedback.py --ticket <ticket_path> --phase <agent_name> --category <category> --note "<one-sentence note>" 2>/tmp/feedback_err_<ticket_basename>_<agent_name>.txt
   ```
   Read-back of this run's own failure line (prints nothing and exits 0 when there is none):
   ```bash
   sed -n '/^submit-failed:/p' /tmp/feedback_err_<ticket_basename>_<agent_name>.txt
   ```
   Recovery search (the `sidecar:` line names a recovery file):
   ```bash
   sed -n '/^sidecar:/p' /tmp/feedback_err_<ticket_basename>_<agent_name>.txt
   ```
   Record `feedback-id:` by the INF-500d-3 capture precedence: the id on stdout; else
   the id inside the recovery file the `sidecar:` line names; else the read-back line
   copied verbatim into `(submit-failed:<reason>:<category>)`; else
   `(submit-failed:written-uncited:<category>)` when a `sidecar:` or
   `[submit_feedback] sink:` line exists but no id was recovered; else
   `(submit-failed:facility-unavailable:<category>)`. The reasons live only in
   `scripts/feedback/submit_failure_reasons.json`. Read only this run's own error file,
   and never look through the temp directory for another recovery file. A failed submit
   is **not** a phase failure: continue the sign-off unchanged.
5. **Self-verify (mandatory):** re-`Read` the ticket and confirm 2a, 2b, and the
   Comments heading all actually landed. If any write was silently lost, return
   `{status: "failed", payload: {blocker_summary: "signoff-write-lost"}}` — do not
   report `ok`.
6. **Knowledge capture (signoff §7):** ask whether you learned something future-you
   would have needed at the start; if so, follow §7. If the capture skills are
   unavailable, log a warning and proceed.
7. On failure at any implementation step: follow the failed-path recipe (signoff §4);
   set status to `failed` and append a `blocker` comment.
8. Skip this entire section if no `ticket_path` was provided.
