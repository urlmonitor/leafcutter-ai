"""
MODULE: doc_type_validators
GOAL: Load doc_types.json and validate the type frontmatter enum for docs/**/*.md
      files, and validate requires_documentation ticket frontmatter entries against
      the same enum.
BUSINESS CONTEXT: Extracted to keep frontmatter_validators.py under the 400-line
      limit while making doc_types.json the single source of truth for the doc type
      enum (EPIC-ArchitectureDocsEnforcement ticket 08).
ARCHITECTURE: Resolves doc_types.json via a portable ``__file__``-ancestor
      directory walk (``_find_doc_types_json()``) rather than a hand-counted
      ``parents[N]`` walk, mirroring the sibling ``diagram_type_validators.
      _find_diagram_types_json()`` pattern already used for the same category
      of problem (a JSON declaring file that must resolve identically from
      both the source-tree layout ``templates/scripts/commit_guardian/`` and
      the deployed layout ``.leafcutter/scripts/commit_guardian/``).

      NOTE ON RESOLVER CHOICE: AC GE-120's it_requirements name
      ``_resolve_root.find_project_root()`` as "the established resolver ...
      reuse it rather than hand-counting parents[N]". That resolver prefers
      ``git rev-parse --show-toplevel`` — i.e. it resolves relative to the
      *invoking process's cwd*, not to where this script itself is installed.
      doc_types.json is a package-bundled declaring file tied to THIS
      script's own location, not to whichever git repo the caller's cwd
      happens to be in (verified empirically: AC GE-120's own test 2/3 stage
      files in an isolated throwaway git repo and invoke the deployed hook
      with cwd set to that repo — using find_project_root() there resolves
      to the throwaway repo, which has no config/doc_types.json, and both
      tests fail with FileNotFoundError). The test module's own docstring
      states the intended computation is "keyed off its own __file__ ... so
      it is unaffected by which cwd the hook is invoked from" — which only
      an ancestor walk from ``__file__`` satisfies. This module therefore
      reuses the diagram_type_validators.py ancestor-walk *pattern* (no
      hand-counted parents[N], portable across both layouts) rather than
      the cwd-dependent resolver, since the two mechanisms disagree here and
      the test is the mechanically-enforced ground truth.

      An absent, unreadable, or malformed declaring file raises an observable
      error naming the file instead of silently substituting the narrower
      DOC_FM_ALLOWED_TYPES fallback (AC GE-120).
"""

import json
from pathlib import Path
from typing import Any

_DOC_TYPES_CACHE: dict | None = None


def _find_doc_types_json(_start_dir: Path | None = None) -> Path:
    """Locate config/doc_types.json via a portable ancestor-directory walk.

    Checks both ``config/doc_types.json`` (self-hosted / dev layout) and
    ``leafcutter/config/doc_types.json`` (consumer-deployed workspace layout,
    per ADR-001) at each ancestor level, starting from this module's own
    ``__file__`` location and stopping at the filesystem root. This is
    ``__file__``-relative, not cwd-relative — it resolves identically no
    matter what directory the invoking process's cwd is set to, which is
    what makes it correct for both the source-tree layout
    (``templates/scripts/commit_guardian/``) and the deployed layout
    (``.leafcutter/scripts/commit_guardian/``). Mirrors
    ``diagram_type_validators._find_diagram_types_json()``.

    Args:
        _start_dir: Override the starting directory (used in tests). Defaults
            to the directory containing this script file.

    Returns:
        Path: The first existing candidate found while walking ancestors. If
            none exists, returns the ``config/doc_types.json`` candidate
            under this script's own directory, so callers get a real,
            nameable path in their error message rather than ``None``.
    """
    script_dir = _start_dir if _start_dir is not None else Path(__file__).resolve().parent
    candidates_checked: list[Path] = []
    for ancestor in [script_dir, *script_dir.parents]:
        for rel in ("config/doc_types.json", "leafcutter/config/doc_types.json"):
            candidate = ancestor / rel
            candidates_checked.append(candidate)
            if candidate.exists():
                return candidate
    return candidates_checked[0]


_DOC_TYPES_JSON: Path = _find_doc_types_json()


