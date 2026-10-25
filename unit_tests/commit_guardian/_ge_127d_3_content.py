"""
MODULE: unit_tests/commit_guardian/_ge_127d_3_content.py
COVERS: GE-127d-3 (+ -i, -ii, -iii, -iv), GE-127d-4, GE-127d-5 -- shared CONTENT
    builders and INDEPENDENT oracles (carries no tests of its own).

GOAL: Generate file text per covered language whose correct measured length is
    known BY CONSTRUCTION (N code lines + K comment lines in a chosen style),
    and re-derive a length independently of the production measure (``ast`` +
    ``tokenize`` for Python, the TypeScript compiler's own comment ranges for
    JS/TS), so no descriptor asserts a hard-coded total and none is a
    tautology against the code under test.

THE MEASURE UNDER TEST (test-writer design decision, not AC-pinned): the shared
    measure is reached as ``_file_size_ratchet.measure_current_length(path)``
    (extension chosen from the path, exactly what the hook calls) -- the
    sub-package ``_file_size_measure/`` hosts the per-language lexers behind it.
    The RULE (BrainCandy 2026-10-16 and 2026-10-20): no comment of any style
    counts, no Python string standing alone as a statement counts, and NO BLANK
    LINE counts anywhere (2026-10-21: a line counts only if it holds a code
    token); the non-blank lines of used strings (assigned, passed, returned,
    part of a larger expression) and f-strings count.

DECISION HISTORY
- 2026-10-20 [GE-127d-3/test-writer]: Initial authoring.
"""

from __future__ import annotations

import ast
import io
import json
import subprocess
import sys
import tokenize
from pathlib import Path

PYTHON = sys.executable
EXTENSIONS = (".py", ".sql", ".js", ".mjs", ".ts", ".tsx", ".sh")
_JS_FAMILY = (".js", ".mjs", ".ts", ".tsx")


def code_line(ext: str, i: int) -> str:
    """One genuine code line of *ext*'s language, unique per *i*."""
    if ext == ".py":
        return f"value_{i} = {i}"
    if ext in _JS_FAMILY:
        return f"const value_{i} = {i};"
    if ext == ".sql":
        return f"SELECT {i} AS value_{i};"
    return f"echo value_{i}"


def styles_for(ext: str) -> tuple[str, ...]:
    """Every comment style *ext*'s language has (docstring/jsx included)."""
    return {
        ".py": ("line", "docstring"),
        ".sh": ("line",),
        ".sql": ("line", "block"),
        ".tsx": ("line", "block", "jsx"),
    }.get(ext, ("line", "block"))


def comment_lines(ext: str, style: str, k: int) -> list[str]:
    """*k* physical lines of explanatory text carried in *style*."""
    texts = [f"explanatory text {i}" for i in range(k)]
    if style == "line":
        prefix = {".py": "# ", ".sh": "# ", ".sql": "-- "}.get(ext, "// ")
        return [prefix + t for t in texts]
    if style == "block":
        if k == 1:
            return [f"/* {texts[0]} */"]
        return ["/* " + texts[0], *["   " + t for t in texts[1:-1]], "   " + texts[-1] + " */"]
    if style == "docstring":
        if k == 1:
            return [f'"""{texts[0]}"""']
        return ['"""' + texts[0], *texts[1:-1], texts[-1] + '"""']
    if style == "jsx":
        return ["{/* " + t + " */}" for t in texts]
    raise ValueError(style)


