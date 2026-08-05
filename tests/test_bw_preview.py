import pytest
from fakes import App, Doc, Group, Node

from operations_pie_menu.operations import bw_preview as bw


@pytest.fixture
def warnings(monkeypatch):
    calls = []
    monkeypatch.setattr(
        bw.QMessageBox, "warning", staticmethod(lambda *a, **k: calls.append(a))
    )
    return calls


def _wire(monkeypatch):
    monkeypatch.setattr(bw, "QByteArray", lambda data: data)
    logged = {"info": [], "warning": [], "error": []}
    monkeypatch.setattr(bw, "log_info", lambda *a: logged["info"].append(a))
    monkeypatch.setattr(bw, "log_warning", lambda *a: logged["warning"].append(a))
    monkeypatch.setattr(bw, "log_error", lambda *a: logged["error"].append(a))
    return logged


def test_bw_no_doc(monkeypatch, warnings):
    monkeypatch.setattr(bw, "Krita", type("_S", (), {"instance": staticmethod(lambda: App(None))}))
    bw.execute_bw_preview()
    assert len(warnings) == 1


def test_bw_toggles_existing(monkeypatch):
    bw_layer = Node("B&W", locked=False)
    bw_layer._visible = True
    root = Group("root", [Node("ink"), bw_layer])
    doc = Doc(None, root=root)
    app = App(doc)
    logged = _wire(monkeypatch)
    monkeypatch.setattr(bw, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))

    bw.execute_bw_preview()

    assert bw_layer._visible is False
    assert bw_layer._locked is True
    assert doc.refreshed == 1
    assert logged["info"]


def test_bw_toggles_nested(monkeypatch):
    bw_layer = Node("B&W")
    bw_layer._visible = False
    inner = Group("inner", [bw_layer])
    root = Group("root", [Node("ink"), inner])
    doc = Doc(None, root=root)
    app = App(doc)
    logged = _wire(monkeypatch)
    monkeypatch.setattr(bw, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))

    bw.execute_bw_preview()

    assert bw_layer._visible is True
    assert logged["info"]


def test_bw_toggle_exception(monkeypatch):
    class _Boom(Node):
        def setLocked(self, v):
            raise RuntimeError("lock fail")

    bw_layer = _Boom("B&W")
    root = Group("root", [bw_layer])
    doc = Doc(None, root=root)
    app = App(doc)
    logged = _wire(monkeypatch)
    monkeypatch.setattr(bw, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))

    bw.execute_bw_preview()

    assert logged["error"]


def test_bw_creates_new(monkeypatch):
    initial = Node("ink")
    doc = Doc(initial)
    app = App(doc)
    logged = _wire(monkeypatch)
    monkeypatch.setattr(bw, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))

    bw.execute_bw_preview()

    bw_layer = [n for n in doc.created if n.name() == "B&W"][0]
    assert bw_layer in doc.rootNode()._children
    assert bw_layer._locked is True
    assert bw_layer._blending == "color"
    assert bw_layer._pixel is not None
    data = bw_layer._pixel[0]
    assert data == b"\x00\x00\x00\xff" * (4 * 4)
    assert doc.active == [initial], "active node restored to original layer"
    assert doc.refreshed >= 1
    assert logged["info"]


def test_bw_creates_non_4byte_pixel(monkeypatch):
    class _BwNode(Node):
        def __init__(self):
            super().__init__("B&W")
            self._pixel = (b"\xaa" * 6,)

    class _FixedDoc(Doc):
        def createNode(self, name, ntype):
            self.created.append(_BwNode())
            return self.created[-1]

    doc = _FixedDoc(None)
    app = App(doc)
    logged = _wire(monkeypatch)
    monkeypatch.setattr(bw, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))

    bw.execute_bw_preview()

    bw_layer = doc.created[0]
    assert bw_layer._pixel[0] == (b"\x00" * 5 + b"\xff") * (4 * 4)


def test_bw_blending_mode_warning(monkeypatch):
    class _Boom(Node):
        def setBlendingMode(self, mode):
            raise RuntimeError("blend fail")

    class _FixedDoc(Doc):
        def createNode(self, name, ntype):
            self.created.append(_Boom(name))
            return self.created[-1]

    doc = _FixedDoc(None)
    app = App(doc)
    logged = _wire(monkeypatch)
    monkeypatch.setattr(bw, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))

    bw.execute_bw_preview()

    assert logged["warning"] and "blend fail" in str(logged["warning"][0])
    assert logged["info"], "blending failure must not abort the rest"


def test_bw_create_exception(monkeypatch, warnings):
    class _BoomDoc(Doc):
        def createNode(self, name, ntype):
            raise RuntimeError("create fail")

    doc = _BoomDoc(None)
    app = App(doc)
    logged = _wire(monkeypatch)
    monkeypatch.setattr(bw, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))

    bw.execute_bw_preview()

    assert logged["error"]
    assert warnings and "create fail" in str(warnings[0])
