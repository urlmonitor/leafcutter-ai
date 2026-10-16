"""
MODULE: agent_preparation_delivery
GOAL: Fail the build when a per-agent preparation (an abilities table, a
    placeholder-guarded table, ...) was computed for an agent but did not reach
    that agent's COMPILED prompt, in every platform root the build wrote.
BUSINESS CONTEXT: AR-300b. Two per-agent preparations were once computed and
    discarded for months with every build exiting 0, because no check looked at
    the artefact an agent actually reads. This gate judges the compiled prompt,
    never the point of preparation, and its covered set is DERIVED from what the
    compiler registered, so a preparation added later is covered with no edit
    here. A run that registered nothing, found no prompt, or reached only part of
    the tree fails and says which side came back empty (KI-ACS-001).
ARCHITECTURE: A per-run, module-level registry (``reset_preparations`` /
    ``register_preparation`` / ``get_preparations``) plus a computation ledger
    (``compute_preparation``: a computed-but-unregistered preparation is reported
    with cause ``unregistered``). ``inject_prepared_placeholder`` is the compiler's
    one entry point for a placeholder-guarded table: compute through the ledger,
    register, substitute. ``verify_preparations_delivered`` returns one verdict
    object (ADR-037 shape) for every outcome; ``render_preparation_verdict``
    prints it (the clean path states its counts too); and
    ``refuse_on_undelivered_preparations`` is the build seam, with
    ``refuse_if_agents_compiled`` the build.py entry that applies it only to an
    output root the agents phase actually compiled into. Build-engine module under
    ``scripts/``: it runs from the package source like ``template_compiler`` and
    needs no deploy-manifest entry. ``template_compiler`` is imported lazily to
    avoid an import cycle (the compiler imports this module).

DECISION HISTORY
- 2026-10-09 [python-coder/AR-300b]: Created. The registry is reset by the
  agents phase itself (``build_agents``) rather than by build.py, so consecutive
  in-process builds never inherit each other's registrations and build.py gains
  no extra line; the gate is wired in build.py (not ``build_agents``) because the
  slice-2 in-process builds plant packages with zero preparations. (#AR-300b)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

_PREPARATIONS: list[dict[str, Any]] = []
_COMPUTED: list[tuple[str, str]] = []
_COMPILED: dict[str, int] = {}

# platform key (as in ``config["platforms"]``) -> compiled root relative to the output root
_PLATFORM_ROOTS = (("claude", "agents"), ("antigravity", "gemini/agents"))
_ALL_ROOTS = "all roots"


def reset_preparations() -> None:
    """Clear the run's registrations, computation ledger and compiled-roots record."""
    _PREPARATIONS.clear()
    _COMPUTED.clear()
    _COMPILED.clear()


def register_preparation(preparation_name: str, agent: str, content: str, destination_offered: bool) -> None:
    """Record that ``preparation_name`` was prepared for ``agent`` (a compiled-prompt file stem).

    Args:
        preparation_name: The kind (a placeholder token name, the skills section, ...).
        agent: Stem of the compiled prompt ``<root>/<agent>.md``.
        content: The text the preparation placed (or tried to place).
        destination_offered: Whether the template offered somewhere to put it.
    """
    _PREPARATIONS.append({"preparation_name": preparation_name, "agent": agent,
                          "content": content, "destination_offered": destination_offered})


def get_preparations() -> list[dict[str, Any]]:
    """Return copies of this run's registrations (keys: preparation_name, agent, content, destination_offered)."""
    return [dict(p) for p in _PREPARATIONS]


def compute_preparation(preparation_name: str, agent: str, builder: Callable[[], str]) -> str:
    """Run ``builder`` once, note (name, agent) in the computed ledger, return its text."""
    content = builder()
    _COMPUTED.append((preparation_name, agent))
    return content


def inject_prepared_placeholder(body: str, token: str, agent: str | None, builder: Callable[[], str]) -> str:
    """Replace ``{{token}}`` in ``body`` with the built content, registering it for ``agent``.

    When the placeholder is absent nothing is computed or registered. When
    ``agent`` is None the substitution is made without touching the registry
    (callers that only render for a hash).

    Args:
        body: Text that may contain the placeholder.
        token: Placeholder name without braces (also the preparation name).
        agent: Stem of the compiled prompt, or None to skip registration.
        builder: Zero-argument callable producing the content.

    Returns:
        ``body`` with every ``{{token}}`` replaced.
    """
    placeholder = "{{" + token + "}}"
    if placeholder not in body:
        return body
    if agent is None:
        return body.replace(placeholder, builder())
    content = compute_preparation(token, agent, builder)
    register_preparation(token, agent, content, True)
    return body.replace(placeholder, content)