def build_text(ext: str, n: int, k: int, style: str, *, blanks: int = 0, blanks_in_comment: int = 0) -> tuple[str, int]:
    """Return ``(text, expected_length)``: n code lines, k comment lines, b blanks.

    The comment block sits between the two halves of the code. ``blanks`` blank
    lines sit between code lines; ``blanks_in_comment`` blank lines sit INSIDE a
    block comment/docstring -- only meaningful for styles that can hold them
    (block, docstring). Neither ever counts (BrainCandy 2026-10-21), so
    ``expected`` is n whatever ``blanks`` is.
    """
    half = n // 2
    if style == "jsx":
        n = max(n, 4)
        half = (n - 4) // 2
        before = [code_line(ext, i) for i in range(half)]
        wrapper_open = ["const view = (", "  <div>"]
        wrapper_close = ["  </div>", ");"]
        after = [code_line(ext, i) for i in range(half, n - 4)]
        body = [*before, *wrapper_open, *comment_lines(ext, "jsx", k), *wrapper_close, *after]
        expected = n
        lines = body
    else:
        block = comment_lines(ext, style, k)
        if blanks_in_comment and style in ("block", "docstring") and len(block) >= 2:
            block = [block[0], *[""] * blanks_in_comment, *block[1:]]
        lines = [*[code_line(ext, i) for i in range(half)], *block, *[code_line(ext, i) for i in range(half, n)]]
        expected = n
    if blanks:
        lines = [*lines[:1], *[""] * blanks, *lines[1:]]
    return "\n".join(lines) + "\n", expected


def py_positioned(position: str, form: str, s_lines: int = 4, extra_code: int = 10) -> str:
    """A .py file with an S-line text slot at *position* in *form*.

    position: module | class | function | between | trailing.
    form: none | hash | string. A "string" slot is a string STANDING ALONE as a
    statement (docstring or bare); "hash" is the same text as ``#`` lines.
    """
    texts = [f"slot text {i}" for i in range(s_lines)]

    def slot(indent: str) -> list[str]:
        if form == "none":
            return []
        if form == "hash":
            return [f"{indent}# {t}" for t in texts]
        if s_lines == 1:
            return [f'{indent}"""{texts[0]}"""']
        return [f'{indent}"""{texts[0]}', *[f"{indent}{t}" for t in texts[1:-1]], f'{indent}{texts[-1]}"""']

    out: list[str] = []
    out += slot("") if position == "module" else []
    out += ["import os", "", "class Box:"]
    out += slot("    ") if position == "class" else []
    out += ["    attr = 1", "", "def alpha():"]
    out += slot("    ") if position == "function" else []
    out += ["    return os.sep", ""]
    out += slot("") if position == "between" else []
    out += ["def beta():", "    return 2", ""]
    out += [f"FILLER_{i} = {i}" for i in range(extra_code)]
    out += slot("") if position == "trailing" else []
    return "\n".join(out) + "\n"


def python_with_string_forms(kind: str, s_lines: int) -> tuple[str, str]:
    """``(base, with_string)`` for the USED-string descriptor.

    kind: assigned | argument | returned | joined | fstring.  ``with_string`` adds
    the S-line text as that kind of string; ``base`` is the same file without it.
    """
    body = [f"line {i}" for i in range(s_lines)]
    triple = '"""' + "\n".join(body) + '"""'
    head = "import os\n\n"
    base_tail = "def go():\n    return 1\n"
    if kind == "assigned":
        add = f"TEXT = {triple}\n"
    elif kind == "argument":
        add = f"print({triple})\n"
    elif kind == "returned":
        add = f"def give():\n    return {triple}\n"
    elif kind == "joined":
        add = f'PREFIX = "p"\nJOINED = PREFIX + {triple}\n'
    else:
        add = "NAME = 1\nf" + '"""' + "\n".join(body) + ' {NAME}"""\n'
    return head + base_tail, head + base_tail + add


def _joined_statements(tree: ast.Module, lines: list[str]) -> int:
    """GE-127d-3-v from ``ast``: each statement with code before it on its first row adds one.

    A standalone string statement adds nothing, and a ``case`` body is left out
    (``match``/``case`` are soft keywords the measure does not split on).
    """
    extra = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt) or node.lineno > len(lines):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, (str, bytes)):
            continue
        before = lines[node.lineno - 1].encode("utf-8")[: node.col_offset].decode("utf-8", "ignore").strip()
        if before and not before.startswith("case "):
            extra += 1
    return extra


