"""Pick the material a judgement needs: tests, the code they cover, the ticket.

Everything here is deterministic. It decides WHAT goes into a request; it never
asks the model anything. Jev's accuracy drops as irrelevant state grows, so the
unit of work is one test function plus only the fixtures and code it touches.
"""

from __future__ import annotations

import ast
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

TEST_FILE_RE = re.compile(r"(^|[\\/])test_[^\\/]*\.py$")
SQL_PATH_RE = re.compile(r"""["']([\w./\\-]+\.sql)["']""")
GATE_LINE_RE = re.compile(
    r"\b(if|elif|while|WHERE|AND|OR|LIMIT|ORDER BY|HAVING|CASE WHEN)\b", re.IGNORECASE
)
EXACT_ASSERTS = {
    "assertEqual", "assertEquals", "assertListEqual", "assertDictEqual",
    "assertTupleEqual", "assertSetEqual", "assertCountEqual", "assertSequenceEqual",
    "assertAlmostEqual", "assertIs", "assertIsNone", "assertMultiLineEqual",
    "assert_called_once_with", "assert_called_with", "assert_has_calls",
}
ASSERT_PREFIXES = ("assert", "fail")
SKIP_NAMES = {"skip", "skipIf", "skipUnless", "xfail", "expectedFailure"}


@dataclass
class TestUnit:
    file: str
    name: str
    source: str
    fixtures: dict[str, str] = field(default_factory=dict)
    static_flags: dict[str, str] = field(default_factory=dict)


@dataclass
class CodeUnit:
    file: str
    excerpt: str
    gates: list[str] = field(default_factory=list)
    from_diff: bool = False
    full_text: str = ""


@dataclass
class Bundle:
    tests: list[TestUnit]
    code: list[CodeUnit]
    ticket_intent: str | None


# --------------------------------------------------------------------- ticket

def read_ticket(path: Path) -> tuple[str, list[str]]:
    """Return (intent text, files_touched) from a ticket markdown file."""
    text = path.read_text(encoding="utf-8", errors="replace")
    files: list[str] = []
    body = text
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if m:
        front, body = m.group(1), m.group(2)
        block = re.search(r"^files_touched:\s*\n((?:\s*-\s*.+\n?)+)", front, re.MULTILINE)
        if block:
            files = [re.sub(r"^\s*-\s*", "", ln).strip().strip("'\"")
                     for ln in block.group(1).splitlines() if ln.strip()]
    # Keep intent sections; drop the process noise (sign-offs, comment log).
    body = re.split(r"^## (Comments|Sign-offs)\b", body, flags=re.MULTILINE)[0]
    return body.strip(), files


# ---------------------------------------------------------------------- tests

def _is_test_fn(node: ast.AST) -> bool:
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test")


def _decorator_names(node) -> set[str]:
    names = set()
    for d in getattr(node, "decorator_list", []):
        target = d.func if isinstance(d, ast.Call) else d
        if isinstance(target, ast.Attribute):
            names.add(target.attr)
        elif isinstance(target, ast.Name):
            names.add(target.id)
    return names


def _assert_calls(fn) -> list[tuple[ast.AST, str]]:
    """Every assertion in fn as (node, kind-name)."""
    found = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert):
            found.append((node, "assert"))
        elif isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if name.startswith(ASSERT_PREFIXES) or name == "raises":
                found.append((node, name))
    return found