def _is_agent_prompt(text: str) -> bool:
    """True when ``text`` is an agent prompt: its own frontmatter carries a ``name``."""
    from template_compiler import parse_frontmatter  # noqa: PLC0415 - import cycle

    fm, _body = parse_frontmatter(text)
    return isinstance(fm, dict) and bool(fm.get("name"))


def note_compiled_agent(output_root: Path, compiled: str) -> None:
    """Record that the agents phase compiled one more agent prompt into ``output_root``.

    Helper templates that compile to something without a ``name`` are not agent
    prompts and are not counted (the gate never examines them either).
    """
    if _is_agent_prompt(compiled):
        _COMPILED[str(output_root)] = _COMPILED.get(str(output_root), 0) + 1


def _norm(text: str) -> str:
    """Whitespace-normalise ``text`` (the comparison form for 'delivered')."""
    return " ".join(text.split())


def _read_prompts(root: Path) -> dict[str, str]:
    """Return {stem: normalised text} for every agent prompt (frontmatter ``name``) in ``root``."""
    prompts: dict[str, str] = {}
    for path in sorted(root.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if _is_agent_prompt(text):
            prompts[path.stem] = _norm(text)
    return prompts


def _load_root(root: Path, findings: list[dict[str, Any]]) -> dict[str, str] | None:
    """Read one compiled root; on an unreadable root append an ``unreadable-root`` finding."""
    if not root.is_dir():
        findings.append({"kind": "unreadable-root", "platform_root": str(root)})
        return None
    try:
        return _read_prompts(root)
    except (OSError, UnicodeDecodeError) as exc:
        _log.warning("cannot read compiled root %s: %s", root, exc)
        findings.append({"kind": "unreadable-root", "platform_root": str(root), "reason": str(exc)})
        return None


def _cause(prep: dict[str, Any], prompt_text: str | None) -> str | None:
    """Return why ``prep`` did not arrive (closed set) or None when it is delivered."""
    content = _norm(prep["content"])
    if not content:
        return "empty-preparation"
    if prompt_text is not None and content in prompt_text:
        return None
    return "no-destination"


def _judge_root(preps: list[dict[str, Any]], prompts: dict[str, str], root: str) -> list[dict[str, Any]]:
    """One finding per (agent, preparation) registered for an agent that did not receive it in ``root``."""
    found = []
    for prep in preps:
        cause = _cause(prep, prompts.get(prep["agent"]))
        if cause:
            found.append({"agent": prep["agent"], "preparation": prep["preparation_name"],
                          "platform_root": root, "cause": cause})
    return found


def _unregistered(preps: list[dict[str, Any]], computed: list[tuple[str, str]]) -> list[dict[str, Any]]:
    """Findings for preparations computed through the ledger but never registered."""
    registered = {(p["preparation_name"], p["agent"]) for p in preps}
    return [{"agent": agent, "preparation": name, "platform_root": _ALL_ROOTS, "cause": "unregistered"}
            for name, agent in dict.fromkeys(computed) if (name, agent) not in registered]


def _population_findings(preps: list[Any], computed: list[Any], inspected: int, expected: int) -> list[dict[str, Any]]:
    """Findings about the examined population itself (empty or short sides)."""
    found: list[dict[str, Any]] = []
    if not preps and not computed:
        found.append({"kind": "empty-population", "side": "preparations"})
    if inspected == 0:
        found.append({"kind": "empty-population", "side": "compiled_prompts"})
    if inspected < expected:
        found.append({"kind": "short-population", "inspected": inspected, "expected": expected})
    return found


def verify_preparations_delivered(compiled_roots: list[Path], *, expected_prompt_count: int,
                                  preparations: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Judge, from the compiled prompts, whether every registered preparation reached its agent.

    Never raises on an empty or short population. Judgement is per
    (agent, preparation, root) over the agents each preparation was REGISTERED
    FOR. Delivered means the whitespace-normalised content occurs in the
    whitespace-normalised prompt.

    Args:
        compiled_roots: Compiled agent-prompt directories (one per platform).
        expected_prompt_count: Prompts the build compiled (templates x roots).
        preparations: Registrations to judge; None reads the run registry and
            computation ledger.

    Returns:
        Verdict dict: ok, inspected_prompt_count, inspected_preparation_kinds,
        preparation_kinds, expected_prompt_count, roots_examined,
        population_source, affected_agent_counts, findings.
    """
    if preparations is None:
        raw, computed, source = get_preparations(), list(_COMPUTED), "run registry and computation ledger"
    else:
        raw, computed, source = [dict(p) for p in preparations], [], "supplied preparations"
    preps = list({(p["preparation_name"], p["agent"]): p for p in raw}.values())
    findings: list[dict[str, Any]] = []
    inspected = 0
    for root in compiled_roots:
        prompts = _load_root(Path(root), findings)
        if prompts is not None:
            inspected += len(prompts)
            findings.extend(_judge_root(preps, prompts, str(root)))
    findings.extend(_unregistered(preps, computed))
    findings.extend(_population_findings(preps, computed, inspected, expected_prompt_count))
    affected: dict[str, set[str]] = {}
    for f in findings:
        if "agent" in f:
            affected.setdefault(f["preparation"], set()).add(f["agent"])
    kinds = sorted({p["preparation_name"] for p in preps})
    return {"ok": not findings, "inspected_prompt_count": inspected,
            "inspected_preparation_kinds": len(kinds), "preparation_kinds": kinds,
            "expected_prompt_count": expected_prompt_count,
            "roots_examined": [str(r) for r in compiled_roots], "population_source": source,
            "affected_agent_counts": {k: len(v) for k, v in sorted(affected.items())},
            "findings": findings}


def _finding_line(finding: dict[str, Any]) -> str:
    """One report line for a finding (agent and preparation named, or the population fact)."""
    if "agent" in finding:
        return (f"  agent={finding['agent']} preparation={finding['preparation']} "
                f"root={finding['platform_root']} cause={finding['cause']}")
    return "  " + " ".join(f"{k}={v}" for k, v in finding.items())


def _headline(verdict: dict[str, Any]) -> str:
    """First report line: the counts, or 'nothing to examine' naming the empty side(s)."""
    sides = [f["side"] for f in verdict["findings"] if f.get("kind") == "empty-population"]
    if sides:
        names = " and no ".join(s.replace("_", " ") for s in sides)
        return f"agent preparation delivery: FAILED -- nothing to examine: no {names}"
    status = "ok" if verdict["ok"] else "FAILED"
    return (f"agent preparation delivery: {status} -- {verdict['inspected_preparation_kinds']} "
            f"preparation kinds checked across {verdict['inspected_prompt_count']} compiled prompts")


def render_preparation_verdict(verdict: dict[str, Any]) -> str:
    """Render the verdict as text; the first line carries the counts (or 'nothing to examine')."""
    lines = [_headline(verdict)]
    lines += [f"preparation {name}: {n} agents affected"
              for name, n in verdict["affected_agent_counts"].items()]
    lines += [_finding_line(f) for f in verdict["findings"]]
    return "\n".join(lines)


def _compiled_roots(project_root: Path, config: dict[str, Any]) -> list[Path]:
    """The compiled roots under the DECLARED output root, for the active platforms."""
    platforms = config.get("platforms", {"claude": True, "antigravity": True})
    out = Path(project_root) / config.get("output_root", ".leafcutter")
    return [out / sub for platform, sub in _PLATFORM_ROOTS if platforms.get(platform)]


def refuse_on_undelivered_preparations(project_root: Path, config: dict[str, Any], dry_run: bool, *,
                                       expected_prompt_count: int) -> int:
    """Build seam: print the verdict (clean runs too) and return 1 to refuse, else 0.

    Args:
        project_root: Project root the build wrote into.
        config: Build config; ``output_root`` and ``platforms`` select the roots.
        dry_run: When True nothing was written, so there is nothing to judge.
        expected_prompt_count: Prompts the build compiled (templates x roots).

    Returns:
        1 when any finding exists, otherwise 0.
    """
    if dry_run:
        print("agent preparation delivery: skipped (dry-run writes no compiled prompts)")
        return 0
    verdict = verify_preparations_delivered(
        _compiled_roots(project_root, config), expected_prompt_count=expected_prompt_count)
    print(render_preparation_verdict(verdict))
    return 0 if verdict["ok"] else 1


def refuse_if_agents_compiled(project_root: Path, config: dict[str, Any], dry_run: bool) -> int:
    """build.py entry: apply the gate only to an output root the agents phase compiled into.

    Returns 0 (nothing to judge) when this process's agents phase never compiled
    into the declared output root; otherwise the seam's result.
    """
    compiled = _COMPILED.get(str(Path(project_root) / config.get("output_root", ".leafcutter")))
    if compiled is None:
        print("agent preparation delivery: skipped -- no agents were compiled in this run")
        return 0
    from agent_grant_delivery_gate import refuse_if_grants_undelivered  # noqa: PLC0415 - import cycle

    roots = _compiled_roots(project_root, config)
    expected = compiled * len(roots)
    prep = refuse_on_undelivered_preparations(project_root, config, dry_run, expected_prompt_count=expected)
    grants = refuse_if_grants_undelivered(project_root, config, dry_run, compiled_roots=roots, expected=expected)
    return prep or grants