def independent_python_length(text: str) -> int:
    """Length by the 2026-10-20 rule plus GE-127d-3-v, derived from ``ast`` + ``tokenize``."""
    norm = text.replace("\r\n", "\n")
    lines = norm.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    tree = ast.parse(norm)
    standalone = [
        (node.lineno, node.end_lineno or node.lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, (str, bytes))
    ]
    counted: set[int] = set()
    skip = (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER)
    for tok in tokenize.generate_tokens(io.StringIO(norm).readline):
        if tok.type in skip:
            continue
        if tok.type == tokenize.STRING and any(a <= tok.start[0] and tok.end[0] <= b for a, b in standalone):
            continue
        counted.update(range(tok.start[0], tok.end[0] + 1))
    rows = sum(1 for row, line in enumerate(lines, start=1) if row in counted and line.strip())
    return rows + _joined_statements(tree, lines)


_NODE_ORACLE = r"""
const ts = require(process.argv[1]);
const fs = require('fs');
const out = {};
for (const file of process.argv.slice(2)) {
  const text = fs.readFileSync(file, 'utf8').replace(/\r\n/g, '\n');
  const kind = file.endsWith('.tsx') ? ts.ScriptKind.TSX : file.endsWith('.ts') ? ts.ScriptKind.TS : ts.ScriptKind.JS;
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, kind);
  const seen = new Set(); const ranges = [];
  const add = (rs) => { if (!rs) return; for (const r of rs) { if (!seen.has(r.pos)) { seen.add(r.pos); ranges.push([r.pos, r.end]); } } };
  const visit = (node) => {
    // GE-127d-3-i: a comment-only JSX expression container is uncounted whole, braces included.
    if (node.kind === ts.SyntaxKind.JsxExpression && !node.expression) {
      const begin = node.getStart(sf), stop = node.getEnd();
      if (!seen.has(begin)) { seen.add(begin); ranges.push([begin, stop]); }
    }
    if (node.kind !== ts.SyntaxKind.JsxText) {
      add(ts.getLeadingCommentRanges(text, node.getFullStart()));
      add(ts.getTrailingCommentRanges(text, node.getEnd()));
    }
    for (const child of node.getChildren(sf)) visit(child);
  };
  visit(sf);
  const mask = new Uint8Array(text.length + 1);
  for (const [a, b] of ranges) for (let i = a; i < b; i++) mask[i] = 1;
  const lines = text.split('\n');
  if (lines.length && lines[lines.length - 1] === '') lines.pop();
  let offset = 0, total = 0;
  for (const line of lines) {
    let code = false, comment = false;
    for (let i = 0; i < line.length; i++) {
      if (mask[offset + i]) comment = true; else if (!/\s/.test(line[i])) code = true;
    }
    if (code) total++;  // blank lines never count (BrainCandy 2026-10-21)
    offset += line.length + 1;
  }
  // GE-127d-3-v from the compiler's tokens: a ';' outside any paren opened since the innermost
  // brace, followed on its line (no comment between) by a token that is not a closer, adds one.
  const toks = [];
  const leaves = (node) => {
    if (node.kind >= ts.SyntaxKind.FirstJSDocNode && node.kind <= ts.SyntaxKind.LastJSDocNode) return;
    const kids = node.getChildren(sf);
    if (kids.length === 0) { if (node.kind !== ts.SyntaxKind.EndOfFileToken && node.getWidth(sf) > 0) toks.push(node); return; }
    for (const kid of kids) leaves(kid);
  };
  leaves(sf);
  const K = ts.SyntaxKind;
  const closers = new Set([K.CloseBraceToken, K.CloseParenToken, K.CloseBracketToken, K.SemicolonToken, K.CommaToken]);
  // GE-127d-3-vi: a brace pair directly holding such a ';' is a block; code after its '{' on that
  // line (no comment between) adds one, and its '}' with a token before it on that line adds one.
  const frames = []; let parens = 0, extra = 0;
  const gapOf = (a, b) => text.slice(a.end, b.getStart(sf));
  for (let i = 0; i < toks.length; i++) {
    const kind = toks[i].kind;
    if (kind === K.OpenParenToken) parens++;
    else if (kind === K.CloseParenToken) parens--;
    else if (kind === K.OpenBraceToken) frames.push({ parens, open: i, sep: false });
    else if (kind === K.CloseBraceToken) {
      const frame = frames.pop();
      if (frame && frame.sep) {
        const after = toks[frame.open + 1], gapA = gapOf(toks[frame.open], after);
        if (after.kind !== K.CloseBraceToken && !gapA.includes('\n') && gapA.trim() === '') extra++;
        if (!gapOf(toks[i - 1], toks[i]).includes('\n')) extra++;
      }
    }
    else if (kind === K.SemicolonToken && parens === (frames.length ? frames[frames.length - 1].parens : 0)) {
      if (frames.length) frames[frames.length - 1].sep = true;
      const next = toks[i + 1];
      const gap = next ? text.slice(toks[i].end, next.getStart(sf)) : '\n';
      if (!closers.has(next ? next.kind : K.CloseBraceToken) && !gap.includes('\n') && gap.trim() === '') extra++;
    }
  }
  out[file] = total + extra;
}
console.log(JSON.stringify(out));
"""


