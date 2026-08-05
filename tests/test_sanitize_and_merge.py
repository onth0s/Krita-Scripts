import pytest
from fakes import App, Bounds, Doc, Group, Node

from operations_pie_menu.operations import merge_to_black as m2b
from operations_pie_menu.operations import sanitize_group as sg


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
    monkeypatch.setattr(sg, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: App(None))}))
    sg.execute_sanitize_group()
    assert len(warnings) == 1


def test_sanitize_no_node(monkeypatch, warnings):
    app = App(Doc(node=None))
    monkeypatch.setattr(sg, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    sg.execute_sanitize_group()
    assert len(warnings) == 1


def test_sanitize_layer_not_in_group(monkeypatch, warnings):
    node = Node("loose", "paintlayer")
    app = App(Doc(node=node, root=Group("root", [])))
    monkeypatch.setattr(sg, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    sg.execute_sanitize_group()
    assert warnings and "Group" in str(warnings[0])


def test_sanitize_validate(monkeypatch):
    app = App(Doc(node=None))
    monkeypatch.setattr(sg, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    assert sg.validate_sanitize_group()[0] is False

    group = Group("g", [])
    app2 = App(Doc(node=group))
    monkeypatch.setattr(sg, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app2)}))
    assert sg.validate_sanitize_group() == (True, "")

    inside = Node("inner", "paintlayer")
    grp = Group("g2", [inside])
    app3 = App(Doc(node=inside))
    monkeypatch.setattr(sg, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app3)}))
    assert sg.validate_sanitize_group() == (True, "")
    del grp


def test_sanitize_full_flow(monkeypatch, warnings):
    monkeypatch.setattr(sg, "is_protected_layer", _no_protected)
    monkeypatch.setattr(sg, "is_empty_paint_layer", lambda node: node._empty)

    white = Node("WHITE", "paintlayer")
    junk = Node("junk_empty", "paintlayer", empty=True)
    ink = Node("ink", "paintlayer", empty=False)
    bw = Node("B&W", "paintlayer", empty=False)
    group = Group("g", [white, junk, ink, bw])
    doc = Doc(node=group)
    app = App(doc)
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
    class _BoomGroup(Group):
        def childNodes(self):
            raise RuntimeError("boom")

    doc = Doc(node=_BoomGroup("g", []))
    app = App(doc)
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

    white = Node("WHITE", "paintlayer", locked=True)
    ink1 = Node("ink1", "paintlayer", empty=False)
    ink2 = Node("ink2", "paintlayer", empty=False)
    bw = Node("B&W", "paintlayer")
    group = Group("g", [white, ink1, ink2, bw])

    class _ProjGroup(Group):
        def projectionPixelData(self, x, y, w, h):
            return bytes(range(16))

    group.projectionPixelData = lambda x, y, w, h: bytes(range(16))
    doc = Doc(node=group)
    doc._root = group
    app = App(doc)
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
    monkeypatch.setattr(m2b, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: App(None))}))
    m2b.execute_merge_to_black()
    assert len(warnings) == 1


def test_merge_black_no_node(monkeypatch, warnings):
    app = App(Doc(node=None))
    monkeypatch.setattr(m2b, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    m2b.execute_merge_to_black()
    assert len(warnings) == 1


def test_merge_black_not_u8(monkeypatch, warnings):
    doc = Doc(node=Group("g", []))

    class _NotU8(Doc):
        def colorDepth(self):
            return "F16"

    app = App(_NotU8(node=doc._node))
    monkeypatch.setattr(m2b, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    logged = []
    monkeypatch.setattr(m2b, "log_warning", lambda *a: logged.append(a))
    m2b.execute_merge_to_black()
    assert logged
    assert warnings and "8-bit" in str(warnings[0])


def test_merge_black_layer_outside_group(monkeypatch, warnings):
    node = Node("loose", "paintlayer")
    app = App(Doc(node=node, root=Group("root", [])))
    monkeypatch.setattr(m2b, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    m2b.execute_merge_to_black()
    assert warnings and "Group" in str(warnings[0])


def test_merge_black_no_paint_layers(monkeypatch, infos):
    monkeypatch.setattr(m2b, "is_protected_layer", _no_protected)
    monkeypatch.setattr(m2b, "is_u8_rgba", lambda doc: True)
    group = Group("g", [Node("WHITE", "paintlayer", locked=True)])
    doc = Doc(node=group)
    app = App(doc)
    monkeypatch.setattr(m2b, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    m2b.execute_merge_to_black()
    assert infos and "no unlocked paint layers" in str(infos[0])


def test_merge_black_empty_bounds(monkeypatch, infos):
    monkeypatch.setattr(m2b, "is_protected_layer", _no_protected)
    monkeypatch.setattr(m2b, "is_u8_rgba", lambda doc: True)
    ink = Node("ink", "paintlayer", empty=False)
    ink._bounds = Bounds(0, 0, 0, 0)
    group = Group("g", [ink])
    doc = Doc(node=group)
    app = App(doc)
    monkeypatch.setattr(m2b, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    m2b.execute_merge_to_black()
    assert infos and "empty" in str(infos[0])


def test_merge_black_exception(monkeypatch, warnings):
    class _BoomGroup(Group):
        def childNodes(self):
            raise RuntimeError("boom")

    doc = Doc(node=_BoomGroup("g", []))
    app = App(doc)
    monkeypatch.setattr(m2b, "Krita", type("_AppStub", (), {"instance": staticmethod(lambda: app)}))
    logged = []
    monkeypatch.setattr(m2b, "log_error", lambda *a: logged.append(a))
    m2b.execute_merge_to_black()
    assert logged
    assert warnings and "boom" in str(warnings[0])


def test_merge_black_flatten_extra_checks():
    group = Group("g", [])
    assert m2b._flatten_extra_checks(None, group) == (True, "")
    inside = Node("inner", "paintlayer")
    grp = Group("g2", [inside])
    assert m2b._flatten_extra_checks(None, inside) == (True, "")
    del grp
    assert m2b._flatten_extra_checks(None, Node("loose", "paintlayer"))[0] is False
