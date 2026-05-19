"""
MODULE: generator
GOAL: Generate batched AI work orders for fixing compliance violations and reviewing draft registry components.
BUSINESS CONTEXT: Work orders are markdown files given to an AI agent to systematically fix frontmatter and DOC_LINKS.
ARCHITECTURE: Not needed.
"""
import json
import typing
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from scripts.doc_compliance.config import DEFAULT_CONFIG_FILE, DEFAULT_COMPONENTS_FILE
from scripts.doc_compliance.utils import safe_print
from scripts.doc_compliance.scanner import Scanner

def get_unreviewed_components(registry: dict) -> list[tuple[str, dict]]:
    """Return a list of component entries that are still in draft/unreviewed state.

    Supports both array-based (list of objects with 'id') and dict-based
    (keyed by component name) component registries.

    Args:
        registry: Parsed components.json dict.

    Returns:
        list[tuple[str, dict]]: List of (key, component_dict) pairs needing review.
    """
    unreviewed = []
    components = registry.get("components", [])

    # Support both formats: array of objects (current) and dict (legacy)
    if isinstance(components, list):
        items = [(comp.get("id", f"unknown_{i}"), comp) for i, comp in enumerate(components)]
    else:
        items = list(components.items())

    for key, comp in items:
        is_draft = comp.get("status", "").lower() == "draft"
        needs_review = "needs review" in comp.get("description", "").lower()
        if is_draft or needs_review:
            unreviewed.append((key, comp))
    return unreviewed

def _get_folder_group(detail_ref: str) -> str:
    """Extract the top-level source folder from a detail_ref path for grouping.

    Args:
        detail_ref: The detail_ref string from a component entry (e.g. 'models\\candles.py').

    Returns:
        str: Top-level folder name (e.g. 'models', 'collector/services', 'sql_functions/functions').
    """
    normalized = detail_ref.replace("\\", "/")
    parts = normalized.split("/")
    # For deeper structures like collector/services/X or sql_functions/procedures/X,
    # use the first two segments — but only if the second segment is a directory
    # (no file extension), not a leaf file like 'models/candles.py'.
    if len(parts) >= 2 and "." not in parts[1]:
        return "/".join(parts[:2])
    return parts[0]


def _group_by_folder(unreviewed: list) -> list[tuple[str, list]]:
    """Group unreviewed components by their source folder.

    Args:
        unreviewed: List of (key, component_dict) tuples.

    Returns:
        list[tuple[str, list]]: Ordered list of (folder_name, items) groups.
    """
    groups = defaultdict(list)
    for key, comp in unreviewed:
        folder = _get_folder_group(comp.get("detail_ref", "unknown"))
        groups[folder].append((key, comp))
    # Sort groups alphabetically for deterministic output
    return sorted(groups.items(), key=lambda x: x[0])


def _create_folder_batches(folder_groups: list, batch_size: int) -> list[list[tuple[str, str, dict]]]:
    """Pack folder groups into batches of approximately batch_size items.

    Small folders are kept intact within a batch. Large folders (exceeding
    batch_size) are split across multiple batches while keeping the folder
    label on each.

    Args:
        folder_groups: Ordered list of (folder_name, items) groups.
        batch_size: Target number of items per batch.

    Returns:
        list[list[tuple[str, str, dict]]]: Batches of (folder, key, comp) tuples.
    """
    batches = []
    current_batch = []
    for folder, items in folder_groups:
        for key, comp in items:
            # Flush when we hit the batch size
            if len(current_batch) >= batch_size:
                batches.append(current_batch)
                current_batch = []
            current_batch.append((folder, key, comp))
    # Don't forget the last batch
    if current_batch:
        batches.append(current_batch)
    return batches


