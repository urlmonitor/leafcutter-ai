"""
MODULE: _rc_edit
GOAL: The ONLY writer of the requirement rule check: apply one field-targeted repair to
    one record file, leave every other byte untouched, and prove it before replacing.
BUSINESS CONTEXT: ACD-2500a-2. Three families have exactly one correct repair; the check
    may write `covered_by`, `components` and `readiness` and nothing else. The
    write-locked fields (criteria, title, req_status, depends_on, ...) must be impossible
    to touch even through a bug in a family.
ARCHITECTURE: Five layers (architect note section 3): (1) `REPAIRABLE_FIELDS` is the
    single allowlist and `apply_edit` raises `ProtectedFieldError` for anything else;
    families cannot write, only the orchestrator calls this module. (2) A unit test pins
    the allowlist disjoint from check_ac_governance's protected fields. (3) Before the
    file is replaced the old and new text are parsed with yaml.SafeLoader and must be
    equal except for the target key, whose new value must be the intended one; otherwise
    `EditError` and the original is untouched. (4)/(5) are byte-level and property tests.
    Edits never load-and-dump: the file is read and written with newline="" (CRLF files
    stay CRLF), only column-0 `key:` lines are acted on (prose inside a `|` block that
    quotes `covered_by:` is never edited), and a key's value extends over every following
    line that is indented or starts with `- ` at column 0 (this store has both the
    indented and the unindented list style in one record). `how` is ("set", value) or
    ("append", item); a missing key is inserted after the `id:` line. The write is an
    atomic temp-file + os.replace in the same directory. Deployed flat.

DECISION HISTORY:
  - 2026-10-14 [python-coder/ACD-2500a-2]: Created. Deliberately does NOT reuse
    backfill_components._backfill_file: it treats `components: []` as missing and would
    insert a SECOND `components:` key (PyYAML keeps the last), so the present-but-empty
    case is replaced in place here.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml

REPAIRABLE_FIELDS = frozenset({"covered_by", "components", "readiness"})


class ProtectedFieldError(ValueError):
    """Raised when an edit targets a field outside REPAIRABLE_FIELDS."""


class EditError(RuntimeError):
    """Raised when an edit cannot be made safely; the original file is left untouched."""


def _scalar(value: Any) -> str:
    """One YAML flow scalar for `value`, quoted only when YAML requires it."""
    return yaml.safe_dump([value], default_flow_style=True, width=10**6).strip()[1:-1]


def _flow(values: list[Any]) -> str:
    """A YAML flow list `[a, b]` of `values`."""
    return "[" + ", ".join(_scalar(v) for v in values) + "]"


def _is_value_line(line: str) -> bool:
    """True for a line that continues a key's value: indented, or a column-0 `- ` item."""
    bare = line.rstrip("\r")
    return bool(bare) and (bare[0] in " \t" or bare == "-" or bare.startswith("- "))


def _span(lines: list[str], field: str) -> tuple[int, int] | None:
    """(first, last) line indexes of column-0 `field:` and its value lines; None when absent."""
    pattern = re.compile(rf"^{re.escape(field)}:(\s|$)")
    hits = [i for i, line in enumerate(lines) if pattern.match(line)]
    if len(hits) > 1:
        reason = f"key {field!r} appears {len(hits)} times at column 0"
        raise EditError(reason)
    if not hits:
        return None
    first = last = hits[0]
    for k in range(first + 1, len(lines)):
        bare = lines[k].rstrip("\r")
        if _is_value_line(lines[k]):
            last = k
        elif bare.strip() == "":
            continue
        else:
            break
    return first, last


def _block_items(lines: list[str]) -> tuple[list[str], str]:
    """(item texts, indent) of a block list given its value lines (the key line excluded)."""
    items: list[str] = []
    indent = "  "
    for line in lines:
        bare = line.rstrip("\r")
        match = re.match(r"^(\s*)- (.*)$", bare)
        if match:
            if not items:
                indent = match.group(1)
            items.append(match.group(2).split(" #")[0].strip())
    return items, indent


def _render_block(field: str, values: list[Any], indent: str, cr: str) -> list[str]:
    """The lines of a block list for `field` (key line plus one `- item` line each)."""
    return [f"{field}:{cr}", *[f"{indent}- {_scalar(v)}{cr}" for v in values]]


