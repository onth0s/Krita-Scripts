
import quick_script_engine.quick_script_engine as qse
from krita_pie_menu.toast_notification import ToastNotification
from quick_script_engine.quick_script_engine import QuickScriptEngineExtension


def test_setup_is_noop():
    QuickScriptEngineExtension(parent=None).setup()


def test_create_actions_registers_incremental_layer_action():
    created = []

    class _Signal:
        def __init__(self):
            self.cb = None

        def connect(self, cb):
            self.cb = cb

    class _Action:
        def __init__(self):
            self.triggered = _Signal()

    class _Win:
        def createAction(self, aid, text, category):
            created.append((aid, text, category))
            return _Action()

    ext = QuickScriptEngineExtension(parent=None)
    ext.createActions(_Win())

    assert created == [
        ("create_incremental_layer_action", "Create Incremental Layer", "tools/scripts")
    ]


def _toast_recorder(toasts):
    def record(message, parent=None, duration_ms=2500, toast_type="warning"):
        toasts.append((message, toast_type))

    return record


def _app_with_doc(doc):
    class _App:
        def activeDocument(self):
            return doc

    return _App


def test_create_incremental_layer_no_document(monkeypatch):
    toasts = []
    monkeypatch.setattr(qse.Krita, "instance", staticmethod(lambda: _app_with_doc(None)()))
    monkeypatch.setattr(ToastNotification, "show_toast", staticmethod(_toast_recorder(toasts)))

    QuickScriptEngineExtension(parent=None).create_incremental_layer()

    assert toasts == [("No active document open.", "warning")]


def test_create_incremental_layer_no_active_layer(monkeypatch):
    class _Doc:
        def activeNode(self):
            return None

    toasts = []
    monkeypatch.setattr(qse.Krita, "instance", staticmethod(lambda: _app_with_doc(_Doc())()))
    monkeypatch.setattr(ToastNotification, "show_toast", staticmethod(_toast_recorder(toasts)))

    QuickScriptEngineExtension(parent=None).create_incremental_layer()

    assert toasts == [("No active layer selected.", "warning")]


class _Layer:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


def test_create_incremental_layer_success(monkeypatch):
    class _Doc:
        def activeNode(self):
            return _Layer("Ink 2")

    toasts = []
    monkeypatch.setattr(qse.Krita, "instance", staticmethod(lambda: _app_with_doc(_Doc())()))
    monkeypatch.setattr(qse, "create_incremental_layer", lambda doc, node: _Layer("3"))
    monkeypatch.setattr(ToastNotification, "show_toast", staticmethod(_toast_recorder(toasts)))

    QuickScriptEngineExtension(parent=None).create_incremental_layer()

    assert toasts == [("Created Layer '3'", "info")]


def test_create_incremental_layer_no_new_layer_no_toast(monkeypatch):
    class _Doc:
        def activeNode(self):
            return _Layer("Ink 2")

    toasts = []
    monkeypatch.setattr(qse.Krita, "instance", staticmethod(lambda: _app_with_doc(_Doc())()))
    monkeypatch.setattr(qse, "create_incremental_layer", lambda doc, node: None)
    monkeypatch.setattr(ToastNotification, "show_toast", staticmethod(_toast_recorder(toasts)))

    QuickScriptEngineExtension(parent=None).create_incremental_layer()

    assert toasts == []