def ts_oracle_lengths(paths: list[str], ts_module_dir: Path) -> dict[str, int]:
    """Lengths derived from the TypeScript compiler's own comment ranges."""
    result = subprocess.run(
        ["node", "-e", _NODE_ORACLE, str(ts_module_dir), *paths],
        capture_output=True, text=True, timeout=120, check=False,
    )
    if result.returncode != 0:
        message = f"node oracle failed: {result.stderr!r}"
        raise AssertionError(message)
    return json.loads(result.stdout)


def locate_typescript(repo_root: Path) -> Path | None:
    """Find leafcutter-web's installed typescript (worktree, then main checkout)."""
    for base in (repo_root, *repo_root.parents[:2]):
        candidate = base / "leafcutter-web" / "node_modules" / "typescript"
        if (candidate / "lib" / "typescript.js").exists():
            return candidate
    return None


# --- GE-127d-3-i literal corpora: (kind, text); kind 'c' counts, 'm' is a genuine comment ---
_JS_LITERALS = [
    ("c", "const a = 1;"), ("c", 'const glob = "templates/**/*.js";'), ("c", "const url = 'https://example.com/a';"),
    ("c", "const t = `see // here /* and */ # tag`;"), ("c", "const re = /\\/\\*/;"), ("m", "/* genuine */"),
    ("m", "// note: this mentions /* but opens nothing"), ("c", "const p = 1;"), ("c", 'const end = "*/";'),
    ("c", "const n = `a ${`b ${c}`} d`;"), ("c", "const tpl = `value ${"), ("m", "  // genuine inside the expression"),
    ("c", "  compute()"), ("c", "} end`;"), ("c", "const z = 2;"),
]
_SQL_LITERALS = [
    ("c", "SELECT '--' AS dashes;"), ("c", "SELECT '/*' AS opener;"), ("c", "SELECT '*/' AS closer;"),
    ("m", "-- genuine comment"), ("m", "/* genuine block */"), ("c", "CREATE FUNCTION f() RETURNS int AS $$"),
    ("c", "BEGIN"), ("m", "  -- genuine inside the dollar body"), ("m", "  /* outer /* nested */ still comment */"),
    ("c", "  RETURN 1;"), ("c", "END;"), ("c", "$$ LANGUAGE plpgsql;"),
]
_PY_LITERALS = [
    ("c", 'a = "#"'), ("c", "b = '\"\"\"'"), ("c", 'c = "/*"'), ("c", 'd = "*/"'), ("c", 'e = print("# not a comment")'),
    ("m", "# genuine comment"), ("c", 'TEXT = """'), ("c", "inside # not a comment"), ("c", '"""'), ("c", "f = 1"),
]
_SH_LITERALS = [
    ("c", "echo $#"), ("c", "echo ${#name}"), ("c", "echo a#b"), ("c", 'echo "a # b"'), ("c", "cat <<'EOF'"),
    ("c", "# looks like a comment but is here-doc body"), ("c", "# another body line"), ("c", "EOF"),
    ("m", "# genuine comment"), ("c", "echo done"),
]
LITERAL_CASES: dict[str, list[tuple[str, str]]] = {
    ".js": _JS_LITERALS, ".mjs": _JS_LITERALS, ".ts": _JS_LITERALS, ".tsx": _JS_LITERALS,
    ".sql": _SQL_LITERALS, ".py": _PY_LITERALS, ".sh": _SH_LITERALS,
}

