#!/usr/bin/env bash
set -euo pipefail

# Build leafcutter's own development environment.
# Compiles agents, skills, hooks, and workflows from templates into the
# parent workspace directory, using leafcutter-ai's own skills_config.json.
#
# Usage (from the repo root):
#   ./build-self.sh
#   ./build-self.sh --dry-run
#
# Equivalent to:
#   cd .. && python leafcutter-ai/scripts/build.py --target-dir .

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(dirname "$REPO_DIR")"

exec python3 "$REPO_DIR/scripts/build.py" --target-dir "$WORKSPACE_DIR" "$@"
