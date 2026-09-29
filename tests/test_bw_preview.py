import pytest
from fakes import App, Bounds, Doc, Group, Node

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


def _app(monkeypatch, doc):
    app = App(doc)
    monkeypatch.setattr(bw, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))
    return app


# ── find_bw_node ─────────────────────────────────────────────────────────────


def test_find_bw_node_prefers_the_lowest_match():
    """childNodes() is bottom-to-top (AGENTS.md 8.1), so the first match is the lowest."""
    low = Node("b&w")  # case/whitespace insensitive
    high = Node("B&W")
    root = Group("root", [Node("ink"), low, high])
    assert bw.find_bw_node(root) is low


def test_find_bw_node_returns_none_when_absent():
    assert bw.find_bw_node(Group("root", [Node("ink")])) is None


# ── toggle path ──────────────────────────────────────────────────────────────


def test_bw_no_doc(monkeypatch, warnings):
    _app(monkeypatch, None)
    assert bw.execute_bw_preview() is False
    assert len(warnings) == 1


def test_bw_toggles_existing(monkeypatch):
    bw_layer = Node("B&W", locked=False)
    bw_layer._visible = True
    root = Group("root", [Node("ink"), bw_layer])
    doc = Doc(None, root=root)
    logged = _wire(monkeypatch)
    _app(monkeypatch, doc)

    assert bw.execute_bw_preview() is True

    assert bw_layer._visible is False
    assert doc.refreshed == 1
    assert logged["info"]


def test_bw_toggles_nested(monkeypatch):
    bw_layer = Node("B&W")
    bw_layer._visible = False
    inner = Group("inner", [bw_layer])
    root = Group("root", [Node("ink"), inner])
    doc = Doc(None, root=root)
    logged = _wire(monkeypatch)
    _app(monkeypatch, doc)

    assert bw.execute_bw_preview() is True
    assert bw_layer._visible is True
    assert logged["info"]


def test_bw_toggle_exception_reports_failure(monkeypatch):
    class _Boom(Node):
        def setVisible(self, v):
            raise RuntimeError("visible fail")

    bw_layer = _Boom("B&W")
    doc = Doc(None, root=Group("root", [bw_layer]))
    logged = _wire(monkeypatch)
    _app(monkeypatch, doc)

    result = bw.execute_bw_preview()

    assert result[0] is False
    assert logged["error"]
    assert not logged["info"], "a failed toggle must not be logged as success"


def test_bw_has_pixels_tolerates_raising_bounds():
    class _Boom(Node):
        def bounds(self):
            raise RuntimeError("freed")

    assert bw._has_pixels(_Boom("B&W")) is False


# ── create path ──────────────────────────────────────────────────────────────


def test_bw_creates_new(monkeypatch):
    initial = Node("ink")
    doc = Doc(initial)
    logged = _wire(monkeypatch)
    _app(monkeypatch, doc)

    assert bw.execute_bw_preview() is True

    bw_layer = [n for n in doc.created if n.name() == "B&W"][0]
    assert bw_layer in doc.rootNode()._children
    assert bw_layer._locked is True
    assert bw_layer._blending == "color"
    assert bw_layer._pixel is not None
    assert bw_layer._pixel[0] == b"\x00\x00\x00\xff" * (4 * 4)
    assert doc.active == [initial], "active node restored to original layer"
    assert doc.refreshed >= 1
    assert logged["info"]


def test_bw_create_exception_reports_failure(monkeypatch, warnings):
    class _BoomDoc(Doc):
        def createNode(self, name, ntype):
            raise RuntimeError("create fail")

    doc = _BoomDoc(None)
    logged = _wire(monkeypatch)
    _app(monkeypatch, doc)

    result = bw.execute_bw_preview()

    assert result == (False, "B&W layer could not be created.")
    assert logged["error"] and "create fail" in str(logged["error"][0]), "detail goes to the log"
    assert warnings == [], "reported via the toast, not a modal dialog"


def test_bw_parenting_failure_removes_nothing_and_reports(monkeypatch):
    class _RootFail(Doc):
        def rootNode(self):
            root = Group("root", [])
            root.addChildNode_ok = False
            return root

    doc = _RootFail(None)
    logged = _wire(monkeypatch)
    _app(monkeypatch, doc)

    result = bw.execute_bw_preview()

    assert result[0] is False
    assert "could not be added" in result[1]
    assert logged["warning"]


