import pytest

from krita_pie_menu import toast_notification as tn
from krita_pie_menu.toast_notification import ToastNotification


@pytest.fixture(autouse=True)
def reset_active_toast():
    ToastNotification._active_toast = None
    yield
    ToastNotification._active_toast = None


def test_show_toast_sets_active():
    ToastNotification.show_toast("first", toast_type="info")
    assert ToastNotification._active_toast is not None
    assert ToastNotification._active_toast.label is not None


def test_show_toast_accent_colors(monkeypatch):
    seen = []
    monkeypatch.setattr(tn, "QColor", lambda *args: seen.append(args))
    for ttype in ("success", "info", "warning"):
        ToastNotification.show_toast("x", toast_type=ttype)
    accents = [args[0] for args in seen if len(args) == 1]
    assert accents == ["#48BB78", "#4299E1", "#ECC94B"]


def test_paint_event_runs_on_stubs():
    # Stub QPainter/QPainterPath flow must run to completion headlessly.
    ToastNotification.show_toast("paint")
    toast = ToastNotification._active_toast
    toast.paintEvent(None)


def test_show_toast_supersedes_previous(monkeypatch):
    ToastNotification.show_toast("first", toast_type="info")
    first = ToastNotification._active_toast

    calls = []
    monkeypatch.setattr(first, "close", lambda: calls.append("close"))
    monkeypatch.setattr(first._fade_timer, "stop", lambda: calls.append("stop"))

    ToastNotification.show_toast("second", toast_type="warning")

    # Supersede must cancel the old toast's pending fade timer BEFORE closing it,
    # otherwise the dead C++ widget's timer fires later (H4).
    assert calls == ["stop", "close"]
    assert ToastNotification._active_toast is not first


def test_show_toast_double_fires_without_crash():
    # Two toasts fired quickly (< duration_ms) must not raise.
    ToastNotification.show_toast("first", duration_ms=2500, toast_type="info")
    ToastNotification.show_toast("second", duration_ms=2500, toast_type="info")
    assert ToastNotification._active_toast is not None


def test_show_toast_supersede_stop_error_swallowed(monkeypatch):
    ToastNotification.show_toast("first", toast_type="info")
    first = ToastNotification._active_toast
    calls = []
    monkeypatch.setattr(
        first._fade_timer, "stop", lambda: (_ for _ in ()).throw(RuntimeError("timer dead"))
    )
    monkeypatch.setattr(first, "close", lambda: calls.append("close"))

    ToastNotification.show_toast("second", toast_type="warning")

    assert calls == ["close"]


def test_show_toast_supersede_close_error_swallowed(monkeypatch):
    ToastNotification.show_toast("first", toast_type="info")
    first = ToastNotification._active_toast
    monkeypatch.setattr(first._fade_timer, "stop", lambda: None)
    monkeypatch.setattr(first, "close", lambda: (_ for _ in ()).throw(RuntimeError("deleted")))

    ToastNotification.show_toast("second", toast_type="warning")

    assert ToastNotification._active_toast is not first


def test_show_toast_uses_parent_geometry(monkeypatch):
    calls = []

    class _Geo:
        def x(self):
            return 50

        def y(self):
            return 100

        def height(self):
            return 700

    class _Parent:
        def geometry(self):
            calls.append("geometry")
            return _Geo()

    monkeypatch.setattr(ToastNotification, "get_left_dockers_offset", classmethod(lambda cls: 0))
    ToastNotification.show_toast("parent", parent=_Parent(), toast_type="info")

    assert calls == ["geometry"]
    assert ToastNotification._active_toast is not None


def test_show_toast_uses_active_window_geometry(monkeypatch):
    import sys

    class _Geo:
        def x(self):
            return 60

        def y(self):
            return 120

        def height(self):
            return 750

    class _Win:
        def geometry(self):
            return _Geo()

    class _AppInst:
        def activeWindow(self):
            return _Win()

    class _FakeQApplication:
        @staticmethod
        def instance():
            return _AppInst()

    monkeypatch.setattr(sys.modules["PyQt5.QtWidgets"], "QApplication", _FakeQApplication)
    ToastNotification.show_toast("activewin", toast_type="info")

    assert ToastNotification._active_toast is not None


def test_show_toast_no_parent_geometry_path():
    # Without a parent, show_toast falls back to QApplication.instance() path;
    # the stub must let it run without raising.
    ToastNotification.show_toast("noparent", toast_type="info")
    assert ToastNotification._active_toast is not None


