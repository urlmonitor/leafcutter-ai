---
name: route-knowledge
allowed-tools: Read
description: >
  Knowledge routing classifier. Use when a user says "remember this",
  "capture this", "we should write this down", "save this for later",
  or any equivalent. Also use as a pre-flight gate before dispatching
  documentation-expert, to confirm the knowledge belongs on a doc surface
  rather than a memory file, glossary entry, or config value.
  Returns a structured routing decision: { target_surface, path, rationale }.
---

# route-knowledge

This skill classifies a piece of knowledge and returns the correct persistence
surface. It is the user-facing / caller-friendly variant of the agent-internal
`route-learning` skill (used in signoff §7). Where `route-learning` is scoped
to post-signoff agent discoveries, `route-knowledge` handles:

1. **User-initiated "remember X" triggers** from the main conversation thread.
2. **Pre-flight gate for `documentation-expert`** — confirms a doc surface is
   correct before Diataxis routing begins.
3. **Phase agent captures** where feedback or context should be persisted mid-task.

---

## Input Contract

The caller passes:

```
{
  "knowledge_text": "<the piece of information to persist>",
  "context": {                            // optional
    "originating_agent": "<agent-name or null>",
    "file_being_edited": "<path or null>",
    "ticket_in_scope":   "<ticket path or null>",
    "trigger_phrase":    "<exact user phrase, e.g. 'remember this'>"
  }
}
```

All fields in `context` are optional. When `originating_agent` is absent,
assume the trigger came from the user conversation thread.

---

## Output Contract

```json
{
  "target_surface": "<surface identifier — see taxonomy below>",
  "path":           "<suggested file path or pattern>",
  "rationale":      "<one sentence explaining why this surface was chosen>"
}
```

If the routing decision is uncertain, the skill returns a second field:

```json
{
  "target_surface": "<best guess>",
  "path":           "<suggested path>",
  "rationale":      "<explanation>",
  "alternatives": [
    {
      "target_surface": "<alt>",
      "path":           "<alt path>",
      "rationale":      "<why this was not chosen>"
    }
  ]
}
```

---

## Surface Taxonomy

| ID | Surface | Condition |
|----|---------|-----------|
| `memory-user` | `memory/feedback_*.md` (user-preference subtype) | Captures how Claude should behave for this specific user; corrections to agent habits or communication style |
| `memory-project` | `memory/project_*.md` (project-context subtype) | Project-level facts that should persist across sessions: repo paths, auth quirks, naming conventions |
| `memory-reference` | `memory/reference_*.md` (reference subtype) | Lookup data the user wants available at every spawn: API keys pattern, port numbers, environment names |
| `CLAUDE.md-inline` | Root `CLAUDE.md` (inline entry) | Short, universal project-wide rule or fact; fits in one bullet or one paragraph; every agent must know it |
| `CLAUDE.md-toc` | Root `CLAUDE.md` (TOC heading + link) | Content warrants its own section or file; add a heading in CLAUDE.md that links to `docs/` — do not paste full text inline |
| `per-folder-readme` | `<folder>/README.md` | Folder-scoped context: purpose of a directory, file conventions within that folder, or local entry-point docs |
| `agent-frontmatter` | `leafcutter/templates/agents/<name>.md` or `PROJECT_CONTEXT.md` | Domain knowledge a specific worker agent needs at every spawn — behavioral rules, domain-specific context |
| `adr` | `docs/architecture/adrs/ADR-NNN-*.md` | Architectural decision + rationale; use when a non-obvious design choice is made and future engineers need the "why" |
| `architecture-doc` | `docs/architecture/<name>.md` | Structural or component description (C4 diagrams, system topology, data-flow maps) |
| `how-to` | `docs/how-to/<name>.md` | Step-by-step task procedure; "how do I X?" style content |
| `reference` | `docs/reference/<name>.md` | Lookup table, schema dictionary, enum list, configuration key reference |
| `explanation` | `docs/explanation/<name>.md` | Conceptual understanding; "why does X work this way?" or "what is the mental model for Y?" |
| `glossary` | `docs/glossary.md` (via `glossary-triage` flow) | Novel project-specific term or abbreviation; NEVER hand-edit — use the triage flow |
| `settings-json` | `config/settings.json` (via `update-config` flow) | Hook registrations, permission flags, environment variables, feature flags |
| `ticket-body` | `tickets/<status>/<ticket>.md` (body section) | Work-in-progress scope item, acceptance criterion, or implementation note that belongs to an active ticket |
| `skills-config` | `config/skills_config.json` | Onboarding-time configuration values: skill auto-load decisions, skill-to-agent assignments |

