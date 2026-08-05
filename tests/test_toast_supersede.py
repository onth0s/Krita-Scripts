import pytest

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


def test_show_toast_no_parent_geometry_path():
    # Without a parent, show_toast falls back to QApplication.instance() path;
    # the stub must let it run without raising.
    ToastNotification.show_toast("noparent", toast_type="info")
    assert ToastNotification._active_toast is not None


def test_fade_out_never_raises_after_close():
    ToastNotification.show_toast("fade", toast_type="info")
    toast = ToastNotification._active_toast
    toast.close()
    toast.fade_out()  # superseded/closed toast: timer may fire late, must not raise


def test_get_left_dockers_offset_headless():
    # Outside Krita there is no active window, so the offset must be 0.
    assert ToastNotification.get_left_dockers_offset() == 0
