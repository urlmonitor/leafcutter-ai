"""
MODULE: bootstrap_install
GOAL: Standalone terminal fallback for the portable onboard agent. Auto-discovers
    the repo structure and emits a skills_config.json draft for new adopters who
    do not have Claude Code available.
BUSINESS CONTEXT: Ticket 07 (EPIC-PortableInstallHardening) introduced the
    portable onboard agent as the primary install path. This script is the fallback
    for non-Claude-Code environments: same discovery logic, no interactive Claude
    layer, produces a skills_config.json draft that the adopter reviews and edits
    before running build.py.
ARCHITECTURE: Standalone stdlib-only Python script (no Claude Code imports, no
    external deps beyond PyYAML which is available in pre-commit environments).
    Discovery uses pathlib glob and file reads. Output: JSON to stdout or --output
    path. --dry-run prints draft without writing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Folder structure discovery
# ---------------------------------------------------------------------------

def _discover_docs_root(repo_root: Path) -> str:
    """Detect the docs root directory."""
    for candidate in ("docs", "documentation", "doc"):
        if (repo_root / candidate).is_dir():
            return f"{candidate}/"
    return "docs/"


def _discover_test_root(repo_root: Path) -> str:
    """Detect the test root directory."""
    for candidate in ("unit_tests", "tests", "test", "spec"):
        if (repo_root / candidate).is_dir():
            return f"{candidate}/"
    return "tests/"


def _discover_top_level_packages(repo_root: Path) -> list[str]:
    """Detect top-level Python packages (directories with __init__.py)."""
    packages = []
    for d in sorted(repo_root.iterdir()):
        if d.is_dir() and (d / "__init__.py").exists():
            packages.append(d.name)
    return packages or []


def _discover_tickets_paths(repo_root: Path) -> dict[str, str]:
    """Detect ticket folder paths.

    Args:
        repo_root: Root directory of the target project.

    Returns:
        Mapping of skills_config key names to relative ticket folder paths.
    """
    tickets = repo_root / "tickets"
    if not tickets.is_dir():
        return {}
    result: dict[str, str] = {}
    for subdir in ("00_inbox", "01_todo", "99_done", "99_rejected"):
        if (tickets / subdir).is_dir():
            key_map = {
                "00_inbox": "tickets_inbox_path",
                "01_todo": "tickets_todo_path",
                "99_done": "tickets_done_path",
                "99_rejected": "tickets_rejected_path",
            }
            result[key_map[subdir]] = f"tickets/{subdir}"
    if (tickets / "00_inbox" / "epics").is_dir():
        result["tickets_inbox_epics_path"] = "tickets/00_inbox/epics"
    return result


def _discover_default_branch(repo_root: Path) -> str:
    """Detect the default git branch (main or master).

    Args:
        repo_root: Root directory of the target project.

    Returns:
        Branch name string, e.g. "main" or "master". Defaults to "main" on error.
    """
    try:
        import subprocess
        r = subprocess.run(
            ["git", "symbolic-ref", "--short", "HEAD"],
            capture_output=True, text=True, check=True, cwd=str(repo_root),
        )
        return r.stdout.strip() or "main"
    except Exception:  # noqa: BLE001
        return "main"


def _discover_changelog_folder(repo_root: Path) -> str:
    """Detect changelog folder."""
    if (repo_root / "changelogs").is_dir():
        return "changelogs/"
    if (repo_root / "CHANGELOG.md").exists():
        return ""
    return "changelogs/"


# ---------------------------------------------------------------------------
# Whitelist file reading
# ---------------------------------------------------------------------------

def _read_whitelist(repo_root: Path) -> dict[str, str]:
    """Read whitelisted files; skip gracefully if absent.

    Args:
        repo_root: Root directory of the target project.

    Returns:
        Mapping of filename to file contents (or truncated contents for README.md).
    """
    result: dict[str, str] = {}
    whitelist = [
        ("README.md", 50),
        ("pyproject.toml", None),
        ("package.json", None),
        ("Makefile", None),
        (".env.example", None),
    ]
    for filename, max_lines in whitelist:
        path = repo_root / filename
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            if max_lines:
                lines = lines[:max_lines]
            result[filename] = "\n".join(lines)
        except OSError:
            pass
    return result


def _extract_project_description(readme_text: str) -> str:
    """Extract first meaningful paragraph from README.

    Args:
        readme_text: Full text content of the README file.

    Returns:
        First non-heading paragraph as a single string, or empty string if not found.
    """
    lines = readme_text.splitlines()
    in_body = False
    para_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            in_body = True
            continue
        if in_body and stripped:
            para_lines.append(stripped)
        elif in_body and para_lines:
            break
    return " ".join(para_lines) if para_lines else ""


def _infer_test_command(files: dict[str, str], test_root: str) -> str:
    """Infer the primary test command."""
    if "pyproject.toml" in files and "[tool.poetry]" in files["pyproject.toml"]:
        return f"poetry run python -m pytest {test_root} -v"
    return f"python -m pytest {test_root} -v"


# ---------------------------------------------------------------------------
# Config assembly
# ---------------------------------------------------------------------------

def discover_config(repo_root: Path) -> dict[str, object]:
    """Run all discovery heuristics and return a proposed config dict.

    Args:
        repo_root: Root directory of the target project.

    Returns:
        Proposed skills_config.json dict with auto-discovered key/value pairs.
    """
    files = _read_whitelist(repo_root)

    docs_root = _discover_docs_root(repo_root)
    test_root = _discover_test_root(repo_root)
    packages = _discover_top_level_packages(repo_root)
    ticket_paths = _discover_tickets_paths(repo_root)
    default_branch = _discover_default_branch(repo_root)
    changelog_folder = _discover_changelog_folder(repo_root)
    project_description = _extract_project_description(files.get("README.md", ""))
    test_command = _infer_test_command(files, test_root)

    config: dict[str, object] = {}

    # Project metadata
    if project_description:
        config["project_description"] = project_description

    # Ticket paths
    config.update(ticket_paths)

    # Branch and worktree
    config["default_branch"] = default_branch
    config["worktree_base_path"] = "../"

    # Packages
    if packages:
        config["top_level_packages"] = packages

    # Testing
    config["testing_context"] = {
        "test_root": test_root,
        "max_test_duration_seconds": 5,
        "naming_pattern": "test_*.py",
    }
    config["test_command_live_trader"] = test_command

    # Docs and changelog
    config["docs_root"] = docs_root
    config["changelog_folder"] = changelog_folder

    return config


# ---------------------------------------------------------------------------
# Interactive prompts
# ---------------------------------------------------------------------------

def _prompt_for_platforms() -> dict[str, bool]:
    """Interactively ask the user which IDEs/Platforms they use.

    Returns:
        Mapping of platform names to boolean selections.
    """
    platforms = {
        "claude_code": False,
        "antigravity": False,
        "cursor": False,
        "copilot": False,
        "cline": False,
    }
    if not sys.stdin.isatty():
        return platforms

    print("\n--- Platform Selection ---", file=sys.stderr)
    print("Which of the following IDEs/agent platforms will you be using?", file=sys.stderr)
    for display_name, key in [
        ("Claude Code", "claude_code"),
        ("Antigravity", "antigravity"),
        ("Cursor", "cursor"),
        ("Copilot", "copilot"),
        ("Cline", "cline"),
    ]:
        while True:
            try:
                resp = input(f"Do you use {display_name}? (y/n) [n]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print(file=sys.stderr)
                return platforms

            if not resp:
                resp = "n"
            
            if resp in ("y", "yes"):
                platforms[key] = True
                break
            elif resp in ("n", "no"):
                platforms[key] = False
                break
            else:
                print("Please answer 'y' or 'n'.", file=sys.stderr)
                
    return platforms


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Entry point for the bootstrap install script.

    Args:
        argv: Argument list. Defaults to sys.argv[1:].

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Bootstrap skills_config.json by auto-discovering the repo structure. "
            "Fallback for non-Claude-Code environments."
        )
    )
    parser.add_argument(
        "--target-dir", "-t", metavar="DIR",
        help="Root directory of the target project. Defaults to current directory.",
    )
    parser.add_argument(
        "--output", "-o", metavar="FILE",
        help="Write draft JSON to this file instead of stdout.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print draft to stdout only; do not write any files.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.target_dir).resolve() if args.target_dir else Path.cwd()

    print(f"Discovering config for: {repo_root}", file=sys.stderr)

    config = discover_config(repo_root)
    
    if not args.dry_run:
        config["platforms"] = _prompt_for_platforms()
    else:
        config["platforms"] = {
            "claude_code": False,
            "antigravity": False,
            "cursor": False,
            "copilot": False,
            "cline": False,
        }
        
    draft = json.dumps(config, indent=2, ensure_ascii=False)

    if args.dry_run or not args.output:
        print(draft)
        if not args.dry_run:
            print(
                "\nReview the draft above, then:\n"
                "  1. Edit .claude/skills_config.json to add/correct values\n"
                "  2. Run: python leafcutter/scripts/build.py --target-dir .\n",
                file=sys.stderr,
            )
        return 0

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(draft, encoding="utf-8")
    print(f"Draft written to: {output_path}", file=sys.stderr)
    print(
        f"Review {output_path}, then:\n"
        "  1. Copy relevant keys to .claude/skills_config.json\n"
        "  2. Run: python leafcutter/scripts/build.py --target-dir .\n",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-05-22 19:35 [EPIC-AntigravitySupport/T05]: Added interactive prompt for IDE/Platform selection to populate the `platforms` key in the config.
# - 2026-05-18 13:00 [EPIC-PortableInstallHardening/T07]: Created module. Standalone stdlib-only terminal fallback for the portable onboard agent. Discovers docs root, test root, top-level packages, ticket paths, default branch, changelog folder, project description from README. Outputs skills_config.json draft to stdout or --output path. --dry-run flag. (#EPIC-PortableInstallHardening/T07)
# ===========================================================================
