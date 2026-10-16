"""Create an ephemeral Codex catalog from explicit local Ollama metadata."""

import json
from pathlib import Path

from .execution_boundary import ExecutorError

EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh"}


def _effort(value):
    if value is False:
        return "none"
    if value is True:
        return "high"
    if isinstance(value, str) and value in EFFORTS:
        return value
    raise ValueError("Unsupported local model reasoning effort")


def write_catalog(home, model, metadata=None, context_window=65536, reasoning_effort=None):
    """Return catalog path, chosen effort and bounded context; perform no network I/O."""
    if type(context_window) is not int or context_window <= 0:
        raise ValueError("Implementation context_window must be a positive integer")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Local catalog requires an explicit model name")
    metadata = metadata or {}
    thinking = metadata.get("thinking") or {}
    if not isinstance(thinking, dict):
        raise ValueError("Local model thinking metadata must be an object")
    values = thinking.get("values", [False])
    if not isinstance(values, list) or not values:
        raise ValueError("Local model thinking values must be a nonempty list")
    supported = list(dict.fromkeys(_effort(value) for value in values))
    fallback = "none" if "none" in supported else supported[0]
    default = _effort(thinking["default"]) if "default" in thinking else fallback
    if default not in supported:
        raise ValueError("Advertised default reasoning effort is unsupported by the local model")
    if reasoning_effort is not None and not isinstance(reasoning_effort, str):
        raise ValueError("Requested reasoning_effort must be a named effort")
    chosen = default if reasoning_effort is None else _effort(reasoning_effort)
    if chosen not in supported:
        raise ValueError("Requested reasoning_effort is unsupported by the local model")
    info = metadata.get("model_info") or {}
    if not isinstance(info, dict):
        raise ValueError("Local model model_info metadata must be an object")
    capacities = [value for key, value in info.items()
                  if key.endswith(".context_length") or key == "context_length"]
    valid = [value for value in capacities if type(value) is int and value > 0]
    window = min([context_window, *valid])
    catalog = {"models": [{
        "slug": model, "display_name": model, "base_instructions": "",
        "context_window": window, "default_reasoning_level": chosen,
        "default_verbosity": "low", "experimental_supported_tools": [],
        "input_modalities": ["text"], "priority": 0, "shell_type": "default",
        "support_verbosity": True, "supported_in_api": True,
        "supported_reasoning_levels": [
            {"effort": effort, "description": "Local model reasoning: " + effort}
            for effort in supported
        ],
        "supports_parallel_tool_calls": False, "supports_reasoning_summaries": False,
        "truncation_policy": {"limit": 10000, "mode": "bytes"}, "visibility": "list",
    }]}
    path = Path(home) / "local-model-catalog.json"
    try:
        path.write_text(json.dumps(catalog), encoding="utf-8")
    except OSError as exc:
        raise ExecutorError("Cannot write isolated local model catalog") from exc
    return path, chosen, window
