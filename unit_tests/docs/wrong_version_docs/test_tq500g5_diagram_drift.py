"""
MODULE: test_tq500g5_diagram_drift
GOAL: Keep the wrong-version runner's C3 component diagram and run-sequence diagram
    in step with the code: the component diagram names every CLI script of the
    family and the route workflow files; the sequence diagram carries every result
    word a run can produce and both stop values.
BUSINESS CONTEXT: TQ-500g-5-i (component diagram) and TQ-500g-5-ii (sequence
    diagram). Vocabularies come from the code via the reference-drift helpers.
AC: TQ-500g-5-i, TQ-500g-5-ii
"""

from __future__ import annotations


from unit_tests.docs.wrong_version_docs.test_tq500g5_reference_drift import (
    ROOT,
    SCRIPTS,
    missing_words,
    result_words,
    stop_values,
)

DIAGRAMS = ROOT / "docs" / "architecture" / "diagrams"
COMPONENTS = DIAGRAMS / "c3-035-wrong-version-runner-components.md"
SEQUENCE = DIAGRAMS / "c3-036-wrong-version-run-sequence.md"
WORKFLOWS = ROOT / "templates" / "workflows-js"
ROUTE_WORKFLOWS = ("fast-lane-ship.js", "build-feature.js", "build-ticket.js", "build-epic.js")


def cli_scripts() -> list[str]:
    """The family's CLI scripts: wrong_version_*.py and consumer_sweep.py (a public ``__main__`` entry)."""
    names = [p.name for p in SCRIPTS.glob("wrong_version_*.py")] + ["consumer_sweep.py"]
    return sorted(n for n in names if "if __name__" in (SCRIPTS / n).read_text(encoding="utf-8"))


def test_ac_tq500g5_i_component_diagram_names_every_cli_and_route_workflow():
    # covers: TQ-500g-5-i
    # angle: criterion
    assert {"wrong_version_writer.py", "wrong_version_gate.py", "wrong_version_runner.py",
            "consumer_sweep.py"} <= set(cli_scripts())
    text = COMPONENTS.read_text(encoding="utf-8")
    assert missing_words(cli_scripts(), text) == []
    for wf in ROUTE_WORKFLOWS:
        assert (WORKFLOWS / wf).exists(), wf
    assert missing_words(ROUTE_WORKFLOWS, text) == []
    # discrimination: dropping one name must be noticed
    assert missing_words(cli_scripts(), text.replace("wrong_version_writer.py", "")) == ["wrong_version_writer.py"]


def test_ac_tq500g5_ii_sequence_diagram_has_every_result_word_and_both_stops():
    # covers: TQ-500g-5-ii
    # angle: criterion
    text = SEQUENCE.read_text(encoding="utf-8")
    assert stop_values() == {"sweep", "write"}
    assert missing_words(result_words(), text) == []
    assert missing_words({f'stopped_at: "{s}"' for s in stop_values()}, text) == []
    # discrimination: dropping a result word or a stop value must be noticed
    assert missing_words(result_words(), text.replace("not_applied", "")) == ["not_applied"]
    assert missing_words({'stopped_at: "write"'}, text.replace('stopped_at: "write"', "")) == ['stopped_at: "write"']
