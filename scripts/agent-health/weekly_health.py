"""
MODULE: leafcutter/scripts/agent-health/weekly_health.py
GOAL: Produce a week-over-week delivery-health report for this repository from
      signals the build system cannot self-certify — git history, GitHub merge
      state, and reopen events — plus a code-volume breakdown by language.
BUSINESS CONTEXT: Answers two operator questions in one command: "is the system
      healthier than last week?" and "are we picking up development speed?".
      The metrics are deliberately sourced from outside the AC store's own
      status fields, because those fields have a documented history of claiming
      work is finished when it is not (the phantom-done failure mode this repo
      exists to prevent). A `work_status: done` flip is cheap to write and has
      been wrong 51 times in two weeks; a merged PR and a reopen are not.
ARCHITECTURE: Not needed.
DOC_LINKS:
  - scripts/agent-health/README.md
  - docs/reference/build-telemetry.md

Metrics are grouped into three tiers, printed in dependency order:

  Tier 1 (trust)     reopen rate, known-issue drain ratio, repeat defects.
                     Read these first. While the reopen rate is high, the
                     tier-3 velocity numbers measure the rate at which the
                     system produces claims, not capability.
  Tier 2 (autonomy)  fast-lane completion and intervention load, sourced from
                     the agent telemetry sink. Reports "no data" honestly when
                     the sink holds no drive events.
  Tier 3 (velocity)  net verified criteria, feature share, production code
                     density, and cycle time.

A fourth section reports code volume by language for the reporting period.

Usage:
    python weekly_health.py [--weeks N] [--repo PATH] [--format markdown|json|tsv]
        [--telemetry PATH] [--no-gh]

    Defaults:
        --weeks     8          whole ISO weeks, ending with the current (partial) one
        --repo      auto       discovered by walking up from this file to the git root
        --format    markdown
        --telemetry <repo>/debugging/logs/agent_telemetry.jsonl

Exit codes:
    0: success (report printed to stdout)
    1: unrecoverable error (not a git repository, or git is unavailable)
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_health_report import build_lane_comparison_report  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_AC_STORE = "docs/acceptance-criteria"
_KI_REGISTERS = "docs/known-issues"
_DEFAULT_WEEKS = 8

# Subject-line markers for work that exists because something else went wrong.
# Used as the intervention proxy until the telemetry sink carries drive events.
_REWORK_MARKERS = (
    "recover", "salvage", "reconcile", "repair",
    "reopen", "revert", "renumber", "correct",
)

# Telemetry event names that mark the start and the successful end of a lane run.
_LANE_START_EVENTS = {"run_started", "drive_started", "lane_started"}
_LANE_SUCCESS_EVENTS = {"pr_opened", "run_completed", "drive_completed"}
_LANE_HALT_EVENTS = {"halted", "escalated", "blocked"}

# Extension -> language. Mirrors the table in the git-analytics skill so both
# surfaces bucket a repository the same way.
_EXTENSION_LANGUAGE: dict[str, str] = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".tsx": "TypeScript (React)", ".jsx": "JavaScript (React)",
    ".java": "Java", ".cs": "C#", ".cpp": "C++", ".cc": "C++", ".cxx": "C++",
    ".c": "C", ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP",
    ".swift": "Swift", ".kt": "Kotlin", ".kts": "Kotlin", ".scala": "Scala",
    ".r": "R", ".sql": "SQL", ".sh": "Shell", ".bash": "Shell",
    ".ps1": "PowerShell", ".html": "HTML", ".css": "CSS/Styles",
    ".scss": "CSS/Styles", ".sass": "CSS/Styles", ".less": "CSS/Styles",
    ".json": "JSON", ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML",
    ".xml": "XML", ".md": "Markdown", ".mdx": "Markdown", ".txt": "Plain Text",
    ".tf": "Terraform", ".proto": "Protobuf", ".dockerfile": "Docker",
}

# Language -> coarse kind, so the report can show the code/spec/prose split
# without the reader summing twenty language rows.
_LANGUAGE_KIND: dict[str, str] = {
    "Python": "code", "JavaScript": "code", "TypeScript": "code",
    "TypeScript (React)": "code", "JavaScript (React)": "code", "Java": "code",
    "C#": "code", "C++": "code", "C": "code", "Go": "code", "Rust": "code",
    "Ruby": "code", "PHP": "code", "Swift": "code", "Kotlin": "code",
    "Scala": "code", "R": "code", "SQL": "code", "Shell": "code",
    "PowerShell": "code", "HTML": "code", "CSS/Styles": "code",
    "JSON": "spec", "YAML": "spec", "TOML": "spec", "XML": "spec",
    "Terraform": "spec", "Protobuf": "spec", "Docker": "spec",
    "Markdown": "prose", "Plain Text": "prose",
}

_TEST_PATH_MARKERS = ("unit_tests/", "tests/", "/tests/", "/test_")


# ---------------------------------------------------------------------------
# Git plumbing
# ---------------------------------------------------------------------------


class GitError(RuntimeError):
    """Raised when a git invocation fails in a way the report cannot survive."""


def run_git(repo: Path, *args: str, tolerate_failure: bool = False) -> str:
    """Run a git command in `repo` and return its stdout.

    Args:
        repo: Path to the repository working tree.
        *args: Arguments passed to git, excluding the leading `git -C <repo>`.
        tolerate_failure: When True, a non-zero exit returns "" instead of
            raising. Used for probes whose absence is itself information
            (an unborn ref, a path that does not exist at an old commit).

    Returns:
        str: Captured stdout, or "" when the call failed and failure was tolerated.

    Raises:
        GitError: The git call failed and `tolerate_failure` is False.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise GitError(f"Could not execute git: {exc}") from exc

    if proc.returncode != 0:
        if tolerate_failure:
            return ""
        raise GitError(
            f"git {' '.join(args)} failed with exit {proc.returncode}: "
            f"{proc.stderr.strip()}"
        )
    return proc.stdout