def _write_review_header(f: typing.TextIO, batch_id: str, batch_len: int, total_unreviewed: int, total_components: int, total_batches: int) -> None:
    """Write the shared header and instructions for a registry review batch file.

    Args:
        f: Open file handle.
        batch_id: Batch identifier string (e.g. '001').
        batch_len: Number of components in this batch.
        total_unreviewed: Total unreviewed components across all batches.
        total_components: Total components in the registry.
        total_batches: Total number of batches generated.
    """
    header = f"""# Component Registry Review — Batch {batch_id}

**Generated:** {datetime.now(timezone.utc).isoformat()}Z
**Components in this batch:** {batch_len}
**Total unreviewed:** {total_unreviewed} of {total_components} (batch {int(batch_id)} of {total_batches})
**Registry file:** `{DEFAULT_COMPONENTS_FILE}`

## Instructions for AI Agent

The component registry (`docs/components.json`) was auto-generated and contains
unreviewed entries. Review and finalize every entry in this batch.

### Execution Rules

For each component below, edit `docs/components.json` directly:

1. **`description`**: Replace the auto-generated placeholder with a real 1-2 sentence description of what this component does. Read the source file at `detail_ref` to understand it.
2. **`type`**: Validate the inferred type is correct. Allowed types: `service`, `data_table`, `data_pipeline`, `engine`, `model`, `api_integration`, `utility`, `infrastructure`.
3. **`name`**: Ensure the human-readable name is correct and properly capitalized.
4. **`status`**: Change from `"draft"` to `"reviewed"` once you have validated and updated the entry.
5. **Delete false positives.** If an entry should NOT be a top-level component (e.g. it's a utility helper or internal detail), remove it from the registry entirely.
6. **Check for missing components.** If you notice a major component in this folder area that was NOT auto-discovered, add it following the format of existing entries.

### Verification

After reviewing ALL batches, run:
```bash
python scripts/doc_compliance_scanner.py --review-registry --project-root <path-to-project>
```
When it prints `[OK]`, proceed with `--generate-orders`.

---

"""
    f.write(header)


def review_registry(output_dir: str = "reports", batch_size: int = 10, project_root: str = ".") -> None:
    """Generate batched AI work orders to review and finalize draft components.

    Components are grouped by source folder so each batch has topical coherence.
    Folder groups are kept intact — a batch may slightly exceed batch_size to
    avoid splitting a folder across two files.

    Args:
        output_dir: Directory to write the review work order files to.
        batch_size: Target number of components per batch.
        project_root: Root directory of the target project.
    """
    components_file = Path(project_root) / DEFAULT_COMPONENTS_FILE
    if not components_file.exists():
        print(f"No components.json found at {components_file}. Run --discover-components first.")
        return

    with open(components_file, "r", encoding="utf-8") as f:
        registry = json.load(f)

    safe_print(f"Reading registry from: {components_file.resolve()}")
    unreviewed = get_unreviewed_components(registry)
    if not unreviewed:
        safe_print("[OK] All components are reviewed. You can proceed with --generate-orders.")
        return

    Path(output_dir).mkdir(exist_ok=True)

    # Group by folder, then pack into batches
    folder_groups = _group_by_folder(unreviewed)
    batches = _create_folder_batches(folder_groups, batch_size)
    components = registry.get("components", [])
    total_components = len(components) if isinstance(components, list) else len(components)

    for i, batch in enumerate(batches):
        batch_id = f"{i + 1:03d}"
        out_path = Path(output_dir) / f"registry_review_batch_{batch_id}.md"

        with open(out_path, "w", encoding="utf-8") as f:
            _write_review_header(
                f, batch_id, len(batch), len(unreviewed),
                total_components, len(batches)
            )

            current_folder = None
            for j, (folder, key, comp) in enumerate(batch):
                # Add folder subheading when the folder changes
                if folder != current_folder:
                    current_folder = folder
                    f.write(f"## Folder: `{folder}`\n\n")

                f.write(f"### {j + 1}. `{key}`\n")
                f.write(f"- **Current name:** {comp.get('name', 'N/A')}\n")
                f.write(f"- **Current type:** {comp.get('type', 'N/A')}\n")
                f.write(f"- **Current description:** {comp.get('description', 'N/A')}\n")
                f.write(f"- **Source:** `{comp.get('detail_ref', 'N/A')}`\n")
                f.write(f"- **Status:** {comp.get('status', 'N/A')}\n\n")

    safe_print(f"[!] {len(unreviewed)} components need review.")
    print(f"Generated {len(batches)} review batches (grouped by folder) in '{output_dir}/'.")
    print("Provide batch files to your AI agent, then re-run --review-registry to verify.")


