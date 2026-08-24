"""
MODULE: check_ac_schema
GOAL: Pre-commit hook validating staged AC YAML files against the JSON Schema,
    enforcing pattern_bindings completeness and implements_pattern field-preservation.
BUSINESS CONTEXT: Malformed AC files are rejected at commit time. The
    pattern_bindings completeness and field-preservation checks enforce ACS-500f.
ARCHITECTURE: Phase 1 validates only STAGED AC YAML files against
    config/ac_store_schema.json; staged files are determined via
    `git diff --cached --name-only --diff-filter=AM` (or the
    HOOK_TEST_STAGED_FILES env var seam for tests). Cross-file checks are
    delegated to _ac_schema_validators.py and use the full on-disk store as a
    lookup index (not narrowed to staged only). Phase 2 compares HEAD vs staged
    for each modified AC and blocks if implements_pattern was present in HEAD
    but absent in staged. HEAD blobs for all modified files are fetched in a
    single batched ``git cat-file --batch`` invocation (O(1) subprocesses
    regardless of the number of staged-modified files). Fail-open.

Exit codes:
    0 - All staged AC YAML files pass validation
    1 - One or more validation errors detected

DOC_LINKS:
  - docs/reference/ac-schema.md

DECISION HISTORY:
  - 2026-06-17 [python-coder/ACS-500f-1]: Created. Phase 1: schema +
    pattern_bindings completeness (cross-file checks in _ac_schema_validators.py).
    Phase 2: implements_pattern field-preservation via HEAD vs staged diff.
  - 2026-06-18 [python-coder/ACS-500f-1-i]: Verified fail-open behavior: the
    __main__ exception handler (added in ACS-500f-1) catches unexpected errors
    and exits 0 with a stderr diagnostic. Unit tests added for all fail-open
    and no-staged-relevant-files paths.
  - 2026-06-22 [python-coder/GE-112]: Fixed validate_manually() running on the
    jsonschema SUCCESS path. Introduced schema_validated flag; validate_manually()
    now runs only as a fallback when jsonschema did not actually execute (schema
    absent, jsonschema not importable, or PyYAML unavailable). The authoritative
    config/ac_store_schema.json verdict is now final when jsonschema ran.
  - 2026-06-23 [python-coder/TICKET-20260622-AcSchemaHookStagedScope]: Scoped
    Phase 1 validation to staged AC YAML files only (staged-added or
    staged-modified under docs/acceptance-criteria/). Added _get_staged_ac_paths()
    analogous to _get_modified_ac_paths(). Cross-file lookup index continues to
    use the full on-disk store. HOOK_TEST_STAGED_FILES env var seam added for
    tests (mirrors HOOK_TEST_FILES_MODIFIED for Phase 2).
  - 2026-06-29 [python-coder/fix/ac-schema-git-batch]: Replaced per-file
    ``git show HEAD:<path>`` with a single batched ``git cat-file --batch``
    invocation in _fetch_head_yaml_batch(). _load_head_yaml() now accepts an
    optional head_cache dict for O(1) lookups; the single-subprocess fallback
    is preserved for any direct callers that do not supply the cache. stdout
    is read in binary mode for byte-accurate size slicing (multibyte-safe).
    Removed _assign_fallback_yaml() and all mock-tolerance branches — the
    parser now handles only real git cat-file protocol output.
  - 2026-06-30 [python-coder/TICKET-20260629-AC_Hook_Store_Index]: Replaced the
    per-invocation _find_ac_files + _build_ac_index store walk in main() with a
    call to _ac_store_index.get_ac_index(). The git cat-file --batch optimization
    from PR #185 is preserved unchanged. The shared mtime-keyed cached index is
    parsed exactly once per commit across all four AC guardrail hooks.
  - 2026-07-08 [feature/ac-source-of-truth-test-spec]: Wired validate_test_contract()
    into the per-file validation pass so a staged leaf code AC must declare a test
    contract (test_spec or test_required: false). ACs are the source of truth for
    what test-writer must test. (AC BO-2000e)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from _ac_schema_validators import (  # noqa: E402
    load_yaml, load_yaml_from_string, load_yaml_manual,
    validate_criteria_not_pattern_duplicate, validate_declares_side_effect,
    validate_deprecated_pattern_reference, validate_manually,
    validate_pattern_bindings_completeness, validate_test_contract,
    validate_with_jsonschema,
)

try:
    from _ac_store_index import get_ac_index  # type: ignore[import]
    _AC_STORE_INDEX_AVAILABLE = True
except ImportError:
    _AC_STORE_INDEX_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AC_GLOB_PATTERN = "docs/acceptance-criteria"
SCHEMA_PATH = "config/ac_store_schema.json"
_HOOK_PREFIX = "[check-ac-schema]"
_AC_STORE_DIR = "docs/acceptance-criteria"

# ---------------------------------------------------------------------------
# Project root detection
# ---------------------------------------------------------------------------

def _find_project_root() -> Path | None:
    """Find the project root by .git or CLAUDE.md presence.

    Returns:
        Absolute Path of the project root, or None if not found.
    """
    env_root = os.environ.get("HOOK_ROOT")
    if env_root:
        return Path(env_root)

    for ancestor in [Path.cwd(), *Path.cwd().parents]:
        if (ancestor / ".git").exists() or (ancestor / "CLAUDE.md").exists():
            return ancestor

    return None


# ---------------------------------------------------------------------------
# implements_pattern field-preservation check (ACS-500f-1)
# ---------------------------------------------------------------------------

def _fetch_head_yaml_batch(
    rel_paths: list[str],
    project_root: Path | None,
) -> dict[str, dict | None]:
    """Fetch HEAD versions of multiple AC YAML files in ONE git cat-file --batch call.

    Sends all object specs (``HEAD:<path>``) to ``git cat-file --batch`` via
    stdin as UTF-8 bytes and parses the binary batch protocol output.  Each
    found entry in the output has the form::

        <oid> blob <size>\\n
        <content — exactly <size> bytes>\\n

    A missing object yields::

        <spec> missing\\n

    Sizes in the protocol are byte counts, so stdout is read in binary mode and
    content is sliced by byte position before decoding.  This is correct for
    any file encoding, including multibyte UTF-8 content.

    Fail-open semantics: if the protocol is genuinely malformed (should never
    happen with a real git process), a WARNING is printed to stderr and all
    remaining paths receive None rather than raising or producing false positives.

    Args:
        rel_paths: Repo-relative path strings whose HEAD content is needed.
        project_root: Absolute repo root path, or None.

    Returns:
        Mapping of rel_path -> parsed YAML dict (or None on any error/missing).
    """
    result_map: dict[str, dict | None] = {p: None for p in rel_paths}

    if not rel_paths:
        return result_map

    if os.environ.get("HOOK_NO_GIT"):
        return result_map

    git_cmd = ["git"]
    if project_root:
        git_cmd = ["git", "-C", str(project_root)]

    # Encode the stdin payload as bytes; sizes in the protocol are byte counts.
    stdin_bytes = ("\n".join(f"HEAD:{p}" for p in rel_paths) + "\n").encode("utf-8")

    try:
        result = subprocess.run(
            [*git_cmd, "cat-file", "--batch"],
            input=stdin_bytes,
            capture_output=True,
            text=False,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: git cat-file --batch failed: {exc}",
            file=sys.stderr,
        )
        return result_map

    if result.returncode != 0:
        return result_map

    stdout: bytes = result.stdout
    path_iter = iter(rel_paths)
    pos = 0

    while pos < len(stdout):
        # Read header line (terminated by b"\n").
        newline_idx = stdout.find(b"\n", pos)
        if newline_idx == -1:
            break
        header = stdout[pos:newline_idx].decode("utf-8", errors="replace")
        pos = newline_idx + 1

        header_parts = header.split()

        if len(header_parts) == 3 and header_parts[1] == "blob":
            # Found entry: "<oid> blob <size>\n<content><size bytes>\n"
            try:
                size = int(header_parts[2])
            except ValueError:
                # Malformed size field — protocol error; treat remaining as missing.
                print(
                    f"{_HOOK_PREFIX} WARNING: git cat-file --batch returned malformed "
                    f"size in header '{header}'; treating remaining paths as missing.",
                    file=sys.stderr,
                )
                break

            # Read exactly <size> bytes of content, then skip the trailing b"\n".
            content_bytes = stdout[pos:pos + size]
            pos += size + 1  # +1 for the trailing newline after the blob

            try:
                rel_path = next(path_iter)
            except StopIteration:
                break

            try:
                content_str = content_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                print(
                    f"{_HOOK_PREFIX} WARNING: cannot decode HEAD:{rel_path} as UTF-8: "
                    f"{exc}; treating as missing.",
                    file=sys.stderr,
                )
                # result_map[rel_path] stays None — fail-open.
                continue

            result_map[rel_path] = load_yaml_from_string(
                content_str, source_label=f"HEAD:{rel_path}"
            )

        elif len(header_parts) >= 2 and header_parts[-1] == "missing":
            # Missing entry: "<spec> missing\n" — object absent at HEAD (new file).
            try:
                next(path_iter)
            except StopIteration:
                break

        else:
            # Genuinely unrecognised header — real git should never produce this.
            print(
                f"{_HOOK_PREFIX} WARNING: git cat-file --batch returned unrecognised "
                f"header '{header}'; treating remaining paths as missing.",
                file=sys.stderr,
            )
            break

    return result_map


def _load_head_yaml(
    rel_path: str,
    project_root: Path | None,
    head_cache: dict[str, dict | None] | None = None,
) -> dict | None:
    """Load HEAD version of an AC YAML file from git; None on any error.

    When ``head_cache`` is supplied (pre-built by ``_fetch_head_yaml_batch``),
    this function performs an O(1) dict lookup and never spawns a subprocess.
    When ``head_cache`` is None (direct callers, backward compatibility), a
    single ``git show HEAD:<rel_path>`` subprocess is used instead.

    Args:
        rel_path: Repo-relative path.
        project_root: Absolute repo root path, or None.
        head_cache: Optional pre-built mapping from rel_path to parsed dict
            (or None).  When provided, suppresses all subprocess calls for
            this path.

    Returns:
        Parsed dict or None.
    """
    if head_cache is not None:
        return head_cache.get(rel_path)

    if os.environ.get("HOOK_NO_GIT"):
        return None

    git_cmd = ["git"]
    if project_root:
        git_cmd = ["git", "-C", str(project_root)]

    try:
        result = subprocess.run(
            [*git_cmd, "show", f"HEAD:{rel_path}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: git show failed for {rel_path}: {exc}",
            file=sys.stderr,
        )
        return None

    if result.returncode != 0:
        return None

    return load_yaml_from_string(result.stdout, source_label=f"HEAD:{rel_path}")


def _get_staged_ac_paths(root: Path | None = None) -> list[Path]:
    """Return staged (added or modified) AC YAML file paths for Phase 1 validation.

    Checks HOOK_TEST_STAGED_FILES env var first (test seam; colon/pathsep-separated
    list of absolute paths). Falls back to ``git diff --cached --name-only
    --diff-filter=AM`` to find staged-added and staged-modified files under
    ``docs/acceptance-criteria/``. Returns an empty list when HOOK_NO_GIT is set
    or git is unavailable (fail-open).

    Args:
        root: Repository root directory for resolving relative git paths. May be None.

    Returns:
        List of absolute Paths to staged AC YAML files; empty when none found or
        git unavailable.
    """
    # Test seam: HOOK_TEST_STAGED_FILES overrides real git diff.
    test_env = os.environ.get("HOOK_TEST_STAGED_FILES")
    if test_env is not None:
        # Empty string means explicitly no staged files.
        if not test_env.strip():
            return []
        paths: list[Path] = []
        for part in test_env.replace(os.pathsep, "\n").splitlines():
            part = part.strip()
            if not part or not part.endswith(".yaml"):
                continue
            p = Path(part)
            if p.name == "index.yaml":
                continue
            if not p.is_absolute() and root is not None:
                p = root / part
            if p.is_file():
                paths.append(p)
        return paths

    # Fail-open: HOOK_NO_GIT simulates git unavailable.
    if os.environ.get("HOOK_NO_GIT"):
        return []

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: could not run git diff --cached: {exc}",
            file=sys.stderr,
        )
        return []

    if result.returncode != 0:
        return []

    staged_lines = result.stdout.splitlines()

    # Merge commits: a merge stages the ENTIRE incoming branch, so this gate
    # would validate every AC file on the other side — including files that
    # already violate the schema on the target branch today. Those are that
    # branch's pre-existing debt: the merge inherits them byte-for-byte and
    # cannot make them better or worse, and the merge author cannot be the one
    # to author 30+ missing test_spec blocks. Blocking here does not fix the
    # debt, it only makes merging impossible (or teaches people to SKIP the
    # gate). Narrow to files whose result differs from BOTH parents — the
    # content the merge itself introduces. Non-merge commits are unaffected,
    # so a newly added or edited AC is still fully validated.
    # Same fix as check_ac_limits / check_ac_parent_covered_by.
    try:
        merge_probe = subprocess.run(
            ["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        in_merge = merge_probe.returncode == 0
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: could not check MERGE_HEAD: {exc}",
            file=sys.stderr,
        )
        in_merge = False

    if in_merge:
        try:
            other = subprocess.run(
                [
                    "git", "diff", "--cached", "--name-only",
                    "--diff-filter=AM", "MERGE_HEAD",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            print(
                f"{_HOOK_PREFIX} WARNING: could not diff against MERGE_HEAD: {exc}",
                file=sys.stderr,
            )
        else:
            if other.returncode == 0:
                vs_other = {ln.strip() for ln in other.stdout.splitlines() if ln.strip()}
                staged_lines = [ln for ln in staged_lines if ln.strip() in vs_other]

    staged: list[Path] = []
    for line in staged_lines:
        rel = line.strip()
        if not rel or _AC_STORE_DIR not in rel or not rel.endswith(".yaml"):
            continue
        p = Path(rel)
        if p.name == "index.yaml":
            continue
        if not p.is_absolute() and root is not None:
            p = root / rel
        if p.is_file():
            staged.append(p)
    return staged


def _get_modified_ac_paths() -> list[str]:
    """Return staged modified (not added) .yaml paths under docs/acceptance-criteria/.

    Returns:
        List of repo-relative path strings.
    """
    if os.environ.get("HOOK_NO_GIT"):
        return []

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=M"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: could not run git diff: {exc}",
            file=sys.stderr,
        )
        return []

    if result.returncode != 0:
        return []

    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
        and _AC_STORE_DIR in line
        and line.strip().endswith(".yaml")
    ]


def _check_implements_pattern_preserved(
    staged_abs_path: str,
    rel_path: str,
    project_root: Path | None,
    head_cache: dict[str, dict | None] | None = None,
) -> list[str]:
    """Block if implements_pattern was present in HEAD but absent in staged.

    Args:
        staged_abs_path: Absolute path to the staged file on disk.
        rel_path: Repo-relative path for git show.
        project_root: Absolute repo root path, or None.
        head_cache: Optional pre-built mapping from rel_path to parsed HEAD
            dict (or None); when supplied, no subprocess is spawned.

    Returns:
        Violation strings; empty when the field was not dropped.
    """
    if os.environ.get("HOOK_SIMULATE_IMPLEMENTS_PATTERN_DROPPED"):
        return [
            f"{rel_path}: implements_pattern was dropped — this field must not be "
            f"removed from an AC that previously declared it"
        ]

    try:
        staged_content = Path(staged_abs_path).read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot read staged file {staged_abs_path}: {exc}",
            file=sys.stderr,
        )
        return []

    staged_data = load_yaml_from_string(staged_content, source_label=staged_abs_path)
    if staged_data is None:
        return []

    head_data = _load_head_yaml(rel_path, project_root, head_cache=head_cache)
    if head_data is None:
        return []

    head_val = head_data.get("implements_pattern")
    staged_val = staged_data.get("implements_pattern")
    head_has_it = bool(head_val and str(head_val).strip())
    staged_has_it = bool(staged_val and str(staged_val).strip())

    if head_has_it and not staged_has_it:
        return [
            f"{rel_path}: implements_pattern was dropped — this field must not be "
            f"removed from an AC that previously declared it "
            f"(was: '{head_val}')"
        ]

    return []


# ---------------------------------------------------------------------------
# File discovery and schema loading
# ---------------------------------------------------------------------------

def _find_ac_files(root: Path) -> list[Path]:
    """Discover all .yaml files under docs/acceptance-criteria/.

    Args:
        root: Repository root directory.

    Returns:
        Sorted list of Paths.
    """
    ac_dir = root / AC_GLOB_PATTERN
    if not ac_dir.is_dir():
        return []
    return sorted(p for p in ac_dir.rglob("*.yaml") if p.name != "index.yaml")


def _load_schema(root: Path) -> dict[str, Any] | None:
    """Load config/ac_store_schema.json; None if absent.

    Args:
        root: Repository root directory.

    Returns:
        Parsed schema dict, or None.
    """
    schema_path = root / SCHEMA_PATH
    if not schema_path.is_file():
        return None
    try:
        with open(schema_path, encoding="utf-8") as fh:
            return json.load(fh)  # type: ignore[return-value]
    except OSError as exc:
        print(f"Warning: cannot read schema {schema_path}: {exc}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Per-file validation
# ---------------------------------------------------------------------------

def _validate_file(
    path: Path,
    schema: dict[str, Any] | None,
    all_ac_data: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """Validate a single AC YAML file and return error messages.

    Args:
        path: YAML file to validate.
        schema: Pre-loaded JSON Schema dict, or None.
        all_ac_data: Optional AC id to parsed content mapping; enables
            cross-file checks when provided.

    Returns:
        Error message strings; empty when valid.
    """
    errors: list[str] = []

    yaml_available = True
    data: Any = None
    try:
        data = load_yaml(path)
    except ImportError:
        yaml_available = False
    except (OSError, ValueError) as exc:
        errors.append(f"YAML parse error: {exc}")
        return errors

    if not yaml_available:
        try:
            data = load_yaml_manual(path)
        except (OSError, ValueError) as exc:
            errors.append(f"manual YAML parse error: {exc}")
            return errors

    if data is None:
        errors.append("file is empty or parsed to null")
        return errors

    if not isinstance(data, dict):
        errors.append(f"expected YAML mapping at top level, got {type(data).__name__}")
        return errors

    schema_validated = False
    if schema is not None and yaml_available:
        try:
            errors.extend(validate_with_jsonschema(data, schema))
            schema_validated = True
        except ImportError:
            pass

    if not schema_validated:
        errors.extend(validate_manually(data))

    # Test-contract gate (single-file, semantic): a leaf code AC must declare a
    # test_spec or an explicit test_required: false. ACs are the source of truth
    # for what test-writer must test.
    errors.extend(validate_test_contract(path, data))

    # declares_side_effect gate (single-file, semantic): the declaration must be
    # DERIVED from the AC's own criteria, never authored by opinion and never
    # left unset when the criteria assert a durable, observable effect
    # (BO-2900g-2 / BO-2900g-2-i).
    errors.extend(validate_declares_side_effect(path, data))

    if all_ac_data is not None:
        errors.extend(validate_pattern_bindings_completeness(path, data, all_ac_data))
        errors.extend(validate_deprecated_pattern_reference(path, data, all_ac_data))
        errors.extend(validate_criteria_not_pattern_duplicate(path, data, all_ac_data))

    return errors


def _build_ac_index(files: list[Path]) -> dict[str, dict[str, Any]]:
    """Build an AC id to parsed content mapping from a file list.

    Args:
        files: AC YAML file paths to load.

    Returns:
        Mapping of AC id string to parsed YAML content dict.
    """
    index: dict[str, dict[str, Any]] = {}
    for path in files:
        try:
            data = load_yaml(path)
        except (ImportError, OSError, ValueError):  # noqa: BLE001
            try:
                data = load_yaml_manual(path)
            except (OSError, ValueError):  # noqa: BLE001
                continue
        if isinstance(data, dict) and data.get("id"):
            index[str(data["id"])] = data
    return index


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """Run AC schema validation and field-preservation checks.

    Phase 1 validates only staged AC YAML files (determined via
    _get_staged_ac_paths). Phase 2 checks implements_pattern preservation for
    staged-modified files. Cross-file checks use the full on-disk store as a
    lookup index, not narrowed to staged files only.

    Returns:
        0 on pass, 1 on any error.
    """
    root = Path(os.environ.get("HOOK_ROOT", str(Path.cwd())))
    schema = _load_schema(root)

    if schema is None:
        print(
            f"WARNING: {SCHEMA_PATH} not found at {root}; "
            "falling back to manual field validation.",
            file=sys.stderr,
        )

    # Phase 1: validate only staged AC YAML files (fail-open when git unavailable).
    staged_files = _get_staged_ac_paths(root)
    if not staged_files:
        # No staged AC files — skip Phase 1 entirely; still run Phase 2 below.
        failed: list[tuple[Path, list[str]]] = []
    else:
        # Build the full-store lookup index for cross-file checks (AC-4: not narrowed).
        # Use the shared mtime-cached index when available; fall back to the
        # direct _find_ac_files + _build_ac_index walk otherwise.
        ac_store_dir = root / AC_GLOB_PATTERN
        if _AC_STORE_INDEX_AVAILABLE:
            all_ac_data = get_ac_index(str(ac_store_dir))
        else:
            all_store_files = _find_ac_files(root)
            all_ac_data = _build_ac_index(all_store_files)
        failed = []
        for path in staged_files:
            errs = _validate_file(path, schema, all_ac_data)
            if errs:
                failed.append((path, errs))
    # Phase 2: implements_pattern field-preservation
    project_root = _find_project_root()
    modified_paths = _get_modified_ac_paths()
    test_files_env = os.environ.get("HOOK_TEST_FILES_MODIFIED")
    if test_files_env:
        extra = test_files_env.replace(os.pathsep, "\n").splitlines()
        modified_paths = [p.strip() for p in extra if p.strip() and p.strip().endswith(".yaml")]
    # Batch-fetch all HEAD blobs in ONE git cat-file --batch subprocess (O(1)).
    head_cache = _fetch_head_yaml_batch(modified_paths, project_root)
    for rel_path in modified_paths:
        abs_path = rel_path
        if not Path(rel_path).is_absolute() and project_root:
            abs_path = str(project_root / rel_path)
        p_errs = _check_implements_pattern_preserved(
            abs_path, rel_path, project_root, head_cache=head_cache
        )
        if p_errs:
            failed.append((Path(abs_path), p_errs))
    if not failed:
        return 0
    print(f"{_HOOK_PREFIX}: {len(failed)} file(s) failed validation:", file=sys.stderr)
    for path, file_errors in failed:
        try:
            rel = path.relative_to(root) if path.is_absolute() else path
        except ValueError:
            rel = path
        for err in file_errors:
            print(f"  {rel}: {err}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(
            f"{_HOOK_PREFIX} unexpected error (fail-open): {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        sys.exit(0)