def discover_repo_root(start: Path) -> Path:
    """Walk up from `start` to the enclosing git working tree.

    Args:
        start: Directory or file path to begin the search from.

    Returns:
        Path: Absolute path to the repository root.

    Raises:
        GitError: No enclosing git repository was found.
    """
    probe = start if start.is_dir() else start.parent
    try:
        proc = subprocess.run(
            ["git", "-C", str(probe), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise GitError(f"Could not execute git: {exc}") from exc
    if proc.returncode != 0:
        raise GitError(f"{probe} is not inside a git repository.")
    return Path(proc.stdout.strip())


def resolve_base_ref(repo: Path) -> str:
    """Pick the ref the report measures: origin/main when present, else HEAD.

    Measuring `origin/main` rather than the local branch keeps the numbers
    independent of whatever worktree the operator happens to be standing in.

    Args:
        repo: Repository root.

    Returns:
        str: A ref name suitable for `git log`.
    """
    if run_git(repo, "rev-parse", "--verify", "origin/main", tolerate_failure=True).strip():
        return "origin/main"
    return "HEAD"


def commit_before(repo: Path, ref: str, boundary: date) -> str:
    """Return the last commit on `ref` strictly before midnight of `boundary`.

    Args:
        repo: Repository root.
        ref: Ref to walk.
        boundary: Date whose 00:00 is the exclusive upper bound.

    Returns:
        str: Commit SHA, or "" when the ref has no commit that old.
    """
    out = run_git(
        repo, "log", ref, f"--before={boundary.isoformat()}T00:00:00",
        "-1", "--pretty=format:%H", tolerate_failure=True,
    )
    return out.strip()


# ---------------------------------------------------------------------------
# Period construction
# ---------------------------------------------------------------------------


def iso_week_starts(today: date, weeks: int) -> list[date]:
    """Return the Mondays of the last `weeks` ISO weeks, oldest first.

    The final entry is the Monday of the week containing `today`, so the most
    recent period is partial whenever the report runs mid-week.

    Args:
        today: The date the report is generated for.
        weeks: How many weeks to include; values below 1 are clamped to 1.

    Returns:
        list[date]: Monday dates, ascending.
    """
    weeks = max(1, weeks)
    this_monday = today - timedelta(days=today.weekday())
    return [this_monday - timedelta(days=7 * i) for i in range(weeks - 1, -1, -1)]


# ---------------------------------------------------------------------------
# AC store and known-issue readers
# ---------------------------------------------------------------------------


def ac_key(path: str) -> str | None:
    """Return the criterion identifier a store path carries, or None.

    The identifier — not the path — is the criterion's identity. Records move
    between a component root and its feature folders routinely, and keying on
    the path would score every such move as one criterion filed and another
    vanished, inflating both the filed count and (when the record was already
    closed) the newly-done count that the trust metric is built on.

    Args:
        path: Repository-relative path to a store file.

    Returns:
        str | None: The identifier (filename stem), or None when the path is
            not an acceptance criterion (a registry index, or not YAML).
    """
    if not path.endswith(".yaml") or path.endswith("index.yaml"):
        return None
    return path.rsplit("/", 1)[-1][: -len(".yaml")]


def work_status_at(repo: Path, rev: str) -> dict[str, str]:
    """Map every acceptance criterion to its `work_status` at `rev`.

    Args:
        repo: Repository root.
        rev: Commit-ish to read the store at.

    Returns:
        dict: Criterion id -> work_status value. Empty when the store did not
            exist at `rev`.
    """
    if not rev:
        return {}
    raw = run_git(
        repo, "grep", "-n", "^work_status:", rev, "--", _AC_STORE,
        tolerate_failure=True,
    )
    result: dict[str, str] = {}
    for line in raw.splitlines():
        parts = line.split(":", 3)
        if len(parts) < 4:
            continue
        key = ac_key(parts[1])
        if key is None:
            continue
        result[key] = parts[3].split("work_status:", 1)[-1].strip().strip("\"'")
    return result


def known_issue_ids_at(repo: Path, rev: str) -> set[str]:
    """Return the set of KI identifiers present in the registers at `rev`.

    Args:
        repo: Repository root.
        rev: Commit-ish to read the registers at.

    Returns:
        set[str]: Identifiers such as {"KI-BO-019", "KI-ACS-004"}.
    """
    if not rev:
        return set()
    raw = run_git(
        repo, "grep", "-E", r"^### KI-[A-Z]+-[0-9]+", rev, "--", _KI_REGISTERS,
        tolerate_failure=True,
    )
    return {m.group(1) for m in re.finditer(r"###\s+(KI-[A-Z]+-\d+)", raw)}


def repeat_defect_count(repo: Path, rev: str) -> int:
    """Count known issues seen more than once at `rev`.

    A rising count means the same defect keeps recurring — the system is
    detecting it repeatedly rather than preventing it.

    Args:
        repo: Repository root.
        rev: Commit-ish to read the registers at.

    Returns:
        int: Number of entries whose Occurrences field is 2 or greater.
    """
    if not rev:
        return 0
    raw = run_git(
        repo, "grep", "-h", "-E", r"^- \*\*Occurrences:\*\*", rev, "--", _KI_REGISTERS,
        tolerate_failure=True,
    )
    counts = [int(m) for m in re.findall(r"\*\*Occurrences:\*\*\s*(\d+)", raw)]
    return sum(1 for c in counts if c >= 2)


def ac_birth_dates(repo: Path, ref: str) -> dict[str, date]:
    """Build a criterion-id -> first-seen-date index for the store in one pass.

    Walking the log once is far cheaper than a `git log --follow` per criterion
    across a store of several thousand records. Keying on the identifier rather
    than the path also makes the index survive a record moving between folders:
    a move re-adds the file at a new path, and taking the earliest add per
    identifier keeps the criterion's true age instead of resetting it to the
    move date.

    Args:
        repo: Repository root.
        ref: Ref to walk.

    Returns:
        dict: Criterion id -> date the criterion first appeared.
    """
    raw = run_git(
        repo, "log", ref, "--diff-filter=A", "--name-only",
        "--date=short", "--format=@%ad", "--", _AC_STORE,
        tolerate_failure=True,
    )
    births: dict[str, date] = {}
    current: date | None = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("@"):
            try:
                current = date.fromisoformat(line[1:])
            except ValueError:
                current = None
            continue
        if current is None:
            continue
        key = ac_key(line)
        if key is None:
            continue
        # The log walks newest-first, so a later write for a key is an older add.
        births[key] = current
    return births


# ---------------------------------------------------------------------------
# Pure metric computations
# ---------------------------------------------------------------------------


def classify_path(path: str) -> tuple[str, str]:
    """Classify a repository path into (language, kind).

    Args:
        path: Repository-relative file path.

    Returns:
        tuple: (language, kind) where kind is one of code / spec / prose / other.
            Unknown extensions map to ("Other", "other").
    """
    name = path.rsplit("/", 1)[-1]
    if name.lower().startswith("dockerfile"):
        return "Docker", "spec"
    dot = name.rfind(".")
    if dot <= 0:
        return "Other", "other"
    language = _EXTENSION_LANGUAGE.get(name[dot:].lower())
    if language is None:
        return "Other", "other"
    return language, _LANGUAGE_KIND.get(language, "other")


def is_test_path(path: str) -> bool:
    """Report whether a path belongs to a test suite.

    Args:
        path: Repository-relative file path.

    Returns:
        bool: True when the path sits in, or names, a test surface.
    """
    return path.startswith(("unit_tests/", "tests/")) or any(
        m in path for m in _TEST_PATH_MARKERS[2:]
    )


def ac_deltas(before: dict[str, str], after: dict[str, str]) -> dict[str, int]:
    """Compute acceptance-criterion movement between two store snapshots.

    Args:
        before: work_status map at the start of the period.
        after: work_status map at the end of the period.

    Returns:
        dict: Keys filed, done, reopened, net_done, store_size.
    """
    filed = len(set(after) - set(before))
    done = sum(1 for p, v in after.items() if v == "done" and before.get(p) != "done")
    reopened = sum(
        1 for p, v in before.items() if v == "done" and p in after and after[p] != "done"
    )
    return {
        "filed": filed,
        "done": done,
        "reopened": reopened,
        "net_done": done - reopened,
        "store_size": len(after),
    }


def safe_ratio(numerator: float, denominator: float) -> float | None:
    """Divide, returning None instead of raising when the denominator is zero.

    Args:
        numerator: Dividend.
        denominator: Divisor.

    Returns:
        float | None: The quotient, or None when the denominator is zero.
    """
    if denominator == 0:
        return None
    return numerator / denominator


def composite_score(net_done: int, done: int, reopened: int) -> float | None:
    """Score delivery discounted by how much of it was later retracted.

    net_done / (1 + reopen_rate). A week that closes 40 criteria and reopens
    none scores 40; one that closes 40 and reopens 40 scores 0.

    Args:
        net_done: done minus reopened for the period.
        done: Criteria newly marked done.
        reopened: Criteria that went from done back to unfinished.

    Returns:
        float | None: The discounted score, or None when nothing was closed.
    """
    rate = safe_ratio(reopened, done)
    if rate is None:
        return None
    return net_done / (1 + rate)


# ---------------------------------------------------------------------------
# Per-period collectors
# ---------------------------------------------------------------------------


def collect_commit_stats(repo: Path, start_sha: str, end_sha: str) -> dict[str, Any]:
    """Gather commit counts, type mix, rework share, and per-language volume.

    Args:
        repo: Repository root.
        start_sha: Exclusive lower bound commit.
        end_sha: Inclusive upper bound commit.

    Returns:
        dict: commits, rework, kinds, languages, kinds_rollup, prod_loc, test_loc.
    """
    empty = {
        "commits": 0, "rework": 0, "kinds": Counter(),
        "languages": defaultdict(lambda: {"added": 0, "deleted": 0, "files": 0}),
        "kinds_rollup": defaultdict(lambda: {"added": 0, "deleted": 0}),
        "prod_loc": 0, "test_loc": 0,
    }
    if not start_sha or not end_sha or start_sha == end_sha:
        return empty

    span = f"{start_sha}..{end_sha}"
    subjects = run_git(
        repo, "log", span, "--no-merges", "--pretty=format:%s", tolerate_failure=True
    ).splitlines()
    kinds = Counter(s.split("(")[0].split(":")[0].strip().lower() for s in subjects)
    rework = sum(
        1 for s in subjects if any(marker in s.lower() for marker in _REWORK_MARKERS)
    )

    languages: dict[str, dict[str, int]] = defaultdict(
        lambda: {"added": 0, "deleted": 0, "files": 0}
    )
    rollup: dict[str, dict[str, int]] = defaultdict(lambda: {"added": 0, "deleted": 0})
    prod_loc = test_loc = 0

    numstat = run_git(
        repo, "log", span, "--no-merges", "--numstat", "--pretty=format:",
        tolerate_failure=True,
    )
    for line in numstat.splitlines():
        fields = line.split("\t")
        if len(fields) != 3 or not fields[0].isdigit() or not fields[1].isdigit():
            continue  # binary files report "-" for both counts
        added, deleted, path = int(fields[0]), int(fields[1]), fields[2]
        language, kind = classify_path(path)
        languages[language]["added"] += added
        languages[language]["deleted"] += deleted
        languages[language]["files"] += 1
        rollup[kind]["added"] += added
        rollup[kind]["deleted"] += deleted
        if kind == "code":
            if is_test_path(path):
                test_loc += added
            else:
                prod_loc += added

    return {
        "commits": len(subjects), "rework": rework, "kinds": kinds,
        "languages": languages, "kinds_rollup": rollup,
        "prod_loc": prod_loc, "test_loc": test_loc,
    }


def collect_cycle_times(
    after: dict[str, str], before: dict[str, str],
    births: dict[str, date], period_end: date,
) -> list[int]:
    """Return the age in days of every criterion closed during the period.

    Args:
        after: work_status map at the end of the period.
        before: work_status map at the start of the period.
        births: Path -> first-seen date index.
        period_end: Last day of the period.

    Returns:
        list[int]: One age per criterion newly marked done; may be empty.
    """
    ages: list[int] = []
    for path, status in after.items():
        if status != "done" or before.get(path) == "done":
            continue
        birth = births.get(path)
        if birth is None:
            continue
        ages.append(max(0, (period_end - birth).days))
    return ages


def collect_lane_health(telemetry_path: Path) -> dict[str, Any]:
    """Summarise lane autonomy from the telemetry sink.

    Reuses build_lane_comparison_report for the per-lane aggregates so this
    report and the agent-health report never disagree about the same sink.

    Args:
        telemetry_path: Path to agent_telemetry.jsonl.

    Returns:
        dict: available (bool), reason (str), lanes (dict), starts, successes,
            halts, completion_rate.
    """
    lanes = build_lane_comparison_report(telemetry_path)

    events: Counter = Counter()
    if telemetry_path.exists():
        try:
            with open(telemetry_path, encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    name = record.get("event") or record.get("event_type")
                    if name:
                        events[name] += 1
        except OSError as exc:
            print(f"WARNING: Could not read {telemetry_path}: {exc}", file=sys.stderr)

    starts = sum(events[e] for e in _LANE_START_EVENTS)
    successes = sum(events[e] for e in _LANE_SUCCESS_EVENTS)
    halts = sum(events[e] for e in _LANE_HALT_EVENTS)

    if not telemetry_path.exists():
        reason = f"sink absent at {telemetry_path}"
    elif starts == 0:
        reason = (
            f"sink holds {sum(events.values())} events but none are lane-run events "
            f"({', '.join(sorted(_LANE_START_EVENTS))})"
        )
    else:
        reason = ""

    return {
        "available": starts > 0,
        "reason": reason,
        "lanes": lanes,
        "starts": starts,
        "successes": successes,
        "halts": halts,
        "completion_rate": safe_ratio(successes, starts),
        "event_total": sum(events.values()),
    }


def collect_pull_requests(repo: Path, weeks: list[date], enabled: bool) -> dict[str, Any]:
    """Fetch merged pull requests grouped by the week they merged in.

    Args:
        repo: Repository root, used to derive the GitHub slug from origin.
        weeks: Monday dates of the reporting periods.
        enabled: When False, skips the network call entirely.

    Returns:
        dict: available (bool), reason (str), by_week (Monday isoformat -> list),
            covered_from (date | None) — the oldest week whose PR counts the
            returned page actually reaches. Weeks older than that are undercounted
            by truncation and must be reported as unknown, not as a low number.
    """
    if not enabled:
        return {
            "available": False, "reason": "disabled via --no-gh",
            "by_week": {}, "covered_from": None,
        }

    remote = run_git(repo, "remote", "get-url", "origin", tolerate_failure=True).strip()
    match = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", remote)
    if not match:
        return {
            "available": False, "reason": f"could not parse a slug from {remote!r}",
            "by_week": {}, "covered_from": None,
        }
    slug = match.group(1)

    # `gh pr list` returns the N most recently merged PRs repository-wide, so an
    # under-provisioned limit does not error — it silently stops short, and the
    # oldest weeks report a low count that reads as a quiet period. Ask for well
    # more than the busiest plausible week, then verify the page actually reached
    # back far enough rather than trusting that it did.
    limit = max(400, 250 * len(weeks))
    try:
        proc = subprocess.run(
            ["gh", "pr", "list", "--repo", slug, "--state", "merged",
             "--limit", str(limit),
             "--json", "number,title,mergedAt,additions,deletions"],
            capture_output=True, text=True, check=False,
        )
    except OSError as exc:
        return {
            "available": False, "reason": f"gh unavailable: {exc}",
            "by_week": {}, "covered_from": None,
        }

    if proc.returncode != 0:
        return {
            "available": False,
            "reason": f"gh exited {proc.returncode}: {proc.stderr.strip()[:160]}",
            "by_week": {}, "covered_from": None,
        }

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return {
            "available": False, "reason": f"gh returned unparseable JSON: {exc}",
            "by_week": {}, "covered_from": None,
        }

    by_week: dict[str, list[dict]] = {w.isoformat(): [] for w in weeks}
    merged_dates: list[date] = []
    for pull in payload:
        merged = (pull.get("mergedAt") or "")[:10]
        if not merged:
            continue
        try:
            merged_date = date.fromisoformat(merged)
        except ValueError:
            continue
        merged_dates.append(merged_date)
        monday = merged_date - timedelta(days=merged_date.weekday())
        key = monday.isoformat()
        if key in by_week:
            by_week[key].append(pull)

    covered_from, reason = pr_coverage_floor(
        len(payload), limit, merged_dates, weeks[0]
    )
    return {
        "available": True, "reason": reason,
        "by_week": by_week, "covered_from": covered_from,
    }


def pr_coverage_floor(
    returned: int, limit: int, merged_dates: list[date], earliest_week: date
) -> tuple[date | None, str]:
    """Determine the oldest week the returned PR page can be trusted for.

    Args:
        returned: Number of pull requests the query returned.
        limit: The `--limit` the query was issued with.
        merged_dates: Merge dates of every returned pull request.
        earliest_week: Monday of the oldest reporting period.

    Returns:
        tuple: (covered_from, reason). `covered_from` is None when the page
            reaches every reporting week; otherwise it is the oldest date the
            page covers, and weeks before it must be reported as unknown.
            `reason` is "" when coverage is complete.
    """
    if returned < limit or not merged_dates:
        # The page was not capped, so it contains every merged PR there is.
        return None, ""
    oldest = min(merged_dates)
    if oldest <= earliest_week:
        return None, ""
    return oldest, (
        f"the GitHub query hit its {limit}-result cap and only reaches back to "
        f"{oldest.isoformat()}; earlier weeks are reported as unknown rather than "
        f"undercounted"
    )


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------


def build_report(
    repo: Path, weeks: int, today: date, telemetry_path: Path, use_gh: bool
) -> dict[str, Any]:
    """Assemble the full report payload.

    Args:
        repo: Repository root.
        weeks: Number of ISO weeks to cover.
        today: Date the report is generated for.
        telemetry_path: Path to the telemetry sink.
        use_gh: Whether to query GitHub for merged pull requests.

    Returns:
        dict: The complete report structure consumed by the renderers.
    """
    ref = resolve_base_ref(repo)
    mondays = iso_week_starts(today, weeks)
    births = ac_birth_dates(repo, ref)
    pull_requests = collect_pull_requests(repo, mondays, use_gh)

    periods: list[dict[str, Any]] = []
    prior_sha = commit_before(repo, ref, mondays[0])
    prior_status = work_status_at(repo, prior_sha)
    prior_ki = known_issue_ids_at(repo, prior_sha)

    for monday in mondays:
        period_end = min(monday + timedelta(days=6), today)
        end_sha = commit_before(repo, ref, monday + timedelta(days=7))
        status = work_status_at(repo, end_sha)
        ki_now = known_issue_ids_at(repo, end_sha)

        stats = collect_commit_stats(repo, prior_sha, end_sha)
        deltas = ac_deltas(prior_status, status)
        ages = collect_cycle_times(status, prior_status, births, period_end)

        # When the GitHub query failed, or was capped before reaching this week,
        # the PR counts are unknown rather than zero. Emitting a number would
        # make "not measured" indistinguishable from "nothing merged" — the same
        # false-green shape the trust tier exists to surface.
        covered_from = pull_requests["covered_from"]
        week_covered = (
            pull_requests["available"]
            and (covered_from is None or monday >= covered_from)
        )
        merged = pull_requests["by_week"].get(monday.isoformat(), [])
        pr_total = len(merged) if week_covered else None
        pr_feat = (
            sum(1 for p in merged if p["title"].lower().startswith("feat"))
            if week_covered else None
        )
        pr_fix = (
            sum(1 for p in merged if p["title"].lower().startswith("fix"))
            if week_covered else None
        )

        periods.append({
            "week": monday.isoformat(),
            "days": (period_end - monday).days + 1,
            "commits": stats["commits"],
            "rework": stats["rework"],
            "rework_share": safe_ratio(stats["rework"], stats["commits"]),
            "kinds": dict(stats["kinds"]),
            "languages": {k: dict(v) for k, v in stats["languages"].items()},
            "kinds_rollup": {k: dict(v) for k, v in stats["kinds_rollup"].items()},
            "prod_loc": stats["prod_loc"],
            "test_loc": stats["test_loc"],
            "prs": pr_total,
            "feat_prs": pr_feat,
            "fix_prs": pr_fix,
            "prs_available": week_covered,
            "ac_filed": deltas["filed"],
            "ac_done": deltas["done"],
            "ac_reopened": deltas["reopened"],
            "ac_net_done": deltas["net_done"],
            "ac_store_size": deltas["store_size"],
            "reopen_rate": safe_ratio(deltas["reopened"], deltas["done"]),
            "composite": composite_score(
                deltas["net_done"], deltas["done"], deltas["reopened"]
            ),
            "ki_open": len(ki_now),
            "ki_filed": len(ki_now - prior_ki),
            "ki_closed": len(prior_ki - ki_now),
            "ki_drain": safe_ratio(len(prior_ki - ki_now), len(ki_now - prior_ki)),
            "ki_repeats": repeat_defect_count(repo, end_sha),
            "cycle_median": statistics.median(ages) if ages else None,
            "cycle_p75": sorted(ages)[int(0.75 * (len(ages) - 1))] if ages else None,
            "closed_within_7d": safe_ratio(sum(1 for a in ages if a <= 7), len(ages)),
        })
        prior_sha, prior_status, prior_ki = end_sha, status, ki_now

    return {
        "repo": str(repo),
        "ref": ref,
        "generated": today.isoformat(),
        "periods": periods,
        "lane": collect_lane_health(telemetry_path),
        "pull_requests_available": pull_requests["available"],
        "pull_requests_reason": pull_requests["reason"],
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _pct(value: float | None) -> str:
    """Format a ratio as a percentage, or a dash when undefined."""
    return "—" if value is None else f"{value * 100:.0f}%"


def _num(value: float | None, digits: int = 0) -> str:
    """Format a number, or a dash when undefined."""
    return "—" if value is None else f"{value:.{digits}f}"


def _int(value: int | None) -> str:
    """Format a count, or a dash when the value is unknown.

    Distinct from formatting 0: a dash means the figure could not be obtained,
    which is a different claim from "the count was zero".
    """
    return "—" if value is None else str(value)


def _ratio_of(numerator: float | None, denominator: float | None) -> float | None:
    """Divide two possibly-unknown values, propagating the unknown.

    Args:
        numerator: Dividend, or None when unknown.
        denominator: Divisor, or None when unknown.

    Returns:
        float | None: The quotient, or None when either input is unknown or
            the denominator is zero.
    """
    if numerator is None or denominator is None:
        return None
    return safe_ratio(numerator, denominator)


def _render_markdown(report: dict[str, Any]) -> str:
    """Render the report as Markdown.

    Args:
        report: Payload from build_report.

    Returns:
        str: Markdown document.
    """
    periods = report["periods"]
    latest = periods[-1]
    out: list[str] = [
        "# Weekly Health Report",
        "",
        f"**Repository:** {report['repo']}  ",
        f"**Measured ref:** `{report['ref']}`  ",
        f"**Generated:** {report['generated']}  ",
        f"**Periods:** {periods[0]['week']} → {latest['week']} "
        f"({len(periods)} weeks; the last is {latest['days']} day(s) so far)",
        "",
        "---",
        "",
        "## Tier 1 — Trust",
        "",
        "Read this first. While the reopen rate is high, the tier-3 velocity numbers",
        "measure the rate at which the system produces claims, not capability.",
        "",
        "| Week | done | reopened | reopen rate | KI filed | KI closed | drain | repeat defects |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for p in periods:
        out.append(
            f"| {p['week']} | {p['ac_done']} | {p['ac_reopened']} | {_pct(p['reopen_rate'])} "
            f"| {p['ki_filed']} | {p['ki_closed']} | {_pct(p['ki_drain'])} | {p['ki_repeats']} |"
        )

    out += [
        "",
        "## Tier 2 — Autonomy",
        "",
    ]
    lane = report["lane"]
    if lane["available"]:
        out += [
            f"- Lane runs started: **{lane['starts']}**",
            f"- Reached a merged PR: **{lane['successes']}**",
            f"- Halted or escalated: **{lane['halts']}**",
            f"- **Completion rate: {_pct(lane['completion_rate'])}**",
            "",
        ]
        if lane["lanes"]:
            out += [
                "| Lane | runs | avg duration (ms) | avg tokens |",
                "|---|---:|---:|---:|",
            ]
            for name, agg in sorted(lane["lanes"].items()):
                out.append(
                    f"| {name} | {agg['count']} | {agg['avg_duration_ms']:.0f} "
                    f"| {agg['avg_total_tokens']:.0f} |"
                )
            out.append("")
    else:
        out += [
            f"> **No lane data — {lane['reason']}.**",
            ">",
            "> Lane completion rate is the metric that answers \"did the fast-lane fixes",
            "> make us faster?\", and it cannot be computed until a lane run emits",
            "> run-start and run-end events into the sink. Until then the intervention",
            "> proxy below is the only autonomy signal available.",
            "",
        ]
    out += [
        "Intervention proxy — commits whose subject signals recovery work",
        "(recover / salvage / reconcile / repair / reopen / revert / renumber / correct):",
        "",
        "| Week | rework commits | of total | per net verified criterion |",
        "|---|---:|---:|---:|",
    ]
    for p in periods:
        per_ac = safe_ratio(p["rework"], p["ac_net_done"]) if p["ac_net_done"] > 0 else None
        out.append(
            f"| {p['week']} | {p['rework']} | {_pct(p['rework_share'])} | {_num(per_ac, 2)} |"
        )

    out += [
        "",
        "## Tier 3 — Velocity",
        "",
        "| Week | PRs | feat | feat share | prod LOC/PR | net verified | composite | median cycle |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for p in periods:
        feat_share = _ratio_of(p["feat_prs"], p["prs"])
        loc_per_pr = _ratio_of(p["prod_loc"], p["prs"])
        cycle = f"{p['cycle_median']:.0f}d" if p["cycle_median"] is not None else "—"
        out.append(
            f"| {p['week']} | {_int(p['prs'])} | {_int(p['feat_prs'])} | {_pct(feat_share)} "
            f"| {_num(loc_per_pr)} | {p['ac_net_done']} | {_num(p['composite'], 1)} | {cycle} |"
        )
    if report["pull_requests_reason"]:
        out += [
            "",
            f"> PR columns read `—` where unknown (never zero) — "
            f"{report['pull_requests_reason']}.",
        ]

    out += [
        "",
        "## Code volume by language",
        "",
        f"Most recent period ({latest['week']}, {latest['days']} day(s)):",
        "",
        "| Language | added | deleted | net | files touched |",
        "|---|---:|---:|---:|---:|",
    ]
    ranked = sorted(
        latest["languages"].items(),
        key=lambda kv: kv[1]["added"] + kv[1]["deleted"],
        reverse=True,
    )
    for language, vol in ranked:
        net = vol["added"] - vol["deleted"]
        out.append(
            f"| {language} | +{vol['added']} | -{vol['deleted']} | {net:+d} | {vol['files']} |"
        )

    out += [
        "",
        "Code / spec / prose split, all periods (lines added):",
        "",
        "| Week | code | spec (yaml, json) | prose (md) | other | test LOC | prod LOC |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for p in periods:
        roll = p["kinds_rollup"]
        out.append(
            f"| {p['week']} | {roll.get('code', {}).get('added', 0)} "
            f"| {roll.get('spec', {}).get('added', 0)} "
            f"| {roll.get('prose', {}).get('added', 0)} "
            f"| {roll.get('other', {}).get('added', 0)} "
            f"| {p['test_loc']} | {p['prod_loc']} |"
        )

    out += [
        "",
        "---",
        "",
        "## How to read this",
        "",
        "- **reopen rate** — criteria retracted ÷ criteria closed. Above ~5% the store",
        "  is asserting more than it can prove; treat tier 3 as unverified.",
        "- **composite** — net verified ÷ (1 + reopen rate). One number for \"how much",
        "  did we really finish\".",
        "- **prod LOC/PR** — capability density. A falling value with a rising PR count",
        "  means the work is moving from building to bookkeeping.",
        "- **median cycle** — days from a criterion first appearing to being closed.",
        "  Latency, as distinct from throughput; the two move independently.",
        "",
    ]
    return "\n".join(out)


def _render_tsv(report: dict[str, Any]) -> str:
    """Render one tab-separated row per period, for spreadsheets.

    Args:
        report: Payload from build_report.

    Returns:
        str: TSV text including a header row.
    """
    columns = [
        "week", "days", "commits", "prs_available", "prs", "feat_prs", "fix_prs",
        "prod_loc", "test_loc",
        "ac_filed", "ac_done", "ac_reopened", "ac_net_done", "reopen_rate", "composite",
        "ki_open", "ki_filed", "ki_closed", "ki_repeats", "rework", "cycle_median",
    ]
    lines = ["\t".join(columns)]
    for p in report["periods"]:
        lines.append("\t".join("" if p.get(c) is None else str(p.get(c, "")) for c in columns))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser.

    Returns:
        argparse.ArgumentParser: Configured parser.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Week-over-week delivery-health report: trust, autonomy, velocity, "
            "and code volume by language."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--weeks", type=int, default=_DEFAULT_WEEKS,
        help=f"Number of ISO weeks to report. Default: {_DEFAULT_WEEKS}",
    )
    parser.add_argument(
        "--repo", default=None,
        help="Repository root. Default: discovered from this file's location.",
    )
    parser.add_argument(
        "--telemetry", default=None,
        help="Path to agent_telemetry.jsonl. Default: <repo>/debugging/logs/agent_telemetry.jsonl",
    )
    parser.add_argument(
        "--format", choices=["markdown", "json", "tsv"], default="markdown",
        help="Output format. Default: markdown",
    )
    parser.add_argument(
        "--no-gh", action="store_true",
        help="Skip the GitHub query; PR columns report unknown, never zero.",
    )
    parser.add_argument(
        "--today", default=None,
        help="Override the report date (YYYY-MM-DD), for reproducible runs.",
    )
    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point for weekly_health.py.

    Args:
        argv: Argument list. When None, uses sys.argv[1:].

    Returns:
        int: Exit code (0 on success, 1 on unrecoverable error).
    """
    args = _build_parser().parse_args(argv)

    try:
        repo = Path(args.repo).resolve() if args.repo else discover_repo_root(Path(__file__).resolve())
    except GitError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.today:
        try:
            today = date.fromisoformat(args.today)
        except ValueError:
            print(f"ERROR: --today must be YYYY-MM-DD, got {args.today!r}", file=sys.stderr)
            return 1
    else:
        today = date.today()

    telemetry = (
        Path(args.telemetry) if args.telemetry
        else repo / "debugging" / "logs" / "agent_telemetry.jsonl"
    )

    try:
        report = build_report(repo, args.weeks, today, telemetry, not args.no_gh)
    except GitError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps(report, indent=2, default=str))
    elif args.format == "tsv":
        print(_render_tsv(report))
    else:
        print(_render_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-26 [manual/weekly-health-report]: Initial creation.
#   Metrics are sourced from git history, GitHub merge state, and reopen events
#   rather than from the AC store's own work_status field, because that field
#   has a documented phantom-done history (51 criteria reopened in the two weeks
#   to 2026-08-26, KI-ACS-004 at 18 occurrences). A reopen is used as a trust
#   signal precisely because it is a confession: the system only ever records
#   one against its own prior claim.
#   Tier ordering (trust -> autonomy -> velocity) is deliberate: velocity over an
#   untrusted store measures claim production, so the renderer prints the trust
#   table first and says so in the body.
#   Lane aggregates reuse generate_health_report.build_lane_comparison_report
#   rather than re-reading the sink independently, so the two reports cannot
#   disagree about the same file. The lane section reports "no data" with the
#   reason rather than printing a zero, because a 0% completion rate and an
#   unwired emitter are different facts (KI-BO-012).
#   ac_birth_dates walks the log once instead of running git log --follow per
#   criterion (~3,400 files); the cost is that a renamed record reads as newly
#   born, which understates cycle time. Stated in the docstring, not corrected.
# ====================================================================
