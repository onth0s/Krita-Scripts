
from krita_pie_menu import SECTOR_CODES
from krita_pie_menu.toast_notification import ToastNotification
from operations_pie_menu.operations_pie_menu import (
    OP_HANDLERS,
    OperationsPieMenuExtension,
    _unassigned_validator,
)


def test_op_handlers_registry_exposes_only_implemented_actions():
    assert set(OP_HANDLERS) == {
        "op_setup_canvas",
        "op_sanitize_group",
        "op_merge_to_black",
        "op_fit_layer",
        "op_bw_preview",
        "op_duplicate_layer",
    }
    for handler in OP_HANDLERS.values():
        assert callable(handler)


def test_unassigned_validator_disables_sector():
    ok, reason = _unassigned_validator()
    assert ok is False
    assert reason


def test_refine_handler_skipped_from_registry():
    assert "op_refine_sketch" not in OP_HANDLERS


def test_build_pie_config_round_trip():
    ext = OperationsPieMenuExtension(parent=None)
    callbacks, items_meta, validators, toggle_states = ext.build_pie_config()

    assert set(callbacks) == set(SECTOR_CODES)
    assert set(items_meta) == set(SECTOR_CODES)
    assert set(validators) == set(SECTOR_CODES)
    assert set(toggle_states) == set()

    assert items_meta["N"] == ("Refine Sketch", "op_refine_sketch")
    assert items_meta["E"] == ("Stub East", "op_placeholder_east")
    ok, _ = validators["E"]()
    assert ok is False


def test_refine_callback_wired_through_condition(monkeypatch):
    ext = OperationsPieMenuExtension(parent=None)
    calls = []
    monkeypatch.setattr(ext, "_get_duplicate_reflay_condition", lambda: True)

    import operations_pie_menu.operations_pie_menu as opmod

    monkeypatch.setattr(opmod, "execute_refine_sketch", lambda **kw: calls.append(kw))

    callbacks, _, _, _ = ext.build_pie_config()
    callbacks["N"]()
    assert calls == [{"duplicate_reflay": True}]


def test_stub_callback_shows_toast_not_messagebox(monkeypatch):
    ext = OperationsPieMenuExtension(parent=None)
    calls = []

    def record(message, parent=None, duration_ms=2500, toast_type="warning"):
        calls.append(message)

    monkeypatch.setattr(ToastNotification, "show_toast", staticmethod(record))
    ext.execute_stub_action("E", "Stub East", "op_placeholder_east")
    assert calls == ["Stub [E] Stub East"]


def test_create_actions_registers_both_actions():
    import operations_pie_menu.operations_pie_menu as opmod

    class _Signal:
        def __init__(self):
            self.cb = None

        def connect(self, cb):
            self.cb = cb

    class _Action:
        def __init__(self):
            self.triggered = _Signal()

    created = []

    class _Win:
        def createAction(self, aid, text, category):
            created.append((aid, text, category))
            return _Action()

    ext = opmod.OperationsPieMenuExtension(parent=None)
    ext.createActions(_Win())

    assert created == [
        ("trigger_operations_pie_menu", "Operations Pie Menu", "tools/scripts"),
        ("configure_operations_pie_menu", "Configure Operations Pie Menu", "tools/scripts"),
    ]


def test_execute_stub_action_triggers_resolved_action(monkeypatch):
    import operations_pie_menu.operations_pie_menu as opmod

    ext = opmod.OperationsPieMenuExtension(parent=None)
    triggered = []

    class _Act:
        def trigger(self):
            triggered.append(1)

    class _App:
        def action(self, aid):
            return _Act()

    monkeypatch.setattr(opmod.Krita, "instance", staticmethod(lambda: _App()))
    ext.execute_stub_action("E", "Stub East", "op_some_registered_action")

    assert triggered == [1]


def test_open_config_dialog_constructs_and_executes(monkeypatch):
    import operations_pie_menu.operations_pie_menu as opmod

    ext = opmod.OperationsPieMenuExtension(parent=None)
    executed = []

    class _Dlg:
        def __init__(self, path, on_save_callback=None):
            self.path = path

        def exec_(self):
            executed.append(self.path)

    monkeypatch.setattr(opmod, "OperationsConfigDialog", _Dlg)
    ext.open_config_dialog()

    assert len(executed) == 1
    assert executed[0].endswith("config.json")
