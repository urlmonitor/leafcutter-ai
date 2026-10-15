#!/usr/bin/env python3
"""
MODULE: commit_changes
GOAL: The one shared commit step. Commits exactly the files a caller names (plus
    the structural parent of a named AC record that the work edited) and nothing
    else, then answers with ONE JSON object on standard output.
BUSINESS CONTEXT: Five staging policies (git add -A, git add -u, exact names,
    "all in scope", stage by name) produced known issues KI-BO-029, KI-BO-20260901-0920
    and KI-BO-20260928. The hardened rule -- stage by name -- becomes a property of
    one script instead of prose repeated in every route (BO-4500a-1, -i..-iv).
ARCHITECTURE: Stdlib only. The commit is built in a PRIVATE temporary index
    (GIT_INDEX_FILE) seeded from HEAD, so the shared index (other callers' staged
    work) is never read as input and never reset. Named paths are the only entries
    added; checks run through `git commit` against that private index. A path a
    check stages outside the list is dropped by rewriting the new commit's tree and
    reported as unlisted_changes. Afterwards only the committed paths' entries in
    the shared index are re-synced to HEAD. Structural parents are derived with the
    canonical scripts/ac_store/ac_parent_id.py (never a private copy).

CLI: commit_changes.py --message-file FILE PATH [PATH ...]   (cwd = workspace)

Answer keys (always present): status, sha, paths, added_parents, unlisted_changes,
    hook_name, failing_files, reason_code, reason, hook_output, autofixed,
    skip_request_ignored, remedy, handoff.

Checks (BO-4500a-3): run once over the named files; a fixing check's rewrite is
    taken in and the checks re-run up to config/commit_step.json
    max_automated_fix_retries (default 3); a judging failure is reported at once as
    hook_failed (reason_code check_failed) with the check's output verbatim; a skip
    request in the environment is dropped and named in skip_request_ignored.

DECISION HISTORY:
  - 2026-10-15 [python-coder/BO-4500a-1]: Created. Staging rule taken from
    commit.md's stage-by-name (the hardened copy), not the fast lane's add -A or
    precommit-autofix's add -u. Private-index mechanism chosen so the property
    "commit = HEAD + named paths" holds whatever the shared index contains.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

_CONFIG_ENV = "LEAFCUTTER_COMMIT_STEP_CONFIG"
_CEILING_KEY = "max_automated_fix_retries"
_DEFAULT_CEILING = 3
_AC_STORE_DEFAULT = "docs/acceptance-criteria"
_AC_STORE_ENV = "LEAFCUTTER_AC_STORE_ROOT"
_USAGE = (
    "usage: commit_changes.py --message-file FILE PATH [PATH ...]\n"
    "  --message-file FILE   file holding the commit message (required)\n"
    "  PATH                  explicit repo file to commit; at least one is required.\n"
    "                        Directories, globs and 'all' requests are refused.\n"
    "  --help                show this text\n"
)


class StepRefusal(Exception):
    """A request the step declines; carries the answer's reason_code and reason."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


def _answer(status: str, **fields: object) -> dict:
    """Build the one answer object with every contract key present."""
    answer: dict = {"status": status, "sha": None, "paths": [], "added_parents": [], "unlisted_changes": []}
    answer.update(hook_name=None, failing_files=[], reason_code=None, reason=None, hook_output=None)
    answer.update(autofixed=[], skip_request_ignored=[], remedy=None, handoff=None)
    answer.update(fields)
    return answer


