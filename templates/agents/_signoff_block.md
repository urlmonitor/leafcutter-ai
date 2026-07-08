## Sign-off (when ticket_path is provided)

If you were invoked with a `ticket_path` argument:

1. **Resolve and load the sign-off skill.** Read it in full before editing anything.
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
4. **submit_feedback (signoff §2a):** call `scripts/feedback/submit_feedback.py` as a
   single shell command with absolute paths. If the script is absent, or
   `feedback_categories.yaml` is missing, or it exits non-zero, record
   `feedback-id: (submit-failed)` and continue — a failed submit is **not** a phase
   failure.
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