def test_bw_blending_mode_warning(monkeypatch):
    class _Boom(Node):
        def setBlendingMode(self, mode):
            raise RuntimeError("blend fail")

    class _FixedDoc(Doc):
        def createNode(self, name, ntype):
            self.created.append(_Boom(name))
            return self.created[-1]

    doc = _FixedDoc(None)
    logged = _wire(monkeypatch)
    _app(monkeypatch, doc)

    assert bw.execute_bw_preview() is True
    assert logged["warning"] and "blend fail" in str(logged["warning"][0])
    assert logged["info"], "blending failure must not abort the rest"


# ── the silent-failure modes ─────────────────────────────────────────────────


def test_bw_rejects_non_u8_document_and_leaves_no_dead_layer(monkeypatch):
    """
    The stride sniff used to mis-size the buffer on U16/F32; setPixelData then
    returned False and the return value was ignored, so a transparent 'B&W' was
    left behind that every later press kept toggling.
    """
    doc = Doc(None)
    doc._color_depth = "U16"
    logged = _wire(monkeypatch)
    _app(monkeypatch, doc)

    result = bw.execute_bw_preview()

    assert result == (False, bw._NOT_U8)
    bw_layer = doc.created[0]
    assert bw_layer.removed, "the un-fillable layer must be removed, not orphaned"
    assert doc.rootNode()._children == []
    assert logged["warning"]


def test_bw_rejects_non_rgba_color_model(monkeypatch):
    doc = Doc(None)
    doc.colorModel = lambda: "G"
    _wire(monkeypatch)
    _app(monkeypatch, doc)

    result = bw.execute_bw_preview()

    assert result == (False, bw._NOT_U8)
    assert doc.created[0].removed


def test_bw_rejects_zero_extent_document(monkeypatch):
    doc = Doc(None)
    doc._width = 0
    logged = _wire(monkeypatch)
    _app(monkeypatch, doc)

    result = bw.execute_bw_preview()

    assert result[0] is False
    assert doc.created[0].removed
    assert logged["warning"]


def test_bw_fill_rejected_by_krita(monkeypatch):
    class _RejectDoc(Doc):
        def createNode(self, name, ntype):
            node = Node(name, ntype)
            node.setPixelData_ok = False
            self.created.append(node)
            return node

    doc = _RejectDoc(None)
    logged = _wire(monkeypatch)
    _app(monkeypatch, doc)

    result = bw.execute_bw_preview()

    assert result[0] is False
    assert doc.created[0].removed
    assert logged["warning"]


def test_bw_fill_exception(monkeypatch):
    class _Boom(Node):
        def setPixelData(self, *args):
            raise RuntimeError("pixel fail")

    class _BoomDoc(Doc):
        def createNode(self, name, ntype):
            self.created.append(_Boom(name))
            return self.created[-1]

    doc = _BoomDoc(None)
    logged = _wire(monkeypatch)
    _app(monkeypatch, doc)

    result = bw.execute_bw_preview()

    assert result[0] is False
    assert logged["error"]
    assert doc.created[0].removed


# ── self-heal: a leftover empty B&W from an earlier failed run ───────────────


def test_bw_refills_an_existing_empty_layer_instead_of_toggling(monkeypatch):
    bw_layer = Node("B&W")
    bw_layer._bounds = Bounds(0, 0, 0, 0)
    bw_layer._visible = True
    doc = Doc(None, root=Group("root", [Node("ink"), bw_layer]))
    logged = _wire(monkeypatch)
    _app(monkeypatch, doc)

    assert bw.execute_bw_preview() is True

    assert bw_layer._visible is True, "a dead layer must not be flipped"
    assert bw_layer._pixel is not None, "it must be refilled instead"
    assert not bw_layer.removed, "the existing layer is reused, not discarded"
    assert logged["warning"] and "empty" in str(logged["warning"][0])


def test_bw_refill_on_non_u8_reports_failure_without_toggling(monkeypatch):
    bw_layer = Node("B&W")
    bw_layer._bounds = Bounds(0, 0, 0, 0)
    doc = Doc(None, root=Group("root", [bw_layer]))
    doc._color_depth = "F32"
    logged = _wire(monkeypatch)
    _app(monkeypatch, doc)

    result = bw.execute_bw_preview()

    assert result == (False, bw._NOT_U8)
    assert not bw_layer.removed, "never destroy a layer the user may be relying on"
    assert logged["warning"]


def test_bw_refill_survives_a_raising_refresh(monkeypatch):
    class _BoomDoc(Doc):
        def refreshProjection(self):
            raise RuntimeError("refresh fail")

    bw_layer = Node("B&W")
    bw_layer._bounds = Bounds(0, 0, 0, 0)
    doc = _BoomDoc(None, root=Group("root", [bw_layer]))
    _wire(monkeypatch)
    _app(monkeypatch, doc)

    assert bw.execute_bw_preview() is True
    assert bw_layer._pixel is not None
