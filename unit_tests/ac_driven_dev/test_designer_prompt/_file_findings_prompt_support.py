"""
MODULE: unit_tests/ac_driven_dev/test_designer_prompt/_file_findings_prompt_support.py
GOAL: Shared helpers of the G4 prompt tests that pin the file-findings side of the test designer
    (tickets 35, 36, 40), the IT PO next-pass rule (ticket 38) and the test writer's build-from-design
    rule (ticket 32): paragraph-scoped reads of an agent template, parsing of the fenced YAML
    examples a prompt teaches, merging an example into a REAL AC record written through
    yaml.safe_dump, and rendering the prompt through the real scripts/render_effective_prompt.py CLI.
BUSINESS CONTEXT: A prompt is the deliverable of these tickets; what is mechanically decidable
    about it is structure (a section, an example that parses and validates against the real schema)
    and the presence of named rules inside the paragraph that carries them, never a whole-file grep.
ARCHITECTURE: Test-support module (no test_ prefix, so it is not collected). Pure helpers; the only
    I/O is reading the template, the schema and a real AC record, and one subprocess for rendering.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
AGENTS_DIR = REPO / "templates" / "agents"
SCHEMA_FILE = REPO / "config" / "ac_store_schema.json"
RENDER_CLI = REPO / "scripts" / "render_effective_prompt.py"
STORE = REPO / "docs" / "acceptance-criteria" / "ac-driven-dev" / "ACD-2500-right-job-right-agent"
PREPASS_CLI = REPO / "scripts" / "ac_store" / "design_prepass.py"
YAML_FENCE = re.compile(r"```ya?ml\n(.*?)```", re.DOTALL)
HEADING = re.compile(r"^(#{2,4}) (.*)$", re.MULTILINE)
VERDICTS = (
    "consistent", "describes, does not implement", "absent, not to-be-created", "behaviour found elsewhere",
)
CHOICES = ("reassign", "split", "assignment stands")


def flat(text: str) -> str:
    """Prose view: emphasis dropped, whitespace collapsed (a wrapped line is one line)."""
    return re.sub(r"\s+", " ", text.replace("`", "").replace("**", "")).strip()


def template(agent: str) -> str:
    """The agent template WITHOUT its YAML frontmatter (the frontmatter lists output field names and
    would match a paragraph needle by accident)."""
    path = AGENTS_DIR / f"{agent}.md"
    assert path.is_file(), f"{path.relative_to(REPO).as_posix()} does not exist"
    body = path.read_text(encoding="utf-8")
    return re.sub(r"\A---\r?\n.*?\r?\n---\r?\n", "", body, count=1, flags=re.DOTALL)


def paragraphs(text: str) -> list[str]:
    return [flat(block) for block in re.split(r"\n\s*\n", text) if block.strip()]


def matching_paragraphs(text: str, *needles: str) -> list[str]:
    """Every flattened paragraph containing every needle (case-insensitive); fail naming the needles."""
    found = [p for p in paragraphs(text) if all(needle.lower() in p.lower() for needle in needles)]
    if not found:
        pytest.fail(f"no paragraph mentions all of {needles!r}")
    return found


def paragraph_with(text: str, *needles: str) -> str:
    """All paragraphs that mention every needle, joined: a rule holds when any paragraph that is about
    the topic states it (the first match alone could be an unrelated paragraph naming the same words)."""
    return " ".join(matching_paragraphs(text, *needles))


def assert_rendered(rendered: set[str], text: str, *needles: str) -> None:
    """Every paragraph of `text` about `needles` is present verbatim in the rendered prompt."""
    missing = [p for p in matching_paragraphs(text, *needles) if p not in rendered]
    assert not missing, f"paragraph(s) about {needles!r} missing from the rendered prompt: {missing[0][:120]}"


def section_titled(text: str, title_word: str, *body_needles: str) -> str:
    """A level 2-4 section whose heading contains `title_word` and whose body has every needle."""
    heads = list(HEADING.finditer(text))
    for index, head in enumerate(heads):
        if title_word.lower() not in head.group(2).lower():
            continue
        end = next((n.start() for n in heads[index + 1:] if len(n.group(1)) <= len(head.group(1))), len(text))
        body = text[head.start():end]
        if all(needle in body for needle in body_needles):
            return body
    pytest.fail(f"no heading titled {title_word!r} with a body naming {body_needles!r}")


def example_with(text: str, key: str) -> dict:
    """Every fenced YAML mapping of `text` that has `key` at its top level, merged and parsed."""
    merged: dict = {}
    for block in YAML_FENCE.findall(text):
        parsed = yaml.safe_load(block)
        if isinstance(parsed, dict) and key in parsed:
            merged.update(parsed)
    assert isinstance(merged.get(key), list), f"the prompt needs a fenced yaml example with a {key} list"
    return merged


def schema() -> dict:
    return json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))


def schema_property(name: str) -> dict:
    props = schema()["properties"]
    assert name in props, f"config/ac_store_schema.json declares no {name!r} property (it lands with ticket 39)"
    return props[name]


def ac_path(ac_id: str) -> Path:
    found = sorted(STORE.rglob(f"{ac_id}.yaml"))
    assert found, f"AC {ac_id} not found under {STORE}"
    return found[0]


def real_record(ac_id: str) -> dict:
    return yaml.safe_load(ac_path(ac_id).read_text(encoding="utf-8"))


def merged_record(tmp_path: Path, ac_id: str, fragment: dict) -> tuple[dict, dict]:
    """The REAL record with `fragment` merged in, written through yaml.safe_dump and read back."""
    real = real_record(ac_id)
    path = tmp_path / f"{ac_id}.yaml"
    path.write_text(yaml.safe_dump({**real, **fragment}, sort_keys=False), encoding="utf-8")
    return yaml.safe_load(path.read_text(encoding="utf-8")), real


def rendered_prompt_paragraphs(agent: str, ac_id: str, tmp_path: Path) -> list[str]:
    """Paragraphs of the prompt `agent` receives, from the real render CLI run as a subprocess.

    The CLI prefers the DEPLOYED copy under .claude/agents (stale until the build runs), so it is
    pointed at a tmp repo root holding a verbatim copy of the TEMPLATE and of the AC record."""
    template(agent)
    root = tmp_path / "repo"
    (root / "templates" / "agents").mkdir(parents=True)
    shutil.copyfile(AGENTS_DIR / f"{agent}.md", root / "templates" / "agents" / f"{agent}.md")
    folder = root / "docs" / "acceptance-criteria" / "ac-driven-dev"
    folder.mkdir(parents=True)
    shutil.copyfile(ac_path(ac_id), folder / f"{ac_id}.yaml")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, str(RENDER_CLI), "--agent", agent, "--ac", ac_id,
         "--repo-root", str(root), "--out-dir", str(out_dir), "--quiet"],
        capture_output=True, text=True, encoding="utf-8", timeout=120, env=env, cwd=str(REPO),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return paragraphs((out_dir / f"effective_prompt_{agent}_{ac_id}.md").read_text(encoding="utf-8"))


def prepass_report(tmp_path: Path, declared: list[dict], record_fields: dict | None = None) -> dict:
    """Run the REAL pre-pass CLI over a tmp store/repo; the record is written by yaml.safe_dump.

    `declared` entries are {path, state: existing|to_be_created}; a path whose file should exist is
    created in the tmp repo (existing paths listed in record_fields['_create'])."""
    fields = dict(record_fields or {})
    create = fields.pop("_create", [])
    repo, store = tmp_path / "prepass_repo", tmp_path / "prepass_store"
    (store / "x").mkdir(parents=True)
    for rel in create:
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("x\n", encoding="utf-8")
    record = {"id": "T-1", "level": "L2", "declared_files": declared, **fields}
    (store / "x" / "T-1.yaml").write_text(yaml.safe_dump(record), encoding="utf-8")
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, str(PREPASS_CLI), "--ids", "T-1", "--store-root", str(store), "--repo-root", str(repo)],
        capture_output=True, text=True, encoding="utf-8", timeout=60, env=env, cwd=str(REPO),
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["records"][0]
