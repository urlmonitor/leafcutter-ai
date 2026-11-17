"""Real owner serializers, isolated sources and public entity API adapters.

No parser or recognizer is doubled here. The API availability assertion gives a
collectable, assertion-red baseline before production modules are introduced.
"""

from __future__ import annotations

import importlib
import importlib.util
import io
import json
import shutil
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import yaml

from kernel.config import SourceConfig, load_kernel_config
from kernel.contracts import Actor, ActorKind, CallerContext, TaskInput
from kernel.contracts.base import canonical_json
from tests.conftest import load_fixture
from tests.kernel.helpers import make_scope

REPO = Path(__file__).resolve().parents[3]
FAMILIES = {"glossary", "doc_type", "entry_kind", "native_kind", "symbol", "artifact_id"}
AC_ID = "EC-1100a-1-i"


def api(module: str, name: str):
    """Import the specified frozen public API, failing as an assertion before it exists."""
    assert importlib.util.find_spec(module) is not None, f"DK-300 production API missing: {module}.{name}"
    return getattr(importlib.import_module(module), name)


def write(root: Path, relative: str, value: Any) -> Path:
    """Use real serializers for every JSON/YAML fixture written on disk."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".json":
        text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    elif path.suffix in {".yaml", ".yml"}:
        text = yaml.safe_dump(value, allow_unicode=True, sort_keys=False)
    else:
        text = value
    path.write_text(text, encoding="utf-8")
    return path


def write_frontmatter(root: Path, relative: str, metadata: dict, body: str) -> Path:
    """Serialize authored Markdown frontmatter through PyYAML, then append source body."""
    return write(root, relative, "---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---\n" + body)


def write_repo(root: Path) -> dict:
    """Materialize reviewed test owner records, never production-derived expected labels."""
    data = load_fixture("entity_context/owners")
    for relative, value in data["json"].items():
        write(root, relative, value)
    for name in ("doc_types.json", "entry_kind_vocabulary.json", "ac_store_schema.json"):
        destination = root / "config" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / "config" / name, destination)
    for relative, value in data["yaml"].items():
        write(root, relative, value)
    for relative, value in data["text"].items():
        write(root, relative, value)
    for relative, value in data["frontmatter"].items():
        if relative.startswith("docs/decisions/"):
            write(root, str(Path(relative).with_suffix(".yaml")), value["metadata"])
        else:
            write_frontmatter(root, relative, value["metadata"], value["body"])
    return data


def config_for(**limits):
    """Use the public defaults and one explicit allowed source catalog for this corpus."""
    config = load_kernel_config()
    assert hasattr(config, "entity_context"), "DK-300 entity_context config is missing"
    sources = [SourceConfig(id="eval.entities", kind="repo_text", categories=["task_context"],
                            roots=["docs", "config", "pkg", "tickets"])]
    entity = config.entity_context.model_copy(update={"source_ids": ["eval.entities"], **limits})
    return config.model_copy(update={"sources": sources, "entity_context": entity})


def task_for(root: Path, goal: str, *, context: CallerContext | None = None, **extra) -> TaskInput:
    """Send an actual client TaskInput through normal admission."""
    return TaskInput(goal=goal, caller=Actor(id="entity-eval", kind=ActorKind.HUMAN),
                     scope=make_scope(root), context=context or CallerContext(), **extra)


def build(root: Path, config=None):
    """Prepare the real derived index outside the initial recognition pass."""
    return api("kernel.entity_index", "build_entity_index")(root, config or config_for())


def recognize(root: Path, goal: str, *, config=None, context=None, **kwargs):
    """Run the real deterministic pass, retaining its typed context."""
    return api("kernel.entity_context", "recognize_entities")(
        task_for(root, goal, context=context), config or config_for(), **kwargs)


def payload(context, *, send_repo_excerpts=True):
    """Obtain the real serialized meaning-only projection."""
    return api("kernel.entity_projection", "entity_context_payload")(
        context, send_repo_excerpts=send_repo_excerpts)


def cards(context, family: str | None = None) -> dict[str, Any]:
    """Select actual returned cards by canonical identity without normalizing identities."""
    return {item.identity: item for item in context.entities if family is None or item.family == family}


def compact_size(value: Any) -> int:
    """Count precisely the production wire serializer, including JSON escaping."""
    return len(canonical_json(value))


def long_goal() -> str:
    """One thousand words with a canonical nested ID at word 999."""
    return " ".join(["ordinary"] * 998 + [AC_ID, "please"])


def cli_run(rig, raw: dict):
    """Invoke the real CLI main with real argv and the real service composition."""
    from kernel.adapters.cli import main
    rig.service()
    input_path = write(rig.repo, "request.json", raw)
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(["run", "--input-file", str(input_path), "--json"], environment=lambda **_: rig.env)
    return code, json.loads(out.getvalue())
