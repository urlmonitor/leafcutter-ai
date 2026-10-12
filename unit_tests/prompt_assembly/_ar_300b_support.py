"""Shared helpers for the AR-300b test files (slice 3, test-writer, TDD red phase).
Imports -- never edits -- the slice 1/2 helpers in ``_ar_300ad_support.py``.

ASSUMED PRODUCTION CONTRACT FOR SLICE 3 (the ACs do not name these identifiers,
so the test-writer fixed them here; python-coder builds to them unless a
documented, justified reason changes them). One NEW module,
``scripts/agent_preparation_delivery.py`` (build-engine module; the wiring
edits to template_compiler.py / build_phases_agents_skills.py / build.py must be
net-neutral or shorter -- those files are over the size ratchet).

A. REGISTRATION (AR-300b-2). A per-run, module-level registry, the SOLE source
   of the set the gate covers::

       reset_preparations() -> None
       register_preparation(preparation_name: str, agent: str, content: str,
                            destination_offered: bool) -> None
       get_preparations() -> list[dict]     # copies; keys exactly
           # preparation_name, agent, content, destination_offered

   ``agent`` is the compiled prompt's file stem (the name ``<root>/<agent>.md``
   bears). ``compile_agent_template`` registers EVERY per-agent preparation it
   computes (placeholder-guarded tables, the declared-skills section, ...)
   through ``register_preparation``, recording whether a destination was
   offered, independent of the placement mechanism. build.py calls
   ``reset_preparations()`` before the phases run; the in-process tests call it
   themselves. A preparation an agent is not granted (nothing prepared) is NOT
   registered. ``content`` is the text the preparation placed (or tried to).
   Computation ledger -- the "forgot to register" guard::

       compute_preparation(preparation_name: str, agent: str,
                           builder: Callable[[], str]) -> str

   calls ``builder()``, notes (name, agent) in the run's computed ledger and
   returns the content. A ledger entry with no matching ``register_preparation``
   by verdict time is reported (cause ``unregistered``). The compiler computes
   through it, so a ninth preparation cannot be silently outside the registry.

B. VERDICT (ADR-037 shape; ONE object for AR-300b-1/-1-i/-1-ii/-2/-3/-4)::

       verify_preparations_delivered(compiled_roots: list[Path], *,
                                     expected_prompt_count: int,
                                     preparations: list[dict] | None = None) -> dict

   ``preparations=None`` reads the run registry (``get_preparations()`` plus the
   computed ledger); a supplied list is used as-is (the gate is runnable against
   a supplied compiled tree, independent of a build). Never raises on an empty
   or short population. Keys::

       ok                         bool   (== not findings)
       inspected_prompt_count     int    prompts read across ALL roots
       inspected_preparation_kinds int   distinct preparation_name values covered
       preparation_kinds          [str]  sorted distinct names covered (the DERIVED set)
       expected_prompt_count      int
       roots_examined             [str]
       population_source          str    non-empty
       affected_agent_counts      {preparation_name: distinct agents with a per-agent finding}
       findings                   [dict]

   ``platform_root`` is the root path as supplied, as ``str``.
   Per-agent finding (judged once per (agent, preparation, platform root), over
   the agents the preparation was REGISTERED FOR, not the agents it was found
   in)::

       {"agent", "preparation", "platform_root", "cause"}

   ``cause`` is a closed value: ``no-destination`` (destination_offered False,
   non-empty content, absent from the prompt), ``empty-preparation`` (content
   empty), ``unregistered`` (computed-ledger entry never registered). Content is
   "delivered" when its whitespace-normalised text occurs in the
   whitespace-normalised compiled prompt. A registered agent with NO prompt in a
   root is a per-agent finding too. Population findings carry ``kind``:
   ``empty-population`` + ``side`` in {"preparations", "compiled_prompts"} (one
   per empty side), ``short-population`` + ``inspected`` + ``expected``,
   ``unreadable-root`` + ``platform_root`` (missing path / broken symlink).

   ``render_preparation_verdict(verdict) -> str``: human summary; its first
   line contains ``<K> preparation kind(s) checked across <N> compiled
   prompt(s)`` (regex ``(\\d+) preparation kinds? checked across (\\d+) compiled
   prompts?``); a verdict with an ``empty-population`` finding instead says
   ``nothing to examine`` and names the empty side; a failing verdict lists each
   finding with its agent and preparation names and the
   affected-agent count per preparation.

C. BUILD SEAM::

       refuse_on_undelivered_preparations(project_root: Path, config: dict,
                                          dry_run: bool, *,
                                          expected_prompt_count: int) -> int

   Resolves the compiled roots from the DECLARED output root
   (``project_root / config["output_root"]`` -> ``agents`` and
   ``gemini/agents``; never ``.claude/agents``), runs the verdict against the
   run registry, PRINTS ``render_preparation_verdict`` (clean runs included) and
   every finding, returns 1 to refuse (any finding) else 0. build.py calls it
   after the phases and exits non-zero on 1.

D. SPAWN ALLOWLIST. After slice 2 ``build_per_agent_spawn_table`` is computed by
   NO build step (its placeholder gate was removed), so nothing is prepared for
   it and nothing is dropped. The ACs do not decide whether it is delivered or
   retired; these tests accept EITHER (whole-population invariant: every
   registered preparation is delivered) and pin only that a spawn-allowlist
   preparation, when registered, is gated like any other (real builder output is
   used as the content in the independence tests).

E. NAMES. ``preparation_name`` of a placeholder-guarded injection is its
   placeholder token name without braces (``project_paths_table``,
   ``doc_type_reference_table``, ``doc_types_dispatch_table``,
   ``agent_priority_table``, ``registry_phase_agents_table``); the declared-skills
   section's name is free (the tests locate it by content, never by name).

Evidence is always the COMPILED prompt (real in-process build_agents output, or
a real build.py run); the registry supplies only the population.
"""

