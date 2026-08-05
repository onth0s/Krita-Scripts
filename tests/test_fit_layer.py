import pytest
from fakes import App, Doc, Group, Node, Window

from operations_pie_menu.operations import fit_layer as fl

YES, NO = 1, 0


class _Bits:
    def __init__(self, raw):
        self._raw = raw

    def setsize(self, n):
        pass

    def __bytes__(self):
        return bytes(self._raw)

    def __iter__(self):
        return iter(self._raw)


class _FakeQImage:
    Format_ARGB32 = 5

    def __init__(self, raw, w, h, bpr, fmt):
        self._raw = bytearray(raw)
        self._w = w
        self._h = h
        self._fmt = fmt
        self._force_convert = False

    def copy(self):
        return _FakeQImage(self._raw, self._w, self._h, self._w * 4, self._fmt)

    def scaled(self, w, h, *args):
        self._w = w
        self._h = h
        return self

    def format(self):
        return 6 if self._force_convert else self._fmt

    def convertToFormat(self, fmt):
        self._fmt = fmt
        self._force_convert = False
        return self

    def width(self):
        return self._w

    def height(self):
        return self._h

    def constBits(self):
        return _Bits(self._raw)


@pytest.fixture
def warnings(monkeypatch):
    calls = []
    monkeypatch.setattr(fl.QMessageBox, "warning", staticmethod(lambda *a, **k: calls.append(a)))
    return calls


@pytest.fixture
def infos(monkeypatch):
    calls = []
    monkeypatch.setattr(
        fl.QMessageBox, "information", staticmethod(lambda *a, **k: calls.append(a))
    )
    return calls


def _wire(monkeypatch, keep_ar=False, convert=False, u8=True):
    monkeypatch.setattr(fl, "is_u8_rgba", lambda doc: u8)
    monkeypatch.setattr(fl, "read_condition_flag", lambda key, default: keep_ar)
    monkeypatch.setattr(fl, "QImage", _FakeQImage)
    monkeypatch.setattr(fl, "QByteArray", lambda data: data)

    class _ConvImage(_FakeQImage):
        def copy(self):
            return self

        def scaled(self, w, h, *args):
            self._force_convert = convert
            return super().scaled(w, h, *args)

    if convert:
        monkeypatch.setattr(fl, "QImage", _ConvImage)

    logged = {"info": [], "warning": [], "error": []}
    monkeypatch.setattr(fl, "log_info", lambda *a: logged["info"].append(a))
    monkeypatch.setattr(fl, "log_warning", lambda *a: logged["warning"].append(a))
    monkeypatch.setattr(fl, "log_error", lambda *a: logged["error"].append(a))
    return logged


def test_fit_no_doc(monkeypatch, warnings):
    monkeypatch.setattr(fl, "Krita", type("_S", (), {"instance": staticmethod(lambda: App(None))}))
    fl.execute_fit_layer()
    assert len(warnings) == 1


def test_fit_no_node(monkeypatch, warnings):
    app = App(Doc(None))
    monkeypatch.setattr(fl, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))
    fl.execute_fit_layer()
    assert len(warnings) == 1


def test_fit_not_u8(monkeypatch, warnings):
    doc = Doc(Node("ink", empty=False))
    doc._color_depth = "F16"
    app = App(doc)
    monkeypatch.setattr(fl, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))
    logged = _wire(monkeypatch, u8=False)
    fl.execute_fit_layer()
    assert logged["warning"] and warnings and "8-bit" in str(warnings[0])


def test_fit_empty_bounds(monkeypatch, infos):
    active = Node("ink", empty=False)
    active._bounds = __import__("fakes", fromlist=["Bounds"]).Bounds(0, 0, 0, 0)
    doc = Doc(active)
    app = App(doc)
    monkeypatch.setattr(fl, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))
    _wire(monkeypatch)
    fl.execute_fit_layer()
    assert infos and "empty" in str(infos[0])


def _run_fit(monkeypatch, active, keep_ar=False, convert=False, view=None):
    parent = active.parentNode() or None
    root = parent if parent is not None else Group("root", [active])
    doc = Doc(active, root=root)
    app = App(doc, window=Window(view))
    logged = _wire(monkeypatch, keep_ar=keep_ar, convert=convert)
    monkeypatch.setattr(fl, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))
    fl.execute_fit_layer()
    assert not logged["error"], logged["error"]
    return doc, root, logged