---

## Decision Tree

Walk each step in order. **First match wins.** Return the surface for the first
step whose condition holds true.

---

### Step 0 — Duplicate Detection

Before routing, normalise the knowledge text (lowercase, strip punctuation) and
search the following stores for a near-identical entry (≥ 0.85 Levenshtein ratio
or semantic equivalence):

- `memory/*.md` files
- `CLAUDE.md` body
- The relevant section of the ticket body (if `ticket_in_scope` is set)

If a near-duplicate is found, return:

```json
{ "target_surface": "duplicate", "path": "<existing file>", "rationale": "Near-duplicate already exists at <file>." }
```

Do not write anything. The caller is responsible for deciding whether to update
the existing entry.

---

### Step 1 — User preference / behaviour correction

**Condition:** The knowledge describes how Claude (or a specific agent) should
behave for _this user specifically_ — communication style, workflow preferences,
tool choices, or a correction to a default behaviour.

**Examples:**
- "Remember: always use absolute paths in Bash commands."
- "I prefer kebab-case for file names."
- "Don't use emojis in responses."
- "When I say 'save this', I always mean user-memory, not CLAUDE.md."

**Route to:** `memory-user`

**Path pattern:** `memory/feedback_<topic>.md`

**Exclusion:** Do NOT use this surface for project facts that every future engineer
should know — those belong in `CLAUDE.md-inline` (Step 4).

**Example output:**
```json
{
  "target_surface": "memory-user",
  "path": "memory/feedback_file_naming.md",
  "rationale": "User preference about file naming convention — scoped to this user's workflow."
}
```

---

### Step 2 — Project-context fact (cross-session persistence)

**Condition:** The knowledge is a project-scoped fact that should survive
across sessions but is NOT broad enough for all agents to need (e.g. repo paths,
SSH key aliases, worktree layout, auth quirks for a specific remote).

**Examples:**
- "The git remote alias is `github.com-urlmonitor`."
- "The worktree root for EPIC-Foo is at `/mnt/c/.../EPIC-Foo/`."
- "Alembic migrations live in `alembic/versions/` — the build step does NOT auto-run them."

**Route to:** `memory-project`

**Path pattern:** `memory/project_<topic>.md`

---

### Step 3 — Reference lookup data

**Condition:** The knowledge is a lookup table, list, or reference value the user
wants available at spawn time — port numbers, API endpoint names, environment
names, schema column lists.

**Examples:**
- "The staging environment URL is `https://staging.example.com`."
- "These are the valid `status` enum values: pending, active, archived."

**Route to:** `memory-reference`

**Path pattern:** `memory/reference_<topic>.md`

---

### Step 4 — Short universal project rule (CLAUDE.md inline)

**Condition:** The knowledge is a short (1–3 sentence), project-wide rule or
convention that EVERY agent needs to know. It fits naturally as a bullet point
or short paragraph in `CLAUDE.md`.

**Examples:**
- "Always run `build-self.sh` after editing templates."
- "The repo root is `leafcutter-ai/`, not `leafcutter/`."
- "Pre-commit hooks run in a virtualenv at `.venv/`."

**Route to:** `CLAUDE.md-inline`

**Path:** `CLAUDE.md` (root)

**CLAUDE.md inline vs TOC-link rule:** see the dedicated sub-section below.

---

### Step 5 — Long universal project rule or reference (CLAUDE.md TOC link)

**Condition:** The knowledge is project-wide but too long for an inline bullet.
It warrants its own section or file in `docs/`. Add a heading in `CLAUDE.md`
that links to the deeper doc — do NOT paste the full content inline.

**Examples:**
- A multi-step pre-drive checklist that is 10+ bullet points.
- A full table of worktree conventions.
- The complete SSH key setup guide.

**Route to:** `CLAUDE.md-toc`

**Path:** Create the full content at `docs/<appropriate-subdir>/<name>.md`, then
add a one-line TOC entry in `CLAUDE.md` pointing to that file.

**CLAUDE.md inline vs TOC-link rule:** see the dedicated sub-section below.

---

### Step 6 — Folder-scoped context

**Condition:** The knowledge is relevant ONLY when working in a specific folder —
the purpose of the folder, local file conventions, or a directory-level entry
point.

**Examples:**
- "Files in `leafcutter/scripts/` are portable; they must not import project-specific modules."
- "The `alembic/versions/` folder auto-numbers migrations. Do not rename files."

**Route to:** `per-folder-readme`

**Path pattern:** `<folder>/README.md`

---

### Step 7 — Agent-specific knowledge