def _git(args: list[str], cwd: Path, env: dict | None = None, stdin: str | None = None):
    """Run git; an unrunnable git is a refusal, a non-zero exit is the caller's to read."""
    try:
        return subprocess.run(["git", *args], cwd=cwd, env=env, input=stdin, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise StepRefusal("git_unavailable", f"cannot run git: {exc}") from exc


def _git_out(args: list[str], cwd: Path, env: dict | None = None) -> str:
    """Run git and return stdout, refusing on a non-zero exit."""
    proc = _git(args, cwd, env)
    if proc.returncode != 0:
        raise StepRefusal("git_error", f"git {' '.join(args[:2])} failed: {proc.stderr.strip()}")
    return proc.stdout


def parse_args(argv: list[str]) -> tuple[str, list[str]]:
    """Split argv into (message_file, explicit path entries); unknown options are refused."""
    message_file: str | None = None
    entries: list[str] = []
    items = list(argv)
    only_paths = False
    while items:
        item = items.pop(0)
        if only_paths or not item.startswith("-") or item == "-":
            entries.append(item)
        elif item == "--":
            only_paths = True
        elif item == "--message-file" and items:
            message_file = items.pop(0)
        elif item.startswith("--message-file="):
            message_file = item.split("=", 1)[1]
        else:
            raise StepRefusal("policy_unknown_option", f"unknown option {item!r}; only --message-file is accepted")
    if message_file is None:
        raise StepRefusal("policy_message_missing", "a message file (--message-file FILE) is required")
    if not entries:
        raise StepRefusal("policy_no_explicit_paths", "an explicit list of files is required")
    return message_file, entries


def _classify_entry(entry: str, cwd: Path, root: Path, tracked: set[str]) -> tuple[str | None, str]:
    """Return (error_code or None, repo-relative posix path) for one named entry."""
    norm = os.path.normpath(entry if os.path.isabs(entry) else os.path.join(cwd, entry))
    target = os.path.join(os.path.realpath(os.path.dirname(norm)), os.path.basename(norm))
    rel = os.path.relpath(target, os.path.realpath(root)).replace(os.sep, "/")
    if rel == ".." or rel.startswith("../"):
        return "policy_path_outside_workspace", rel
    if rel in tracked or os.path.isfile(target):
        return None, rel
    if os.path.isdir(target) or entry.startswith(":") or any(ch in entry for ch in "*?["):
        return "policy_path_not_a_file", rel
    return "policy_path_not_found", rel


def validate_paths(entries: list[str], cwd: Path, root: Path, tracked: set[str]) -> list[str]:
    """Validate every entry before anything is staged; one bad entry refuses the call."""
    good: list[str] = []
    bad: list[tuple[str, str]] = []
    for entry in entries:
        code, rel = _classify_entry(entry, cwd, root, tracked)
        if code:
            bad.append((code, entry))
        elif rel not in good:
            good.append(rel)
    if bad:
        detail = "; ".join(f"{entry} ({code})" for code, entry in bad)
        raise StepRefusal(bad[0][0], f"cannot commit these entries: {detail}")
    return good


def _load_derive_parent_id() -> Callable[[str], str | None] | None:
    """Load the canonical derive_parent_id; None when the module is not deployed."""
    here = Path(__file__).resolve().parent
    # Deployed: scripts/ac_store beside this file. Source tree: <repo>/scripts/ac_store.
    for candidate in (
        here / "ac_store" / "ac_parent_id.py",
        here.parent.parent / "scripts" / "ac_store" / "ac_parent_id.py",
    ):
        if not candidate.is_file():
            continue
        spec = importlib.util.spec_from_file_location("ac_parent_id", str(candidate))
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.derive_parent_id
    return None


def _record_id(path: Path) -> str:
    """Read an AC record's id (first top-level id: line); fall back to the file stem."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return path.stem
    match = re.search(r"^id:\s*['\"]?([^\s'\"#]+)", text, re.MULTILINE)
    return match.group(1) if match else path.stem


def _find_parent_file(child: Path, parent_id: str, store: Path) -> Path | None:
    """Locate the parent record: same folder first, then anywhere in the AC store."""
    sibling = child.parent / f"{parent_id}.yaml"
    if sibling.is_file():
        return sibling
    return next(iter(sorted(store.rglob(f"{parent_id}.yaml"))), None) if store.is_dir() else None


def parent_candidates(named: list[str], root: Path) -> list[str]:
    """Return repo-relative structural parents (one hop) of the named AC records."""
    store_rel = os.environ.get(_AC_STORE_ENV, _AC_STORE_DEFAULT).strip("/")
    records = [rel for rel in named if rel.endswith(".yaml") and rel.startswith(store_rel + "/")]
    if not records:
        return []
    derive = _load_derive_parent_id()
    if derive is None:
        # Fail closed: AC records are being committed but their parents cannot be
        # worked out, so silently committing without them would recreate
        # KI-BO-20260928 (the edited parent left unstaged) as an apparent success.
        msg = (
            "AC records were named but the parent resolver (ac_store/ac_parent_id.py) "
            "is not deployed beside this script, so their edited parents cannot be "
            f"included: {', '.join(records)}"
        )
        raise StepRefusal("step_parent_resolver_unavailable", msg)
    found: list[str] = []
    for rel in named:
        if not rel.endswith(".yaml") or not rel.startswith(store_rel + "/"):
            continue
        parent_id = derive(_record_id(root / rel))
        parent = _find_parent_file(root / rel, parent_id, root / store_rel) if parent_id else None
        if parent is not None:
            parent_rel = parent.relative_to(root).as_posix()
            if parent_rel not in named and parent_rel not in found:
                found.append(parent_rel)
    return found


def _changed_vs_base(root: Path, env: dict, base: str | None) -> set[str]:
    """Paths whose private-index entry differs from the base commit."""
    if base is None:
        out = _git_out(["ls-files", "-z"], root, env)
    else:
        out = _git_out(["diff-index", "--cached", "--name-only", "-z", base], root, env)
    return {p for p in out.split("\0") if p}


def _hooks_present(root: Path, env: dict | None = None) -> bool:
    """True when the repository carries an executable pre-commit or commit-msg hook."""
    for name in ("pre-commit", "commit-msg"):
        path = _git(["rev-parse", "--git-path", f"hooks/{name}"], root, env).stdout.strip()
        if path and os.access(root / path, os.X_OK):
            return True
    return False


def _drop_unlisted(root: Path, env: dict, base: str | None, unlisted: list[str], msg: str) -> str:
    """Replace the new commit by one without the unlisted paths; return its sha."""
    for path in unlisted:
        entry = _git(["ls-tree", "-z", base, "--", path], root).stdout if base else ""
        if entry:
            meta = entry.split("\t", 1)[0].split()
            _git_out(["update-index", "--cacheinfo", f"{meta[0]},{meta[2]},{path}"], root, env)
        else:
            _git_out(["update-index", "--force-remove", "--", path], root, env)
    tree = _git_out(["write-tree"], root, env).strip()
    old = _git_out(["rev-parse", "HEAD"], root).strip()
    who = _git_out(["log", "-1", "--format=%an%n%ae%n%aI", old], root).splitlines()
    author = {**os.environ, "GIT_AUTHOR_NAME": who[0], "GIT_AUTHOR_EMAIL": who[1], "GIT_AUTHOR_DATE": who[2]}
    parent_args = ["-p", base] if base else []
    proc = _git(["commit-tree", tree, *parent_args], root, author, stdin=msg)
    if proc.returncode != 0:
        raise StepRefusal("git_error", f"commit-tree failed: {proc.stderr.strip()}")
    new = proc.stdout.strip()
    _git_out(["update-ref", "-m", "commit_changes: drop unlisted paths", "HEAD", new, old], root)
    return new


def _sync_shared_index(root: Path, paths: list[str]) -> None:
    """Re-sync ONLY the committed paths' shared-index entries to the new HEAD."""
    env = {**os.environ, "GIT_LITERAL_PATHSPECS": "1"}
    proc = _git(["reset", "-q", "--", *paths], root, env)
    if proc.returncode != 0:
        print(f"[commit_changes] warning: index sync failed: {proc.stderr.strip()}", file=sys.stderr)


def _run_commit(root: Path, env: dict, msg_file: str) -> subprocess.CompletedProcess:
    """Run the real `git commit` (hooks active) against the private index."""
    return _git(["commit", "-q", "--cleanup=verbatim", "-F", msg_file], root, env)


def _content_ids(root: Path, paths: list[str]) -> dict[str, str]:
    """Map each of *paths* that exists on disk to the git object id of its content."""
    present = [p for p in paths if (root / p).is_file()]
    if not present:
        return {}
    out = _git_out(["hash-object", "--", *present], root)
    return dict(zip(present, out.split(), strict=True))


def _rewritten_by_checks(root: Path, before: dict[str, str], paths: list[str]) -> list[str]:
    """Return which of *paths* changed on disk since *before* was taken.

    A change means a fixing check rewrote that file while the commit ran -- whether
    or not the check also staged it. No change means the failure came from a check
    that judges rather than fixes (or from git itself), and that kind of failure is
    reported, not retried (BO-4500a-3).
    """
    after = _content_ids(root, paths)
    return [p for p in paths if before.get(p) != after.get(p)]


def _check_message_file(message_file: str) -> None:
    """Refuse a message file that is absent, unreadable or only whitespace."""
    path = Path(message_file)
    if not path.is_file():
        raise StepRefusal("policy_message_not_found", f"message file not found: {message_file}")
    try:
        text = path.read_bytes().decode("utf-8", errors="replace")
    except OSError as exc:
        raise StepRefusal("policy_message_unreadable", f"message file unreadable: {message_file} ({exc})") from exc
    if not text.strip():
        raise StepRefusal("policy_message_empty", f"message file is empty: {message_file}")


def _commit_in_private_index(root: Path, named: list[str], msg_file: str, scratch: Path) -> dict:
    """Build HEAD + named paths (+ parents) in a private index and commit it."""
    base_proc = _git(["rev-parse", "--verify", "-q", "HEAD"], root)
    base = base_proc.stdout.strip() if base_proc.returncode == 0 else None
    env, ignored = _scrub_environment(dict(os.environ))
    env["GIT_INDEX_FILE"] = str(scratch / "index")
    _git_out(["read-tree", base] if base else ["read-tree", "--empty"], root, env)
    parents = parent_candidates(named, root)
    _git_out(["update-index", "--add", "--remove", "--", *named, *parents], root, env)
    changed = _changed_vs_base(root, env, base)
    paths = [p for p in named if p in changed]
    if not paths:
        return _answer("nothing_to_commit", reason_code="nothing_changed", reason="named paths have no changes")
    added = [p for p in parents if p in changed]
    failure, fixed = _run_checks_and_commit(root, env, msg_file, [*named, *parents])
    extra = {"autofixed": fixed, "skip_request_ignored": ignored}
    if failure is not None:
        return {**failure, **extra}
    return {**_finish(root, env, base, paths, added, msg_file), **extra}


def _ceiling() -> int:
    """Read max_automated_fix_retries once, before any check runs (BO-4500a-3-ii).

    Source: the file named by LEAFCUTTER_COMMIT_STEP_CONFIG, else config/commit_step.json
    beside the source tree or the deployed install; default 3 when no file exists.
    """
    here = Path(__file__).resolve().parent
    override = os.environ.get(_CONFIG_ENV)
    for path in [Path(override)] if override else [here.parent.parent / "config" / "commit_step.json", here.parent / "config" / "commit_step.json"]:
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8")).get(_CEILING_KEY, _DEFAULT_CEILING)
        except (OSError, ValueError, AttributeError) as exc:
            raise StepRefusal("step_config_unreadable", f"cannot read {path}: {exc}") from exc
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise StepRefusal("step_config_unreadable", f"{path}: {_CEILING_KEY} must be a non-negative integer")
        return value
    return _DEFAULT_CEILING


def _scrub_environment(env: dict) -> tuple[dict, list[str]]:
    """Return (environment the checks run in, skip requests dropped) -- BO-4500a-3-i.

    Removes every way a CALLER can switch the checks off through the environment
    it hands this step: SKIP, PRE_COMMIT_ALLOW_NO_CONFIG, and a core.hooksPath
    injected through either git config-in-environment form --
    GIT_CONFIG_COUNT/KEY_n/VALUE_n (the whole numbered set goes) or
    GIT_CONFIG_PARAMETERS (what `git -c core.hooksPath=...` hands its children).

    A core.hooksPath set in the repository's own git config is deliberately NOT
    overridden: that is the project choosing where its checks live (husky and
    similar tools use it), not a caller turning them off.
    """
    clean = dict(env)
    ignored = [name.strip() for name in clean.pop("SKIP", "").split(",") if name.strip()]
    if clean.pop("PRE_COMMIT_ALLOW_NO_CONFIG", ""):
        ignored.append("PRE_COMMIT_ALLOW_NO_CONFIG")
    numbered = any(k.lower() == "core.hookspath" for n, k in env.items() if n.startswith("GIT_CONFIG_KEY_"))
    if numbered:
        clean = {k: v for k, v in clean.items() if not k.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_", "GIT_CONFIG_COUNT"))}
    parameters = "core.hookspath" in clean.get("GIT_CONFIG_PARAMETERS", "").lower()
    if parameters:
        clean.pop("GIT_CONFIG_PARAMETERS")
    if numbered or parameters:
        ignored.append("core.hooksPath")
    return clean, ignored


def _handoff(root: Path, check: str | None, output: str) -> dict | None:
    """Run remedy_handoff.py (BO-3800a) on the check's output; None when none applies.

    A check without an engage-specialist declaration makes the script exit non-zero;
    that is the "author clears it" case, not an error.
    """
    here = Path(__file__).resolve().parent
    script = next((c for c in (root / "scripts" / "commit_guardian" / "remedy_handoff.py", here / "commit_guardian" / "remedy_handoff.py") if c.is_file()), None)
    if check is None or script is None:
        return None
    try:
        proc = subprocess.run([sys.executable, str(script), "--hook-id", check], cwd=root, input=output, capture_output=True, text=True, check=False)
        return json.loads(proc.stdout) if proc.returncode == 0 else None
    except (OSError, ValueError) as exc:
        print(f"[commit_changes] warning: no handoff built: {exc}", file=sys.stderr)
        return None


def _run_checks_and_commit(root: Path, env: dict, msg_file: str, carried: list[str]) -> tuple[dict | None, list[dict]]:
    """Run the checks through `git commit`; return (failure answer or None, autofixed).

    Only a fixing check that rewrote a file this commit carries earns a re-run, and
    at most `max_automated_fix_retries` of them, read before the first run; a judging
    failure is reported at once (BO-4500a-3, -3-ii).
    """
    ceiling = _ceiling()
    fixed: list[dict] = []
    before = _content_ids(root, carried)
    retries = 0
    while True:
        proc = _run_commit(root, env, msg_file)
        if proc.returncode == 0:
            return None, fixed
        output = proc.stdout + proc.stderr
        rewritten = _rewritten_by_checks(root, before, carried)
        if not rewritten or not _hooks_present(root, env):
            return _failed_commit(root, env, output, carried), fixed
        fixed.append({"hook_name": _hook_name(output), "files": rewritten})
        if retries >= ceiling:  # a fixer still rewriting on the last allowed run
            last = fixed[-1]
            return _answer("hook_failed", hook_name=last["hook_name"], failing_files=last["files"], reason_code="check_unsettled", reason=output.strip()[-400:], hook_output=output), fixed
        _git_out(["update-index", "--add", "--remove", "--", *rewritten], root, env)
        before = _content_ids(root, carried)
        retries += 1


def _hook_name(output: str) -> str | None:
    """Name the first failing check in pre-commit style output, when present."""
    match = re.search(r"^(.+?)\.{3,}.*Failed\s*$", output, re.MULTILINE)
    return match.group(1).strip() if match else None


def _failed_commit(root: Path, env: dict, output: str, carried: list[str]) -> dict:
    """Map a failed `git commit` to hook_failed or refused; nothing was recorded."""
    if not _hooks_present(root, env):
        return _answer("refused", reason_code="commit_error", reason=output.strip()[-400:])
    check = _hook_name(output)
    handoff = _handoff(root, check, output)
    named_in_output = [p for p in carried if re.search(rf"(?<![\w/.-]){re.escape(p)}(?![\w])", output)]
    return _answer("hook_failed", hook_name=check, failing_files=named_in_output, reason_code="check_failed", reason=output.strip()[-400:], hook_output=output, remedy=handoff["remedy"] if handoff else None, handoff=handoff)


def _finish(root: Path, env: dict, base: str | None, paths: list[str], added: list[str], msg_file: str) -> dict:
    """Drop any check-staged strays from the commit, sync the shared index, answer."""
    listed = set(paths) | set(added)
    files = _git_out(["diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "-z", "HEAD"], root)
    unlisted = sorted(p for p in files.split("\0") if p and p not in listed)
    sha = _git_out(["rev-parse", "HEAD"], root).strip()
    if unlisted:
        message = _git_out(["log", "-1", "--format=%B", sha], root)
        sha = _drop_unlisted(root, env, base, unlisted, message)
    _sync_shared_index(root, sorted(listed))
    return _answer("committed", sha=sha, paths=sorted(set(paths) | set(added)), added_parents=added, unlisted_changes=unlisted)


def _checked_run(argv: list[str]) -> dict:
    """Validate the request, then commit; refusals propagate as StepRefusal."""
    message_file, entries = parse_args(argv)
    _check_message_file(message_file)
    cwd = Path.cwd()
    root = Path(_git_out(["rev-parse", "--show-toplevel"], cwd).strip())
    tracked = {p for p in _git_out(["ls-files", "-z"], root).split("\0") if p}
    named = validate_paths(entries, cwd, root, tracked)
    scratch = Path(tempfile.mkdtemp(prefix="commit_changes_"))
    try:
        return _commit_in_private_index(root, named, str(Path(message_file).resolve()), scratch)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def run(argv: list[str]) -> dict:
    """Run the step; every outcome, refusals included, is returned as an answer."""
    try:
        return _checked_run(argv)
    except StepRefusal as refusal:
        return _answer("refused", reason_code=refusal.code, reason=refusal.reason)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: print exactly one JSON object; exit 0 on committed/nothing_to_commit."""
    args = list(sys.argv[1:] if argv is None else argv)
    if "--help" in args or "-h" in args:
        sys.stdout.write(_USAGE)
        return 0
    try:
        answer = run(args)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"[commit_changes] unexpected error: {exc}", file=sys.stderr)
        answer = _answer("refused", reason_code="internal_error", reason=str(exc))
    sys.stdout.write(json.dumps(answer) + "\n")
    return 0 if answer["status"] in {"committed", "nothing_to_commit"} else 1


if __name__ == "__main__":
    sys.exit(main())
