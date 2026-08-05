import pytest
from PyQt5.QtCore import Qt

from krita_pie_menu.pie_widget import PieMenuWidget


class _Pt:
    def __init__(self, x, y):
        self._x = x
        self._y = y

    def x(self):
        return self._x

    def y(self):
        return self._y


class _Event:
    def __init__(self, key, auto_repeat=False, button=None):
        self._key = key
        self._auto = auto_repeat
        self._button = button
        self.ignored = False

    def key(self):
        return self._key

    def button(self):
        return self._button

    def isAutoRepeat(self):
        return self._auto

    def ignore(self):
        self.ignored = True


@pytest.fixture
def qt_enums(monkeypatch):
    """Bind stable sentinels for Qt enum members so identity-based `in` checks work."""
    sentinels = {}
    for name in (
        "Key_Space",
        "Key_Tab",
        "Key_Control",
        "Key_Alt",
        "Key_Return",
        "Key_Enter",
        "Key_F11",
        "Key_Escape",
        "RightButton",
        "LeftButton",
    ):
        sentinel = object()
        sentinels[name] = sentinel
        monkeypatch.setattr(Qt, name, sentinel)
    return sentinels


@pytest.fixture
def widget():
    return PieMenuWidget({})


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


def test_interrupt_hides_invisibly_not_with_hide(widget, monkeypatch):
    # AGENTS.md §9.2: interrupt must NOT call hide()/releaseKeyboard();
    # it must go transparent + offscreen while keeping the key grab.
    hidden = []
    moved = []
    opacity_calls = []
    monkeypatch.setattr(widget, "hide", lambda: hidden.append(1))
    monkeypatch.setattr(widget, "move", lambda x, y: moved.append((x, y)))
    monkeypatch.setattr(widget, "setWindowOpacity", lambda v: opacity_calls.append(v))

    widget.active_direction = "E"
    widget.interrupt_and_wait_for_release()
    widget.interrupt_and_wait_for_release()  # idempotent

    assert widget.is_interrupted is True
    assert widget.active_direction is None
    assert hidden == []  # never hide()
    assert opacity_calls == [0.0]
    assert moved == [(-10000, -10000)]


def test_keypress_f11_esc_interrupts(widget, qt_enums, monkeypatch):
    interrupted = []
    monkeypatch.setattr(widget, "interrupt_and_wait_for_release", lambda: interrupted.append(1))
    widget.keyPressEvent(_Event(qt_enums["Key_F11"]))
    widget.keyPressEvent(_Event(qt_enums["Key_Escape"]))
    assert len(interrupted) == 2


def test_autorepeat_ignored(widget, qt_enums, monkeypatch):
    triggered = []
    closed = []
    monkeypatch.setattr(widget, "trigger_selected_action", lambda: triggered.append(1))
    monkeypatch.setattr(widget, "cleanup_and_close", lambda: closed.append(1))

    ev = _Event(qt_enums["Key_Space"], auto_repeat=True)
    widget.keyReleaseEvent(ev)
    assert ev.ignored is True
    assert triggered == []
    assert closed == []


def test_interrupted_release_of_interrupt_key_does_not_close(widget, qt_enums, monkeypatch):
    # AGENTS.md §9.3: releasing F11/Esc during an interrupt must NOT close.
    widget.is_interrupted = True
    closed = []
    monkeypatch.setattr(widget, "cleanup_and_close", lambda: closed.append(1))

    widget.keyReleaseEvent(_Event(qt_enums["Key_F11"]))
    widget.keyReleaseEvent(_Event(qt_enums["Key_Escape"]))
    assert closed == []


@pytest.mark.parametrize("trigger", ["Key_Space", "Key_Tab", "Key_Control", "Key_Alt", "Key_Return", "Key_Enter"])
def test_interrupted_release_of_trigger_key_closes(widget, qt_enums, monkeypatch, trigger):
    widget.is_interrupted = True
    closed = []
    monkeypatch.setattr(widget, "cleanup_and_close", lambda: closed.append(1))

    widget.keyReleaseEvent(_Event(qt_enums[trigger]))
    assert closed == [1]


def test_release_trigger_key_triggers_action_when_not_interrupted(widget, qt_enums, monkeypatch):
    triggered = []
    monkeypatch.setattr(widget, "trigger_selected_action", lambda: triggered.append(1))
    widget.keyReleaseEvent(_Event(qt_enums["Key_Space"]))
    assert triggered == [1]


