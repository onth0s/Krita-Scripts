import pytest
from fakes import Action, App, Doc, Group, Node, Selection, View, Window, make_resolver

from operations_pie_menu.operations import refine_sketch as rs

YES, NO = 1, 0


@pytest.fixture
def warnings(monkeypatch):
    calls = []
    monkeypatch.setattr(
        rs.QMessageBox, "warning", staticmethod(lambda *a, **k: calls.append(a))
    )
    return calls


@pytest.fixture
def wire(monkeypatch):
    """Standard monkeypatches shared across refine tests."""
    monkeypatch.setattr(rs, "is_empty_paint_layer", lambda node: node._empty)
    monkeypatch.setattr(rs, "QByteArray", lambda data: data)
    monkeypatch.setattr(rs.QApplication, "processEvents", staticmethod(lambda: None))
    logged = {"info": [], "warning": [], "error": []}
    monkeypatch.setattr(rs, "log_info", lambda *a: logged["info"].append(a))
    monkeypatch.setattr(rs, "log_warning", lambda *a: logged["warning"].append(a))
    monkeypatch.setattr(rs, "log_error", lambda *a: logged["error"].append(a))
    return logged


# ── extra checks + selection cut/paste ───────────────────────────────────────


def test_refine_extra_checks(wire):
    assert rs._refine_sketch_extra_checks(None, Group("g", [])) == (
        False,
        "Refine Sketch requires a Paint Layer (Group selected).",
    )
    assert rs._refine_sketch_extra_checks(None, Node("empty"))[0] is False
    assert rs._refine_sketch_extra_checks(None, Node("ink", empty=False)) == (True, "")


def test_selection_cut_paste_no_selection(wire):
    layer = Node("ink", empty=False)
    assert rs.handle_selection_cut_paste(Doc(layer), App(), layer) is layer


def test_selection_cut_paste_missing_actions(wire, monkeypatch):
    layer = Node("ink", empty=False)
    doc = Doc(layer)
    doc._selection = Selection(4, 4)
    monkeypatch.setattr(rs, "resolve_action", lambda app, ids: None)
    assert rs.handle_selection_cut_paste(doc, App(), layer) is layer


def test_selection_cut_paste_flow(wire, monkeypatch):
    layer = Node("ink", empty=False)
    pasted = Node("pasted", empty=False)
    doc = Doc(layer)
    doc._selection = Selection(4, 4)
    doc._node = pasted  # simulate paste -> new active node

    cut, paste, deselect = Action(), Action(), Action()
    actions = {"edit_cut": cut, "edit_paste": paste, "deselect": deselect}
    monkeypatch.setattr(rs, "resolve_action", make_resolver(actions))

    result = rs.handle_selection_cut_paste(doc, App(doc, actions=actions), layer)

    assert result is pasted
    assert cut.triggered == 1 and paste.triggered == 1 and deselect.triggered == 1
    assert doc.done_waits >= 3


def test_selection_cut_paste_no_deselect_action(wire, monkeypatch):
    layer = Node("ink", empty=False)
    doc = Doc(layer)
    doc._selection = Selection(4, 4)
    cut, paste = Action(), Action()
    actions = {"edit_cut": cut, "edit_paste": paste}
    monkeypatch.setattr(rs, "resolve_action", make_resolver(actions))

    rs.handle_selection_cut_paste(doc, App(doc, actions=actions), layer)
    assert doc._selection is None


# ── fill_layer_random_hsl ────────────────────────────────────────────────────


def test_fill_random_hsl_skips_non_u8(wire):
    layer = Node("ink", empty=False)
    doc = Doc(layer)
    doc._color_depth = "F16"
    rs.fill_layer_random_hsl(doc, layer)
    assert wire["warning"] and layer._pixel is None


def test_fill_random_hsl_fills(wire, monkeypatch):
    layer = Node("ink", empty=False)
    doc = Doc(layer)
    monkeypatch.setattr(rs.random, "random", lambda: 0.25)
    rs.fill_layer_random_hsl(doc, layer)
    assert layer._pixel is not None
    data = layer._pixel[0]
    assert len(data) == 4 * 4 * 4
    assert all(data[i + 3] == 0xFF for i in range(0, len(data), 4)), "alpha preserved"
    assert data[0] != 0xFF, "blue channel overwritten by HSL color"


def test_fill_random_hsl_exception(wire):
    class _Boom(Node):
        def pixelData(self, x, y, w, h):
            raise RuntimeError("read fail")

    layer = _Boom("ink", empty=False)
    doc = Doc(layer)
    rs.fill_layer_random_hsl(doc, layer)
    assert wire["error"] and "read fail" in str(wire["error"][0])


# ── apply_duplicate_reflay ───────────────────────────────────────────────────


def test_duplicate_reflay_success(wire, monkeypatch):
    active = Node("ink", empty=False)
    parent = Group("parent", [active])
    doc = Doc(active, root=parent)
    merge = Action()
    actions = {"layer_merge_down": merge}
    monkeypatch.setattr(rs, "resolve_action", make_resolver(actions))

    result = rs.apply_duplicate_reflay(doc, App(doc, actions=actions), active)

    dup = doc.active[0]
    assert result is dup
    assert dup is not active and dup._parent is parent
    assert merge.triggered == 1


