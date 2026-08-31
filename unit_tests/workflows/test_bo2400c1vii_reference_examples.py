"""The worked examples in the fast-lane prompt-caching reference must actually run.

BO-2400c-1-vii. A reference page's examples are the part readers copy, so the
one claim about that page a machine can genuinely settle is whether calling
them against the real function works. This file settles it by EXECUTING every
``python`` block on the page against the real ``assemble_context_bundle`` --
not by searching the page for the names of removed parameters.

Why that distinction is the whole point of this file: a test asserting the
string ``conventions`` is absent from the page passes the moment somebody
deletes a word, while the ordering contract, the required-parameter count or
the caching claim stay wrong. It is also satisfied by a page with no examples
at all. Executing the examples cannot be satisfied that way -- an example that
passes a parameter the function no longer accepts raises ``TypeError`` here,
and an example that drifts from the signature in any other direction raises
too.

This is the same standard BO-2400c-1-vi's tests are held to (real subprocess,
assert on real output), applied to the documentation surface rather than the
code surface.

WHY THE THREE EXAMPLE TESTS ARE NOT PARAMETRIZED (KI-BO-20260826-1900):
the natural shape here is one parametrized test over the example blocks, and
that shape is unmergeable. The done-proof gate resolves a ``# covers:`` tag to
a pytest nodeid via ``nodeid.endswith("::" + func_name)``
(scripts/ac_store/done_proof.py:1000-1006). A parametrized nodeid ends
``::func[0]``, so the lookup never matches, the gate reports "linked test not
run", and the required Proof-of-done CI check fails — even though the test
exists and passes. Do not collapse these back into a parametrize until that
gate matches parametrized ids.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REFERENCE_PAGE = _REPO_ROOT / "docs" / "reference" / "fast-lane-prompt-caching.md"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.injection_builders import assemble_context_bundle  # noqa: E402

# Fenced ``python`` blocks on the page. The signature block is a bare `def`
# stub rather than a call, so it is excluded by _is_executable_example below.
_PYTHON_BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)

# Identifiers the page's examples reference without defining, because the page
# is illustrating a call rather than presenting a runnable script. Supplying
# them here is what makes the examples executable; it does not weaken the
# check, since every one is an opaque string the function only concatenates.
_PLACEHOLDER_NAMES = (
    "arch_content",
    "hl_content",
    "test_file_content",
    "prior_tests_content",
    "batch_ac_content",
    "conv_content",
)


def _example_blocks() -> list[str]:
    """Return every fenced python block on the reference page.

    Returns:
        The raw source of each ``python`` fenced block, page order preserved.
    """
    text = _REFERENCE_PAGE.read_text(encoding="utf-8")
    return _PYTHON_BLOCK.findall(text)


def _is_executable_example(source: str) -> bool:
    """Whether a block is a worked example rather than a signature stub.

    The page carries one ``def assemble_context_bundle(...)`` block that
    documents the signature and is deliberately not callable code. Every other
    python block is an example a reader would copy.

    Args:
        source: The raw source of one fenced python block.

    Returns:
        True when the block should be executed as a worked example.
    """
    return "assemble_context_bundle(" in source and not source.lstrip().startswith("def ")


def _exec_namespace() -> dict[str, object]:
    """Build the globals dict a page example is executed in.

    Returns:
        A namespace pre-seeded with the real function and with the opaque
        placeholder strings the examples reference but do not define.
    """
    namespace: dict[str, object] = {
        "assemble_context_bundle": assemble_context_bundle,
    }
    for name in _PLACEHOLDER_NAMES:
        namespace[name] = f"## {name}\ncontent for {name}"
    return namespace


def test_ac1vii_the_page_still_carries_worked_examples():
    # covers: BO-2400c-1-vii
    """Guard the guard: an empty page would vacuously satisfy every other test.

    Without this, deleting the Examples section entirely would turn this file
    green -- the exact shape of false pass the criterion's test_rationale
    warns about.
    """
    examples = [b for b in _example_blocks() if _is_executable_example(b)]
    assert len(examples) >= 3, (
        "The reference page must keep its worked examples. Found "
        f"{len(examples)} executable example block(s); expected at least 3 "
        "(minimal call, call with optional layers, custom breakpoint marker)."
    )


def _assert_example_executes(index: int) -> dict[str, object]:
    """Execute worked example *index* and fail with a readable diagnosis.

    NOT PARAMETRIZED, DELIBERATELY — see this module's docstring note on
    KI-BO-20260826-1900. The done-proof gate resolves a ``# covers:`` tag to a
    pytest nodeid with ``nodeid.endswith("::" + func_name)``, which a
    parametrized id (``::func[0]``) can never satisfy, so a parametrized test
    is reported as "not run" and blocks the merge. Each example therefore gets
    its own named test function, and this helper holds the shared body.

    Args:
        index: Position of the example among the page's executable blocks.

    Returns:
        The namespace the example was executed in.
    """
    examples = [b for b in _example_blocks() if _is_executable_example(b)]
    assert index < len(examples), (
        f"Expected at least {index + 1} executable examples on the page, "
        f"found {len(examples)}."
    )
    source = examples[index]
    namespace = _exec_namespace()

    try:
        exec(compile(source, f"<reference-page-example-{index}>", "exec"), namespace)
    except TypeError as exc:
        pytest.fail(
            f"Worked example {index} on {_REFERENCE_PAGE.name} does not match the "
            f"real assemble_context_bundle signature: {exc}\n"
            "A reader copying this example gets a call that raises.\n"
            f"Example source:\n{source}"
        )

    assert isinstance(namespace.get("bundle"), str), (
        f"Worked example {index} was expected to bind a string to `bundle`."
    )
    return namespace


def test_ac1vii_the_minimal_example_executes_against_the_real_function():
    # covers: BO-2400c-1-vii
    """The minimal-call example runs.

    RED before BO-2400c-1-vii: it passed ``conventions=`` and ``acs=``, which
    BO-2400c-1-vi removed, so it raised TypeError.
    """
    _assert_example_executes(0)


def test_ac1vii_the_optional_layers_example_executes_against_the_real_function():
    # covers: BO-2400c-1-vii
    """The prior_outputs + working_diff example runs. RED for the same reason."""
    _assert_example_executes(1)


def test_ac1vii_the_custom_marker_example_executes_against_the_real_function():
    # covers: BO-2400c-1-vii
    """The custom-breakpoint-marker example runs. RED for the same reason."""
    namespace = _assert_example_executes(2)
    bundle = namespace["bundle"]
    assert isinstance(bundle, str)
    assert "<!-- STABLE_END -->" in bundle, (
        "The custom-marker example should place the overridden marker in the output."
    )
    assert "<!-- CACHE_BREAKPOINT -->" not in bundle, (
        "Overriding the marker should replace the default, not add to it."
    )


def test_ac1vii_the_minimal_example_produces_exactly_one_breakpoint_marker():
    # covers: BO-2400c-1-vii
    """The page's claim about its own minimal example is true.

    The page states the minimal example's output 'contains one
    <!-- CACHE_BREAKPOINT --> dividing the two stable layers from the single
    volatile layer'. That is a factual claim about output, so it is checked
    against output rather than taken on trust.
    """
    examples = [b for b in _example_blocks() if _is_executable_example(b)]
    namespace = _exec_namespace()
    exec(compile(examples[0], "<reference-page-minimal-example>", "exec"), namespace)

    bundle = namespace["bundle"]
    assert isinstance(bundle, str)
    assert bundle.count("<!-- CACHE_BREAKPOINT -->") == 1, (
        "The page says its minimal example yields exactly one breakpoint "
        f"marker; the example actually yields "
        f"{bundle.count('<!-- CACHE_BREAKPOINT -->')}."
    )
