
from conditions_pie_menu.conditions_pie_menu import ConditionsPieMenuExtension
from krita_pie_menu import SECTOR_CODES


def _make_ext(tmp_path, monkeypatch):
    ext = ConditionsPieMenuExtension(parent=None)
    monkeypatch.setattr(ext, "config_path", str(tmp_path / "config.json"))
    return ext


def test_toggle_condition_flips_and_persists(tmp_path, monkeypatch):
    ext = _make_ext(tmp_path, monkeypatch)

    assert ext.toggle_condition("duplicate_reflay") is True
    assert ext.get_condition("duplicate_reflay") is True
    assert ext.toggle_condition("duplicate_reflay") is False
    assert ext.get_condition("duplicate_reflay") is False


def test_get_condition_defaults_false(tmp_path, monkeypatch):
    ext = _make_ext(tmp_path, monkeypatch)
    assert ext.get_condition("missing_flag") is False
    assert ext.get_condition("missing_flag", default=True) is True


def test_build_pie_config_toggle_states_from_config(tmp_path, monkeypatch):
    ext = _make_ext(tmp_path, monkeypatch)
    ext.toggle_condition("duplicate_reflay")  # -> True

    callbacks, items_meta, validators, toggle_states = ext.build_pie_config()

    assert set(callbacks) == set(SECTOR_CODES)
    assert set(items_meta) == set(SECTOR_CODES)

    # Validators cover only the 6 stub sectors; the NE/W toggles are always live.
    assert set(validators) == set(SECTOR_CODES) - {"NE", "W"}

    assert toggle_states["NE"] is True
    assert toggle_states["W"] is False

    for code in ("N", "E", "SE", "S", "SW", "NW"):
        ok, reason = validators[code]()
        assert ok is False
        assert reason


def test_toggle_callbacks_flip_states(tmp_path, monkeypatch):
    from krita_pie_menu.toast_notification import ToastNotification

    ext = _make_ext(tmp_path, monkeypatch)
    toasts = []
    monkeypatch.setattr(
        ToastNotification,
        "show_toast",
        staticmethod(lambda message, parent=None, duration_ms=2500, toast_type="warning": toasts.append(message)),
    )

    callbacks, _, _, _ = ext.build_pie_config()

    callbacks["NE"]()
    assert ext.get_condition("duplicate_reflay") is True
    assert toasts[-1].startswith("Duplicate RefLay: ON")

    callbacks["W"]()
    assert ext.get_condition("keep_aspect_ratio") is True
    assert toasts[-1].startswith("Keep Aspect Ratio")


def test_stub_callbacks_toast_not_crash(tmp_path, monkeypatch):
    from krita_pie_menu.toast_notification import ToastNotification

    ext = _make_ext(tmp_path, monkeypatch)
    toasts = []
    monkeypatch.setattr(
        ToastNotification,
        "show_toast",
        staticmethod(lambda message, parent=None, duration_ms=2500, toast_type="warning": toasts.append(message)),
    )

    callbacks, _, _, _ = ext.build_pie_config()
    callbacks["N"]()
    assert any("stub" in msg.lower() for msg in toasts)
