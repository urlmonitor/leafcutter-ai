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
#: Guards and budgets that end a run, as (what was reached, the config key that raises it). The
#: keys are both the guard names of the scheduler and the error codes capabilities report.
GUARDS: dict[str, tuple[str, str]] = {
    "budget_exhausted": ("the Jev call budget", "limits.max_jev_calls"),
    "max_jev_calls": ("the Jev call budget", "limits.max_jev_calls"),
    "max_host_operations": ("the host operation budget", "limits.max_host_operations"),
    "max_active_seconds": ("the active-time budget", "limits.max_active_seconds"),
    "max_cost_usd": ("the cost budget", "limits.max_cost_usd"),
    "max_scheduler_iterations": ("the scheduler iteration limit",
                                 "limits.max_scheduler_iterations"),
    "no_progress": ("the no-progress guard", "limits.no_progress_limit"),
}
_UNRESOLVED_AT = "unresolved_at_"
_MAX_SHOWN = 8
_EXCERPT_CHARS = 240


def guard_hit(limitations: list[str], diagnostics: list[str] | tuple[str, ...] = ()
              ) -> str | None:
    """Return the name of the budget or guard that stopped the run, or None.

    Read from a limitation code (`budget_exhausted: ...`, `unavailable: budget_exhausted`), from the
    `unresolved_at_<guard>` lines a guard stop leaves, or from the `guard: <name>` diagnostic.
    """
    for text in limitations:
        code, _, reason = (part.strip() for part in text.partition(":"))
        if code in GUARDS:
            return code
        if reason in GUARDS:  # `unavailable: budget_exhausted` (a routing step refused for budget)
            return reason
        if code.startswith(_UNRESOLVED_AT) and code[len(_UNRESOLVED_AT):] in GUARDS:
            return code[len(_UNRESOLVED_AT):]
    for text in diagnostics:
        name = text.removeprefix("guard:").strip()
        if text.startswith("guard:") and name in GUARDS:
            return name
    return None


def guard_sentences(guard: str) -> tuple[str, str]:
    """Return (what stopped the run, what the user can do) for a budget or guard."""
    reached, key = GUARDS[guard]
    return (f"The run stopped because {reached} was reached (`{key}` in the kernel config).",
            f"You can raise `{key}` in the kernel config, narrow the question, or decide from "
            "the ranked options if the run listed any.")


def has_plain_reason(limitations: list[str], diagnostics: list[str] | tuple[str, ...] = ()
                     ) -> bool:
    """Return True when a limitation or a guard already explains the stop in plain words."""
    return (any(text.split(":", 1)[0] in _PLAIN_CODES for text in limitations)
            or guard_hit(limitations, diagnostics) is not None)


def can_do_hint() -> str:
    """Return the limitation line that says what the kernel can do and how to rephrase."""
    return (f"can_do: This kernel can {CAN_DO}. Try rephrasing your request, for example "
            + ", ".join(SUGGESTIONS) + ".")


def stop_explanation(status: str, limitations: list[str],
                     diagnostics: list[str] | tuple[str, ...] = ()) -> list[str]:
    """Return report lines saying why a blocked or partial run stopped and what to do next.

    A budget or guard stop names which one was hit and offers what the user can do about it
    (raise the budget, narrow the question, decide from the ranked options); rephrasing is
    suggested only for a request the kernel could not serve at all.
    """
    if status not in ("blocked", "partial"):
        return []
    lines = ["## Why the run stopped", ""]
    reasons = [t.partition(":")[2].strip() or t for t in limitations
               if t.split(":", 1)[0] in _PLAIN_CODES or t.startswith("no_capability")]
    guard = guard_hit(limitations, diagnostics)
    if guard:
        happened, remedy = guard_sentences(guard)
        return [*lines, f"- {happened}", "", f"What you can do: {remedy}", ""]
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


def _by_relevance(evidence: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Return the evidence best first: by the relevance retrieval judged, unjudged items last."""
    def key(item: Mapping[str, Any]) -> float:
        value = (item.get("provenance") or {}).get("relevance")
        return -value if isinstance(value, int | float) else 1.0

    return sorted(evidence, key=key)


def _key_evidence(evidence: list[Mapping[str, Any]]) -> list[str]:
    """Return the most relevant evidence items as `locator: excerpt` bullets (one line each)."""
    lines = []
    for item in _by_relevance(evidence)[:_MAX_SHOWN]:
        where = item.get("source", {}).get("locator", "")
        text = " ".join(str(item.get("excerpt") or "").split())
        lines.append(f"- {where}: {text[:_EXCERPT_CHARS]}{'...' if len(text) > _EXCERPT_CHARS else ''}")
    return lines


def _evidence_lines(payload: Mapping[str, Any]) -> list[str]:
    """Return the readable section of an evidence_bundle.v1 output: findings and sources."""
    findings = [f.get("claim", "") for f in payload.get("findings", [])]
    sources = sorted({e.get("source", {}).get("locator", "") for e in payload.get("evidence", [])}
                     - {""})
    if findings:
        lines = ["## Findings", "", *_bullets(findings), ""]
    elif payload.get("evidence"):
        lines = ["## Key evidence", "",
                 "The run recorded no separate findings; these are the most relevant excerpts as found.", "",
                 *_key_evidence(payload["evidence"]), ""]
    else:
        lines = ["## Findings", "", "- No findings were recorded.", ""]
    lines += _coverage_lines(payload)
    if sources:
        lines += ["## Sources", "", *_bullets(sources), ""]
    return lines


def _coverage_lines(payload: Mapping[str, Any]) -> list[str]:
    """Return the Coverage and Unknowns sections: what is only partly covered or still unknown."""
    lines: list[str] = []
    coverage = {k: v for k, v in (payload.get("coverage") or {}).items()}
    if coverage:
        lines += ["## Coverage", "", *_bullets([f"{need}: {status}" for need, status
                                                 in sorted(coverage.items())]), ""]
    unknowns = [str(u) for u in payload.get("unknowns") or []]
    if unknowns:
        lines += ["## Unknowns", "", *_bullets(unknowns), ""]
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
# - 2026-10-01 [python-coder]: A budget or guard stop names what was hit and the config key that
#   raises it and offers raise-the-budget, narrow-the-question or decide-from-the-ranked-options;
#   "try rephrasing" stays for requests the kernel could not serve (round 6 told a budget stop to
#   rephrase). Evidence bundles gain Coverage and Unknowns sections and key evidence is ordered by
#   judged relevance. (#KernelV01/E)
# - 2026-10-02 [python-coder]: A bundle with evidence but no findings shows its key excerpts
#   instead of only "No findings were recorded". (#KernelBootstrapV0/GROUND)
# - 2026-10-01 22:00 [python-coder]: Ideas are rendered under a heading that says they are
#   proposals and not decisions, next to the unchanged JSON output block. (#KernelBootstrapV0/INTENT)
# - 2026-10-01 22:00 [python-coder]: The "can do" hint is a limitation line (code `can_do`) only
#   when no limitation already explains the stop, so the envelope says it too without repeating
#   what a decline already says. (#KernelBootstrapV0/INTENT)
# ====================================================================