def test_mouse_right_click_interrupts(widget, qt_enums, monkeypatch):
    interrupted = []
    monkeypatch.setattr(widget, "interrupt_and_wait_for_release", lambda: interrupted.append(1))

    ev = _Event(qt_enums["RightButton"], button=qt_enums["RightButton"])
    widget.mousePressEvent(ev)
    assert interrupted == [1]


def test_mouse_left_click_in_deadzone_interrupts(widget, qt_enums, monkeypatch):
    interrupted = []
    monkeypatch.setattr(widget, "interrupt_and_wait_for_release", lambda: interrupted.append(1))

    widget.active_direction = None
    widget.mousePressEvent(_Event(None, button=qt_enums["LeftButton"]))
    assert interrupted == [1]


def test_mouse_left_click_with_direction_forwards_to_base(qt_super, qt_enums, monkeypatch):
    widget = PieMenuWidget({})
    widget.active_direction = "N"
    widget.mousePressEvent(_Event(None, button=qt_enums["LeftButton"]))
    assert widget.is_interrupted is False


def test_mouse_other_button_forwards_to_base(qt_super, qt_enums, monkeypatch):
    widget = PieMenuWidget({})
    widget.mousePressEvent(_Event(None, button=object()))
    assert widget.is_interrupted is False


def test_keypress_autorepeat_ignored(qt_super, qt_enums, monkeypatch):
    widget = PieMenuWidget({})
    ev = _Event(qt_enums["Key_Space"], auto_repeat=True)
    widget.keyPressEvent(ev)
    assert ev.ignored is True


def test_keypress_other_key_forwards_to_base(qt_super, qt_enums, monkeypatch):
    widget = PieMenuWidget({})
    widget.keyPressEvent(_Event(999))
    assert widget.is_interrupted is False


def test_keyrelease_other_key_forwards_to_base(qt_super, qt_enums, monkeypatch):
    widget = PieMenuWidget({})
    ev = _Event(999)
    widget.keyReleaseEvent(ev)
    assert widget.is_interrupted is False


def test_show_at_cursor_restores_opacity_and_flags(widget, monkeypatch):
    # §9.2 step 1: opacity must be restored and interrupt flag cleared on show.
    opacity_calls = []
    monkeypatch.setattr(widget, "setWindowOpacity", lambda v: opacity_calls.append(v))

    widget.is_interrupted = True
    widget.show_at_cursor()

    assert widget.is_interrupted is False
    assert widget.active_direction is None
    assert opacity_calls == [1.0]


def test_update_selection_from_mouse_deadzone(monkeypatch):
    from krita_pie_menu import pie_widget

    widget = PieMenuWidget({})
    widget.origin_pos = _Pt(100, 100)

    def fake_pos():
        return _Pt(120, 100)  # 20px from origin -> inside deadzone (45)

    monkeypatch.setattr(pie_widget.QCursor, "pos", staticmethod(fake_pos))
    widget.active_direction = "E"
    widget.update_selection_from_mouse()
    assert widget.active_direction is None


def test_update_selection_from_mouse_sector_change(monkeypatch):
    from krita_pie_menu import pie_widget

    widget = PieMenuWidget({})
    widget.origin_pos = _Pt(100, 100)

    def fake_pos():
        return _Pt(100, 160)  # 60px down -> S sector

    monkeypatch.setattr(pie_widget.QCursor, "pos", staticmethod(fake_pos))
    widget.active_direction = "E"
    widget.update_selection_from_mouse()
    assert widget.active_direction == "S"


def test_update_selection_from_mouse_uses_cursor_fallback_origin(monkeypatch):
    from krita_pie_menu import pie_widget

    widget = PieMenuWidget({})
    widget.origin_pos = None

    def fake_global(x, y):
        return _Pt(x, y)

    def fake_pos():
        return _Pt(245, 245)  # ~21px from (260,260) -> inside 45px deadzone

    monkeypatch.setattr(pie_widget.QCursor, "pos", staticmethod(fake_pos))
    monkeypatch.setattr(widget, "mapToGlobal", lambda point: fake_global(260, 260))
    widget.update_selection_from_mouse()
    assert widget.active_direction is None
