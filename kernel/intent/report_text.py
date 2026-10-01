"""
MODULE: kernel.intent.report_text
GOAL: Plain-language report wording: why a run stopped, what the kernel can do instead, a
    suggested rephrasing, and readable sections for evidence and idea (options) outputs.
BUSINESS CONTEXT: A bare "blocked" tells a user nothing (live runs showed this): the report and
    the envelope must say in plain words why the run stopped and what the kernel can do. Ideas
    are proposals, never decisions, and the report must present them that way (spec 10.4).
ARCHITECTURE: Pure template functions over limitation strings and output payload dicts (no model
    text, no IO, no scheduler imports); `nodes_lifecycle` calls them while it renders report.md
    and assembles the outcome.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kernel.contracts import schema_ids

CAN_DO = ("decide between options or approaches, find evidence in this repository, or "
          "generate ideas (as proposals, not decisions)")
SUGGESTIONS = ('"Decide which option to pick for ..."', '"Find where ... is defined in this '
               'repository"', '"Suggest ideas to improve ..."')
#: Limitation codes whose text is already a plain explanation with next steps.
_PLAIN_CODES = frozenset({"out_of_scope_write", "out_of_domain", "unclear_request"})
_MAX_SHOWN = 8


def has_plain_reason(limitations: list[str]) -> bool:
    """Return True when a limitation already explains the stop in plain words."""
    return any(text.split(":", 1)[0] in _PLAIN_CODES for text in limitations)


def can_do_hint() -> str:
    """Return the limitation line that says what the kernel can do and how to rephrase."""
    return (f"can_do: This kernel can {CAN_DO}. Try rephrasing your request, for example "
            + ", ".join(SUGGESTIONS) + ".")


def stop_explanation(status: str, limitations: list[str]) -> list[str]:
    """Return report lines saying why a blocked or partial run stopped and what to do next."""
    if status not in ("blocked", "partial"):
        return []
    lines = ["## Why the run stopped", ""]
    reasons = [t.partition(":")[2].strip() or t for t in limitations
               if t.split(":", 1)[0] in _PLAIN_CODES or t.startswith("no_capability")]
    lines += [f"- {r}" for r in reasons] or [
        f"- The run ended {status} before it could produce the requested result."]
    lines += ["", f"What the kernel can do: {CAN_DO}.", "",
              "Try rephrasing, for example: " + ", ".join(SUGGESTIONS) + ".", ""]
    return lines


def _bullets(values: list[str]) -> list[str]:
    """Return up to the display cap of bullets, with a count of the remainder."""
    shown = [f"- {v}" for v in values[:_MAX_SHOWN]]
    if len(values) > _MAX_SHOWN:
        shown.append(f"- ... and {len(values) - _MAX_SHOWN} more")
    return shown


def _options_lines(payload: Mapping[str, Any]) -> list[str]:
    """Return the readable section of an options.v1 output: proposals, never decisions."""
    lines = ["## Ideas (proposals, not decisions)", "",
             "These options were generated as proposals. None of them is approved or chosen.", ""]
    for option in payload.get("options", []):
        text = f"**{option.get('title', option.get('id'))}**"
        description = option.get("description")
        lines.append(f"- {text} (proposed): {description}" if description
                     else f"- {text} (proposed)")
    criteria = [c.get("question", c.get("id")) for c in payload.get("proposed_criteria", [])]
    if criteria:
        lines += ["", "Proposed criteria to weigh them against:", *_bullets(criteria)]
    return [*lines, ""]


def _evidence_lines(payload: Mapping[str, Any]) -> list[str]:
    """Return the readable section of an evidence_bundle.v1 output: findings and sources."""
    findings = [f.get("claim", "") for f in payload.get("findings", [])]
    sources = sorted({e.get("source", {}).get("locator", "") for e in payload.get("evidence", [])}
                     - {""})
    lines = ["## Findings", "", *(_bullets(findings) or ["- No findings were recorded."]), ""]
    if sources:
        lines += ["## Sources", "", *_bullets(sources), ""]
    return lines


def output_sections(schema_id: str | None, payload: Mapping[str, Any] | None) -> list[str]:
    """Return the readable sections for an evidence or options root output (else nothing)."""
    if not payload:
        return []
    if schema_id == schema_ids.OPTIONS:
        return _options_lines(payload)
    if schema_id == schema_ids.EVIDENCE_BUNDLE:
        return _evidence_lines(payload)
    return []


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 22:00 [python-coder]: Ideas are rendered under a heading that says they are
#   proposals and not decisions, next to the unchanged JSON output block. (#KernelBootstrapV0/INTENT)
# - 2026-10-01 22:00 [python-coder]: The "can do" hint is a limitation line (code `can_do`) only
#   when no limitation already explains the stop, so the envelope says it too without repeating
#   what a decline already says. (#KernelBootstrapV0/INTENT)
# ====================================================================