def generate_orders(batch_size: int = 10, output_dir: str = "reports", project_root: str = ".") -> None:
    """Scan for compliance violations and generate batched AI work orders.

    Args:
        batch_size: Number of violations per work order batch.
        output_dir: Directory to write work order markdown files.
        project_root: Root directory of the target project.
    """
    config_file = Path(project_root) / DEFAULT_CONFIG_FILE
    components_file = Path(project_root) / DEFAULT_COMPONENTS_FILE
    if not config_file.exists():
        print("No doc_compliance.json found. Run --bootstrap first.")
        return
    if not components_file.exists():
        print("No components.json found. Run --discover-components first.")
        return

    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)
    with open(components_file, "r", encoding="utf-8") as f:
        registry = json.load(f)

    # Gate: registry must be fully reviewed before generating work orders
    unreviewed = get_unreviewed_components(registry)
    if unreviewed:
        safe_print(f"[X] Cannot generate work orders: {len(unreviewed)} components in "
                   f"docs/components.json are still in draft/unreviewed state.")
        print(f"Run --review-registry first to generate a review work order.")
        return

    print("Scanning for compliance violations...")
    scanner = Scanner(config, registry)
    scanner.scan_docs()
    scanner.scan_python()
    scanner.scan_sql()
    scanner.finalize_scan()

    violations = scanner.violations
    if not violations:
        print("No compliance violations found. Great job!")
        return

    # Sort by priority
    priority_map = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
    violations.sort(key=lambda x: priority_map.get(x["priority"], 5))

    Path(output_dir).mkdir(exist_ok=True)

    batches = [violations[i:i + batch_size] for i in range(0, len(violations), batch_size)]

    for i, batch in enumerate(batches):
        batch_id = f"{i+1:03d}"
        batch_file = Path(output_dir) / f"doc_compliance_batch_{batch_id}.md"
        with open(batch_file, "w", encoding="utf-8") as f:
            header = f"""# Documentation Compliance Work Order — Batch {batch_id}

**Generated:** {datetime.now(timezone.utc).isoformat()}Z
**Files in this batch:** {len(batch)}
**Estimated effort:** ~15 minutes

## Instructions for AI Agent

You are fixing documentation compliance issues. For each file below,
apply the specified fix according to the **Execution Rules**.

### Execution Rules

1. **Infer values — do NOT paste placeholders literally.** Fields marked `<INFER ...>` must be replaced with real values:
   - `title`: Derive from the file's first `# Heading` or, if absent, from the filename.
   - `type`: Choose one of the allowed types in `docs/FRONTMATTER.md`.
   - `components`: Look up valid component keys in `docs/components.json`. If the file clearly relates to a component not yet in the registry, follow `scripts/doc_compliance/BOOTSTRAP_GUIDE.md` Step 2 to add it. Only remove the `components:` field if the file is truly component-agnostic (e.g. a top-level README).
2. **Insert at line 1.** Frontmatter MUST be the very first content in the file. If partial or malformed YAML frontmatter already exists, replace it entirely.
3. **Preserve existing content.** Do not modify any content below the closing `---`.
4. **Verify.** After fixing all files, run from the project root:
   `python scripts/doc_compliance_scanner.py --verify-batch {batch_id}`
5. **Self-correct on failure.** If the verification command fails or reports remaining violations, read the error output, fix the issues, and re-run until it passes.

### Standards Reference

- Frontmatter spec & allowed values: `docs/FRONTMATTER.md`
- Component registry (valid keys): `docs/components.json`
- DOC_LINKS format: `.agents/rules/documentation.md` Section 8

---

"""
            f.write(header)

            for j, v in enumerate(batch):
                f.write(f"### Fix {j+1} of {len(batch)}: {v['file']}\n")
                f.write(f"**Violation:** {v['type']}\n")
                f.write(f"**Priority:** {v['priority']}\n")
                f.write("**Fix:** Apply the following template (replace `<INFER ...>` markers):\n```yaml\n")
                f.write(v["suggestion"])
                f.write("\n```\n\n")

    print(f"Scanned {scanner.stats['docs']} docs, {scanner.stats['python']} Python files, {scanner.stats['sql']} SQL files.")
    print(f"Found {len(violations)} violations. Generated {len(batches)} work orders in '{output_dir}'.")

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-04 19:00 [Antigravity]: Initial creation. Extracted generate_orders() and
  review_registry() from the monolithic doc_compliance_scanner.py to reduce file size
  below the pre-commit 400-line threshold.
- 2026-05-04 19:30 [Antigravity]: Fixed syntax errors from improper multiline f-string
  concatenation in work order write blocks; refactored to triple-quoted string blocks.
====================================================================
"""
