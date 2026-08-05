import pytest

from krita_pie_menu import SECTOR_CODES, SECTOR_NAMES
from krita_pie_menu.pie_widget import PieMenuWidget
from krita_pie_menu.toast_notification import ToastNotification

WARNING_TOAST = "warning"
INFO_TOAST = "info"


@pytest.fixture
def toast_recorder(monkeypatch):
    calls = []

    def record(message, parent=None, duration_ms=2500, toast_type="warning"):
        calls.append((message, toast_type))

    monkeypatch.setattr(ToastNotification, "show_toast", staticmethod(record))
    return calls


def make_widget(callbacks=None):
    return PieMenuWidget(
        callbacks or {},
        items_meta={code: (code, f"action_{code}") for code in SECTOR_CODES},
    )


@pytest.fixture
def qt_super(monkeypatch):
    """Give the shared stub QWidget no-op event handlers so super() calls run."""
    from krita_pie_menu import pie_widget

    for name in (
        "paintEvent",
        "mouseMoveEvent",
        "keyPressEvent",
        "keyReleaseEvent",
        "mousePressEvent",
    ):
        monkeypatch.setattr(pie_widget.QWidget, name, lambda self, ev: None)


def test_sector_codes_canonical_order():
    assert SECTOR_CODES == ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def test_sector_names_derived_from_codes():
    assert len(SECTOR_NAMES) == len(SECTOR_CODES)
    assert SECTOR_NAMES[0][0] == "N"
    assert [code for code, _ in SECTOR_NAMES] == list(SECTOR_CODES)


def test_execute_sector_enabled_invokes_callback(toast_recorder):
    widget = make_widget()
    invoked = []

    def callback():
        invoked.append(1)

    widget._execute_sector("E", callback)

    assert invoked == [1]
    assert len(toast_recorder) == 1
    message, toast_type = toast_recorder[0]
    assert toast_type == INFO_TOAST
    assert "Triggered" in message


def test_execute_sector_disabled_skips_callback(toast_recorder):
    widget = make_widget()
    widget.sector_states["E"] = (False, "No active document.")
    invoked = []

    widget._execute_sector("E", lambda: invoked.append(1))

    assert invoked == []
    assert len(toast_recorder) == 1
    message, toast_type = toast_recorder[0]
    assert toast_type == WARNING_TOAST
    assert "No active document." in message


def test_execute_sector_disabled_without_reason(toast_recorder):
    widget = make_widget()
    widget.sector_states["E"] = (False, "")
    widget._execute_sector("E", None)

    assert len(toast_recorder) == 1
    message, toast_type = toast_recorder[0]
    assert toast_type == WARNING_TOAST
    assert "disabled" in message


def test_execute_sector_false_result_suppresses_success_toast(toast_recorder):
    widget = make_widget()

    widget._execute_sector("E", lambda: False)

    assert len(toast_recorder) == 1
    message, toast_type = toast_recorder[0]
    assert toast_type == WARNING_TOAST
    assert "could not be executed" in message


def test_execute_sector_none_callback_cleanly_closes(toast_recorder):
    widget = make_widget()

    widget._execute_sector("NW", None)

    assert len(toast_recorder) == 1
    assert toast_recorder[0][1] == INFO_TOAST


def test_sector_states_default_to_enabled():
    widget = make_widget()
    for code in SECTOR_CODES:
        assert widget.sector_states[code] == (True, "")


def test_validator_reason_surfaced_in_sector_states():
    widget = PieMenuWidget(
        {},
        validators={"N": lambda: (False, "Unavailable here.")},
    )
    assert widget.sector_states["N"] == (False, "Unavailable here.")


def test_validator_bool_result_uses_default_reason():
    widget = PieMenuWidget({}, validators={"N": lambda: False})
    assert widget.sector_states["N"] == (False, "Action not available in current context.")
    widget2 = PieMenuWidget({}, validators={"N": lambda: True})
    assert widget2.sector_states["N"] == (True, "Action not available in current context.")


