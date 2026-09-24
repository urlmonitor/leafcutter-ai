"""Repository-bound AC and target evidence loading for the background worker.

ACD-1300f-1 / ACD-1300f-2 / ACD-1300e-3: source records and target completion
are separate inputs; working-branch claims never establish external completion.
"""

from __future__ import annotations
import io
from pathlib import Path
import subprocess
import tarfile
import yaml


def _run_git(argv, **kwargs):
    try:
        return subprocess.run(argv, **kwargs)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("Git evidence operation failed: " + type(exc).__name__) from exc


def load_records(repo: Path) -> dict:
    records = {}
    repo = Path(repo).resolve()
    for path in sorted((repo / "docs/acceptance-criteria").rglob("*.yaml")):
        if not path.resolve().is_relative_to(repo):
            raise ValueError("AC path escapes repository")
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ValueError("Malformed AC YAML: " + str(path.relative_to(repo))) from exc
        if not isinstance(data, dict) or not data.get("id"):
            continue
        if data["id"] in records:
            raise ValueError("Duplicate AC identity: " + data["id"])
        records[data["id"]] = data
    return records


def load_reference_contents(repo: Path, records: dict) -> dict:
    result = {}
    repo = Path(repo).resolve()
    for record in records.values():
        for link in record.get("doc_links") or []:
            if not isinstance(link, (str, dict)):
                raise ValueError("AC document links must be strings or objects")
            name = link if isinstance(link, str) else link.get("path", "")
            if not isinstance(name, str):
                raise ValueError("AC document link path must be a string")
            if not name or (isinstance(link, dict) and link.get("status") == "planned"):
                continue
            path = (repo / name).resolve()
            if not path.is_relative_to(repo):
                raise ValueError("Reference path escapes repository: " + name)
            if path.is_file():
                result[name] = path.read_text(encoding="utf-8")
            else:
                result[name] = None
    return result


def refresh_target(repo: Path, target_ref: str) -> None:
    """Refresh a configured remote-tracking target without changing a checkout.

    Local refs deliberately stay local. Remote refs require fresh remote evidence;
    network/auth failures stop admission instead of treating cached data as current.
    """
    if not isinstance(target_ref, str) or not target_ref or target_ref.startswith("-"):
        raise ValueError("Invalid target reference")
    remotes = _run_git(
        ["git", "-C", str(repo), "remote"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.splitlines()
    normalized = target_ref.removeprefix("refs/remotes/")
    remote = next(
        (r for r in sorted(remotes, key=len, reverse=True) if normalized.startswith(r + "/")), None
    )
    if remote is None:
        if target_ref.startswith("refs/remotes/"):
            raise ValueError("Configured target remote is unavailable")
        local = _run_git(
            ["git", "-C", str(repo), "rev-parse", "--verify", target_ref + "^{commit}"],
            capture_output=True,
            timeout=10,
        )
        if local.returncode:
            raise ValueError("Target reference cannot be resolved: " + target_ref)
        return
    branch = normalized[len(remote) + 1 :]
    verified = _run_git(
        ["git", "check-ref-format", "refs/heads/" + branch],
        capture_output=True,
        timeout=10,
    )
    if verified.returncode:
        raise ValueError("Invalid remote target branch")
    fetched = _run_git(
        [
            "git",
            "-C",
            str(repo),
            "fetch",
            "--no-tags",
            "--",
            remote,
            "+refs/heads/" + branch + ":refs/remotes/" + normalized,
        ],
        capture_output=True,
        timeout=60,
    )
    if fetched.returncode:
        raise ValueError(
            "Cannot refresh target reference; check remote availability and authentication"
        )


def target_completed(repo: Path, target_ref: str) -> set[str]:
    """Read target-tree declarations plus evidence, never the current worktree."""
    if not target_ref or target_ref.startswith("-"):
        raise ValueError("Invalid target reference")
    resolved = _run_git(
        ["git", "-C", str(repo), "rev-parse", "--verify", target_ref + "^{commit}"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if resolved.returncode:
        raise ValueError("Target reference cannot be resolved: " + target_ref)
    target_sha = resolved.stdout.strip()
    proc = _run_git(
        ["git", "-C", str(repo), "archive", "--format=tar", target_sha, "docs/acceptance-criteria"],
        capture_output=True,
        timeout=60,
    )
    if proc.returncode:
        # A resolved target with no AC store is an empty baseline.
        return set()
    tree = _run_git(
        ["git", "-C", str(repo), "ls-tree", "-r", "--name-only", target_sha],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    target_paths = set(tree.stdout.splitlines())
    records = {}
    with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as archive:
        for item in archive:
            if not item.isfile() or not item.name.endswith(".yaml") or item.size > 2_000_000:
                continue
            try:
                data = yaml.safe_load(archive.extractfile(item).read())
            except yaml.YAMLError as exc:
                raise ValueError("Malformed target AC YAML: " + item.name) from exc
            if isinstance(data, dict) and data.get("id"):
                records[data["id"]] = data

    def complete(ac, visiting):
        if ac in visiting or ac not in records:
            return False
        d = records[ac]
        if d.get("work_status") != "done":
            return False
        children = d.get("covered_by") or []
        evidence = d.get("implemented_by") or []
        backed = any(
            isinstance(ref, str) and ref.split("#", 1)[0] in target_paths for ref in evidence
        )
        return backed or bool(
            children and all(complete(child, visiting | {ac}) for child in children)
        )

    return {ac for ac in records if complete(ac, set())}