from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import (  # noqa: E402,F401
    REPO_ROOT,
    agent_fm,
    agent_prompts,
    build_package,
    planted_package,
    real_slice,
    source_templates,
    strip_delivered_sections,
    write_compiled_tree,
)

SKILLS = {
    "zz-alpha": "Alpha skill forges alpha widgets on request",
    "zz-beta": "Beta skill audits beta ledgers before release",
    "zz-gamma": "Gamma skill reconciles gamma queues nightly",
}
BODY = "# Agent\n\nDo the work.\n"
COUNTS_RE = re.compile(r"(\d+) preparation kinds? checked across (\d+) compiled prompts?")


def prep_module():
    """Import the (not-yet-written) delivery gate module: a clear red when absent."""
    return importlib.import_module("agent_preparation_delivery")


def grant(*ids: str) -> list[dict]:
    return [{"skill_id": i, "mode": "always"} for i in ids]


def default_templates() -> dict:
    """Three granted agents and one ungranted agent that offers a placeholder."""
    return {
        "zz-holder-a": (agent_fm("zz-holder-a", grant("zz-alpha", "zz-beta")), BODY),
        "zz-holder-b": (agent_fm("zz-holder-b", grant("zz-alpha")), BODY),
        "zz-holder-c": (agent_fm("zz-holder-c", grant("zz-gamma")), BODY),
        "zz-plain": (agent_fm("zz-plain"), BODY + "\n{{project_paths_table}}\n"),
    }


def registry_for(templates: dict) -> list[dict]:
    """Registry records consistent with ``templates`` (each lists two other agents to spawn)."""
    ids = sorted(templates)
    return [
        {"id": stem, "template_path": f"templates/agents/{stem}.md", "role": f"{stem} role",
         "tier": "phase", "is_ticket_phase": False,
         "spawn_allowlist": [i for i in ids if i != stem][:2], "skills_used": [],
         "skills_invoked": [dict(e) for e in fm.get("skills", [])]}
        for stem, (fm, _b) in templates.items()
    ]


@dataclass
class Built:
    mod: object
    project: Path
    out_root: Path
    roots: list[Path]
    preparations: list[dict]
    registry: list[dict]
    expected: int
    templates: dict


def fresh_build(tmp_path: Path, monkeypatch, templates: dict | None = None) -> Built:
    """Reset the run registry, run the REAL ``build_agents`` in-process over a
    planted package and return the compiled roots plus what the build registered."""
    mod = prep_module()
    mod.reset_preparations()
    templates = templates or default_templates()
    registry = registry_for(templates)
    pkg = planted_package(tmp_path / "src", templates, SKILLS, registry_agents=registry)
    project = tmp_path / "project"
    roots = build_package(pkg, project / ".leafcutter", monkeypatch)
    return Built(mod, project, project / ".leafcutter", roots, list(mod.get_preparations()),
                 registry, len(templates) * len(roots), templates)


def verdict_of(mod, roots, preparations, expected) -> dict:
    return mod.verify_preparations_delivered(
        list(roots), expected_prompt_count=expected, preparations=list(preparations))


def per_agent(verdict: dict) -> list[dict]:
    return [f for f in verdict["findings"] if "agent" in f]


def population(verdict: dict, kind: str) -> list[dict]:
    return [f for f in verdict["findings"] if f.get("kind") == kind]


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def norm(text: str) -> str:
    return " ".join(text.split())


def entry(name: str, agent: str, content: str, offered: bool = True) -> dict:
    return {"preparation_name": name, "agent": agent, "content": content,
            "destination_offered": offered}


def block_for(name: str, agent: str) -> str:
    """A distinctive compiled-prompt block a synthetic preparation delivers."""
    return f"## ZZ {name}\n\nblock {name} prepared for {agent} only.\n"


def append_block(roots, stems, text: str) -> None:
    for root in roots:
        for stem in stems:
            p = root / f"{stem}.md"
            p.write_text(p.read_text(encoding="utf-8").rstrip("\n") + "\n\n" + text, encoding="utf-8")