**Condition:** The knowledge is relevant only to one specific agent's behaviour —
a domain convention the agent needs to know, a behavioral correction, or a
decision rule scoped to that agent's work.

**Examples:**
- "python-coder should always check for an existing `tests/conftest.py` before creating fixtures."
- "documentation-expert should use `docs/how-to/` (not `docs/tutorials/`) for step-by-step guides."

**Route to:** `agent-frontmatter`

**Path pattern:** `.claude/skills/<agent-relevant-skill>/PROJECT_CONTEXT.md`
(preferred, for portable skill companions) or
`leafcutter/templates/agents/<name>.md` (for template-level changes requiring a
rebuild).

---

### Step 8 — Architectural decision

**Condition:** A non-obvious design choice was made and future engineers need the
"why" — trade-offs considered, alternatives rejected, constraints that shaped the
decision.

**Examples:**
- "We chose JSONB over a separate table for symbol metadata because…"
- "We rejected the polling approach in favour of push because…"

**Route to:** `adr`

**Path pattern:** `docs/architecture/adrs/ADR-NNN-<slug>.md`

**Note:** Use `adr-author` agent to draft the ADR; do not hand-write it.

---

### Step 9 — Structural / component description

**Condition:** The knowledge describes HOW the system is structured — components,
containers, data flows, deployment topology. Belongs in an architecture doc
(potentially with a C4 diagram).

**Route to:** `architecture-doc`

**Path pattern:** `docs/architecture/<name>.md`

---

### Step 10 — Task procedure ("how do I X?")

**Condition:** The knowledge is a step-by-step guide for completing a specific
task. The user or a future engineer will want to look it up when they need to
perform that task.

**Route to:** `how-to`

**Path pattern:** `docs/how-to/<name>.md`

---

### Step 11 — Lookup table or schema ("what are the valid values of X?")

**Condition:** The knowledge is a reference table, enum list, schema description,
configuration key reference, or any other "look up a specific value" content.

**Route to:** `reference`

**Path pattern:** `docs/reference/<name>.md`

---

### Step 12 — Conceptual understanding ("why does X work this way?")

**Condition:** The knowledge explains a concept, mental model, or design
rationale. The reader wants to understand, not to do or look up.

**Route to:** `explanation`

**Path pattern:** `docs/explanation/<name>.md`

---

### Step 13 — Novel project term

**Condition:** The knowledge introduces or precisely defines a new term,
abbreviation, or domain-specific jargon used in the project.

**Route to:** `glossary`

**Path:** `docs/glossary.md`

**IMPORTANT:** Never hand-edit `docs/glossary.md`. Use the `glossary-triage`
flow — dispatch the `glossary-triage` agent with the candidate term, context
windows, and existing glossary terms. The agent decides whether to add or
blacklist the term.

See the **Glossary Surface** sub-section below for the caller contract.

---

### Step 14 — Hook, permission, or environment variable

**Condition:** The knowledge is a hook registration, permission flag, environment
variable declaration, or feature flag that belongs in the harness configuration.

**Route to:** `settings-json`

**Path:** `config/settings.json`

**Note:** Use the `update-config` flow rather than direct file editing, if
available.

---

### Step 15 — Active ticket scope item

**Condition:** The knowledge is a work-in-progress acceptance criterion,
implementation note, or scope boundary that belongs in a specific open ticket.

**Route to:** `ticket-body`

**Path pattern:** `tickets/01_todo/<ticket>.md` (body section)

---

### Step 16 — Onboarding / install-time configuration

**Condition:** The knowledge is a configuration value that the `onboard` wizard
sets during initial install — skill auto-load decisions, model assignments,
or feature-flag defaults.

**Route to:** `skills-config`

**Path:** `config/skills_config.json`

---

### Step 17 — No clear surface (fall-through)

If none of the above steps match, return:

```json
{
  "target_surface": "unknown",
  "path": null,
  "rationale": "No surface matched the decision tree. Surface to user for manual routing."
}
```

---

## CLAUDE.md Inline vs TOC-Link Rule

When routing to `CLAUDE.md-inline` (Step 4) or `CLAUDE.md-toc` (Step 5), apply
these rules to choose between them:

### Inline rule

Route to `CLAUDE.md-inline` when ALL of the following hold:

1. The content fits in 1–3 sentences or a short bullet.
2. The content is universal — every agent in every session needs it.
3. No further explanation, table, or step-by-step breakdown is needed.

**Worked example — Inline:**

