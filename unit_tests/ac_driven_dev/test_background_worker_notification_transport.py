"""Desktop transport routing and inert message data; never display test toasts."""

import base64
import re
from types import SimpleNamespace

import pytest

from scripts.background_worker import notifications
from scripts.background_worker.store import Store


@pytest.fixture
def transport(monkeypatch):
    environment = {"PATH": "/usr/bin", "DISPLAY": ":0", "WSLENV": "SECRET/u",
                   "SECRET": "private", "OPENAI_API_KEY": "private"}
    monkeypatch.setattr(notifications, "os", SimpleNamespace(name="posix", environ=environment))
    monkeypatch.setattr(notifications, "sys", SimpleNamespace(platform="linux"))
    calls = []
    monkeypatch.setattr(notifications.subprocess, "run", lambda argv, **kwargs: calls.append((argv, kwargs)))
    return calls


def test_wsl_routes_inert_unicode_data_to_fixed_hidden_windows_notifier(transport, monkeypatch):
    # covers: ACD-1300d-2
    monkeypatch.setattr(notifications.platform, "release", lambda: "6.6.87.2-microsoft-standard-WSL2")
    message = "O'Brien $(Invoke-Expression 'bad'); `backtick`\nGrüße ✓"
    notifications._send(message)
    argv, kwargs = transport[0]
    assert argv[0] == "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    assert argv[argv.index("-WindowStyle") + 1] == "Hidden"
    script = base64.b64decode(argv[-1]).decode("utf-16-le")
    encoded_message = re.search(r"FromBase64String\('([A-Za-z0-9+/=]+)'\)", script).group(1)
    assert base64.b64decode(encoded_message).decode("utf-8") == message
    assert message not in script
    assert "Invoke-Expression" not in script
    assert "ShowBalloonTip" in script
    assert kwargs["env"] == {"PATH": "/usr/bin", "DISPLAY": ":0"}
    assert kwargs["timeout"] == 15 and kwargs["check"] is True
    assert not kwargs.get("shell")


def test_native_linux_keeps_notify_send(transport, monkeypatch):
    # covers: ACD-1300d-2
    monkeypatch.setattr(notifications.platform, "release", lambda: "6.8.0-generic")
    notifications._send("needs attention")
    assert transport[0][0] == ["notify-send", "Leafcutter", "needs attention"]


def test_wsl_missing_transport_persists_failure_and_request_without_retry(
    transport, monkeypatch, tmp_path
):
    # covers: ACD-1300d-2-i
    monkeypatch.setattr(notifications.platform, "release", lambda: "microsoft-standard-WSL2")
    calls = []

    def unavailable(argv, **kwargs):
        calls.append(argv)
        raise FileNotFoundError("Windows interop unavailable")

    monkeypatch.setattr(notifications.subprocess, "run", unavailable)
    db = tmp_path / "state.sqlite"
    with Store(db) as store:
        store.update_settings(enabled=True)
        run = store.claim_feature({"feature_id": "DEM-100a", "ac_ids": ["DEM-100a-1"]})
        store.block_run(run["id"], "Needs answer", {"questions": ["Which target?"]})
        notifications.notify_outcomes(db, store)
        notifications.notify_outcomes(db, store)
        assert len(calls) == 1
        assert store.list_inbox()[0]["details"]["questions"] == ["Which target?"]
        assert store.get_run(run["id"])["state"] == "blocked"
    notice = notifications.notification_status(db)[0]
    assert notice["state"] == "failed" and notice["error"] == "FileNotFoundError"
