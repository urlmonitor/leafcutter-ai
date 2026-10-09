"""
MODULE: product_truth_descriptions
GOAL: Hold every flow step and branch `description` to one plain sentence of
    WHAT happens -- a length bound and a code-token lint, both hard errors --
    and declare the closed vocabulary of `actor_kind`.
BUSINESS CONTEXT: Kernel decision dec-7b1dcfd47f85cf0a renamed the step field
    `human` to `description` and added `actor_kind`. The old field read like a
    boolean ("a human does this step") and had grown into engineering
    narrative: code paths, symbol names, build status, design notes and a
    generated contract dump, median 410 and up to 2,473 characters. That text
    went stale as the code moved and buried what the step does. Product truth
    says WHAT happens; HOW it is built lives in code, ACs and `io_contracts`.
    Every flow was migrated in the same change, so both gates block from the
    day they land rather than going through a shape-version warning period.
ARCHITECTURE: Pure, stateless leaf module. description_problems() is the one
    rule set: the validator gate (check_descriptions) and any authoring tool
    or test call it, so the rule cannot drift between them. Each rule is one
    named regex family; plain English must pass, so every rule targets a
    shape that ordinary prose does not produce (see _RULES and the allow-rules
    in _path_tokens / _dotted_tokens).
"""
from __future__ import annotations

import re

#: Longest description, in characters, that still reads as one sentence. The
#: rewritten record's longest description is well under it; a step that needs
#: more than this is two steps, or is carrying detail that belongs elsewhere.
DESCRIPTION_MAX_CHARS = 200

#: Who runs a step, per ADR-053's four mechanisms. Mirrored by the enum in
#: flow.schema.json and by the Atlas view types.
ACTOR_KINDS = ("deterministic", "jev", "llm", "human")

_EXTENSIONS = ("py", "pyi", "ts", "tsx", "js", "jsx", "mjs", "cjs", "json", "jsonl", "md", "yaml", "yml",
               "sql", "sh", "ps1", "toml", "ini", "cfg", "html", "css", "csv", "txt", "lock")
_REPO_ROOTS = ("docs", "scripts", "templates", "kernel", "knowledge", "tests", "unit_tests", "config",
               "tickets", "leafcutter-web", "integrations", ".claude", ".leafcutter")

#: (reason, pattern) pairs. A match anywhere in the description is a problem.
_RULES = (
    ("backtick", re.compile(r"`")),
    ("more than one line", re.compile(r"[\r\n]")),
    ("generated contract text", re.compile(r"Contract fields and examples", re.IGNORECASE)),
    ("file name or extension", re.compile(r"\.(?:%s)\b" % "|".join(_EXTENSIONS), re.IGNORECASE)),
    ("snake_case identifier", re.compile(r"\b[A-Za-z0-9]+_[A-Za-z0-9_]+\b")),
    ("camelCase identifier", re.compile(r"\b[a-z]+[A-Z][A-Za-z0-9]*\b")),
    # "step(s)" is the one parenthesis glued to a word that prose writes.
    ("function call", re.compile(r"[A-Za-z0-9_]\((?!s\))")),
    ("code punctuation", re.compile(r"[{}\[\]<>=|\\]|->|::")),
    ("command-line flag", re.compile(r"(?<![\w-])--?[a-z][\w-]*")),
    ("ticket, AC or ADR id", re.compile(r"\b[A-Z]{2,6}-\d+[A-Za-z0-9-]*\b|\bEPIC-[A-Za-z]|#\d+")),
    ("record id", re.compile(r"\b(?:dec|run|clf)-[0-9a-f]{3,}\b")),
    ("build status", re.compile(r"\b(?:TODO|FIXME|TBD|WIP)\b|\b(?:(?:not |un)?implemented|"
                                r"not (?:yet )?(?:built|wired)|unbuilt|stub(?:s|bed)?)\b", re.IGNORECASE)),
)