def strip_abilities(roots, stems) -> None:
    """Break ONLY the compiled artifact: drop the delivered abilities section."""
    for root in roots:
        for stem in stems:
            p = root / f"{stem}.md"
            old = p.read_text(encoding="utf-8")
            new = strip_delivered_sections(old)
            assert new != old, f"control: {p} had no abilities section to strip"
            p.write_text(new, encoding="utf-8")


def abilities_preps(preparations: list[dict], agent: str, skill_id: str) -> list[dict]:
    """Registrations for ``agent`` whose content names ``skill_id`` (the abilities
    preparation, located by content so the test pins no preparation name)."""
    return [p for p in preparations if p["agent"] == agent and skill_id in p["content"]]


def spawn_entry(built: Built, stem: str, name: str = "zz-spawn-allowlist") -> dict:
    """The spawn-allowlist preparation as the REAL builder renders it for ``stem``."""
    import injection_builders  # noqa: PLC0415

    return entry(name, stem, injection_builders.build_per_agent_spawn_table(stem, built.registry))


def deliver_spawn(built: Built) -> list[dict]:
    """Deliver the real spawn table into every compiled prompt; return its entries."""
    entries = []
    for stem in built.templates:
        e = spawn_entry(built, stem)
        append_block(built.roots, [stem], e["content"])
        entries.append(e)
    return entries


def copy_roots(roots, dst: Path) -> list[Path]:
    """Byte copies of compiled roots (``agents`` / ``gemini/agents`` layout kept)."""
    import shutil  # noqa: PLC0415

    out = []
    for root in roots:
        target = dst / root.parent.name / root.name if root.parent.name == "gemini" else dst / root.name
        shutil.copytree(root, target)
        out.append(target)
    return out


def remove_text(roots, stems, text: str) -> None:
    """Remove a delivered block from compiled prompts (control: it was there)."""
    for root in roots:
        for stem in stems:
            p = root / f"{stem}.md"
            old = p.read_text(encoding="utf-8")
            assert text in old, f"control: block absent from {p} before removal"
            p.write_text(old.replace(text, ""), encoding="utf-8")


def undelivered_names(preparations: list[dict], stem: str, root: Path) -> set[str]:
    """Independent oracle: names registered for ``stem`` whose content is absent
    from the compiled prompt in ``root`` (whitespace-normalised)."""
    text = norm((root / f"{stem}.md").read_text(encoding="utf-8"))
    return {p["preparation_name"] for p in preparations
            if p["agent"] == stem and norm(p["content"]) and norm(p["content"]) not in text}


def real_build(tmp_path: Path, monkeypatch) -> Built:
    """The REAL ``build_agents`` phase in-process over a copy of the actual
    templates/agents + skills + registry (the tracked tree), registry reset first."""
    import json  # noqa: PLC0415

    mod = prep_module()
    mod.reset_preparations()
    pkg = real_slice(tmp_path / "src")
    project = tmp_path / "project"
    roots = build_package(pkg, project / ".leafcutter", monkeypatch)
    stems = [t.stem for t in source_templates()]
    registry = json.loads((pkg / "config" / "agent_registry.json").read_text("utf-8"))["agents"]
    return Built(mod, project, project / ".leafcutter", roots, list(mod.get_preparations()),
                 registry, len(stems) * len(roots), {s: None for s in stems})


# ---- real build.py mutation: break only the compiled artifact -------------------
WRAPPER_SOURCE = '''
import os, re, runpy, sys
from pathlib import Path
build = sys.argv[1]
sys.path.insert(0, os.path.dirname(build))
import build_phases as bp
_HEAD = re.compile(r"^#{2,3}\\s+(?:your\\s+)?(?:available\\s+)?(?:skills?|abilit(?:y|ies))\\s*$", re.I)
def strip(text):
    out, skipping = [], False
    for line in text.split("\\n"):
        if line.startswith("## "):
            skipping = bool(_HEAD.match(line))
            if skipping:
                continue
        if not skipping:
            out.append(line)
    return "\\n".join(out).rstrip("\\n") + "\\n"
_orig = bp._write
def _write(path, content, dry_run, force):
    if Path(path).parent.name == "agents" and isinstance(content, str):
        content = strip(content)
    return _orig(path, content, dry_run, force)
bp._write = _write
sys.argv = sys.argv[1:]
runpy.run_path(build, run_name="__main__")
'''


def run_real_build(layout: Path, work: Path, *, strip_compiled_abilities: bool) -> subprocess.CompletedProcess:
    """Run the layout's own build.py. With ``strip_compiled_abilities`` the
    compiled agent prompts are written with the abilities section removed (the
    preparation is still computed from correct inputs; only the artifact breaks)."""
    build = layout / "scripts" / "build.py"
    if strip_compiled_abilities:
        wrapper = work / "build_with_stripped_compiled_output.py"
        wrapper.write_text(WRAPPER_SOURCE, encoding="utf-8")
        argv = [sys.executable, str(wrapper), str(build), "--target-dir", str(layout)]
    else:
        argv = [sys.executable, str(build), "--target-dir", str(layout)]
    return subprocess.run(argv, cwd=str(layout), capture_output=True, text=True,
                          timeout=420, check=False)
