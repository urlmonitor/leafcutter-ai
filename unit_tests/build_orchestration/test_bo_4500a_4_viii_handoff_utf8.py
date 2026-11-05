"""BO-4500a-4-viii: a failing check's UTF-8 output reaches remedy_handoff intact.

The step hands a failed check's output to remedy_handoff.py on stdin. On a cp1252
host that pipe used the locale code page, so an emoji in the output (the file-size
check's ruler) killed the writer thread and hung the step. A stand-in
remedy_handoff.py echoes what it read, so the test sees both ends of the pipe.
"""

import json
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "templates" / "scripts"))

import commit_changes  # noqa: E402

_ECHO = "import json, sys\nprint(json.dumps({'got': sys.stdin.read()}))\n"
_DEADLINE_S = 30
_HUNG = {"hung": f"the handoff did not return within {_DEADLINE_S}s: the stdin pipe broke"}


def _handoff_with_echo(output: str) -> dict | None:
    # The broken pipe hangs rather than raises (the dead writer never closes stdin),
    # so the call runs on a daemon thread with a deadline and a hang is a failure.
    root = Path(tempfile.mkdtemp(prefix="bo4500a4viii_"))
    guardian = root / "scripts" / "commit_guardian"
    guardian.mkdir(parents=True)
    (guardian / "remedy_handoff.py").write_text(_ECHO, encoding="utf-8")
    result: list = []
    worker = threading.Thread(target=lambda: result.append(commit_changes._handoff(root, "check-file-size", output)), daemon=True)
    worker.start()
    worker.join(_DEADLINE_S)
    if worker.is_alive():
        return _HUNG
    shutil.rmtree(root, ignore_errors=True)
    return result[0]


class TestHandoffPipeIsUtf8(unittest.TestCase):
    def test_failed_check_output_with_emoji_reaches_the_handoff_intact(self):
        # covers: BO-4500a-4-viii
        # angle: criterion
        output = "\U0001f4cf FILE GREW → 432 lines"
        answer = _handoff_with_echo(output)
        self.assertEqual(answer, {"got": output})

    def test_ascii_check_output_is_unchanged_control(self):
        # covers: BO-4500a-4-viii
        # angle: criterion
        answer = _handoff_with_echo("FILE GREW: 432 lines")
        self.assertEqual(json.loads(json.dumps(answer)), {"got": "FILE GREW: 432 lines"})


if __name__ == "__main__":
    unittest.main()