REGEX_DIVISION_JS = [
    ("c", "const r1 = /[/*]/;"), ("c", "const r2 = /\\/\\*/;"), ("c", "if (x) /'/.test(s);"), ("c", "const d1 = a / b / c;"),
    # No `;` inside the braces: with one it is a one-line block measuring 3 (GE-127d-3-vi).
    ("c", "const d2 = (a) / 2; // c"), ("c", 'function f() { return /"/ }'), ("c", "x = y++ / 2;"),
    ("m", "// genuine"), ("m", "// genuine two"), ("m", "/* genuine block */"), ("c", "const after = 1;"),
]
JSX_LINES = [
    ("c", "const el = ("), ("c", '  <div title="https://example.com/a">'),
    ("c", "    don't stop // not a comment /* nor this */ \"quoted\""), ("m", "    {/* real comment */}"),
    ("c", "    <span>text</span>"), ("c", "  </div>"), ("c", ");"), ("c", "const id = <T,>(x) => x;"),
]
TS_ASSERTION_LINES = [
    ("c", "const a = <string>someValue;"), ("c", "const b = 'it' + \"s\";"), ("m", "// genuine"), ("c", "const c = 2;"),
]


def corpus_text(rows: list[tuple[str, str]], repeat: int, pad_code: int, ext: str) -> tuple[str, int]:
    """Repeat a literal corpus *repeat* times with *pad_code* generic code lines."""
    lines = [code_line(ext, i) for i in range(pad_code)]
    for _ in range(repeat):
        lines += [text for _kind, text in rows]
    per_repeat = sum(1 for kind, _ in rows if kind == "c")
    return "\n".join(lines) + "\n", pad_code + repeat * per_repeat


UNTOKENIZABLE = {
    ".js": ("JavaScript", "const a = 1;\n/* never closed\nconst b = 2;\n", "const a = 1;\n/* closed */\nconst b = 2;\n"),
    ".py": ("Python", 'x = 1\n"""never closed\ny = 2\n', 'x = 1\n"""closed"""\ny = 2\n'),
    ".sql": ("SQL", "CREATE FUNCTION f() RETURNS int AS $$ BEGIN RETURN 1;\n",
             "CREATE FUNCTION f() RETURNS int AS $$ BEGIN RETURN 1; END; $$ LANGUAGE plpgsql;\n"),
    ".sh": ("shell", 'echo "never closed\necho two\n', 'echo "closed"\necho two\n'),
}

ACCEPTED_SYNTAX = {
    ".js": "const a = `x ${`y ${z}`} w`;\nconst b = o?.p;\nconst c = o?.[k];\nconst d = o?.();\nconst re = /\\/\\*/;\nconst re2 = /[/*]/;\n",
    ".py": 'name = 1\ntext = f"{name!r:>{len(\'#\')}} {\'#\'}"\nother = f"{\'# inside field\'}"\n',
}

OLD_RULE_SOURCE = (
    "import re\n"
    "_T1 = re.compile(r'\"\"\".*?\"\"\"\\r?\\n?', re.DOTALL)\n"
    "_T2 = re.compile(r\"'''.*?'''\\r?\\n?\", re.DOTALL)\n"
    "_B = re.compile(r'/\\*.*?\\*/\\r?\\n?', re.DOTALL)\n"
    "def old_count(content, *a, **k):\n"
    "    return len(_B.sub('', _T2.sub('', _T1.sub('', content))).splitlines())\n"
)


def runs_to_blocks(js_text: str) -> str:
    """Rewrite every run of ``//`` lines into one ``/* */`` block (the KI's conversion)."""
    out: list[str] = []
    run: list[str] = []

    def flush() -> None:
        if not run:
            return
        texts = [ln.strip()[2:] for ln in run]
        indent = run[0][: len(run[0]) - len(run[0].lstrip())]
        if any("*/" in t for t in texts):
            out.extend(run)
        else:
            out.extend([f"{indent}/*", *[f"{indent} {t.strip()}" for t in texts], f"{indent} */"])
        run.clear()

    for line in js_text.split("\n"):
        if line.lstrip().startswith("//"):
            run.append(line)
        else:
            flush()
            out.append(line)
    flush()
    return "\n".join(out)
