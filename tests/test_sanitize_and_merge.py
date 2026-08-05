import pytest

from operations_pie_menu.operations import merge_to_black as m2b
from operations_pie_menu.operations import sanitize_group as sg

# ── Fake layer tree primitives ───────────────────────────────────────────────


class _Bounds:
    def __init__(self, x, y, w, h):
        self._v = (x, y, w, h)

    def x(self):
        return self._v[0]

    def y(self):
        return self._v[1]

    def width(self):
        return self._v[2]

    def height(self):
        return self._v[3]


class _Node:
    def __init__(self, name, ntype="paintlayer", empty=True, locked=False):
        self._name = name
        self._type = ntype
        self._empty = empty
        self._locked = locked
        self._visible = True
        self._bounds = _Bounds(0, 0, 2, 2)
        self._parent = None
        self.removed = False

    def name(self):
        return self._name

    def setName(self, n):
        self._name = n

    def type(self):
        return self._type

    def locked(self):
        return self._locked

    def setLocked(self, v):
        self._locked = v

    def visible(self):
        return self._visible

    def setVisible(self, v):
        self._visible = v

    def bounds(self):
        return self._bounds

    def parentNode(self):
        return self._parent

    def remove(self):
        self.removed = True
        if self._parent is not None:
            self._parent._children.remove(self)

    def setAlphaLocked(self, v):
        pass

    def setPixelData(self, *a):
        pass

    def duplicate(self):
        return None


class _Group:
    def __init__(self, name, children):
        self._name = name
        self._children = list(children)
        for child in self._children:
            child._parent = self

    def name(self):
        return self._name

    def type(self):
        return "grouplayer"

    def childNodes(self):
        return list(self._children)

    def addChildNode(self, node, reference):
        node._parent = self
        if reference is None:
            self._children.append(node)
        else:
            idx = self._children.index(reference)
            self._children.insert(idx + 1, node)

    def remove(self):
        pass


class _Doc:
    def __init__(self, node, root=None):
        self._node = node
        self._root = root
        self.created = []
        self.active = []
        self.refreshed = 0
        self._u8rgba = True

    def activeNode(self):
        return self._node

    def rootNode(self):
        return self._root

    def createNode(self, name, ntype):
        n = _Node(name, ntype)
        self.created.append(n)
        return n

    def setActiveNode(self, node):
        self.active.append(node)

    def refreshProjection(self):
        self.refreshed += 1

    def colorModel(self):
        return "RGBA"

    def colorDepth(self):
        return "U8"

    def setPixelData(self, *a):
        pass


class _App:
    def __init__(self, doc=None):
        self._doc = doc
        self.actions = {}

    def activeDocument(self):
        return self._doc

    def action(self, name):
        return self.actions.get(name)

    def activeWindow(self):
        return None


@pytest.fixture
def warnings(monkeypatch):
    calls = []
    monkeypatch.setattr(sg.QMessageBox, "warning", staticmethod(lambda *a, **k: calls.append(a)))
    monkeypatch.setattr(m2b.QMessageBox, "warning", staticmethod(lambda *a, **k: calls.append(a)))
    return calls


@pytest.fixture
def infos(monkeypatch):
    calls = []
    monkeypatch.setattr(
        m2b.QMessageBox, "information", staticmethod(lambda *a, **k: calls.append(a))
    )
    return calls


def _no_protected(node):
    return node.name().strip().upper() in {"WHITE", "B&W", "LINES"}


# ── sanitize_group ───────────────────────────────────────────────────────────


def test_sanitize_no_doc(monkeypatch, warnings):
    monkeypatch.setattr(sg, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: _App(None))}))
    sg.execute_sanitize_group()
    assert len(warnings) == 1


