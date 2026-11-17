"""BO-2400c-1-xi: assemble-bundle writes UTF-8 to stdout whatever the code page.

Runs the real command as a subprocess with the child's stdout forced to cp1252
(PYTHONIOENCODING=cp1252, PYTHONUTF8=0) so the defect reproduces on any OS.
"""
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "injection_builders.py"

EMOJI = "\U0001f464"
LAYERS = {
    "architecture": f"architecture {EMOJI} layer\n",
    "high_level": "high level layer\n",
    "prior_tests": "prior tests layer\n",
}


def _run(tmp_path, layers):
    args = [sys.executable, str(SCRIPT), "assemble-bundle"]
    for name, text in layers.items():
        p = tmp_path / f"{name}.txt"
        p.write_bytes(text.encode("utf-8"))
        args += ["--" + name.replace("_", "-"), str(p)]
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1252"
    env["PYTHONUTF8"] = "0"
    return subprocess.run(args, capture_output=True, env=env, cwd=str(REPO_ROOT))


def _expected(layers):
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        from injection_builders import assemble_context_bundle
    finally:
        sys.path.pop(0)
    return assemble_context_bundle(**layers)


def test_bundle_command_emits_utf8_when_stdout_encoding_is_cp1252(tmp_path):
    # covers: BO-2400c-1-xi
    # angle: failure
    proc = _run(tmp_path, LAYERS)
    assert b"UnicodeEncodeError" not in proc.stderr, proc.stderr.decode("utf-8", "replace")
    assert proc.returncode == 0
    assert proc.stdout.decode("utf-8") == _expected(LAYERS) + "\n"


def test_bundle_command_utf8_output_has_no_bom_or_extra_bytes(tmp_path):
    # covers: BO-2400c-1-xi
    # angle: seam
    proc = _run(tmp_path, LAYERS)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert not proc.stdout.startswith(b"\xef\xbb\xbf")
    assert proc.stdout == (_expected(LAYERS) + "\n").encode("utf-8")


def test_ascii_bundle_bytes_unchanged_negative_control(tmp_path):
    # covers: BO-2400c-1-xi
    # angle: boundary
    ascii_layers = {k: v.replace(EMOJI, "x") for k, v in LAYERS.items()}
    proc = _run(tmp_path, ascii_layers)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    # Windows text-mode print() translates LF to CRLF; that is existing
    # behaviour for ASCII bundles, so normalise it for the control only.
    out = proc.stdout.replace(b"\r\n", b"\n")
    assert out == (_expected(ascii_layers) + "\n").encode("ascii")
