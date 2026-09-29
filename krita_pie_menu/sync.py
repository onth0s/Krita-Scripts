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
from typing import Any, Callable, Dict, List, Optional

from krita import Krita
from PyQt5.QtWidgets import QApplication

from .logger import log_error, log_info, log_warning
from .utils import describe_action, keep_action_alive, probe_action_ids, resolve_action

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


def diagnose_action_ids(
    app: Any,
    candidate_ids: List[str],
    label: str = "diagnostic",
    samples: int = 200,
) -> Dict[str, Dict[str, int]]:
    """
    Sample ``app.action(id)`` repeatedly and report the outcome distribution.

    Built for the unresolved ``layer_merge_down`` anomaly, where the same action
    reported "is disabled" on one run and "not found" on the next inside a single
    second. A one-shot probe cannot distinguish an intermittent failure from a
    genuinely absent ID; sampling in a tight loop can, because a real
    intermittency shows up as a *mixed* distribution rather than a uniform one.

    Intended to be run from Krita's Scripter, e.g.::

        from krita import Krita
        from krita_pie_menu.sync import diagnose_action_ids
        diagnose_action_ids(Krita.instance(), ["layer_merge_down", "merge_layer_down"])

    A uniform ``none`` means the ID really is absent -- stop looking for a
    lifetime bug. A mixed distribution (some ``none``, some ``disabled``) proves
    the lookup is unstable and the cause is Krita-side state, not the candidate
    list. Returns the raw counts so the caller can assert on them.
    """
    if app is None:
        app = Krita.instance()

    report: Dict[str, Dict[str, int]] = {}
    for act_id in candidate_ids:
        counts: Dict[str, int] = {}
        for _ in range(samples):
            try:
                action = app.action(act_id)
            except Exception as exc:  # noqa: BLE001 - diagnosis must not raise
                key = f"raised:{type(exc).__name__}"
            else:
                if action is None:
                    key = "none"
                elif not action:
                    key = "falsy_wrapper"
                elif not action_is_enabled(action):
                    key = "disabled"
                else:
                    key = "enabled"
            counts[key] = counts.get(key, 0) + 1
        report[act_id] = counts
        summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        verdict = "UNSTABLE" if len(counts) > 1 else "stable"
        log_warning("sync", f"[{label}] {act_id!r} x{samples}: {summary} ({verdict})")

    return report


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
        # A bare "not found; tried [...]" cannot tell a genuinely absent ID from
        # one that resolved moments ago. Probe each candidate so the log records
        # which it was -- this is the whole diagnosis for the alternation seen in
        # the wild (layer_merge_down reporting "is disabled" one run and "not
        # found" the next). Only reached on the failure path, so the extra
        # lookups cost nothing when the action is present.
        for act_id, verdict in probe_action_ids(app, candidate_ids):
            log_warning("sync", f"  {label}: candidate {act_id!r} {verdict}")
        log_warning("sync", f"'{label}' not found; tried {list(candidate_ids)}")
        return False
    # Pin the wrapper so PyQt5 cannot destroy the C++ object out from under a
    # later re-resolve. See utils.keep_action_alive.
    keep_action_alive(action)
    log_info("sync", f"'{label}' resolved: {describe_action(action)}")
    if not action:
        # resolve_action deliberately accepts a falsy non-None result (a truthy
        # test would skip a genuine action). But a live PyQt5 QAction is ALWAYS
        # truthy, so a falsy one means the wrapper's C++ object was destroyed.
        # Say so here rather than letting it fail later with an opaque
        # AttributeError from trigger().
        log_warning(
            "sync",
            f"'{label}' resolved to a FALSY object ({action!r}); PyQt5 QActions are always "
            "truthy, so the underlying C++ object is likely already destroyed",
        )
    if not action_is_enabled(action):
        log_warning("sync", f"'{label}' is disabled in the current context; trigger() would be a no-op")
        return False
    try:
        action.trigger()
    except Exception as e:
        log_error("sync", f"'{label}' failed to trigger", e)
        return False
    return settle_until(is_done, doc=doc, timeout_ms=timeout_ms)
