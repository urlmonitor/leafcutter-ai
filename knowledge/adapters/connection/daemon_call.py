"""Run blocking driver calls on abandonable daemon threads.

MODULE: knowledge.adapters.connection.daemon_call
GOAL: Let a retrieval answer and exit on time even when a driver call never returns.
BUSINESS CONTEXT: A blocked name lookup or connect cannot be cancelled; waiting for it breaks the request deadline.
ARCHITECTURE: One daemon thread per call; the awaiting coroutine is released on completion, cancellation or timeout.

DECISION HISTORY
========================================
- 2026-10-23 12:00 [python-coder]: Replace the default executor, whose threads are joined at exit, with daemon threads. (#KM-400d-4-ii)
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import threading

logger = logging.getLogger(__name__)


async def run_in_daemon(func, *args, timeout: float | None = None):
    """Call ``func`` on a daemon thread and await its result.

    Args:
        func: Blocking callable.
        *args: Positional arguments for it.
        timeout: Seconds to wait before abandoning the thread (raises TimeoutError).

    Returns:
        Whatever ``func`` returned.

    Raises:
        BaseException: Whatever ``func`` raised (including SystemExit/KeyboardInterrupt from the
            worker) is delivered to and re-raised in the awaiting coroutine, so it never hangs.
    """
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    context = contextvars.copy_context()

    def settle(setter, value) -> None:
        """Deliver an outcome unless the awaiting side already gave up."""
        if not future.done():
            setter(value)

    def work() -> None:
        """Run the call and hand its outcome to the event loop."""
        try:
            outcome = (future.set_result, context.run(func, *args))
        except BaseException as exc:  # noqa: BLE001 - re-raised in the awaiting coroutine, never swallowed
            outcome = (future.set_exception, exc)
        try:
            loop.call_soon_threadsafe(settle, *outcome)
        except RuntimeError:
            logger.warning("Abandoned driver call finished after the event loop closed")

    threading.Thread(target=work, name="knowledge-neo4j-worker", daemon=True).start()
    return await asyncio.wait_for(future, timeout)
