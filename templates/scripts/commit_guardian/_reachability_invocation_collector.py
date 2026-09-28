"""
MODULE: scripts/commit_guardian/_reachability_invocation_collector.py
GOAL: Implements collected_invocations() -- the "what does this automation
    actually invoke?" half of the shared reachability-inventory seam. Split
    out of _reachability_inventory.py verbatim (NO behaviour change) to buy
    back file-size-ratchet headroom, mirroring check_done_proof.py's own
    precedent of moving cohesive helper groups into sibling `_*.py` modules
    (e.g. _ac_store_locator.py, _staged_ac_yaml_paths.py).
BUSINESS CONTEXT: See _reachability_inventory.py's own module docstring for
    the full seam contract this implements ("what does this automation
    actually invoke?", consumed forwards by BO-2900b-1 and backwards by
    BO-2900c, hardened for JavaScript automation by BO-2900b-3).
    _reachability_inventory.py re-exports :class:`Invocation` and
    :func:`collected_invocations` from here, so ``from
    _reachability_inventory import collected_invocations`` (the seam's
    declared public import path) is unaffected by this split.
ARCHITECTURE: Two public symbols:
        Invocation
            NamedTuple(script: str, line: int, surface: str, capability: str).
        collected_invocations(script_paths) -> list[Invocation]
            AST-based (never substring/regex-over-raw-text) scan of Python
            automation scripts for real ``subprocess.run``/``call``/
            ``check_call``/``check_output``/``Popen`` calls whose argv names a
            surface script, taking the very next positional token as the
            capability. ROLLOUT NOTE (BO-2900b-1): only ``.py`` automation
            scripts are recognised; a ``.js``/``.yaml``/other script
            contributes no invocations here (not an error -- see
            debugging/test_judge/callers.py's own documented limit, "one hop,
            Python direct calls only; JS/YAML/CI invocations need their own
            handling"). BO-2900b-3 extends THIS function (never a second
            collector) to recognise JavaScript command construction, resist
            comment/message/variable-name decoys, and satisfy the
            rename-invariance property.

    All I/O (file reads) is wrapped per the Error Handling Policy (Rule 1);
    unreadable/unparseable individual scripts are logged and skipped rather
    than aborting the whole scan.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Iterable, NamedTuple

# subprocess entry points an automation script's real invocation of a command
# surface can go through. Anything else (a bare os.system string, a shell
# pipeline) is out of scope here, matching this repository's automation-script
# convention (see templates/workflows-js/fast-lane-ship.js and this AC's own
# fixtures, all of which invoke via subprocess.run(...)).
_SUBPROCESS_RUN_ATTRS = frozenset({"run", "call", "check_call", "check_output", "Popen"})


class Invocation(NamedTuple):
    """One real, executed invocation of a command-surface capability.

    Attributes:
        script: Repo-relative or absolute path of the automation script the
            invocation was collected from.
        line: 1-based source line of the executed-command expression.
        surface: The (best-effort resolved) path of the command surface the
            capability was run against.
        capability: The first positional argument of the executed command --
            never a name found elsewhere in the script (see module docstring).
    """

    script: str
    line: int
    surface: str
    capability: str


def _is_subprocess_run_call(node: ast.AST) -> bool:
    """True when *node* is a real AST Call to one of ``subprocess``'s run-a-process functions."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    func = node.func
    return (
        func.attr in _SUBPROCESS_RUN_ATTRS
        and isinstance(func.value, ast.Name)
        and func.value.id == "subprocess"
    )


def _resolve_sibling_path_expr(node: ast.AST, script_path: Path) -> str | None:
    """Resolve a ``Path(__file__).resolve().parent / "name.py"``-shaped expression.

    This is the one non-literal right-hand-side shape this repository's own
    fixture and real automation scripts use to name a sibling surface script.
    Recognised structurally (a ``/`` BinOp whose left side mentions
    ``__file__`` and whose right side is a string literal) and re-derived
    against *script_path*'s own parent directory -- never by executing the
    expression. Any other shape returns ``None`` (left unresolved, never
    guessed at).
    """
    if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
        return None
    right = node.right
    if not (isinstance(right, ast.Constant) and isinstance(right.value, str)):
        return None
    if not any(isinstance(n, ast.Name) and n.id == "__file__" for n in ast.walk(node.left)):
        return None
    return str(script_path.resolve().parent / right.value)


