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
