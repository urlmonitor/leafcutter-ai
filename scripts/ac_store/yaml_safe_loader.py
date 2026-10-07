"""
MODULE: yaml_safe_loader
GOAL: Give every reader of the acceptance-criteria store (and every other
    first-party YAML reader in this package) one shared accessor that picks
    PyYAML's C-backed safe loader when it is available and falls back to the
    pure-Python one when it is not -- instead of each of the 70+ call sites
    naming ``yaml.safe_load`` directly.
BUSINESS CONTEXT: Measured over the real 4,635-file AC store on 2026-10-05: a
    full sweep with the pure-Python safe parser takes 24.68s; the identical
    sweep through ``yaml.CSafeLoader`` takes 1.86s -- a 13.25x difference. The
    two headline consumers of a full sweep -- the required "AC store valid"
    pull-request gate (``validate_ac_schema.py``) and a ticket-generation dry
    run -- each spend about 95% of their wall-clock time inside the parser.
    The store only grows (3,340 records in August 2026, 4,635 in October), so
    this cost compounds every month it is deferred.
ARCHITECTURE: A single, uncached accessor module, generalising the one
    existing in-repo precedent at scripts/render_effective_prompt.py:57
    (``_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)``). Three
    public functions:

    - ``get_safe_yaml_loader()`` -- resolves the loader CLASS. Re-resolved on
      every call (never cached at import time) so a test that simulates the
      C extension's absence (deleting ``yaml.CSafeLoader`` for the duration
      of a check) is actually exercised rather than measuring a choice an
      earlier import already baked in.
    - ``load_yaml_text(text)`` -- parses a YAML string through that loader.
    - ``load_yaml_file(path)`` -- reads ``path`` as UTF-8 and parses it via
      ``load_yaml_text``.

    Call sites that already hold an open file handle or a already-read
    string are expected to call ``yaml.load(x, Loader=get_safe_yaml_loader())``
    directly rather than route through ``load_yaml_text``/``load_yaml_file``
    -- both shapes resolve the SAME parser choice through the SAME function,
    which is the property the AC's seam test (no direct caller of the
    pure-Python ``safe_load`` entry point left anywhere in the package)
    actually checks.

    DECISION HISTORY:
    - 2026-10-05 [python-coder/TQ-600a-11]: Created. The guarded
      ``getattr(yaml, "CSafeLoader", yaml.SafeLoader)`` form is used rather
      than a hard ``from yaml import CSafeLoader`` import, because the C
      extension is genuinely absent on some adopter installs of this
      package (PyYAML built without libyaml) and a hard import would make
      the package uninstallable there, failing at import time on an
      unrelated command (TQ-600a-11's own it_requirement). No
      ``yaml.__with_libyaml__`` or version-string sniffing is used for the
      same reason it_requirements forbid it: a wheel can report the flag
      and still not expose the class.

      BEHAVIOUR CHANGE, STATED EXPLICITLY (not merely a speed-up): probing
      the four historically-divergent YAML input classes this AC names
      (duplicate mapping keys, timestamp scalars, ambiguous numeric literal
      forms, merge keys) under the installed PyYAML 6.0.1 + libyaml found
      the pure-Python ``SafeLoader`` and ``CSafeLoader`` AGREE on all four.
      The one real divergence found was RECURSION DEPTH: an input built from
      600 levels of nested empty flow sequences (``"[" * 600 + "]" * 600``)
      makes the pure-Python parser raise ``RecursionError`` (it hits
      Python's own recursion limit via PyYAML's recursive-descent
      composer), while ``CSafeLoader`` -- implemented in C, not subject to
      Python's recursion limit -- parses it without error. Switching the
      default parser therefore REMOVES a recursion-depth guard that the
      pure-Python path incidentally provided. For this package's own
      first-party store, read only by internal tooling (never by a
      transitively-untrusted upload path), that trade is accepted -- but it
      is a widening of what the parser accepts, not a pure performance
      change, and is recorded here rather than left for a future reader to
      rediscover. This does NOT widen the SAFETY posture: ``CSafeLoader`` is
      the C implementation of the identical "safe" schema as
      ``SafeLoader`` -- neither the unsafe full loader (``yaml.Loader`) nor
      ``yaml.load`` without an explicit ``Loader=`` is used anywhere in this
      module.

    - 2026-10-07 [python-coder/TQ-600a-11 fix-pass]: A FIFTH divergence class
      was found, where the four named above read as an exhaustive list but
      are not: a TAB CHARACTER INSIDE A FLOW-CONTEXT SEQUENCE, e.g.
      ``"key: [\\t]\\n"``. The pure-Python ``SafeLoader`` correctly raises
      ``yaml.scanner.ScannerError`` on this input (a tab is not valid YAML
      whitespace inside flow context); ``CSafeLoader`` parses it
      PERMISSIVELY as ``{'key': []}``, silently dropping the malformed
      content instead of rejecting it. Unlike the recursion-depth divergence
      above, this one is NOT accepted package-wide: it was found because it
      defeats the specific fail-open ``except yaml.YAMLError`` guard in the
      AC store's own malformed-file detection
      (``_ac_store_index._load_one_yaml_file``, fed by
      ``templates/scripts/commit_guardian/_ac_schema_validators.load_yaml``)
      -- with ``CSafeLoader`` in place there, a malformed AC file was
      silently accepted as valid instead of being skipped with a warning,
      precisely the phantom-done failure class this repository's guardrails
      exist to prevent. That ONE call site was reverted to the pure-Python
      ``yaml.SafeLoader`` for this reason (see its own DECISION HISTORY for
      the measured cost); every other call site in this package is
      unaffected and stays on the fast accessor. A reader relying on "four
      divergence classes, all checked and found to agree" as exhaustive
      would be misled without this entry.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def get_safe_yaml_loader() -> type:
    """Return the fastest safe YAML loader class available right now.

    Resolves ``yaml.CSafeLoader`` (the libyaml-backed implementation of the
    SAME safe schema as ``yaml.SafeLoader``) when the installed PyYAML
    exposes it, else falls back to the pure-Python ``yaml.SafeLoader``. The
    choice is made fresh on every call via ``getattr(..., default)`` --
    never cached at import time and never decided by inspecting
    ``yaml.__with_libyaml__`` or a version string -- so an environment (or a
    test that simulates one) where the C extension is absent is handled
    directly rather than assumed.

    Returns:
        ``yaml.CSafeLoader`` if present on the installed ``yaml`` module,
        otherwise ``yaml.SafeLoader``. Never the unsafe full ``yaml.Loader``.
    """
    return getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def load_yaml_text(text: str) -> Any:
    """Parse a YAML string through the fastest available safe loader.

    This is a pure, in-memory parse -- no I/O crosses a process or system
    boundary here, so per this repo's Error Handling Policy Rule 4 it is not
    wrapped in try/except. A malformed document raises ``yaml.YAMLError``
    (or a subclass) straight through to the caller, exactly as
    ``yaml.safe_load`` already does.

    Args:
        text: Raw YAML document text.

    Returns:
        The parsed Python object (dict, list, scalar, or None for an empty
        document), identical in shape to what the pure-Python ``safe_load``
        entry point would have returned for every real AC-store record this
        AC's own record-by-record comparison (TQ-600a-11-ii) checks.
    """
    return yaml.load(text, Loader=get_safe_yaml_loader())


def load_yaml_file(path: str | Path) -> Any:
    """Read ``path`` as UTF-8 text and parse it via :func:`load_yaml_text`.

    Args:
        path: Filesystem path to a YAML file.

    Returns:
        The parsed Python object.

    Raises:
        OSError: If ``path`` cannot be read (missing, permission denied,
            etc.) -- logged at WARNING before re-raising, per this repo's
            Error Handling Policy Rule 1 (external I/O must be wrapped) and
            Rule 3 (never silently swallow).
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("yaml_safe_loader: failed to read %s: %s", path, exc)
        raise
    return load_yaml_text(text)
