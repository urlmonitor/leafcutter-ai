"""Read archived receipts after case grouping without changing recorded bytes."""
from pathlib import Path
import re

BASE = Path(__file__).resolve().parents[1]
EVALUATIONS = {"public-evaluation", "repair-evaluation", "final-verification"}


def receipt_path(path: Path) -> Path:
    """Resolve an original report location to its case/attempt archive path.

    Args:
        path: Original receipt path, or an already relocated path.

    Returns:
        Current archive path; unrelated paths are returned unchanged.
    """
    path = Path(path)
    try:
        relative = path.resolve().relative_to(BASE)
    except ValueError:
        return path
    match = re.match(r"^([NHP]\d{2})(?:\.|$)", path.name)
    if not match or path.suffix != ".json":
        return path
    case = match.group(1)
    parent = relative.parent.as_posix()
    if parent in EVALUATIONS:
        pieces = path.name.split(".")
        attempt = pieces[1] if pieces[1] == "started" or pieces[1].startswith("resume-") else None
        folder = BASE / parent / case
        return folder / attempt / path.name if attempt else folder / path.name
    if parent in {"needs-evaluation", "needs-evaluation/controller-envelope-repair"}:
        return BASE / parent / case / path.name
    if parent in {"needs-evaluation/host-packets", "needs-evaluation/inputs", "needs-evaluation/responses"}:
        return BASE / parent / ("holdouts" if case.startswith("H") else "original") / path.name
    return path


def href(value: str) -> str:
    """Return a report-root-relative current link for an original receipt path."""
    return receipt_path(BASE / value).relative_to(BASE).as_posix()


def require_unarchived_controller() -> None:
    """Protect exported historical evidence from new provider calls or rewrites."""
    if (BASE / "archive" / "receipt-relocations.json").exists():
        raise ValueError("This is an immutable historical proof archive; start a new evaluation directory for new execution.")