def _edited_lines(lines: list[str], span: tuple[int, int] | None, field: str, how: tuple, cr: str) -> list[str]:
    """`lines` with the edit applied. Raises EditError for a shape this writer will not guess."""
    op, value = how
    if span is None:
        if op == "set" and not isinstance(value, list):
            new = [f"{field}: {_scalar(value)}{cr}"]
        else:
            new = _render_block(field, value if op == "set" else [value], "  ", cr)
        at = next((i + 1 for i, line in enumerate(lines) if line.startswith("id:")), len(lines))
        return [*lines[:at], *new, *lines[at:]]
    first, last = span
    head = lines[first].rstrip("\r")
    rest = head[len(field) + 1:].strip()
    items, indent = _block_items(lines[first + 1:last + 1])
    block_style = bool(items) and rest in ("", "null", "~")
    if op == "set":
        if not isinstance(value, list):
            return [*lines[:first], f"{field}: {_scalar(value)}{cr}", *lines[last + 1:]]
        new = _render_block(field, value, indent, cr) if block_style else [f"{field}: {_flow(value)}{cr}"]
        return [*lines[:first], *new, *lines[last + 1:]]
    # append
    if block_style:
        return [*lines[:last + 1], f"{indent}- {_scalar(value)}{cr}", *lines[last + 1:]]
    if rest.startswith("[") and rest.endswith("]"):
        inner = rest[1:-1].strip()
        grown = f"{inner}, {_scalar(value)}" if inner else _scalar(value)
        return [*lines[:first], f"{field}: [{grown}]{cr}", *lines[last + 1:]]
    if rest in ("", "null", "~"):
        return [*lines[:first], f"{field}: [{_scalar(value)}]{cr}", *lines[last + 1:]]
    reason = f"cannot append to {field!r}: unsupported value shape {rest!r}"
    raise EditError(reason)


def _expected(old: dict, field: str, how: tuple) -> Any:
    """The value `field` must hold after applying `how` to the parsed `old` record."""
    op, value = how
    if op == "set":
        return value
    current = old.get(field)
    base = list(current) if isinstance(current, list) else []
    return base if value in base else [*base, value]


def _verify(old_text: str, new_text: str, field: str, how: tuple) -> None:
    """Prove the two texts differ in the target key only, and that key holds the intended value."""
    try:
        old = yaml.load(old_text, Loader=yaml.SafeLoader)  # noqa: S506
        new = yaml.load(new_text, Loader=yaml.SafeLoader)  # noqa: S506
    except yaml.YAMLError as exc:
        reason = f"edited text does not parse: {exc}"
        raise EditError(reason) from exc
    if not isinstance(old, dict) or not isinstance(new, dict):
        reason = "record is not a mapping"
        raise EditError(reason)
    rest_old = {k: v for k, v in old.items() if k != field}
    rest_new = {k: v for k, v in new.items() if k != field}
    if rest_old != rest_new:
        reason = f"edit changed a field other than {field!r}"
        raise EditError(reason)
    if new.get(field) != _expected(old, field, how):
        reason = f"{field!r} does not hold the intended value after the edit"
        raise EditError(reason)


def _atomic_write(path: Path, text: str) -> None:
    """Write `text` to a temp file beside `path`, then os.replace it over `path`."""
    fd, temp = tempfile.mkstemp(dir=str(path.parent), prefix=".rc_edit_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temp, path)
    except OSError:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


def apply_edit(path: Path, field: str, how: tuple) -> bool:
    """Apply ("set", value) or ("append", item) to `field` of the record at `path`.

    Returns True when the file changed, False when it already held the intended value.
    Raises ProtectedFieldError for a non-repairable field and EditError when the edit
    cannot be proven safe; the file is only replaced after the proof passes.
    """
    if field not in REPAIRABLE_FIELDS:
        reason = f"field {field!r} is not repairable (allowed: {sorted(REPAIRABLE_FIELDS)})"
        raise ProtectedFieldError(reason)
    if how[0] not in ("set", "append"):
        reason = f"unknown edit operation {how[0]!r}"
        raise EditError(reason)
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            old_text = handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        reason = f"cannot read {path} for the {field!r} repair: {exc}"
        raise EditError(reason) from exc
    old = yaml.load(old_text, Loader=yaml.SafeLoader)  # noqa: S506
    if isinstance(old, dict) and old.get(field) == _expected(old, field, how) and field in old:
        return False
    cr = "\r" if "\r\n" in old_text else ""
    unterminated = bool(cr) and not old_text.endswith("\n")  # CRLF file whose last line has no EOL
    lines = (old_text + "\r\n" if unterminated else old_text).split("\n")
    new_text = "\n".join(_edited_lines(lines, _span(lines, field), field, how, cr))
    if unterminated:
        new_text = new_text.removesuffix("\r\n")
    _verify(old_text, new_text, field, how)
    _atomic_write(Path(path), new_text)
    return True
