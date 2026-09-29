import pytest
from fakes import Action, App, Doc, Node

from krita_pie_menu import sync


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Keep the settle loop from actually sleeping between polls."""
    monkeypatch.setattr(sync.time, "sleep", lambda _s: None)


@pytest.fixture(autouse=True)
def captured_logs(monkeypatch):
    logged = {"warning": [], "error": []}
    monkeypatch.setattr(sync, "log_warning", lambda mod, msg: logged["warning"].append(msg))
    monkeypatch.setattr(sync, "log_error", lambda mod, msg, *a: logged["error"].append(msg))
    return logged


# ── pump_events ──────────────────────────────────────────────────────────────


def test_pump_events_without_doc():
    assert sync.pump_events() is None


def test_pump_events_waits_for_document():
    doc = Doc(Node("ink"))
    sync.pump_events(doc)
    assert doc.done_waits == 1


# ── settle_until ─────────────────────────────────────────────────────────────


def test_settle_until_returns_true_immediately():
    assert sync.settle_until(lambda: True, timeout_ms=5000) is True


def test_settle_until_returns_true_once_predicate_flips():
    state = {"n": 0}

    def _ready():
        state["n"] += 1
        return state["n"] > 3

    assert sync.settle_until(_ready, timeout_ms=5000) is True
    assert state["n"] == 4


def test_settle_until_times_out_and_reports_false():
    assert sync.settle_until(lambda: False, timeout_ms=0) is False


def test_settle_until_passes_document_to_wait_for_done():
    doc = Doc(Node("ink"))
    assert sync.settle_until(lambda: True, doc=doc, timeout_ms=5000) is True
    assert doc.done_waits >= 1


# ── action_is_enabled ────────────────────────────────────────────────────────


def test_action_is_enabled_none_is_false():
    assert sync.action_is_enabled(None) is False


def test_action_is_enabled_reads_qaction_flag():
    assert sync.action_is_enabled(Action(enabled=True)) is True
    assert sync.action_is_enabled(Action(enabled=False)) is False


def test_action_is_enabled_without_isEnabled_attribute():
    class _Bare:
        pass

    assert sync.action_is_enabled(_Bare()) is True


def test_action_is_enabled_swallows_exception():
    class _Boom:
        def isEnabled(self):
            raise RuntimeError("no qaction")

    assert sync.action_is_enabled(_Boom()) is True


# ── trigger_action_verified ──────────────────────────────────────────────────


def test_trigger_action_verified_missing_action(captured_logs):
    app = App(None, actions={})
    assert sync.trigger_action_verified(app, ["nope"], lambda: True, label="merge") is False
    assert captured_logs["warning"]


def test_trigger_action_verified_disabled_action_is_never_triggered(captured_logs):
    """The core silent no-op: a disabled QAction must not be triggered at all."""
    merge = Action(enabled=False)
    app = App(None, actions={"layer_merge_down": merge})

    ok = sync.trigger_action_verified(app, ["layer_merge_down"], lambda: True, label="merge")

    assert ok is False
    assert merge.triggered == 0
    assert captured_logs["warning"]


def test_trigger_action_verified_success_when_postcondition_holds():
    merge = Action(on_trigger=lambda: None)
    app = App(None, actions={"layer_merge_down": merge})

    ok = sync.trigger_action_verified(app, ["layer_merge_down"], lambda: True, label="merge")

    assert ok is True
    assert merge.triggered == 1


def test_trigger_action_verified_fails_when_postcondition_never_holds(captured_logs):
    merge = Action()
    app = App(None, actions={"layer_merge_down": merge})

    ok = sync.trigger_action_verified(
        app, ["layer_merge_down"], lambda: False, doc=None, timeout_ms=0, label="merge"
    )

    assert ok is False
    assert merge.triggered == 1, "the action ran but the expected change never appeared"


def test_trigger_action_verified_trigger_exception_is_logged(captured_logs):
    class _Boom(Action):
        def trigger(self):
            raise RuntimeError("kaboom")

    merge = _Boom()
    app = App(None, actions={"layer_merge_down": merge})

    ok = sync.trigger_action_verified(app, ["layer_merge_down"], lambda: True, label="merge")

    assert ok is False
    assert captured_logs["error"]


def test_trigger_action_verified_passes_document_along():
    doc = Doc(Node("ink"))
    merge = Action(on_trigger=lambda: None)
    app = App(doc, actions={"layer_merge_down": merge})

    assert sync.trigger_action_verified(app, ["layer_merge_down"], lambda: True, doc=doc, label="m")
    assert doc.done_waits >= 1


def test_trigger_action_verified_falls_back_through_candidate_ids():
    first, second = Action(), Action()
    app = App(None, actions={"merge_layer_down": first, "layer_merge_down": second})

    ok = sync.trigger_action_verified(
        app, ["layer_merge_down", "merge_layer_down"], lambda: True, label="merge"
    )

    assert ok is True
    assert second.triggered == 1
    assert first.triggered == 0
