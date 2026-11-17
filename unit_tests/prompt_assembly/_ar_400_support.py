"""Shared helpers for the AR-400 template-fix test files (TDD red phase).

Every AR-400 test here reads the REAL templates under ``templates/agents`` and
``templates/skills`` and checks the COMPILED prompt, never the template text:

* ``built_prompts(stem)`` runs the real ``build_agents`` phase IN-PROCESS over a copy
  of the real tree (the same seam ``_ar_300ad_support.build_package`` uses -- no
  ``scripts/build.py`` spawn) and returns the compiled prompt from EVERY platform root
  (claude + gemini, ADR-002). The build runs once per test process.
* ``compile_real(stem)`` compiles one real template with the real registry's agents,
  for the checks that need only one compile.

The ``reference gate`` of AR-400a-1 / AR-400b-1 / AR-400f-1 is NOT built yet, so no
helper here calls it; tests that can only be meaningful once it exists are deferred.
"""

from __future__ import annotations

import functools
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import (  # noqa: E402,F401
    REPO_ROOT,
    TEMPLATES_AGENTS,
    ability_rows,
    build_package,
    compile_with,
    installed_skill_ids,
    prose_lines,
    real_slice,
    strip_delivered_sections,
    template_frontmatter,
)
from _ar_300e_support import named_sub_agents, real_known_ids, real_registry, spawn_accounts  # noqa: E402,F401

SKILLS_ROOT = REPO_ROOT / "templates" / "skills"


def template_path(stem: str) -> Path:
    return TEMPLATES_AGENTS / f"{stem}.md"


def compile_real(stem: str) -> str:
    """The real compiler over the real template with the real registry's agents."""
    return compile_with(template_path(stem), agents=real_registry(), skills_root=SKILLS_ROOT)


@functools.lru_cache(maxsize=1)
def _built_roots() -> tuple[Path, ...]:
    """Build the real tree once per process (in-process ``build_agents``, no build.py)."""
    from _pytest.monkeypatch import MonkeyPatch

    base = Path(tempfile.mkdtemp(prefix="ar400_build_"))
    with MonkeyPatch.context() as mp:
        pkg = real_slice(base / "src")
        roots = build_package(pkg, base / "project" / ".leafcutter", mp)
    return tuple(roots)


def built_prompts(stem: str) -> dict[str, str]:
    """``{platform root: compiled prompt text}`` for ``stem``, every root the build wrote."""
    out = {}
    for root in _built_roots():
        prompt = root / f"{stem}.md"
        assert prompt.is_file(), f"build wrote no {stem}.md under {root}"
        out[str(root)] = prompt.read_text(encoding="utf-8")
    assert len(out) >= 2, f"expected both platform roots, got {sorted(out)}"
    return out


def tools_of(stem: str) -> list[str]:
    """The template's declared ``tools:`` as an ordered list of exact tokens."""
    raw = template_frontmatter(template_path(stem)).get("tools") or ""
    return [t.strip() for t in str(raw).split(",") if t.strip()]


def skills_entries(stem: str) -> list[dict]:
    return [e for e in (template_frontmatter(template_path(stem)).get("skills") or []) if isinstance(e, dict)]


def instruction_lines(text: str) -> list[str]:
    """Prose lines of a compiled prompt outside code fences and OUTSIDE the delivered
    abilities section (its table rows quote skill descriptions, not instructions)."""
    return list(prose_lines(strip_delivered_sections(text)))


def abilities_section(text: str) -> str:
    """The delivered abilities section (``## Your Available Skills`` ... next ``## ``)."""
    m = re.search(r"^## Your Available Skills\s*$(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1) if m else ""