def test_duplicate_reflay_exception(wire):
    class _Boom(Node):
        def duplicate(self):
            raise RuntimeError("dup fail")

    active = _Boom("ink", empty=False)
    doc = Doc(active)
    result = rs.apply_duplicate_reflay(doc, App(doc), active)
    assert result is active
    assert wire["error"]


# ── apply_luminosity_overlay ─────────────────────────────────────────────────


def test_luminosity_overlay(wire, monkeypatch):
    active = Node("ink", empty=False)
    parent = Group("parent", [active])
    doc = Doc(active, root=parent)
    view = View()
    merge = Action()
    actions = {"layer_merge_down": merge}
    monkeypatch.setattr(rs, "resolve_action", make_resolver(actions))

    rs.apply_luminosity_overlay(doc, App(doc, window=Window(view), actions=actions), active, view)

    temp = [n for n in doc.created if n.name() == "Refine_Lum_Temp"][0]
    assert temp._blending == "luminize"
    assert temp._inherit_alpha is True
    assert temp in parent._children
    assert view.active_nodes == [temp]
    assert merge.triggered == 1


def test_luminosity_overlay_gray_pixel(wire, monkeypatch):
    active = Node("ink", empty=False)
    doc = Doc(active)
    monkeypatch.setattr(rs, "resolve_action", lambda app, ids: None)

    rs.apply_luminosity_overlay(doc, App(doc), active, None)

    temp = doc.created[0]
    assert temp._pixel is not None and temp._pixel[0][:4] == b"\x80\x80\x80\xff"


def test_luminosity_overlay_pixel_exception(wire):
    class _Boom(Node):
        def pixelData(self, x, y, w, h):
            raise RuntimeError("pixel fail")

    class _BoomDoc(Doc):
        def createNode(self, name, ntype):
            n = _Boom(name, ntype)
            self.created.append(n)
            return n

    active = Node("ink", empty=False)
    doc = _BoomDoc(active)
    rs.apply_luminosity_overlay(doc, App(doc), active, None)
    assert wire["error"]


# ── execute_refine_sketch ────────────────────────────────────────────────────


def test_refine_no_doc(monkeypatch, warnings):
    monkeypatch.setattr(rs, "Krita", type("_S", (), {"instance": staticmethod(lambda: App(None))}))
    rs.execute_refine_sketch()
    assert len(warnings) == 1


def test_refine_no_node(monkeypatch, warnings):
    app = App(Doc(None))
    monkeypatch.setattr(rs, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))
    rs.execute_refine_sketch()
    assert len(warnings) == 1


def test_refine_group_selected(monkeypatch, warnings):
    app = App(Doc(Group("g", [])))
    monkeypatch.setattr(rs, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))
    rs.execute_refine_sketch()
    assert warnings and "Group" in str(warnings[0])


def test_refine_empty_layer(monkeypatch, warnings, wire):
    app = App(Doc(Node("empty")))
    monkeypatch.setattr(rs, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))
    rs.execute_refine_sketch()
    assert warnings and "empty" in str(warnings[0])


def _run_full_refine(monkeypatch, duplicate_reflay=False):
    active = Node("ink", empty=False)
    parent = Group("parent", [active, Node("WHITE", locked=True)])
    doc = Doc(active, root=parent)
    view = View()
    reset = Action()
    actions = {
        "reset_fg_bg": reset,
        "layer_merge_down": Action(),
    }
    app = App(doc, window=Window(view), actions=actions)

    new_layer = Node("sketch1", empty=False)
    new_layer._parent = parent
    preset = object()

    wire = {}
    monkeypatch.setattr(rs, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))
    monkeypatch.setattr(rs, "is_empty_paint_layer", lambda node: node._empty)
    monkeypatch.setattr(rs, "resolve_action", make_resolver(actions))
    monkeypatch.setattr(rs, "QByteArray", lambda data: data)
    monkeypatch.setattr(rs.QApplication, "processEvents", staticmethod(lambda: None))
    monkeypatch.setattr(rs.random, "random", lambda: 0.25)
    monkeypatch.setattr(rs, "create_incremental_layer", lambda d, layer: new_layer)
    monkeypatch.setattr(
        rs, "set_foreground_black", lambda d, v: wire.setdefault("fg", []).append(v)
    )
    monkeypatch.setattr(rs, "find_brush_preset", lambda a, n: preset)
    monkeypatch.setattr(
        rs,
        "is_protected_layer",
        lambda node: node.name().strip().upper() in {"WHITE", "B&W", "LINES"},
    )
    logs = []
    monkeypatch.setattr(rs, "log_info", lambda *a: logs.append(a))

    rs.execute_refine_sketch(duplicate_reflay=duplicate_reflay)

    return doc, active, parent, view, reset, new_layer, preset, logs, wire


def test_refine_full_flow(monkeypatch):
    doc, active, parent, view, reset, new_layer, preset, logs, wire = _run_full_refine(
        monkeypatch
    )
    assert active._alpha_locked is True
    assert active._pixel is not None, "HSL byte fill must have run"
    assert doc.active[-1] is new_layer
    assert view.resources == [preset]
    assert reset.triggered == 1
    assert logs
    names = [c.name() for c in parent._children]
    assert names.count("WHITE") == 1


def test_refine_full_flow_with_duplicate_reflay(monkeypatch):
    doc, active, parent, view, reset, new_layer, preset, logs, wire = _run_full_refine(
        monkeypatch, duplicate_reflay=True
    )
    assert len(doc.active) > 1
    assert doc.refreshed >= 2