def _load_doc_types() -> dict:
    """Load and cache doc type definitions from doc_types.json.

    doc_types.json is the single source of truth for the doc type enum (see the
    file's own ``_comment``). An absent, unreadable, or malformed declaring file
    is a configuration defect, not a degraded-but-usable state: this raises
    rather than silently substituting the narrower DOC_FM_ALLOWED_TYPES fallback.
    A guard that quietly answers a different question than the one it was
    configured with is enforcing a rule nobody wrote (AC GE-120).

    Returns:
        dict: Mapping of doc_type key to its definition dict. Each value has
            ``description``, ``writer_agent`` (str or None), and ``default_path``
            fields.

    Raises:
        FileNotFoundError: If doc_types.json does not exist at the resolved
            project-root path.
        OSError: If doc_types.json exists but cannot be read.
        json.JSONDecodeError: If doc_types.json exists but is not valid JSON.
    """
    global _DOC_TYPES_CACHE
    if _DOC_TYPES_CACHE is not None:
        return _DOC_TYPES_CACHE

    if not _DOC_TYPES_JSON.exists():
        raise FileNotFoundError(
            f"doc_type_validators: declaring file not found: {_DOC_TYPES_JSON}. "
            "config/doc_types.json is the single source of truth for the doc "
            "type enum; refusing to silently fall back to a narrower built-in list."
        )

    try:
        with open(_DOC_TYPES_JSON, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as exc:
        raise OSError(
            f"doc_type_validators: cannot read declaring file {_DOC_TYPES_JSON}: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise json.JSONDecodeError(
            f"doc_type_validators: declaring file {_DOC_TYPES_JSON} contains "
            f"invalid JSON: {exc.msg}",
            exc.doc,
            exc.pos,
        ) from exc

    _DOC_TYPES_CACHE = data.get("doc_types", {})
    return _DOC_TYPES_CACHE


def is_component_exempt(doc_type: str | None) -> bool:
    """Return True if the declaring file marks *doc_type* as not component-linked.

    Derives the exemption from doc_types.json's own ``description`` field (e.g.
    the ``card`` entry reads "...Not component-linked.") rather than hardcoding
    a second list of exempt type names — a second hardcoded statement about the
    same fact is how the two drift apart (AC GE-120 it_requirements #4). Callers
    that enforce the ``components`` required-field check should consult this
    before flagging a doc as missing ``components``.

    Args:
        doc_type: The frontmatter ``type`` value to check, or None.

    Returns:
        bool: True if the doc type's description marks it as not
            component-linked; False for unknown types, absent descriptions, or
            types without the marker phrase.
    """
    if doc_type is None:
        return False
    known = _load_doc_types()
    entry = known.get(doc_type, {})
    description = str(entry.get("description", ""))
    return "not component-linked" in description.lower()


def validate_doc_type(fm: dict[str, Any]) -> list[str]:
    """Validate the ``type`` field against the allowed doc type enum.

    Reads valid values from ``config/doc_types.json`` (the single source of
    truth). An absent or unreadable declaring file raises rather than
    silently falling back to a narrower built-in list — see
    ``_load_doc_types()``. The ``type`` field is required on docs/ files;
    this function only validates the *value* when the field is present.

    Args:
        fm: Parsed frontmatter dictionary.

    Returns:
        list[str]: Error message if type is invalid, empty list when the field
            is absent or contains a valid value.
    """
    doc_type = fm.get("type")
    if doc_type is None:
        return []  # Absence already caught by validate_required_fields
    known = _load_doc_types()
    if doc_type not in known:
        return [
            f"unknown doc type: {doc_type}; "
            f"valid values: {', '.join(sorted(known.keys()))}"
        ]
    return []


def validate_requires_documentation(fm: dict[str, Any]) -> list[str]:
    """Validate the optional ``requires_documentation`` ticket frontmatter field.

    When present, must be a YAML list where each entry is a key in
    ``doc_types.json``. Tickets missing this field pass without error
    (field is optional, backward-compatible).

    Args:
        fm: Parsed frontmatter dictionary.

    Returns:
        list[str]: Error messages for invalid entries; empty list when the
            field is absent or all entries are valid.
    """
    value = fm.get("requires_documentation")
    if value is None:
        return []  # Optional field; absence is fine
    if not isinstance(value, list):
        return ["'requires_documentation' must be a list (e.g. [how_to, reference])"]
    known = _load_doc_types()
    if not known:
        return []  # doc_types.json's "doc_types" key is empty — permissive fallback
    errors: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            errors.append(
                f"'requires_documentation' entries must be strings; got {entry!r}"
            )
        elif entry not in known:
            errors.append(
                f"unknown doc_type in requires_documentation: {entry}; "
                f"valid values: {', '.join(sorted(known.keys()))}"
            )
    return errors


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-08-18 [python-coder/GE-120]: Replaced the hand-counted
  ``parents[2]`` path computation (resolved to the never-existent
  ``.leafcutter/leafcutter/config/doc_types.json`` in the deployed layout
  and ``templates/leafcutter/config/`` in the source layout) with
  ``_find_doc_types_json()``, a ``__file__``-ancestor directory walk mirroring
  ``diagram_type_validators._find_diagram_types_json()``. AC GE-120's own
  it_requirements named ``_resolve_root.find_project_root()`` as the resolver
  to reuse, but that resolver is cwd-dependent (prefers ``git rev-parse
  --show-toplevel``); GE-120's own tests 2/3 stage files in an isolated
  throwaway git repo and invoke the deployed hook with cwd set there, so
  find_project_root() resolves to the throwaway repo (no config/doc_types.json)
  and both tests fail — confirmed empirically. The test module's docstring
  states the intended computation is "keyed off its own __file__ ... so it is
  unaffected by which cwd the hook is invoked from", which only a __file__
  ancestor walk satisfies; used the existing diagram_type_validators.py
  pattern instead of introducing a novel scheme. Because config/doc_types.json
  was never actually read, the 10-entry declaring file was silently replaced
  by the 7-entry DOC_FM_ALLOWED_TYPES fallback: `card` (every generated agent
  card) and the canonical `how_to` spelling were rejected. Also removed the
  silent ``.exists()`` fallthrough and the swallowed ``except
  (json.JSONDecodeError, OSError): pass`` — ``_load_doc_types()`` now raises
  an error naming the declaring file's path when it is absent, unreadable, or
  malformed, instead of substituting the narrower built-in list. Added
  ``is_component_exempt()`` so the "Not component-linked" property (currently
  only in doc_types.json's free-text ``description`` field, e.g. the ``card``
  entry) can be derived from the declaring file rather than hardcoded a
  second time — NOT YET WIRED into
  frontmatter_validators.validate_required_fields(), which lives in a
  different source file (see sign-off comment for the scope boundary). Does
  not widen DOC_FM_ALLOWED_TYPES; the fix is to read the file. (AC GE-120)
- 2026-05-14 00:00 [EPIC-ArchitectureDocsEnforcement/ticket 08]:
  Created. Extracted doc-type validation into this module to keep
  frontmatter_validators.py under 400 lines and make doc_types.json
  the SSOT for the type: enum on docs/ files. Added
  validate_requires_documentation() for the new optional ticket
  frontmatter field introduced by ticket 08. Mirrors the
  diagram_type_validators.py pattern introduced in ticket 05.
====================================================================
"""