def test_sanitize_no_node(monkeypatch, warnings):
    app = _App(_Doc(node=None))
    monkeypatch.setattr(sg, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    sg.execute_sanitize_group()
    assert len(warnings) == 1


def test_sanitize_layer_not_in_group(monkeypatch, warnings):
    node = _Node("loose", "paintlayer")
    app = _App(_Doc(node=node))
    monkeypatch.setattr(sg, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    sg.execute_sanitize_group()
    assert warnings and "Group" in str(warnings[0])


def test_sanitize_validate(monkeypatch):
    app = _App(_Doc(node=None))
    monkeypatch.setattr(sg, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    assert sg.validate_sanitize_group()[0] is False

    group = _Group("g", [])
    app2 = _App(_Doc(node=group))
    monkeypatch.setattr(sg, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app2)}))
    assert sg.validate_sanitize_group() == (True, "")

    inside = _Node("inner", "paintlayer")
    grp = _Group("g2", [inside])
    app3 = _App(_Doc(node=inside))
    monkeypatch.setattr(sg, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app3)}))
    assert sg.validate_sanitize_group() == (True, "")
    del grp


def test_sanitize_full_flow(monkeypatch, warnings):
    monkeypatch.setattr(sg, "is_protected_layer", _no_protected)
    monkeypatch.setattr(sg, "is_empty_paint_layer", lambda node: node._empty)

    white = _Node("WHITE", "paintlayer")
    junk = _Node("junk_empty", "paintlayer", empty=True)
    ink = _Node("ink", "paintlayer", empty=False)
    bw = _Node("B&W", "paintlayer", empty=False)
    group = _Group("g", [white, junk, ink, bw])
    doc = _Doc(node=group)
    app = _App(doc)
    monkeypatch.setattr(sg, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    logged = []
    monkeypatch.setattr(sg, "log_info", lambda *a: logged.append(a))

    sg.execute_sanitize_group()

    assert junk.removed is True, "empty unprotected paint layer must be purged"
    assert len(doc.created) == 1, "exactly one fresh layer must be created"
    fresh = doc.created[0]
    assert group._children[-1] is bw, "B&W must end up at absolute top"
    assert bw._locked is True
    names = [c.name() for c in group._children]
    assert names == ["WHITE", "1", "2", "B&W"]
    assert doc.active == [fresh]
    assert doc.refreshed == 1
    assert logged
    assert warnings == []


def test_sanitize_exception(monkeypatch, warnings):
    class _BoomGroup(_Group):
        def childNodes(self):
            raise RuntimeError("boom")

    doc = _Doc(node=_BoomGroup("g", []))
    app = _App(doc)
    monkeypatch.setattr(sg, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    logged = []
    monkeypatch.setattr(sg, "log_error", lambda *a: logged.append(a))

    sg.execute_sanitize_group()

    assert logged
    assert warnings and "boom" in str(warnings[0])


# ── merge_to_black ───────────────────────────────────────────────────────────


def _fake_qimage(monkeypatch, data):
    class _FakeBits(bytearray):
        def setsize(self, n):
            pass

    class _FakeQImage:
        Format_ARGB32 = 5

        def __init__(self, payload, width, height, bpr, fmt):
            self._fmt = fmt
            self._data = _FakeBits(payload)

        def format(self):
            return 5

        def convertToFormat(self, fmt):
            return self

        def bits(self):
            return self._data

    monkeypatch.setattr(m2b, "QImage", _FakeQImage)
    monkeypatch.setattr(m2b, "QByteArray", lambda data: data)
    return _FakeQImage


def test_merge_black_full_flow(monkeypatch, warnings, infos):
    monkeypatch.setattr(m2b, "is_protected_layer", _no_protected)
    monkeypatch.setattr(m2b, "is_u8_rgba", lambda doc: True)
    _fake_qimage(monkeypatch, bytes(range(16)))  # 4 px * 4 bytes

    white = _Node("WHITE", "paintlayer", locked=True)
    ink1 = _Node("ink1", "paintlayer", empty=False)
    ink2 = _Node("ink2", "paintlayer", empty=False)
    bw = _Node("B&W", "paintlayer")
    group = _Group("g", [white, ink1, ink2, bw])

    class _ProjGroup(_Group):
        def projectionPixelData(self, x, y, w, h):
            return bytes(range(16))

    group.projectionPixelData = lambda x, y, w, h: bytes(range(16))
    doc = _Doc(node=group)
    doc._root = group
    app = _App(doc)
    monkeypatch.setattr(m2b, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    logged = []
    monkeypatch.setattr(m2b, "log_info", lambda *a: logged.append(a))

    m2b.execute_merge_to_black()

    # ink1/ink2 merged away; WHITE + B&W preserved.
    names = [c.name() for c in group._children]
    assert names[0] == "WHITE" and names[-1] == "B&W"
    merged = [c for c in group._children if c not in (white, bw)]
    assert merged and merged[0].name() == "1"
    assert doc.active == [merged[0]]
    assert doc.refreshed >= 1
    assert logged
    assert warnings == []
    assert infos == []


def test_merge_black_no_doc(monkeypatch, warnings):
    monkeypatch.setattr(m2b, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: _App(None))}))
    m2b.execute_merge_to_black()
    assert len(warnings) == 1