def _inside_loop(fn, target) -> bool:
    loops = (ast.For, ast.AsyncFor, ast.While, ast.comprehension,
             ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
    for node in ast.walk(fn):
        if isinstance(node, loops) and node is not fn:
            if any(child is target for child in ast.walk(node)):
                return True
    return False


def static_flags(fn, cls, source: str, helpers: list | None = None) -> dict[str, str]:
    """Checks code can answer exactly -- never sent to the model.

    `helpers` are the methods/functions the test reaches by name (inherited
    `self._run_x()` bodies, module helpers). Assertions often live there.
    """
    flags: dict[str, str] = {}
    skips = (_decorator_names(fn) | (_decorator_names(cls) if cls else set())) & SKIP_NAMES
    if skips:
        flags["skipped"] = f"decorated with {sorted(skips)}"
    bodies = [fn, *(helpers or [])]
    asserts = [(b, a) for b in bodies for a in _assert_calls(b)]
    if not asserts:
        flags["no_assertions"] = "no assert statement or assert*/raises call in the test or the helpers it calls"
        return flags
    if re.search(r"assertTrue\(\s*True\s*\)|^\s*assert\s+True\b", source, re.MULTILINE):
        flags["trivially_true"] = "asserts a constant True"
    exact = False
    for _, (node, kind) in asserts:
        if kind in EXACT_ASSERTS:
            exact = True
        elif kind == "assert" and isinstance(node.test, ast.Compare) and any(
                isinstance(op, (ast.Eq, ast.Is)) for op in node.test.ops):
            exact = True
    if not exact:
        flags["no_exact_assertion"] = (
            "every assertion is one-sided (not-equal, truthy, contains, not-none...) "
            "-- nothing pins an exact value or count, so an empty result can pass")
    if all(_inside_loop(body, node) for body, (node, _) in asserts):
        flags["asserts_only_in_loop"] = "all assertions sit inside a loop/comprehension that may run zero times"
    if re.search(r"localhost:\d{4}", source):
        flags["hardcoded_local_db"] = "connects to a hardcoded localhost port"
    if re.search(r"\.commit\(\)", source):
        flags["commits"] = "calls .commit() -- rollback isolation is not what protects this test"
    return flags


FIXTURE_METHODS = {"setUp", "setUpClass", "tearDown", "tearDownClass", "asyncSetUp"}


def extract_tests(path: Path, only: set[str] | None = None) -> list[TestUnit]:
    text = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(text)
    fn_types = (ast.FunctionDef, ast.AsyncFunctionDef)
    module_helpers = {n.name: n for n in tree.body if isinstance(n, fn_types) and not _is_test_fn(n)}
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    seg = lambda n: ast.get_source_segment(text, n) or ""  # noqa: E731
    units: list[TestUnit] = []

    def mro(cls) -> list[ast.ClassDef]:
        """The class and its bases that are defined in this file, nearest first."""
        out, todo = [], [cls]
        while todo:
            c = todo.pop(0)
            if c in out:
                continue
            out.append(c)
            todo += [classes[b.id] for b in c.bases if isinstance(b, ast.Name) and b.id in classes]
        return out

    def add(fn, cls):
        if only and fn.name not in only:
            return
        src = seg(fn)
        methods: dict[str, tuple[str, ast.AST]] = {}
        for c in reversed(mro(cls)) if cls is not None else []:
            for n in c.body:  # nearest class wins: iterate far->near, overwrite
                if isinstance(n, fn_types) and not _is_test_fn(n):
                    methods[n.name] = (c.name, n)
        fixtures: dict[str, str] = {}
        reached: list[ast.AST] = []
        for name in FIXTURE_METHODS & methods.keys():
            fixtures[f"{methods[name][0]}.{name}"] = seg(methods[name][1])
        # Follow names transitively (3 hops): self._helper(), module_helper().
        frontier, seen = [src], set()
        for _ in range(3):
            nxt = []
            for body in frontier:
                for word in set(re.findall(r"[A-Za-z_]\w*", body)):
                    if word in seen:
                        continue
                    if word in methods and word not in FIXTURE_METHODS:
                        owner, node = methods[word]
                        fixtures[f"{owner}.{word}"] = seg(node)
                        reached.append(node)
                    elif word in module_helpers:
                        node = module_helpers[word]
                        fixtures[word] = seg(node)
                        reached.append(node)
                    else:
                        continue
                    seen.add(word)
                    nxt.append(seg(node))
            frontier = nxt
        units.append(TestUnit(file=str(path), name=f"{cls.name}.{fn.name}" if cls else fn.name,
                              source=src, fixtures=fixtures,
                              static_flags=static_flags(fn, cls, src, reached)))

    for node in tree.body:
        if _is_test_fn(node):
            add(node, None)
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if _is_test_fn(sub):
                    add(sub, node)
    return units


# ----------------------------------------------------------------------- code

def resolve_code_for_test(test_path: Path, repo: Path) -> list[Path]:
    """Guess the code under test from imports and referenced .sql paths."""
    text = test_path.read_text(encoding="utf-8", errors="replace")
    found: list[Path] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        tree = None
    if tree:
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                mods = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            elif isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            for mod in mods:
                rel = Path(*mod.split("."))
                for cand in (repo / rel.with_suffix(".py"), repo / rel / "__init__.py"):
                    if cand.is_file() and "test" not in cand.name and cand not in found:
                        found.append(cand)
    for m in SQL_PATH_RE.finditer(text):
        cand = repo / m.group(1).replace("\\", "/")
        if cand.is_file() and cand not in found:
            found.append(cand)
    return found


def _git(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                                text=True, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"git {' '.join(args)} failed to run in {repo}: {exc}") from exc
    return result.stdout


def code_unit(path: Path, repo: Path, diff_base: str | None, max_chars: int) -> CodeUnit:
    rel = str(path.relative_to(repo)) if path.is_relative_to(repo) else str(path)
    if diff_base:
        diff = _git(repo, "diff", "--unified=6", diff_base, "--", rel)
        if diff.strip():
            added = [ln[1:].strip() for ln in diff.splitlines()
                     if ln.startswith("+") and not ln.startswith("+++")]
            gates = [ln for ln in added if GATE_LINE_RE.search(ln) and not ln.startswith(("#", "--"))]
            return CodeUnit(rel, diff[:max_chars], gates[:12], from_diff=True)
    text = path.read_text(encoding="utf-8", errors="replace")
    return CodeUnit(rel, text[:max_chars], full_text=text)


def gate_windows(text: str, gates: list[str], max_chars: int, radius: int = 30) -> str | None:
    """Lines around each gate occurrence, merged; None if no gate is found in text."""
    lines = text.splitlines()
    norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()  # noqa: E731
    hits = set()
    for g in gates:
        key = norm(g)[:60]
        if not key:
            continue
        for i, ln in enumerate(lines):
            if key in norm(ln) or (len(key) > 20 and norm(ln) and norm(ln) in key and len(norm(ln)) > 15):
                hits.add(i)
    if not hits:
        return None
    keep = sorted({j for i in hits for j in range(max(0, i - radius), min(len(lines), i + radius + 1))})
    out, prev = [], -2
    for j in keep:
        if j != prev + 1:
            out.append(f"... (line {j + 1})")
        out.append(lines[j])
        prev = j
    return "\n".join(out)[:max_chars]


def narrow(code: CodeUnit, referenced: str, max_chars: int) -> str:
    """For a whole .py file, keep only the defs the test mentions (plus module constants).

    Diffs and SQL are returned as-is: a diff is already narrow, and a SQL file is
    usually one procedure.
    """
    if code.from_diff or not code.full_text:
        return code.excerpt
    if not code.file.endswith(".py"):
        if len(code.full_text) <= max_chars:
            return code.full_text
        return gate_windows(code.full_text, code.gates, max_chars) or code.excerpt
    text = code.full_text
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return code.excerpt
    words = set(re.findall(r"[A-Za-z_]\w+", referenced))
    keep: list[str] = []
    for node in tree.body:
        seg = ast.get_source_segment(text, node) or ""
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            keep.append(seg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in words:
            keep.append(seg)
        elif isinstance(node, ast.ClassDef) and node.name in words:
            methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            used = [n for n in methods if n.name in words or n.name == "__init__"]
            # Methods called by the used methods, one hop: that is where gates hide.
            used_names = {n.name for n in used}
            for n in methods:
                if n.name not in used_names and any(
                        re.search(rf"\b{re.escape(n.name)}\b", ast.get_source_segment(text, u) or "")
                        for u in used):
                    used.append(n)
            body = "\n\n".join("    " + (ast.get_source_segment(text, n) or "")
                               for n in sorted(used, key=lambda n: n.lineno))
            keep.append(f"class {node.name}:  # only the methods the test reaches\n{body}")
    narrowed = "\n\n".join(k for k in keep if k)
    return (narrowed or code.excerpt)[:max_chars]


def changed_files(repo: Path, base: str) -> list[Path]:
    out = _git(repo, "diff", "--name-only", base)
    return [repo / ln for ln in out.splitlines() if ln.strip() and (repo / ln).is_file()]


def split_tests_and_code(paths: list[Path]) -> tuple[list[Path], list[Path]]:
    tests = [p for p in paths if TEST_FILE_RE.search(str(p))]
    code = [p for p in paths if p not in tests and p.suffix in {".py", ".sql"}]
    return tests, code
