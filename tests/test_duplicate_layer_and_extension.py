import pytest

from krita_pie_menu.base_extension import BasePieMenuExtension
from operations_pie_menu.operations.duplicate_layer import execute_duplicate_layer


class _Node:
    def __init__(self, name="layer"):
        self._name = name
        self._locked = None
        self._visible = None
        self.dup_calls = 0

    def name(self):
        return self._name

    def parentNode(self):
        return None

    def setLocked(self, v):
        self._locked = v

    def setVisible(self, v):
        self._visible = v

    def duplicate(self):
        self.dup_calls += 1
        dup = _Node(self._name + "_copy")
        return dup


class _Parent:
    def __init__(self):
        self.added = []

    def addChildNode(self, node, reference):
        self.added.append((node, reference))


class _Doc:
    def __init__(self, node=None, selection=None):
        self._node = node
        self._root = _Parent()
        self._selection = selection
        self.active = []
        self.refreshed = 0
        self.done_waits = 0

    def activeNode(self):
        return self._node

    def rootNode(self):
        return self._root

    def setActiveNode(self, node):
        self.active.append(node)
        self._node = node

    def refreshProjection(self):
        self.refreshed += 1

    def selection(self):
        return self._selection

    def setSelection(self, sel):
        self._selection = sel

    def waitForDone(self):
        self.done_waits += 1


class _App:
    def __init__(self, doc=None, actions=None):
        self._doc = doc
        self._actions = actions or {}

    def activeDocument(self):
        return self._doc

    def action(self, name):
        return self._actions.get(name)


@pytest.fixture
def warnings(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "operations_pie_menu.operations.duplicate_layer.QMessageBox.warning",
        staticmethod(lambda *a, **k: calls.append(a)),
    )
    return calls


def test_execute_duplicate_layer_no_doc(monkeypatch, warnings):
    monkeypatch.setattr(
        "operations_pie_menu.operations.duplicate_layer.Krita.instance",
        staticmethod(lambda: _App(None)),
    )
    execute_duplicate_layer()
    assert len(warnings) == 1


def test_execute_duplicate_layer_no_node(monkeypatch, warnings):
    monkeypatch.setattr(
        "operations_pie_menu.operations.duplicate_layer.Krita.instance",
        staticmethod(lambda: _App(_Doc(node=None))),
    )
    execute_duplicate_layer()
    assert len(warnings) == 1


def test_execute_duplicate_layer_success(monkeypatch, warnings):
    module = "operations_pie_menu.operations.duplicate_layer"
    node = _Node("working")
    parent = _Parent()
    doc = _Doc(node=node)
    doc._root = parent
    logged = []
    monkeypatch.setattr(module + ".Krita.instance", staticmethod(lambda: _App(doc)))
    monkeypatch.setattr(module + ".log_info", lambda *a: logged.append(a))

    execute_duplicate_layer()

    # Original is locked+hidden, duplicate added above it and re-shown.
    assert node._locked is True and node._visible is False
    assert node.dup_calls == 1
    assert len(parent.added) == 1
    dup_node = parent.added[0][0]
    assert parent.added == [(dup_node, node)]
    assert dup_node._locked is False and dup_node._visible is True
    assert doc.active == [dup_node]
    assert doc.refreshed == 1
    assert logged
    assert warnings == []


def test_execute_duplicate_layer_exception(monkeypatch, warnings):
    module = "operations_pie_menu.operations.duplicate_layer"

    class _BoomNode(_Node):
        def duplicate(self):
            raise RuntimeError("boom")

    doc = _Doc(node=_BoomNode())
    logged = []
    monkeypatch.setattr(module + ".Krita.instance", staticmethod(lambda: _App(doc)))
    monkeypatch.setattr(module + ".log_error", lambda *a: logged.append(a))

    execute_duplicate_layer()

    assert logged
    assert warnings and "boom" in str(warnings[0])


class _Sel:
    def __init__(self, w, h):
        self._w = w
        self._h = h

    def width(self):
        return self._w

    def height(self):
        return self._h