> User says: "Remember: the git remote alias is `github.com-urlmonitor`."
>
> Decision: Short, universal fact — one bullet in `CLAUDE.md`.
> ```json
> { "target_surface": "CLAUDE.md-inline", "path": "CLAUDE.md", "rationale": "One-liner SSH alias fact — universal, fits inline." }
> ```

### TOC-link rule

Route to `CLAUDE.md-toc` when ANY of the following hold:

1. The content requires more than 3 sentences, a table, or a multi-step list.
2. The content makes more sense as a named section in `docs/` that other docs
   can cross-reference.
3. Inlining would make `CLAUDE.md` harder to scan — prefer a heading + link.

**Worked example — TOC link:**

> User says: "Remember the full pre-drive checklist we use before every epic."
>
> Decision: Multi-step list — create `docs/how-to/pre-drive-checklist.md` and
> add a `| Pre-Drive Checklist | docs/how-to/pre-drive-checklist.md | ... |`
> entry in `CLAUDE.md`'s reference table.
>
> ```json
> { "target_surface": "CLAUDE.md-toc", "path": "docs/how-to/pre-drive-checklist.md", "rationale": "Multi-step checklist — too long for inline; create dedicated how-to and link from CLAUDE.md TOC." }
> ```

---

## Glossary Surface (caller contract)

When the routing decision is `glossary`, the caller MUST follow this contract:

1. **Do NOT** edit `docs/glossary.md` directly.
2. Dispatch `glossary-triage` via the `Agent` tool with:
   ```
   term: <the novel term>
   occurrences: [<list of 1-5 context windows showing the term in use>]
   existing_glossary_terms: <list of headings already in docs/glossary.md>
   existing_blacklist_terms: <list of terms in docs/glossary_blacklist.md>
   ```
3. The agent returns one of: `add_to_glossary` (with `draft_entry`),
   `add_to_blacklist`, or `false_positive`.
4. Apply the decision according to the triage agent's output — never override it.

**Why:** The glossary has a blacklist to prevent false positives. Hand-editing
bypasses the blacklist check and leads to duplicate or inconsistent entries.

---

## Relationship to `route-learning`

`route-learning` (referenced in `signoff` §7 and `agent_knowledge_system.md`)
covers the agent-internal post-signoff path. `route-knowledge` complements it:

| Dimension | `route-learning` | `route-knowledge` |
|-----------|-----------------|-------------------|
| Trigger | Agent signoff §7 (post-execution) | User "remember X" or pre-flight gate |
| Caller | Phase agents only | User, phase agents, documentation-expert |
| Surface coverage | Steps 1–11 (code → retrospectives) | Full taxonomy (Steps 0–17 above) |
| Output format | `{file, section, entry_kind}` for `capture-learning` | `{target_surface, path, rationale}` for caller routing |
| Glossary surface | Not covered | Step 13 (with triage contract) |
| CLAUDE.md inline/TOC rule | Not covered | Steps 4–5 (explicit rule + examples) |
| Structured JSON output | Internal (passed to capture-learning) | Caller-actionable JSON |

When an agent is in the signoff §7 path and wants to persist an agent-internal
learning, use `route-learning`. When the trigger comes from a user or a
caller that needs programmatic routing, use `route-knowledge`.

---

## Integration with `documentation-expert`

`documentation-expert` SHOULD call `route-knowledge` as a pre-flight gate when
it receives a "remember this" or "capture this" request, before dispatching a
Diataxis specialist:

```
Pre-flight: invoke route-knowledge with the knowledge text.
IF target_surface IN {"how-to", "reference", "explanation", "architecture-doc", "adr"}:
  → Proceed with normal Diataxis dispatch.
ELSE:
  → Do NOT dispatch a Diataxis writer.
  → Return the routing decision to the caller so they can act on the correct surface.
```

This prevents `documentation-expert` from writing a how-to when the knowledge
actually belongs in `memory/` or `CLAUDE.md`.

---

## References

- [Agent Knowledge Plane](../../docs/architecture/agent_knowledge_plane.md) —
  canonical surface inventory; this skill's decision tree is the programmatic
  counterpart to that document's channel table.
- [Agent Knowledge System](../../docs/architecture/agent_knowledge_system.md) —
  describes `route-learning` (Step 5 in the system) and `capture-learning` for
  the post-signoff capture path.
- `.claude/skills/signoff/SKILL.md` §7 — mandatory knowledge-capture trigger
  after every phase agent sign-off (uses `route-learning`, not this skill).
- `docs/glossary.md` — glossary managed by `glossary-triage`; never hand-edit.
- `leafcutter/templates/agents/documentation-expert.md` — consumes this skill
  as a pre-flight gate before Diataxis routing.
