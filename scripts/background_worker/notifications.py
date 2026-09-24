"""Durable, deduplicated native notification attempts independent of run outcomes."""

from contextlib import contextmanager
import os
import sqlite3
import subprocess
import sys
import logging

LOGGER = logging.getLogger(__name__)


@contextmanager
def _connection(db):
    conn = sqlite3.connect(str(db), timeout=30)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS notifications(event_id TEXT PRIMARY KEY, state TEXT, error TEXT)"
    )
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def notification_status(db):
    with _connection(db) as conn:
        return [
            dict(zip(("event_id", "state", "error"), row))
            for row in conn.execute(
                "SELECT event_id,state,error FROM notifications ORDER BY event_id"
            )
        ]


def _send(message):
    env = os.environ.copy()
    env["LEAFCUTTER_NOTICE"] = message
    if os.name == "nt":
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$n=New-Object System.Windows.Forms.NotifyIcon; "
            "$n.Icon=[System.Drawing.SystemIcons]::Information; $n.Visible=$true; "
            "$n.ShowBalloonTip(5000,'Leafcutter',$env:LEAFCUTTER_NOTICE,"
            "[System.Windows.Forms.ToolTipIcon]::Info); Start-Sleep -Seconds 6; $n.Dispose()"
        )
        argv = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script]
    elif sys.platform == "darwin":
        argv = [
            "osascript",
            "-e",
            'display notification (system attribute "LEAFCUTTER_NOTICE") with title "Leafcutter"',
        ]
    else:
        argv = ["notify-send", "Leafcutter", message]
    kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    try:
        subprocess.run(argv, env=env, capture_output=True, check=True, timeout=15, **kwargs)
    except (OSError, subprocess.SubprocessError) as exc:
        LOGGER.warning("Desktop notification failed: %s", type(exc).__name__)
        raise


def notify_outcomes(db, store):
    events = []
    for item in store.list_inbox():
        events.append(
            (
                "request:" + str(item.get("id", item.get("item_id"))),
                store.get_run(item["run_id"])["feature_id"]
                + " needs your attention. Run the worker inbox command.",
            )
        )
    for run in store.list_runs():
        if run["state"] in {"delivered", "ready_for_user_review"}:
            events.append(
                (
                    "delivered:" + run.get("run_id", run["id"]),
                    run["feature_id"] + ": a draft PR is ready. Run the worker status command.",
                )
            )
    for identity, message in events:
        with _connection(db) as conn:
            inserted = conn.execute(
                "INSERT OR IGNORE INTO notifications VALUES(?, 'attempting', NULL)", (identity,)
            ).rowcount
        if not inserted:
            continue
        try:
            _send(message)
            state, error = "sent", None
        except (OSError, subprocess.SubprocessError) as exc:
            state, error = "failed", type(exc).__name__
        with _connection(db) as conn:
            conn.execute(
                "UPDATE notifications SET state=?,error=? WHERE event_id=?",
                (state, error, identity),
            )