def test_validator_exception_surfaces_error_reason():
    def boom():
        raise RuntimeError("doc gone")

    widget = PieMenuWidget({}, validators={"N": boom})
    is_enabled, reason = widget.sector_states["N"]
    assert is_enabled is False
    assert "Action error" in reason and "doc gone" in reason


def test_init_ui_toggle_buttons_created():
    widget = PieMenuWidget(
        {},
        items_meta={code: (code, f"action_{code}") for code in SECTOR_CODES},
        toggle_states={"N": True, "W": False},
    )
    assert set(widget.buttons) == set(SECTOR_CODES)
    assert widget.buttons["N"] is not None


def test_make_click_handler_invokes_sector_execution(toast_recorder):
    widget = make_widget()
    invoked = []

    def callback():
        invoked.append(1)

    handler = widget.make_click_handler("S", callback)
    handler()

    assert invoked == [1]
    assert toast_recorder and toast_recorder[0][1] == INFO_TOAST


def test_show_at_cursor_refreshes_toggle_properties(monkeypatch):
    from krita_pie_menu import pie_widget

    widget = PieMenuWidget(
        {},
        items_meta={code: (code, f"action_{code}") for code in SECTOR_CODES},
        toggle_states={"N": True, "W": False},
    )
    monkeypatch.setattr(pie_widget.QCursor, "pos", staticmethod(lambda: type("P", (), {"x": lambda s: 0, "y": lambda s: 0})()))
    widget.show_at_cursor()
    assert widget.origin_pos is not None


def test_paint_event_center_zone(qt_super):
    widget = make_widget()
    widget.active_direction = None
    widget.paintEvent(None)


def test_paint_event_active_direction(qt_super):
    widget = make_widget()
    widget.sector_states["N"] = (True, "")
    widget.active_direction = "N"
    widget.paintEvent(None)
    widget.sector_states["N"] = (False, "blocked")
    widget.paintEvent(None)


def test_paint_event_toggle_underscore(qt_super):
    widget = PieMenuWidget(
        {},
        items_meta={code: (code, f"action_{code}") for code in SECTOR_CODES},
        toggle_states={"N": True, "W": False},
    )
    widget.paintEvent(None)


def test_mouse_move_event_repaints(qt_super, monkeypatch):
    from krita_pie_menu import pie_widget

    widget = make_widget()
    widget.origin_pos = type("P", (), {"x": lambda s: 100, "y": lambda s: 100})()
    monkeypatch.setattr(pie_widget.QCursor, "pos", staticmethod(lambda: type("P", (), {"x": lambda s: 100, "y": lambda s: 100})()))

    class _Ev:
        def key(self):
            return 0

    widget.mouseMoveEvent(_Ev())
    assert widget.active_direction is None


def test_trigger_selected_action_executes_sector(toast_recorder, monkeypatch):
    widget = make_widget()
    invoked = []
    widget.callbacks["E"] = lambda: invoked.append(1)
    widget.active_direction = "E"
    monkeypatch.setattr(widget, "update_selection_from_mouse", lambda: None)
    widget.trigger_selected_action()
    assert invoked == [1]


def test_trigger_selected_action_no_direction_closes(monkeypatch):
    widget = make_widget()
    closed = []
    monkeypatch.setattr(widget, "cleanup_and_close", lambda: closed.append(1))
    monkeypatch.setattr(widget, "update_selection_from_mouse", lambda: None)
    widget.active_direction = None
    widget.trigger_selected_action()
    assert closed == [1]


def test_cleanup_and_close_swallows_release_keyboard_error(monkeypatch):
    widget = make_widget()
    monkeypatch.setattr(widget, "releaseKeyboard", lambda: (_ for _ in ()).throw(RuntimeError("grab gone")))
    closed = []
    monkeypatch.setattr(widget, "close", lambda: closed.append(1))
    widget.cleanup_and_close()
    assert widget.is_interrupted is False
    assert closed == [1]
