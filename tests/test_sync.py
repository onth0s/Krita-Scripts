import pytest
from fakes import Action, App, Doc, Node

from krita_pie_menu import sync


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Keep the settle loop from actually sleeping between polls."""
    monkeypatch.setattr(sync.time, "sleep", lambda _s: None)


@pytest.fixture(autouse=True)
def captured_logs(monkeypatch):
    logged = {"info": [], "warning": [], "error": []}
    monkeypatch.setattr(sync, "log_info", lambda mod, msg: logged["info"].append(msg))
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


# ── diagnosability of the "not found" alternation ─────────────────────────────
#
# In the wild, `layer_merge_down` reported "is disabled" on one run and "not
# found" on the next, inside the same second. A bare "not found; tried [...]"
# cannot say whether the ID is genuinely absent or the lookup returned a dead
# wrapper, so these tests pin the per-candidate diagnosis that resolves it.


def test_missing_action_probes_every_candidate(captured_logs):
    app = App(None, actions={})

    assert sync.trigger_action_verified(
        app, ["layer_merge_down", "merge_layer_down"], lambda: True, label="merge"
    ) is False

    joined = "\n".join(captured_logs["warning"])
    assert "layer_merge_down" in joined
    assert "returned None (ID absent from the registry)" in joined
    assert "not found; tried" in joined


def test_missing_action_reports_a_falsy_wrapper_distinctly(captured_logs):
    """
    A live PyQt5 QAction is always truthy, so a falsy resolution means the C++
    wrapper's object was destroyed. That must be named at the point of
    resolution, not surface later as an opaque AttributeError from trigger().
    """
    class _Dead:
        def __bool__(self):
            return False

    class _DeadApp:
        def action(self, act_id):
            return _Dead()

    assert sync.trigger_action_verified(_DeadApp(), ["x"], lambda: True, label="merge") is False
    assert any("resolved to a FALSY object" in m for m in captured_logs["warning"])


def test_resolved_action_identity_is_logged(captured_logs):
    merge = Action()
    merge.objectName = lambda: "layer_merge_down"
    app = App(None, actions={"layer_merge_down": merge})

    sync.trigger_action_verified(app, ["layer_merge_down"], lambda: True, label="merge")

    assert any("resolved:" in m and "layer_merge_down" in m for m in captured_logs["info"])


def test_resolved_action_is_pinned_against_collection():
    """PyQt5 deletes an unparented QAction's C++ object when the wrapper is collected."""
    import gc

    merge = Action(on_trigger=lambda: None)
    app = App(None, actions={"layer_merge_down": merge})

    assert sync.trigger_action_verified(app, ["layer_merge_down"], lambda: True, label="m") is True

    from krita_pie_menu import utils

    assert utils._ACTION_KEEPALIVE.get(id(merge)) is merge
    del merge
    gc.collect()
    assert app.actions["layer_merge_down"] is not None


# ── diagnose_action_ids: one-shot proof of intermittency ──────────────────────


def test_diagnose_reports_a_uniformly_absent_id_as_stable(captured_logs):
    app = App(None, actions={})

    report = sync.diagnose_action_ids(app, ["nope"], samples=5)

    assert report == {"nope": {"none": 5}}
    assert any("(stable)" in m for m in captured_logs["warning"])
    assert "UNSTABLE" not in "\n".join(captured_logs["warning"])


def test_diagnose_reports_a_mixed_distribution_as_unstable(captured_logs):
    """
    The decisive test for the layer_merge_down anomaly: a genuinely intermittent
    lookup shows up as a mixed distribution, which a one-shot probe could never
    distinguish from a permanently absent ID.
    """
    calls = {"n": 0}

    class _FlakyApp:
        def action(self, act_id):
            calls["n"] += 1
            return None if calls["n"] % 2 else Action(enabled=False)

    report = sync.diagnose_action_ids(_FlakyApp(), ["layer_merge_down"], samples=4)

    assert report == {"layer_merge_down": {"none": 2, "disabled": 2}}
    assert any("UNSTABLE" in m for m in captured_logs["warning"])


def test_diagnose_distinguishes_enabled_disabled_none_and_falsy(captured_logs):
    class _Dead:
        def __bool__(self):
            return False

    class _MixedApp:
        def action(self, act_id):
            return {
                "on": Action(enabled=True),
                "off": Action(enabled=False),
                "gone": None,
                "dead": _Dead(),
            }[act_id]

    report = sync.diagnose_action_ids(_MixedApp(), ["on", "off", "gone", "dead"], samples=1)

    assert report == {
        "on": {"enabled": 1},
        "off": {"disabled": 1},
        "gone": {"none": 1},
        "dead": {"falsy_wrapper": 1},
    }


def test_diagnose_survives_a_raising_lookup(captured_logs):
    class _BoomApp:
        def action(self, act_id):
            raise RuntimeError("registry gone")

    report = sync.diagnose_action_ids(_BoomApp(), ["x"], samples=2)

    assert report == {"x": {"raised:RuntimeError": 2}}


def test_diagnose_falls_back_to_krita_instance(monkeypatch, captured_logs):
    class _Inst:
        def action(self, act_id):
            return None

    monkeypatch.setattr(sync.Krita, "instance", staticmethod(lambda: _Inst()))
    assert sync.diagnose_action_ids(None, ["x"], samples=1) == {"x": {"none": 1}}
