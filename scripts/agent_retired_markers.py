"""
MODULE: agent_retired_markers
GOAL: Strip the retired registry-injection tokens (``{{my_skills_used}}``,
    ``{{my_spawn_allowlist}}``) from a template body at compile time and report
    each leftover by template name, so a mid-migration definition compiles to a
    clean prompt and the residue does not become permanent by being harmless.
BUSINESS CONTEXT: AR-300d-4 / AR-300d-4-i. Delivery of an agent's abilities no
    longer depends on a marker an author has to remember: it follows the
    frontmatter declaration. A definition that still carries a retired token
    must therefore get ONE abilities section (the declared one), no visible
    ``{{...}}`` text, and a report naming the definition so the token is removed.
    The tokens are neither substituted from the registry nor used as a placement
    site. Spawn-allowlist DELIVERY is not built here (AR-300b); only the token's
    retirement is.
ARCHITECTURE: ``strip_retired_markers(body, template_name)`` is pure apart from
    one WARNING log record per template that carries a token. The same token
    names are matched by ``build_placeholder_detection``'s retired-token rule
    (the scan-side report). Build-engine module under ``scripts/``; no
    deploy-manifest entry needed.

DECISION HISTORY
- 2026-10-09 [python-coder/AR-300d-4-i]: Created; replaces the marker-gated
  substitution branches in ``template_compiler._apply_registry_injection``.
  (#AR-300d-4-i)
"""

from __future__ import annotations

import logging
import re

_log = logging.getLogger(__name__)
RETIRED_TOKEN_NAMES = ("my_skills_used", "my_spawn_allowlist")
_TOKEN = r"\{\{\s*(?:" + "|".join(RETIRED_TOKEN_NAMES) + r")\s*\}\}"
_OWN_LINE_RE = re.compile(rf"^[ \t]*{_TOKEN}[ \t]*\n(?:[ \t]*\n)?", re.MULTILINE)
_ANY_RE = re.compile(_TOKEN)


def strip_retired_markers(body: str, template_name: str) -> str:
    """Remove every retired token from ``body``, logging a WARNING naming ``template_name``.

    Args:
        body: Template body text (frontmatter removed).
        template_name: File name of the template, used in the report.

    Returns:
        ``body`` without any retired token; unchanged when none is present.
    """
    found = sorted({re.sub(r"[{}\s]", "", m.group(0)) for m in _ANY_RE.finditer(body)})
    if not found:
        return body
    _log.warning(
        "%s carries retired marker(s) %s: not substituted and not a placement site; "
        "abilities are delivered from the frontmatter declaration -- remove the marker",
        template_name, ", ".join("{{" + name + "}}" for name in found),
    )
    return _ANY_RE.sub("", _OWN_LINE_RE.sub("", body))