def test_fit_paint_layer_stretch(monkeypatch):
    active = Node("ink", empty=False, locked=True)
    active._alpha_locked = True
    active._blending = "multiply"
    active._opacity = 128
    active._inherit_alpha = True
    doc, root, logged = _run_fit(monkeypatch, active)

    assert active.removed is True
    scaled = doc.created[0]
    assert scaled in root._children
    assert scaled._pixel is not None
    assert doc.active[-1] is scaled
    assert logged["info"]


def test_fit_paint_layer_keep_aspect_ratio(monkeypatch):
    active = Node("ink", empty=False)
    doc, root, logged = _run_fit(monkeypatch, active, keep_ar=True)
    assert active.removed is True
    assert doc.active[-1] in root._children
    assert logged["info"]


def test_fit_paint_layer_convert_format(monkeypatch):
    active = Node("ink", empty=False)
    doc, root, logged = _run_fit(monkeypatch, active, convert=True)
    assert active.removed is True
    assert logged["info"]


def test_fit_group_layer(monkeypatch):
    child1 = Node("c1", empty=False)
    child2 = Node("c2", empty=False)
    group = Group("g", [child1, child2])
    doc, root, logged = _run_fit(monkeypatch, group)

    assert group.removed is True
    assert len(doc.created) == 0, "group path duplicates in place (no createNode)"
    scaled_groups = [c for c in root._children if c is not group]
    assert scaled_groups and doc.active[-1] is scaled_groups[0]
    assert child1._pixel is not None and child2._pixel is not None
    assert logged["info"]


def test_fit_group_skips_empty_children(monkeypatch):
    empty = Node("e", empty=False)
    empty._bounds = __import__("fakes", fromlist=["Bounds"]).Bounds(0, 0, 0, 0)
    child = Node("c1", empty=False)
    group = Group("g", [child, empty])
    doc, root, logged = _run_fit(monkeypatch, group)

    assert group.removed is True
    assert logged["info"]
    assert child._pixel is not None


def test_fit_group_keep_aspect_ratio(monkeypatch):
    child1 = Node("c1", empty=False)
    child2 = Node("c2", empty=False)
    group = Group("g", [child1, child2])
    doc, root, logged = _run_fit(monkeypatch, group, keep_ar=True)

    assert group.removed is True
    assert logged["info"]
    assert child1._pixel is not None


def test_fit_group_convert_format(monkeypatch):
    child1 = Node("c1", empty=False)
    group = Group("g", [child1])
    doc, root, logged = _run_fit(monkeypatch, group, convert=True)

    assert group.removed is True
    assert logged["info"]


def test_fit_paint_layer_restore_exceptions_log_warning(monkeypatch):
    class _RestoreBoom(Node):
        def alphaLocked(self):
            raise RuntimeError("a")

        def opacity(self):
            raise RuntimeError("o")

        def blendingMode(self):
            raise RuntimeError("b")

        def visible(self):
            raise RuntimeError("v")

        def locked(self):
            raise RuntimeError("l")

        def inheritAlpha(self):
            raise RuntimeError("i")

    active = _RestoreBoom("ink", empty=False)
    doc, root, logged = _run_fit(monkeypatch, active)

    assert active.removed is True
    assert logged["info"]
    assert len(logged["warning"]) == 6, logged["warning"]


def test_fit_group_no_paint_layers(monkeypatch, infos):
    group = Group("g", [])
    doc, root, logged = _run_fit(monkeypatch, group)
    assert infos and "no paint layers" in str(infos[0])
    assert not logged["info"]


def test_fit_exception(monkeypatch, warnings):
    class _Boom(Node):
        def pixelData(self, x, y, w, h):
            raise RuntimeError("read fail")

    active = _Boom("ink", empty=False)
    app = App(Doc(active))
    monkeypatch.setattr(fl, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))
    logged = _wire(monkeypatch)
    fl.execute_fit_layer()
    assert logged["error"]
    assert warnings and "read fail" in str(warnings[0])


def test_keep_aspect_ratio_enabled(monkeypatch):
    monkeypatch.setattr(fl, "read_condition_flag", lambda key, default: True)
    assert fl._is_keep_aspect_ratio_enabled() is True
    monkeypatch.setattr(fl, "read_condition_flag", lambda key, default: False)
    assert fl._is_keep_aspect_ratio_enabled() is False