def _resolve_string_expr(node: ast.AST, script_path: Path) -> str | None:
    """Best-effort resolution of a string-valued expression node to its value.

    Handles a plain string literal, and the
    ``str(Path(__file__).resolve().parent / "name.py")`` sibling-path idiom
    via :func:`_resolve_sibling_path_expr`. Any other shape returns ``None``.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "str":
        if len(node.args) == 1:
            return _resolve_sibling_path_expr(node.args[0], script_path)
    return None


def _module_level_string_bindings(tree: ast.Module, script_path: Path) -> dict[str, str]:
    """Best-effort map of module-level ``Name -> resolved string value``.

    Only plain module-level ``NAME = <expr>`` assignments are considered
    (never conditional/nested assignment, never execution) -- see
    :func:`_resolve_string_expr` for which expression shapes resolve.

    Args:
        tree: Parsed AST of an automation script.
        script_path: The script's own path (used to resolve a
            ``Path(__file__)``-relative sibling expression against the
            script's real directory).

    Returns:
        Mapping of resolved module-level string bindings; unresolvable
        right-hand sides are simply absent, never guessed at.
    """
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        value = _resolve_string_expr(node.value, script_path)
        if value is not None:
            bindings[target.id] = value
    return bindings


def _argv_literal_tokens(call_node: ast.Call, bindings: dict[str, str]) -> list[str | None]:
    """Best-effort resolved string value for each element of a subprocess call's argv list.

    ``call_node``'s first positional argument is expected to be a literal
    list (the ``subprocess.run([...])`` convention this repository's
    automation scripts use). Each element resolves via a literal string, a
    bound module-level Name (*bindings*), or ``None`` when unresolved (e.g.
    ``sys.executable``) -- unresolved tokens are skipped as surface/capability
    candidates, never guessed at.

    Args:
        call_node: The ``subprocess.run``/etc. Call node.
        bindings: Module-level string bindings from
            :func:`_module_level_string_bindings`.

    Returns:
        One entry per argv element, in order; ``None`` where unresolved.
    """
    if not call_node.args or not isinstance(call_node.args[0], ast.List):
        return []
    tokens: list[str | None] = []
    for elt in call_node.args[0].elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            tokens.append(elt.value)
        elif isinstance(elt, ast.Name) and elt.id in bindings:
            tokens.append(bindings[elt.id])
        else:
            tokens.append(None)
    return tokens


def _invocation_from_call(
    call_node: ast.Call, bindings: dict[str, str], script_path: Path
) -> Invocation | None:
    """Build an :class:`Invocation` from one subprocess-run Call node, or ``None``.

    The surface token is the first resolved argv element ending in ``.py``;
    the capability is the very next argv element, accepted only when it is
    itself resolved and is not a flag (does not start with ``-``) -- the
    first positional argument of the executed command, matching BO-2900b-3's
    own description of this same mechanism.

    Args:
        call_node: A Call node already confirmed to be a subprocess-run call.
        bindings: Module-level string bindings for this script.
        script_path: The automation script's own path (recorded on the
            resulting Invocation).

    Returns:
        An :class:`Invocation`, or ``None`` when no resolved surface+capability
        pair is found in this call's argv.
    """
    tokens = _argv_literal_tokens(call_node, bindings)
    for index, token in enumerate(tokens):
        if token is None or not token.endswith(".py"):
            continue
        if index + 1 >= len(tokens):
            return None
        capability = tokens[index + 1]
        if capability is None or capability.startswith("-"):
            return None
        return Invocation(
            script=str(script_path),
            line=call_node.lineno,
            surface=token,
            capability=capability,
        )
    return None


def collected_invocations(script_paths: Iterable[Path]) -> list[Invocation]:
    """Collect every real, executed capability invocation from *script_paths*.

    See the module docstring's ROLLOUT NOTE: only ``.py`` automation scripts
    are recognised in this AC's implementation; other extensions contribute
    no invocations (silently, not as an error -- BO-2900b-3 extends this same
    function for JavaScript automation).

    Args:
        script_paths: Automation script paths to scan.

    Returns:
        One :class:`Invocation` per real ``subprocess.run``/``call``/
        ``check_call``/``check_output``/``Popen`` call whose argv resolves a
        surface-script token followed by a capability token. Unreadable or
        unparseable scripts are logged to stderr and skipped, never fatal to
        the rest of the scan.
    """
    invocations: list[Invocation] = []
    for script_path in script_paths:
        if script_path.suffix != ".py":
            continue
        try:
            source = script_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(
                f"WARNING: _reachability_invocation_collector: cannot read {script_path}: {exc}",
                file=sys.stderr,
            )
            continue
        try:
            tree = ast.parse(source, filename=str(script_path))
        except SyntaxError as exc:
            print(
                f"WARNING: _reachability_invocation_collector: cannot parse {script_path}: {exc}",
                file=sys.stderr,
            )
            continue
        bindings = _module_level_string_bindings(tree, script_path)
        for node in ast.walk(tree):
            if not _is_subprocess_run_call(node):
                continue
            invocation = _invocation_from_call(node, bindings, script_path)
            if invocation is not None:
                invocations.append(invocation)
    return invocations