#: A sentence end followed by the start of another sentence.
_SENTENCE_BREAK = re.compile(r"[.!?][\"')\]]?\s+[\"'(]?[A-Z0-9]")
#: Prose abbreviations whose full stop does not end the sentence (e.g. Pro, vs. Team).
_PROSE_ABBREVIATION = re.compile(r"\b(?:e\.g|i\.e|vs|etc|approx|cf|incl)\.", re.IGNORECASE)
#: Dotted tokens prose writes: abbreviations made of single letters (e.g., i.e., a.m.).
_ABBREVIATION = re.compile(r"^(?:[A-Za-z]\.)+[A-Za-z]?\.?$")
_TRAILING = ".,;:!?\"')]"
_LEADING = "\"'(["


def _tokens(text: str) -> list[str]:
    return [word.strip(_TRAILING).lstrip(_LEADING) for word in text.split()]


def _path_tokens(text: str) -> list[str]:
    """Slash tokens that name a path, not two plain alternatives like and/or."""
    found = []
    for token in _tokens(text):
        if "/" not in token:
            continue
        parts = token.split("/")
        if (token.startswith(("/", "./", "../", "~/")) or len(parts) > 2 or parts[0] in _REPO_ROOTS
                or any(char in token for char in "._") or ("-" in token and token == token.lower())):
            found.append(token)
    return found


def _dotted_tokens(text: str) -> list[str]:
    """Dotted names (module.attr, a domain) other than single-letter abbreviations."""
    return [token for token in _tokens(text)
            if re.search(r"[A-Za-z_]\w*\.[A-Za-z_]", token) and not _ABBREVIATION.match(token)]


def description_problems(text: object) -> list[str]:
    """Return why *text* is not one plain sentence of what happens; empty when it is.

    Args:
        text: A step or branch `description`.

    Returns:
        One ``"<reason>: '<offending text>'"`` entry per rule broken, in rule order.
    """
    if not isinstance(text, str) or not text.strip():
        return ["empty: a description must say what happens"]
    problems = []
    if len(text) > DESCRIPTION_MAX_CHARS:
        problems.append(f"too long: {len(text)} characters, over the {DESCRIPTION_MAX_CHARS}-character bound")
    sentence_break = _SENTENCE_BREAK.search(_PROSE_ABBREVIATION.sub("abbr", text.strip()))
    if sentence_break:
        problems.append("more than one sentence: '" + sentence_break.group(0) + "'")
    for reason, pattern in _RULES:
        match = pattern.search(text)
        if match:
            problems.append(f"{reason}: '{match.group(0)}'")
    for reason, tokens in (("file path", _path_tokens(text)), ("dotted identifier", _dotted_tokens(text))):
        if tokens:
            problems.append(f"{reason}: '{tokens[0]}'")
    return problems


def check_descriptions(flows: dict, errors: list[str]) -> int:
    """File one error per broken rule on every step and branch description.

    A branch may omit its description (the schema does not require one); a
    present one is held to the same rules as a step's.

    Args:
        flows: ``{flow id -> flow}`` as read by load_flows().
        errors: Shared error list.

    Returns:
        How many descriptions were measured, so a run that measured none is
        told apart from one where none broke a rule.
    """
    measured = 0
    for flow_id in sorted(flows):
        flow = flows[flow_id]
        for kind, nodes in (("step", flow.get("steps", [])), ("branch", flow.get("branches", []))):
            for node in nodes:
                if kind == "branch" and "description" not in node:
                    continue
                measured += 1
                for problem in description_problems(node.get("description")):
                    errors.append(f"[description] {flow_id} {kind} '{node.get('id')}': {problem}")
    return measured


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-10-09 [python-coder]: New module (TICKET-20261009-ProductTruthDescriptionActorKind,
  kernel decision dec-7b1dcfd47f85cf0a). Both gates are errors from day one
  because the same change migrates every flow; a shape-version warning period
  (product_truth_bounds) would only have delayed a bound nothing exceeds.
  Considered and rejected: requiring a capital first letter and a final full
  stop (would fail short test-fixture sentences without making any real
  description clearer), flagging PascalCase words (entity names such as
  MockData and product names such as GitHub are plain in this record), and
  flagging every slash (and/or, input/output are prose).
====================================================================
"""