class _Act:
    def __init__(self):
        self.triggered = 0

    def trigger(self):
        self.triggered += 1


def test_execute_duplicate_layer_selection_cut(monkeypatch, warnings):
    module = "operations_pie_menu.operations.duplicate_layer"
    node = _Node("sketch")
    pasted = _Node("pasted_sketch")
    doc = _Doc(node=node, selection=_Sel(50, 50))
    actions = {
        "edit_cut": _Act(),
        "edit_paste": _Act(),
        "deselect": _Act(),
    }
    app = _App(doc=doc, actions=actions)

    # When paste triggers in Krita, activeNode changes to pasted layer
    def fake_paste_trigger():
        actions["edit_paste"].triggered += 1
        doc.setActiveNode(pasted)

    actions["edit_paste"].trigger = fake_paste_trigger

    monkeypatch.setattr(module + ".Krita.instance", staticmethod(lambda: app))
    monkeypatch.setattr(module + ".read_condition_flag", lambda flag, d: True)

    execute_duplicate_layer()

    assert actions["edit_cut"].triggered == 1
    assert actions["edit_paste"].triggered == 1
    assert actions["deselect"].triggered == 1
    assert doc.activeNode() == pasted
    assert doc.refreshed == 1
    assert warnings == []


def test_execute_duplicate_layer_selection_copy(monkeypatch, warnings):
    module = "operations_pie_menu.operations.duplicate_layer"
    node = _Node("sketch")
    pasted = _Node("pasted_sketch")
    doc = _Doc(node=node, selection=_Sel(50, 50))
    actions = {
        "edit_copy": _Act(),
        "edit_paste": _Act(),
        "deselect": _Act(),
    }
    app = _App(doc=doc, actions=actions)

    def fake_paste_trigger():
        actions["edit_paste"].triggered += 1
        doc.setActiveNode(pasted)

    actions["edit_paste"].trigger = fake_paste_trigger

    monkeypatch.setattr(module + ".Krita.instance", staticmethod(lambda: app))
    monkeypatch.setattr(module + ".read_condition_flag", lambda flag, d: False)

    execute_duplicate_layer()

    assert actions["edit_copy"].triggered == 1
    assert actions["edit_paste"].triggered == 1
    assert actions["deselect"].triggered == 1
    assert doc.activeNode() == pasted
    assert doc.refreshed == 1
    assert warnings == []


def test_execute_duplicate_layer_selection_deselect_fallback(monkeypatch, warnings):
    module = "operations_pie_menu.operations.duplicate_layer"
    node = _Node("sketch")
    doc = _Doc(node=node, selection=_Sel(50, 50))
    actions = {
        "edit_cut": _Act(),
        "edit_paste": _Act(),
    }
    app = _App(doc=doc, actions=actions)
    monkeypatch.setattr(module + ".Krita.instance", staticmethod(lambda: app))
    monkeypatch.setattr(module + ".read_condition_flag", lambda flag, d: True)

    execute_duplicate_layer()

    assert actions["edit_cut"].triggered == 1
    assert actions["edit_paste"].triggered == 1
    assert doc.selection() is None


def test_execute_duplicate_layer_empty_selection_fallback(monkeypatch, warnings):
    module = "operations_pie_menu.operations.duplicate_layer"
    node = _Node("working")
    parent = _Parent()
    doc = _Doc(node=node, selection=_Sel(0, 0))
    doc._root = parent
    monkeypatch.setattr(module + ".Krita.instance", staticmethod(lambda: _App(doc)))

    execute_duplicate_layer()

    assert node._locked is True and node._visible is False
    assert node.dup_calls == 1



# ---- BasePieMenuExtension ---------------------------------------------------


class _Concrete(BasePieMenuExtension):
    def build_pie_config(self):
        return {"N": lambda: None}, {"N": ("Refine", "op_refine_sketch")}, {}, {}

    def open_config_dialog(self):
        pass


