"""
MODULE: test_inf_500d_4_iv_usable_stream_parity
GOAL: Pin that the ONE usable-stream rule and its inline copy agree.
AC: INF-500d-4-iv (writers default to the declared root; with no usable declaration
    emit_event warns, names it and writes nothing); ADR-069 section 4.

``scripts/knowledge/sink_resolution.read_usable_stream`` is the rule. ``emit_event.py``
must stay standard-library-only, so it carries an inline copy in ``_declared_stream``.
Two copies drift silently: each is right about the value it computes. This table feeds
the SAME declaration files to both and asserts they agree on usable / unusable (and,
when usable, on the stream they return).

REAL-ARTIFACT NOTE: declarations come from the real build helper and are round-tripped
    through ``h.rewrite_declaration`` (or written with ``json.dumps`` for the shapes the
    helper cannot produce). Both functions are loaded in a FRESH subprocess, never via
    importlib.reload, and the deployed copies are the ones loaded.
"""
# @ac-tag: INF-500d-4-iv

from __future__ import annotations

import json
from pathlib import Path

import pytest

from unit_tests.feedback import _inf_500d_4_helpers as h

_STREAM = "operational_telemetry_stream"

_PROBE = """
import importlib.util, json, sys
from pathlib import Path
out_root, emit_path, cases = Path(sys.argv[1]), Path(sys.argv[2]), json.loads(sys.argv[3])
sys.path.insert(0, str(out_root / "scripts" / "knowledge"))
import sink_resolution
spec = importlib.util.spec_from_file_location("emit_event_under_test", emit_path)
emit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(emit)
result = {}
for name, root in cases.items():
    root = Path(root)
    shared, shared_why = sink_resolution.read_usable_stream(root, "operational_telemetry_stream")
    inline, inline_why = emit._declared_stream(root / "config" / "knowledge_sink.json")
    result[name] = {
        "shared": str(shared) if shared is not None else None, "shared_why": shared_why,
        "inline": str(inline) if inline is not None else None, "inline_why": inline_why,
    }
print(json.dumps(result))
"""


def _case_roots(base: Path) -> tuple[dict[str, Path], Path]:
    """One deployed install per declaration shape; returns ``({name: out_root}, the valid log root)``."""
    enduring = base / "enduring" / "debugging" / "logs"
    enduring.mkdir(parents=True)
    other = base / "elsewhere"
    roots: dict[str, Path] = {}

    def install(name: str) -> Path:
        project = base / name
        project.mkdir()
        roots[name] = h.deploy_install(project)
        return roots[name]

    install("absent")  # no declaration written
    (install("empty_object") / "config" / "knowledge_sink.json").write_text("{}\n", encoding="utf-8")
    (install("unparseable") / "config" / "knowledge_sink.json").write_text("{not json", encoding="utf-8")
    (install("not_an_object") / "config" / "knowledge_sink.json").write_text("[1, 2]\n", encoding="utf-8")

    h.declare(install("valid"), enduring)
    h.declare(install("no_root"), enduring)
    h.rewrite_declaration(roots["no_root"], operational_log_root=None)
    h.declare(install("relative_root"), enduring)
    h.rewrite_declaration(roots["relative_root"], operational_log_root="debugging/logs")
    h.declare(install("stream_outside_root"), enduring)
    h.rewrite_declaration(roots["stream_outside_root"], **{_STREAM: str(other / "agent_telemetry.jsonl")})
    h.declare(install("stream_nested_two_levels_under_root"), enduring)
    h.rewrite_declaration(roots["stream_nested_two_levels_under_root"],
                          **{_STREAM: str(enduring / "sub" / "deeper" / "agent_telemetry.jsonl")})
    h.declare(install("relative_stream"), enduring)
    h.rewrite_declaration(roots["relative_stream"], **{_STREAM: "agent_telemetry.jsonl"})
    h.declare(install("no_stream"), enduring)
    h.rewrite_declaration(roots["no_stream"], **{_STREAM: None})
    return roots, enduring


def test_both_copies_of_the_usable_stream_rule_agree_on_every_declaration_shape(tmp_path):
    # covers: INF-500d-4-iv
    # angle: seam
    """The same declaration, fed to sink_resolution.read_usable_stream and emit_event._declared_stream, is
    usable to both or unusable to both -- and a usable one yields the same stream. The exact expectations
    (only the valid declaration is usable) keep the table from agreeing vacuously on 'everything unusable'."""
    tmpdir = tmp_path / "tmpdir"
    tmpdir.mkdir()
    roots, enduring = _case_roots(tmp_path)
    emit_path = roots["valid"].parent / ".claude" / "skills" / "agent-telemetry" / "scripts" / "emit_event.py"
    assert emit_path.is_file(), "fixture: the deployed emit_event.py must exist"

    proc = h.run_code(_PROBE, [str(roots["valid"]), str(emit_path), json.dumps({k: str(v) for k, v in roots.items()})],
                      tmp_path, tmpdir)
    assert proc.returncode == 0, f"the probe could not load both copies in a fresh process:\n{proc.stderr}"
    verdicts = json.loads(proc.stdout)
    assert set(verdicts) == set(roots) and len(verdicts) == 11, f"the table must cover all 11 shapes: {sorted(verdicts)}"

    disagreements = {
        name: v for name, v in verdicts.items()
        if (v["shared"] is None) != (v["inline"] is None) or (v["shared"] != v["inline"])
    }
    assert not disagreements, (
        f"the two copies of the usable-stream rule disagree (a FINDING): {json.dumps(disagreements, indent=2)}")

    usable = {name for name, v in verdicts.items() if v["shared"] is not None}
    assert usable == {"valid"}, f"only the valid declaration is usable; got {sorted(usable)}"
    assert verdicts["valid"]["shared"] == str(enduring / "agent_telemetry.jsonl")
    for name, v in verdicts.items():
        if name != "valid":
            assert v["shared_why"] and v["inline_why"], f"{name}: both copies must say why it is unusable"


@pytest.mark.parametrize("shape", ["no_root", "relative_root", "empty_object"])
def test_a_root_problem_is_named_by_the_shared_rule_and_the_inline_copy_alike(tmp_path, shape):
    # covers: INF-500d-4-iv
    # angle: boundary
    """Both copies name operational_log_root for every root problem (the writers' refusal text depends on it)."""
    tmpdir = tmp_path / "tmpdir"
    tmpdir.mkdir()
    roots, _enduring = _case_roots(tmp_path)
    emit_path = roots["valid"].parent / ".claude" / "skills" / "agent-telemetry" / "scripts" / "emit_event.py"
    proc = h.run_code(_PROBE, [str(roots["valid"]), str(emit_path), json.dumps({shape: str(roots[shape])})],
                      tmp_path, tmpdir)
    assert proc.returncode == 0, proc.stderr
    verdict = json.loads(proc.stdout)[shape]
    assert "operational_log_root" in verdict["shared_why"], verdict
    assert "operational_log_root" in verdict["inline_why"], verdict
