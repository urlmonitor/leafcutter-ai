"""
MODULE: skill_ref_recognition
GOAL: Decide, for one document, which lines tell the reader to USE an ability
    (a skill), and say which ability each one names -- the single recognition
    rule behind the ability-reference gate.
BUSINESS CONTEXT: The build refuses a specialist's instructions that point at an
    ability that does not exist, that the specialist is not granted, that is
    spelled in the wrong letter case, or that is really another specialist
    (AR-400a-1, AR-400b-1, AR-400b-2). A refusal is only as trustworthy as the
    rule that decides what an instruction is: too narrow and a real fault hides,
    too wide and the gate gets switched off. Negations, sentences about another
    specialist, citations of an ability's file and installer file operations are
    deliberately NOT instructions (AR-400b-2-i..iv).
ARCHITECTURE: ``recognise(text, known_ids, agent_ids)`` is a pure function (no
    I/O). It blanks the frontmatter and HTML comments (newlines kept, so line
    numbers match the file on disk), finds candidate references per line (a
    ``.claude|templates/skills/<id>`` path, a ``<id> skill`` phrase, a written-out
    ``Skill: <id>``), then judges each one inside its own CLAUSE (clauses end at
    ``;`` and at sentence ends): an instruction verb that no negator governs makes
    it an instruction; a clause with no live verb that cites a source ("defined
    in", "see") makes it a citation; a clause whose grammatical subject is another
    specialist, or that is an installer file operation, makes it neither. Each
    result carries the text as written and the canonical id it resolves to
    case-insensitively against the known ability set (or None). The caller
    (``check_skill_refs``) owns reading files; ``agent_skill_ref_grants`` owns
    what each result means. No second regex set for "what is an instruction" may
    exist elsewhere in scripts/.

DECISION HISTORY
- 2026-10-16 [python-coder/AR-400b-2]: Created. Replaces check_skill_refs'
  imperative-marker heuristic and the deleted registry_validator xref regexes.
  Negation is clause-scoped (never line-wide); the other-specialist test is
  data-driven from ``agent_ids``. (#TICKETLESS reason=ar-400b-2-recognition-rule)
"""

from __future__ import annotations

import re
from typing import Any

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*(?:\n|\Z)", re.DOTALL)
_PATH_RE = re.compile(r"(?:\.claude|templates)/skills/([A-Za-z0-9][\w.-]*)((?:/[\w.\-]+)*)")
_PHRASE_RE = re.compile(r"(`?)([A-Za-z0-9][\w-]*)\1\s+skill\b(?!\.md)", re.IGNORECASE)
_GENERIC_RE = re.compile(r"\b(?:any|an?|each|every|some)\s+$", re.IGNORECASE)
_FILE_NAME_RE = re.compile(r"\.[A-Za-z0-9]+$")
_TOOL_CALL_RE = re.compile(r"(?<![\w-])Skill:\s*(`?)([A-Za-z0-9][\w-]*)\1")
_STRONG = r"load|read|invoke|apply|use|call|consult|resolve|follow|execute"
_WEAK = r"run|python3?|bash"
_VERB_RE = re.compile(rf"(?<![\w-])(?:(?P<strong>{_STRONG})|(?P<weak>{_WEAK}))(?![\w-])", re.IGNORECASE)
_NEGATED_RE = re.compile(r"(?:\b(?:not|never|no longer|without)|n't)\s+(?:\w+\s+){0,2}$", re.IGNORECASE)
_CITE_RE = re.compile(
    r"\b(?:(?:normatively\s+|as\s+)?(?:defined|specified|described|documented|given)\s+in|see|per"
    r"|according\s+to|source\s+of\s+truth)\b", re.IGNORECASE)
_FILE_OP_RE = re.compile(
    r"(?<![\w-])(?:mkdir|cp|mv|rm|ln|ls|cat|copy|copies|copied|echo|print|printf)(?![\w-])"
    r"|\bexists?\b|\binstall(?:ed|s)\b", re.IGNORECASE)
_SUBJECT_RE = re.compile(
    r"^[\s>*_#|`\-\d.()\[\]]*(?:(?:note|important|warning|caveat)\s*:?\s*[*_`]*\s*)?(?:the\s+)?[*_`]*"
    r"([A-Za-z0-9][\w-]*)", re.IGNORECASE)
_CLAUSE_END_RE = re.compile(r";|(?<=[.!?])\s+")


def _blank(match: re.Match[str]) -> str:
    """Replace every character but newlines with a space (line numbers survive)."""
    return re.sub(r"[^\n]", " ", match.group(0))


def _scrub(text: str) -> str:
    """Blank the frontmatter and HTML comments, keeping every newline in place."""
    return _COMMENT_RE.sub(_blank, _FRONTMATTER_RE.sub(_blank, text, count=1))


