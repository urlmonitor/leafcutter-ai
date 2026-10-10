"""
MODULE: product_truth_dependencies
GOAL: Hold the validator's guarded third-party imports and decide, from the
    ImportError actually raised, what the refusal to run must say -- naming the
    module that failed to import rather than always blaming jsonschema.
BUSINESS CONTEXT: Schema validation is mandatory, so a missing dependency makes
    the validator refuse (exit 2) instead of warn-and-skip. One try/except used
    to wrap both `import jsonschema` and `from product_truth_contracts import ...`,
    so a jsonschema older than 4.18 (which lacks `referencing`, imported by
    product_truth_contracts) was reported as "jsonschema is not installed" while
    jsonschema was installed -- a false diagnosis the user cannot act on.
ARCHITECTURE: Leaf module that must never raise on import. At module level it
    imports only the stdlib plus the two guarded imports below; the first
    ImportError is kept in _IMPORT_FAILURE. A name whose import failed is bound to
    None here (never left unbound) so `from product_truth_dependencies import ...`
    cannot itself fail; validate_product_truth.main() calls dependency_refusal()
    and returns before any code that would touch those names runs.

DECISION HISTORY
- 2026-10-08 00:00 [python-coder]: UXP-300-4 -- the two guarded imports, the kept
  ImportError, the jsonschema-missing message, the version lookup and the refusal
  builder moved here from validate_product_truth.py, which the change had pushed
  from 398 to 441 measured lines against the 400-line ratchet. Refusal texts and
  exit code are unchanged. (UXP-300-4)
"""
from __future__ import annotations

import importlib.metadata

_IMPORT_FAILURE: ImportError | None = None
try:
    import jsonschema
except ImportError as _exc:
    jsonschema = None  # type: ignore[assignment]
    _IMPORT_FAILURE = _exc
try:
    from product_truth_contracts import check_contracts, contract_summary
except ImportError as _exc:
    check_contracts = None  # type: ignore[assignment]
    contract_summary = None  # type: ignore[assignment]
    _IMPORT_FAILURE = _IMPORT_FAILURE or _exc

_JSONSCHEMA_MISSING_MSG = (
    "FAIL: jsonschema is required for product-truth validation but is not installed. "
    "Install it (pip install 'jsonschema>=4.0', or pip install -r requirements-dev.txt). "
    "Refusing to run — schema validation must not silently no-op."
)


def _failed_module_name(exc: ImportError) -> str:
    """Name the module that failed to import; fall back to the error text."""
    return exc.name or str(exc) or "an unknown module"


def _installed_jsonschema_version() -> str:
    """Installed jsonschema version via metadata only (never imports it)."""
    try:
        return importlib.metadata.version("jsonschema")
    except importlib.metadata.PackageNotFoundError:
        return "unknown (no jsonschema distribution metadata found)"


def dependency_refusal() -> str | None:
    """Return the refusal text for a failed dependency import, or None when all loaded."""
    if _IMPORT_FAILURE is None:
        return None
    name = _failed_module_name(_IMPORT_FAILURE)
    if name == "jsonschema" or name.startswith("jsonschema."):
        return _JSONSCHEMA_MISSING_MSG
    version = _installed_jsonschema_version()
    hint = (
        f"The installed jsonschema {version} is too old to provide `referencing` "
        "(jsonschema >= 4.18 depends on it); upgrade with pip install -U 'jsonschema>=4.18'. "
        if name.split(".")[0] == "referencing"
        else ""
    )
    return (
        f"FAIL: product-truth validation could not import required module '{name}' "
        f"(installed jsonschema: {version}). {hint}"
        "Refusing to run — schema validation must not silently no-op."
    )