def test_merge_black_no_node(monkeypatch, warnings):
    app = _App(_Doc(node=None))
    monkeypatch.setattr(m2b, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    m2b.execute_merge_to_black()
    assert len(warnings) == 1


def test_merge_black_not_u8(monkeypatch, warnings):
    doc = _Doc(node=_Group("g", []))

    class _NotU8(_Doc):
        def colorDepth(self):
            return "F16"

    app = _App(_NotU8(node=doc._node))
    monkeypatch.setattr(m2b, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    logged = []
    monkeypatch.setattr(m2b, "log_warning", lambda *a: logged.append(a))
    m2b.execute_merge_to_black()
    assert logged
    assert warnings and "8-bit" in str(warnings[0])


def test_merge_black_layer_outside_group(monkeypatch, warnings):
    node = _Node("loose", "paintlayer")
    app = _App(_Doc(node=node))
    monkeypatch.setattr(m2b, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    m2b.execute_merge_to_black()
    assert warnings and "Group" in str(warnings[0])


def test_merge_black_no_paint_layers(monkeypatch, infos):
    monkeypatch.setattr(m2b, "is_protected_layer", _no_protected)
    monkeypatch.setattr(m2b, "is_u8_rgba", lambda doc: True)
    group = _Group("g", [_Node("WHITE", "paintlayer", locked=True)])
    doc = _Doc(node=group)
    app = _App(doc)
    monkeypatch.setattr(m2b, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    m2b.execute_merge_to_black()
    assert infos and "no unlocked paint layers" in str(infos[0])


def test_merge_black_empty_bounds(monkeypatch, infos):
    monkeypatch.setattr(m2b, "is_protected_layer", _no_protected)
    monkeypatch.setattr(m2b, "is_u8_rgba", lambda doc: True)
    ink = _Node("ink", "paintlayer", empty=False)
    ink._bounds = _Bounds(0, 0, 0, 0)
    group = _Group("g", [ink])
    doc = _Doc(node=group)
    app = _App(doc)
    monkeypatch.setattr(m2b, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    m2b.execute_merge_to_black()
    assert infos and "empty" in str(infos[0])


def test_merge_black_exception(monkeypatch, warnings):
    class _BoomGroup(_Group):
        def childNodes(self):
            raise RuntimeError("boom")

    doc = _Doc(node=_BoomGroup("g", []))
    app = _App(doc)
    monkeypatch.setattr(m2b, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    logged = []
    monkeypatch.setattr(m2b, "log_error", lambda *a: logged.append(a))
    m2b.execute_merge_to_black()
    assert logged
    assert warnings and "boom" in str(warnings[0])


def test_merge_black_flatten_extra_checks():
    group = _Group("g", [])
    assert m2b._flatten_extra_checks(None, group) == (True, "")
    inside = _Node("inner", "paintlayer")
    grp = _Group("g2", [inside])
    assert m2b._flatten_extra_checks(None, inside) == (True, "")
    del grp
    assert m2b._flatten_extra_checks(None, _Node("loose", "paintlayer"))[0] is False