def _candidates(line: str) -> list[dict[str, Any]]:
    """Every path / phrase / tool-call mention on ``line``, in order of position."""
    found: list[dict[str, Any]] = []
    for m in _PATH_RE.finditer(line):
        ident, inner = m.group(1).rstrip(".-"), m.group(2).lstrip("/").rstrip(".")
        if inner or not _FILE_NAME_RE.search(ident):  # `templates/skills/README.md` is a file, not an ability
            found.append({"id": ident, "inner": inner, "tick": True, "forced": False, "span": m.span()})
    for m in _PHRASE_RE.finditer(line):
        generic = not m.group(1) and bool(_GENERIC_RE.search(line[:m.start()]))  # "any x skill" names no ability
        found.append({"id": m.group(2), "inner": "", "tick": bool(m.group(1)), "forced": False,
                      "generic": generic, "span": m.span()})
    for m in _TOOL_CALL_RE.finditer(line):
        found.append({"id": m.group(2), "inner": "", "tick": bool(m.group(1)), "forced": True, "span": m.span()})
    return sorted(found, key=lambda c: c["span"][0])


def _resolve(cand: dict[str, Any], known: set[str], canon: dict[str, str],
             agents: set[str]) -> tuple[bool, str | None, bool]:
    """Return (plausible, canonical_id, names_agent) for one candidate."""
    text = cand["id"]
    canonical = text if text in known else canon.get(text.casefold())
    names_agent = canonical is None and text in agents
    shaped_like_id = (cand["tick"] or "-" in text) and not cand.get("generic")
    plausible = bool(canonical) or names_agent or shaped_like_id
    return plausible, canonical, names_agent


def _clause_of(line: str, pos: int) -> tuple[int, int]:
    """The (start, end) of the clause of ``line`` that contains offset ``pos``."""
    start = 0
    for m in _CLAUSE_END_RE.finditer(line):
        if m.end() > pos:
            return start, m.start()
        start = m.end()
    return start, len(line)


def _other_subject(clause: str, agents: set[str], self_id: str | None) -> bool:
    """True when the clause's grammatical subject is a specialist id other than ``self_id``."""
    m = _SUBJECT_RE.match(clause)
    return m is not None and m.group(1) in agents and m.group(1) != self_id


def _live_verbs(masked: str) -> tuple[bool, bool, bool]:
    """Return (strong live verb, weak live verb, any negated verb) for a masked clause."""
    strong = weak = negated = False
    for m in _VERB_RE.finditer(masked):
        if _NEGATED_RE.search(masked[:m.start()]):
            negated = True
        elif m.group("strong"):
            strong = True
        else:
            weak = True
    return strong, weak, negated


def _judge(clause: str, masked: str, forced: bool, agents: set[str], self_id: str | None) -> str | None:
    """Classify one reference's clause: ``instruction``, ``citation`` or None (neither)."""
    if _other_subject(clause, agents, self_id):
        return None
    strong, weak, negated = _live_verbs(masked)
    if strong or (weak and not _FILE_OP_RE.search(masked)):
        return "instruction"
    if forced and not negated:
        return "instruction"
    if not negated and not weak and _CITE_RE.search(masked):
        return "citation"
    return None


def _line_refs(line: str, lineno: int, known: set[str], canon: dict[str, str],
               agents: set[str], self_id: str | None) -> list[dict[str, Any]]:
    """The recognised references on one scrubbed line (one per ability, first wins)."""
    resolved = [(c, *_resolve(c, known, canon, agents)) for c in _candidates(line)]
    resolved = [r for r in resolved if r[1]]
    if not resolved:
        return []
    chars = list(line)
    for cand, *_rest in resolved:
        chars[cand["span"][0]:cand["span"][1]] = " " * (cand["span"][1] - cand["span"][0])
    masked_line = "".join(chars)
    refs: dict[str, dict[str, Any]] = {}
    for cand, _ok, canonical, names_agent in resolved:
        start, end = _clause_of(line, cand["span"][0])
        kind = _judge(line[start:end], masked_line[start:end], cand["forced"], agents, self_id)
        key = cand["id"].casefold()
        if kind is None or (key in refs and not (cand["inner"] and not refs[key]["inner"])):
            continue
        refs[key] = {"ability_text": cand["id"], "canonical_id": canonical, "line": lineno,
                     "names_agent": names_agent, "citation": kind == "citation", "inner": cand["inner"]}
    return list(refs.values())


def recognise(text: str, known_ids: set[str], agent_ids: set[str], self_id: str | None = None) -> list[dict[str, Any]]:
    """Return the instructions (and citations) in ``text`` that name an ability.

    Args:
        text: A whole document; frontmatter and HTML comments are ignored.
        known_ids: The ability ids that exist (``templates/skills/`` directory names).
        agent_ids: The specialist ids (data, never named in the rule).
        self_id: The specialist the document defines, when it defines one; a sentence
            about that specialist is addressed to the reader, so it is not "another".

    Returns:
        One dict per ability named per line, in line order: ``ability_text`` (as
        written), ``canonical_id`` (case-insensitive match in ``known_ids`` or None),
        ``line`` (1-based), ``names_agent`` (the text is a specialist id, not an
        ability), ``citation`` (the ability's file is cited as a source, not used) and
        ``inner`` (the path inside the bundle, "" when none).
    """
    canon = {k.casefold(): k for k in known_ids}
    refs: list[dict[str, Any]] = []
    for lineno, line in enumerate(_scrub(text).splitlines(), start=1):
        if "skill" in line.casefold():
            refs.extend(_line_refs(line, lineno, known_ids, canon, agent_ids, self_id))
    return refs
