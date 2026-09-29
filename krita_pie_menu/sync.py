"""
Qt-aware synchronization helpers for pie-menu operations.

Operations trigger Krita ``QAction``s and pump the Qt event loop so the
application can catch up with the document. Neither of those is atomic:

* ``QAction.trigger()`` is a **silent no-op** when the action is disabled in the
  current context (see AGENTS.md section 2). Nothing is raised, nothing is
  logged, and the document is left half-mutated.
* ``Document.waitForDone()`` waits on the *document job queue*. It cannot prove
  that a triggered action actually executed.

So every fire-and-forget trigger is wrapped here with a precondition check
(``isEnabled``) and a postcondition check (did the state actually change?).
``settle_until`` is the one legitimate timeout in this codebase: a bounded wait
that **reports failure** instead of silently continuing. It is not a watchdog --
synchronous Python work in Krita cannot be interrupted, so it never fires on a
slow-but-correct run.
"""
import time
from typing import Any, Callable, List, Optional

from PyQt5.QtWidgets import QApplication

from .logger import log_error, log_warning
from .utils import resolve_action

DEFAULT_SETTLE_TIMEOUT_MS = 2000
DEFAULT_SETTLE_INTERVAL_MS = 10


def pump_events(doc: Optional[Any] = None) -> None:
    """
    Give the Qt event loop one turn, then block on the document job queue.

    This is the minimum synchronisation step between two operations that must
    happen in order. It provides no guarantee that a previously triggered action
    has run -- only :func:`trigger_action_verified` can establish that.
    """
    QApplication.processEvents()
    if doc is not None:
        doc.waitForDone()


def settle_until(
    predicate: Callable[[], bool],
    doc: Optional[Any] = None,
    timeout_ms: int = DEFAULT_SETTLE_TIMEOUT_MS,
    interval_ms: int = DEFAULT_SETTLE_INTERVAL_MS,
) -> bool:
    """
    Pump the Qt event loop until ``predicate()`` returns True or the deadline passes.

    Checks the predicate once before the deadline test, so a slow machine that
    converges on the final iteration still succeeds. Returns True as soon as the
    predicate holds, False when the deadline is reached.
    """
    deadline = time.monotonic() + timeout_ms / 1000.0
    while True:
        pump_events(doc)
        if predicate():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval_ms / 1000.0)


def action_is_enabled(action: Any) -> bool:
    """
    Reads ``QAction.isEnabled()``, tolerating objects that do not expose it.

    A missing or throwing ``isEnabled`` is treated as enabled: the real Krita
    binding always has it, and the postcondition check in
    :func:`trigger_action_verified` is the real safety net.
    """
    if action is None:
        return False
    checker = getattr(action, "isEnabled", None)
    if checker is None:
        return True
    try:
        return bool(checker())
    except Exception:
        return True


def trigger_action_verified(
    app: Any,
    candidate_ids: List[str],
    is_done: Callable[[], bool],
    doc: Optional[Any] = None,
    timeout_ms: int = DEFAULT_SETTLE_TIMEOUT_MS,
    label: str = "action",
) -> bool:
    """
    Resolve, precondition-check, trigger, then postcondition-check a Krita action.

    Returns True only when ``is_done()`` observed the expected state change.
    Returns False when the action is missing, disabled, throws, or the expected
    change never materialises within ``timeout_ms``.
    """
    action = resolve_action(app, candidate_ids)
    if action is None:
        log_warning("sync", f"'{label}' not found; tried {list(candidate_ids)}")
        return False
    if not action_is_enabled(action):
        log_warning("sync", f"'{label}' is disabled in the current context; trigger() would be a no-op")
        return False
    try:
        action.trigger()
    except Exception as e:
        log_error("sync", f"'{label}' failed to trigger", e)
        return False
    return settle_until(is_done, doc=doc, timeout_ms=timeout_ms)