def test_fade_in_starts_timer(monkeypatch):
    ToastNotification.show_toast("fadein", toast_type="info")
    toast = ToastNotification._active_toast
    calls = []
    monkeypatch.setattr(toast._fade_timer, "start", lambda *a: calls.append(a))
    toast.fade_in()
    assert calls


def test_fade_out_never_raises_after_close():
    ToastNotification.show_toast("fade", toast_type="info")
    toast = ToastNotification._active_toast
    toast.close()
    toast.fade_out()  # superseded/closed toast: timer may fire late, must not raise


def test_fade_out_superseded_runtime_error(monkeypatch):
    ToastNotification.show_toast("fade", toast_type="info")
    toast = ToastNotification._active_toast

    class _Raise:
        def __init__(self, *a, **k):
            raise RuntimeError("C++ object deleted")

    monkeypatch.setattr(tn, "QPropertyAnimation", _Raise)
    toast.fade_out()  # must swallow the RuntimeError


def test_get_left_dockers_offset_headless():
    # Outside Krita there is no active window, so the offset must be 0.
    assert ToastNotification.get_left_dockers_offset() == 0


def test_get_left_dockers_offset_active_window_no_qwindow(monkeypatch):
    class _Win:
        def qwindow(self):
            return None

    class _App:
        def activeWindow(self):
            return _Win()

    class _FakeKrita:
        instance = staticmethod(lambda: _App())

    monkeypatch.setattr("krita.Krita", _FakeKrita)
    assert ToastNotification.get_left_dockers_offset() == 0


def test_get_left_dockers_offset_with_docks(monkeypatch):
    sentinel = object()

    class _FakeQt:
        LeftDockWidgetArea = sentinel

    monkeypatch.setattr(tn, "Qt", _FakeQt)

    class _Geo:
        def x(self):
            return 100

        def width(self):
            return 300

    class _Dock:
        def isVisible(self):
            return True

        def isFloating(self):
            return False

        def geometry(self):
            return _Geo()

    class _Main:
        def findChildren(self, cls):
            return [_Dock(), _Dock()]

        def dockWidgetArea(self, dock):
            return sentinel

    class _QWin:
        def findChild(self, cls):
            return _Main()

        def parent(self):
            return None

    class _Win:
        def qwindow(self):
            return _QWin()

    class _App:
        def activeWindow(self):
            return _Win()

    class _FakeKrita:
        instance = staticmethod(lambda: _App())

    monkeypatch.setattr("krita.Krita", _FakeKrita)
    assert ToastNotification.get_left_dockers_offset() == 400


def test_get_left_dockers_offset_exception(monkeypatch):
    class _Win:
        def qwindow(self):
            raise RuntimeError("boom")

    class _App:
        def activeWindow(self):
            return _Win()

    class _FakeKrita:
        instance = staticmethod(lambda: _App())

    monkeypatch.setattr("krita.Krita", _FakeKrita)
    assert ToastNotification.get_left_dockers_offset() == 0


def test_get_left_dockers_offset_walks_parent_chain(monkeypatch):
    from PyQt5.QtWidgets import QMainWindow

    class _Wrap:
        def __init__(self, up):
            self._up = up

        def parent(self):
            return self._up

    class _NoChild:
        def findChild(self, cls):
            return None

        def parent(self):
            return _Wrap(QMainWindow())

    class _Win:
        def qwindow(self):
            return _NoChild()

    class _App:
        def activeWindow(self):
            return _Win()

    class _FakeKrita:
        instance = staticmethod(lambda: _App())

    monkeypatch.setattr("krita.Krita", _FakeKrita)
    # The walk must climb parent() to the QMainWindow (no direct findChild hit).
    assert ToastNotification.get_left_dockers_offset() == 0


def test_get_left_dockers_offset_walk_finds_no_main_window(monkeypatch):
    class _NoParent:
        def findChild(self, cls):
            return None

        def parent(self):
            return None

    class _Win:
        def qwindow(self):
            return _NoParent()

    class _App:
        def activeWindow(self):
            return _Win()

    class _FakeKrita:
        instance = staticmethod(lambda: _App())

    monkeypatch.setattr("krita.Krita", _FakeKrita)
    assert ToastNotification.get_left_dockers_offset() == 0
