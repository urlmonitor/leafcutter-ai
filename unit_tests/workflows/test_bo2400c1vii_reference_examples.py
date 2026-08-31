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


@pytest.mark.parametrize("index", range(3))
def test_ac1vii_each_documented_example_executes_against_the_real_function(index):
    # covers: BO-2400c-1-vii
    """Every worked example on the page runs against the real function.

    RED before BO-2400c-1-vii: all three examples passed ``conventions=`` and
    ``acs=``, which BO-2400c-1-vi removed, so each raised TypeError.
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