def test_extension_load_save_config_delegate(tmp_path, monkeypatch):
    ext = _Concrete(
        parent=None,
        config_path=str(tmp_path / "config.json"),
        default_config={"N": {"label": "Refine Sketch", "action_id": "op_refine_sketch"}},
    )
    monkeypatch.setattr(ext, "config_path", str(tmp_path / "config.json"))

    cfg = ext.load_config()
    assert cfg["N"]["label"] == "Refine Sketch"

    assert ext.save_config({"x": 1}) is True
    assert (tmp_path / "config.json").read_text(encoding="utf-8")


def test_show_pie_menu_creates_widget(monkeypatch):
    from krita_pie_menu import base_extension

    created = []
    shown = []

    class _FakeWidget:
        def __init__(self, *args, **kwargs):
            created.append(kwargs)

        def show_at_cursor(self):
            shown.append(1)

        def isVisible(self):
            return False

        destroyed = type("_S", (), {"connect": staticmethod(lambda cb: None)})()

    monkeypatch.setattr(base_extension, "PieMenuWidget", _FakeWidget)

    ext = _Concrete(parent=None, config_path="unused.json", default_config={})
    ext.show_pie_menu()

    assert created, "widget must be constructed"
    assert created[0]["object_name"] == "BasePieWidget"
    assert shown == [1]


def test_show_pie_menu_skips_when_already_visible(monkeypatch):
    from krita_pie_menu import base_extension

    created = []
    monkeypatch.setattr(base_extension, "PieMenuWidget", lambda **kw: created.append(kw) or None)

    ext = _Concrete(parent=None, config_path="unused.json", default_config={})
    ext.pie_widget = _FakeVisible()
    ext.show_pie_menu()

    assert created == []


class _FakeVisible:
    def isVisible(self):
        return True


def test_on_widget_destroyed_clears_reference():
    ext = _Concrete(parent=None, config_path="unused.json", default_config={})
    ext.pie_widget = object()
    ext._on_widget_destroyed()
    assert ext.pie_widget is None


def test_setup_is_noop():
    ext = _Concrete(parent=None, config_path="unused.json", default_config={})
    ext.setup()


def test_abstract_build_pie_config_raises():
    class _Abstract(BasePieMenuExtension):
        pass

    ext = _Abstract(parent=None, config_path="unused.json", default_config={})
    import pytest

    with pytest.raises(NotImplementedError):
        ext.build_pie_config()


def test_abstract_open_config_dialog_raises():
    class _Abstract(BasePieMenuExtension):
        pass

    ext = _Abstract(parent=None, config_path="unused.json", default_config={})
    import pytest

    with pytest.raises(NotImplementedError):
        ext.open_config_dialog()


def test_show_pie_menu_recovers_from_stale_widget(monkeypatch):
    from krita_pie_menu import base_extension

    created = []
    shown = []

    class _Stale:
        def isVisible(self):
            raise RuntimeError("C++ object deleted")

    class _FakeWidget:
        def __init__(self, *args, **kwargs):
            created.append(kwargs)

        def show_at_cursor(self):
            shown.append(1)

        def isVisible(self):
            return False

        destroyed = type("_S", (), {"connect": staticmethod(lambda cb: None)})()

    monkeypatch.setattr(base_extension, "PieMenuWidget", _FakeWidget)

    ext = _Concrete(parent=None, config_path="unused.json", default_config={})
    ext.pie_widget = _Stale()
    ext.show_pie_menu()

    assert created
    assert shown == [1]


def test_show_pie_menu_swallows_connect_error(monkeypatch):
    from krita_pie_menu import base_extension

    shown = []

    class _FakeWidget:
        def __init__(self, *args, **kwargs):
            pass

        def show_at_cursor(self):
            shown.append(1)

        destroyed = type("_S", (), {"connect": staticmethod(lambda cb: (_ for _ in ()).throw(RuntimeError("no signal")))})()

    monkeypatch.setattr(base_extension, "PieMenuWidget", _FakeWidget)

    ext = _Concrete(parent=None, config_path="unused.json", default_config={})
    ext.show_pie_menu()

    assert shown == [1]
