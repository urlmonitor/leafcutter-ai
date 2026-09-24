"""Source artifact inventories used when cleaning stale build outputs."""

from pathlib import Path


def _build_source_manifests(output_root: Path) -> dict:
    """Compute the set of artifact names that build.py currently manages.

    Scans the template directories for each artifact type and returns a dict
    mapping artifact type names to the set of expected output file/directory
    base names that a build pass would produce. This set is used by
    clean_stale_artifacts() to determine which compiled outputs are stale.

    Args:
        output_root: The consolidated output directory (e.g. ``<target>/.leafcutter``
            or ``<target>`` when shims are used). The cleaned directories are
            ``agents/``, ``skills/``, and ``hooks/`` under this root.

    Returns:
        Dict with keys ``"agents"``, ``"skills"``, ``"hooks"``, each mapping to
        a ``set[str]`` of expected base names.
    """
    package_root = Path(__file__).resolve().parent.parent
    templates_dir = package_root / "templates"

    # Agents: each *.md file in templates/agents/ (excluding helper _*.md files)
    agents_template_dir = templates_dir / "agents"
    agents: set[str] = set()
    if agents_template_dir.exists():
        for f in agents_template_dir.glob("*.md"):
            if not f.name.startswith("_"):
                agents.add(f.name)

    # Skills: each subdirectory in templates/skills/
    skills_template_dir = templates_dir / "skills"
    skills: set[str] = set()
    if skills_template_dir.exists():
        for d in skills_template_dir.iterdir():
            if d.is_dir():
                skills.add(d.name)

    # Hooks: each *.py (or other files) in templates/hooks/ (if it exists)
    hooks_template_dir = templates_dir / "hooks"
    hooks: set[str] = set()
    if hooks_template_dir.exists():
        for f in hooks_template_dir.iterdir():
            if f.is_file():
                hooks.add(f.name)

    # Workflow scripts: each *.js file in templates/workflows-js/
    workflows_js_dir = templates_dir / "workflows-js"
    workflows: set[str] = set()
    if workflows_js_dir.exists():
        for f in workflows_js_dir.glob("*.js"):
            if f.is_file():
                workflows.add(f.name)

    return {
        "agents": agents,
        "skills": skills,
        "hooks": hooks,
        "workflows": workflows,
    }
