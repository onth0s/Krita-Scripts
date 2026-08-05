
from krita_pie_menu import utils


class _FakeNode:
    def __init__(self, name="Layer", node_type="paintlayer"):
        self._name = name
        self._type = node_type
        self.calls = []
        self._parent = None
        self._created = []

    def name(self):
        return self._name

    def type(self):
        return self._type

    def parentNode(self):
        return self._parent

    def setParent(self, parent):
        self._parent = parent


class _FakeParent:
    def __init__(self):
        self.added = []

    def addChildNode(self, node, reference_node):
        self.added.append((node, reference_node))


class _FakeDoc:
    def __init__(self, active_node=None):
        self._active = active_node
        self.created = []
        self.refreshed = 0
        self.active_set = []

    def activeNode(self):
        return self._active

    def rootNode(self):
        return _FakeParent()

    def createNode(self, name, node_type):
        node = _FakeNode(name, node_type)
        self.created.append(node)
        return node

    def setActiveNode(self, node):
        self.active_set.append(node)

    def refreshProjection(self):
        self.refreshed += 1


def test_create_incremental_layer():
    doc = _FakeDoc()
    ref = _FakeNode("sketch_3")
    parent = _FakeParent()
    ref.setParent(parent)

    created = utils.create_incremental_layer(doc, ref)

    assert created.name() == "4"
    assert created.type() == "paintlayer"
    assert parent.added == [(created, ref)]
    assert doc.active_set == [created]
    assert doc.refreshed == 1


def test_create_incremental_layer_uses_active_node_when_no_ref():
    doc = _FakeDoc()
    ref = _FakeNode("line_2")
    parent = _FakeParent()
    ref.setParent(parent)
    doc._active = ref

    created = utils.create_incremental_layer(doc)

    assert created.name() == "3"


def test_create_incremental_layer_returns_none_when_no_context():
    assert utils.create_incremental_layer(None) is None
    assert utils.create_incremental_layer(_FakeDoc()) is None


def test_resolve_action_finds_first_match():
    class _App:
        def action(self, act_id):
            return act_id if act_id == "krita_filter_hsvadjustment" else None

    action = utils.resolve_action(_App(), ["krita_filter_hsvadjustment", "krita_filter_levels"])
    assert action == "krita_filter_hsvadjustment"


def test_resolve_action_returns_none_when_missing():
    class _App:
        def action(self, act_id):
            return None

    assert utils.resolve_action(_App(), ["a", "b"]) is None


def test_resolve_action_falls_back_to_krita_instance(monkeypatch):
    from krita_pie_menu import utils as u

    seen = []

    class _App:
        def action(self, act_id):
            seen.append(act_id)
            return "found"

    monkeypatch.setattr(u.Krita, "instance", staticmethod(lambda: _App()))
    assert utils.resolve_action(None, ["x"]) == "found"
    assert seen == ["x"]


def test_find_brush_preset_exact():
    class _App:
        def resources(self, kind):
            return {"0 STD DRW": "preset-obj"}

    assert utils.find_brush_preset(_App(), "0 STD DRW") == "preset-obj"


def test_find_brush_preset_substring_and_fallback():
    class _App:
        def __init__(self, names):
            self._names = names

        def resources(self, kind):
            return {n: f"obj-{n}" for n in self._names}

    app = _App(["Basic-5 Opacity", "My STD DRW Brush"])
    assert utils.find_brush_preset(app, "Basic-5 Opacity") == "obj-Basic-5 Opacity"
    assert utils.find_brush_preset(app, "0 STD DRW") == "obj-My STD DRW Brush"


def test_find_brush_preset_none_when_missing():
    class _App:
        def resources(self, kind):
            return {"Other": 1}

    assert utils.find_brush_preset(_App(), "0 STD DRW") is None
    assert utils.find_brush_preset(None) is None


def test_set_foreground_black(monkeypatch):

    captured = []

    class _Doc:
        def colorModel(self):
            return "RGBA"

        def colorDepth(self):
            return "U8"

        def colorProfileName(self):
            return ""

    class _View:
        def setForeGroundColor(self, col):
            captured.append(col)

    utils.set_foreground_black(_Doc(), _View())
    assert len(captured) == 1


def test_set_foreground_black_noop_without_context():
    utils.set_foreground_black(None, None)
    utils.set_foreground_black(object(), None)


def test_make_doc_active_validator_states(monkeypatch):
    from krita_pie_menu import utils as u

    class _Doc:
        def __init__(self, node=None):
            self._node = node

        def activeNode(self):
            return self._node

    class _App:
        def __init__(self, doc):
            self._doc = doc

        def activeDocument(self):
            return self._doc

    validator = u.make_doc_active_validator()

    monkeypatch.setattr(u.Krita, "instance", staticmethod(lambda: _App(None)))
    ok, reason = validator()
    assert ok is False
    assert "document" in reason

    monkeypatch.setattr(u.Krita, "instance", staticmethod(lambda: _App(_Doc(None))))
    ok, reason = validator()
    assert ok is False
    assert "layer" in reason

    monkeypatch.setattr(u.Krita, "instance", staticmethod(lambda: _App(_Doc(_FakeNode("L")))))
    ok, reason = validator()
    assert ok is True
    assert reason == ""


def test_make_doc_active_validator_extra_checks(monkeypatch):
    from krita_pie_menu import utils as u

    calls = []

    def extra(doc, node):
        calls.append((doc, node))
        return False, "rejected"

    validator = u.make_doc_active_validator(extra)

    class _NoDocApp:
        def activeDocument(self):
            return None

    monkeypatch.setattr(u.Krita, "instance", staticmethod(lambda: _NoDocApp()))
    ok, reason = validator()
    assert ok is False
    assert "document" in reason
    assert calls == []
