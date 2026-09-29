import pytest
from fakes import Action, App, Bounds, Doc, Group, Node, Selection, View, Window, make_resolver

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
    logged = {"info": [], "warning": [], "error": []}
    monkeypatch.setattr(rs, "log_info", lambda *a: logged["info"].append(a))
    monkeypatch.setattr(rs, "log_warning", lambda *a: logged["warning"].append(a))
    monkeypatch.setattr(rs, "log_error", lambda *a: logged["error"].append(a))
    return logged


def _fake_merge(parent, doc, consumed, result_node):
    """Reproduce a successful Krita merge-down: consume the layer, re-target active."""

    def _do():
        if consumed in parent._children:
            parent._children.remove(consumed)
        doc._node = result_node

    return _do


def _merge_watcher(parent, doc, merge, surviving):
    """
    Patch `addChildNode` so that the next merge-down really consumes what was added.

    Mirrors Krita: the merged-away layer leaves the stack and the layer below it
    becomes active. Without this the postcondition in `_is_detached` never holds
    and the verified-trigger path cannot be exercised.
    """

    def _watch_add(node, ref):
        result = Group.addChildNode(parent, node, ref)
        merge.on_trigger = _fake_merge(parent, doc, node, surviving)
        return result

    return _watch_add


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
    assert rs.handle_selection_cut_paste(Doc(layer), App(), layer) == (layer, True)


def test_selection_cut_paste_missing_actions(wire, monkeypatch):
    layer = Node("ink", empty=False)
    doc = Doc(layer)
    doc._selection = Selection(4, 4)
    monkeypatch.setattr(rs, "resolve_action", lambda app, ids: None)
    assert rs.handle_selection_cut_paste(doc, App(), layer) == (layer, True)


def test_selection_cut_paste_disabled_actions_leave_selection(wire, monkeypatch):
    """A disabled cut/paste must be detected BEFORE the pixels are removed."""
    layer = Node("ink", empty=False)
    doc = Doc(layer)
    doc._selection = Selection(4, 4)
    actions = {"edit_cut": Action(enabled=False), "edit_paste": Action(enabled=False)}
    monkeypatch.setattr(rs, "resolve_action", make_resolver(actions))

    result, ok = rs.handle_selection_cut_paste(doc, App(doc, actions=actions), layer)

    assert (result, ok) == (layer, True)
    assert doc._selection is not None, "selection must survive when cut/paste is disabled"


def test_selection_cut_paste_flow(wire, monkeypatch):
    layer = Node("ink", empty=False)
    pasted = Node("pasted", empty=False)
    doc = Doc(layer)
    doc._selection = Selection(4, 4)
    doc._node = pasted  # simulate paste -> new active node

    cut, paste, deselect = Action(), Action(), Action()
    actions = {"edit_cut": cut, "edit_paste": paste, "deselect": deselect}
    monkeypatch.setattr(rs, "resolve_action", make_resolver(actions))

    result, ok = rs.handle_selection_cut_paste(doc, App(doc, actions=actions), layer)

    assert result is pasted and ok is True
    assert cut.triggered == 1 and paste.triggered == 1 and deselect.triggered == 1
    assert doc.done_waits >= 3


def test_selection_cut_paste_reports_loss_when_paste_is_a_noop(wire, monkeypatch):
    """Cut succeeded but paste did nothing -> pixels are gone, must report failure."""
    layer = Node("ink", empty=False)
    doc = Doc(layer)
    doc._selection = Selection(4, 4)
    # doc._node stays `layer`: paste produced no new node.
    actions = {"edit_cut": Action(), "edit_paste": Action(enabled=False)}
    monkeypatch.setattr(rs, "resolve_action", make_resolver(actions))
    actions["edit_paste"].enabled = True  # enabled, but the fake never changes doc._node

    result, ok = rs.handle_selection_cut_paste(doc, App(doc, actions=actions), layer)

    assert result is layer and ok is False
    assert wire["error"], "the lost cut must be logged"


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
    doc._color_depth = "U16"
    assert rs.fill_layer_random_hsl(doc, layer) is False
    assert wire["warning"] and layer._pixel is None


def test_fill_random_hsl_skips_non_rgba(wire):
    layer = Node("ink", empty=False)
    doc = Doc(layer)
    monkeypatch_color_model = {"value": "RGB"}
    doc.colorModel = lambda: monkeypatch_color_model["value"]
    assert rs.fill_layer_random_hsl(doc, layer) is False
    assert wire["warning"]


def test_fill_random_hsl_fills_bounds_only(wire, monkeypatch):
    layer = Node("ink", empty=False)
    layer._bounds = Bounds(5, 7, 2, 2)
    doc = Doc(layer)
    monkeypatch.setattr(rs.random, "random", lambda: 0.25)

    assert rs.fill_layer_random_hsl(doc, layer) is True

    # Scoped to the layer's own bounds, NOT the whole 4x4 canvas.
    assert layer._pixel[1:] == (5, 7, 2, 2)
    data = layer._pixel[0]
    assert len(data) == 2 * 2 * 4
    assert all(data[i + 3] == 0xFF for i in range(0, len(data), 4)), "alpha preserved"
    assert data[0] != 0xFF, "blue channel overwritten by HSL color"


def test_fill_random_hsl_empty_bounds(wire):
    layer = Node("ink", empty=False)
    layer._bounds = Bounds(0, 0, 0, 0)
    doc = Doc(layer)
    assert rs.fill_layer_random_hsl(doc, layer) is False
    assert wire["warning"]


def test_fill_random_hsl_bad_buffer_size(wire, monkeypatch):
    class _ShortBuffer(Node):
        def pixelData(self, x, y, w, h):
            return b"\xff" * 7

    layer = _ShortBuffer("ink", empty=False)
    doc = Doc(layer)
    assert rs.fill_layer_random_hsl(doc, layer) is False
    assert wire["warning"] and "buffer size" in wire["warning"][0][1]


def test_fill_random_hsl_set_pixel_data_rejected(wire, monkeypatch):
    layer = Node("ink", empty=False)
    layer.setPixelData_ok = False
    doc = Doc(layer)
    assert rs.fill_layer_random_hsl(doc, layer) is False
    assert wire["warning"] and layer._pixel is None


def test_fill_random_hsl_exception(wire):
    class _Boom(Node):
        def pixelData(self, x, y, w, h):
            raise RuntimeError("read fail")

    layer = _Boom("ink", empty=False)
    doc = Doc(layer)
    assert rs.fill_layer_random_hsl(doc, layer) is False
    assert wire["error"] and "read fail" in str(wire["error"][0])


# ── apply_duplicate_reflay ───────────────────────────────────────────────────


def test_duplicate_reflay_success(wire, monkeypatch):
    active = Node("ink", empty=False)
    parent = Group("parent", [active])
    doc = Doc(active, root=parent)
    merge = Action()
    actions = {"layer_merge_down": merge}
    monkeypatch.setattr(rs, "resolve_action", make_resolver(actions))
    monkeypatch.setattr(parent, "addChildNode", _merge_watcher(parent, doc, merge, active))

    result, ok = rs.apply_duplicate_reflay(doc, App(doc, actions=actions), active, View())

    assert ok is True
    assert result is active, "after a successful merge-down the original is active again"
    assert merge.triggered == 1
    assert len(parent._children) == 1, "the duplicate must be consumed"


def test_duplicate_reflay_duplicate_returns_none(wire, monkeypatch):
    active = Node("ink", empty=False)
    parent = Group("parent", [active])
    doc = Doc(active, root=parent)
    monkeypatch.setattr(active, "duplicate", lambda: None)

    result, ok = rs.apply_duplicate_reflay(doc, App(doc), active, View())

    assert (result, ok) == (active, False)
    assert wire["warning"]


def test_duplicate_reflay_parenting_failure(wire, monkeypatch):
    active = Node("ink", empty=False)
    parent = Group("parent", [active])
    parent.addChildNode_ok = False
    doc = Doc(active, root=parent)

    result, ok = rs.apply_duplicate_reflay(doc, App(doc), active, View())

    assert (result, ok) == (active, False)
    assert wire["warning"]


def test_duplicate_reflay_disabled_merge_removes_duplicate(wire, monkeypatch):
    active = Node("ink", empty=False)
    parent = Group("parent", [active])
    doc = Doc(active, root=parent)
    merge = Action(enabled=False)
    actions = {"layer_merge_down": merge}
    monkeypatch.setattr(rs, "resolve_action", make_resolver(actions))

    result, ok = rs.apply_duplicate_reflay(doc, App(doc, actions=actions), active, View())

    assert (result, ok) == (active, False)
    assert merge.triggered == 0, "a disabled action must never be triggered"
    assert len(parent._children) == 1, "the orphaned duplicate must be cleaned up"


def test_duplicate_reflay_exception(wire):
    class _Boom(Node):
        def duplicate(self):
            raise RuntimeError("dup fail")

    active = _Boom("ink", empty=False)
    doc = Doc(active)
    result, ok = rs.apply_duplicate_reflay(doc, App(doc), active, None)
    assert (result, ok) == (active, False)
    assert wire["error"]


def test_duplicate_reflay_exception_after_duplication_cleans_up(wire, monkeypatch):
    active = Node("ink", empty=False)
    parent = Group("parent", [active])
    doc = Doc(active, root=parent)

    def _boom():
        raise RuntimeError("boom after dup")

    monkeypatch.setattr(rs, "_sync_active", _boom)

    result, ok = rs.apply_duplicate_reflay(doc, App(doc), active, None)

    assert (result, ok) == (active, False)
    assert wire["error"]
    assert len(parent._children) == 1, "duplicate must be removed when a later step throws"


def test_duplicate_reflay_survives_a_failing_cleanup(wire, monkeypatch):
    """A duplicate that cannot even be removed must not mask the original error."""

    class _Unremovable(Node):
        def remove(self):
            raise RuntimeError("cannot detach")

    active = Node("ink", empty=False)
    parent = Group("parent", [active])
    doc = Doc(active, root=parent)

    def _boom():
        raise RuntimeError("boom after dup")

    monkeypatch.setattr(active, "duplicate", lambda: _Unremovable("dup"))
    monkeypatch.setattr(rs, "_sync_active", _boom)

    result, ok = rs.apply_duplicate_reflay(doc, App(doc), active, None)

    assert (result, ok) == (active, False), "cleanup failure must not change the verdict"


# ── apply_luminosity_overlay ─────────────────────────────────────────────────


def test_luminosity_overlay_skips_non_u8(wire):
    active = Node("ink", empty=False)
    doc = Doc(active)
    doc._color_depth = "F32"
    assert rs.apply_luminosity_overlay(doc, App(doc), active, View()) is False
    assert wire["warning"]
    assert doc.created == [], "no temp layer may be created when we bail"


def test_luminosity_overlay(wire, monkeypatch):
    active = Node("ink", empty=False)
    parent = Group("parent", [active])
    doc = Doc(active, root=parent)
    view = View()
    merge = Action()
    actions = {"layer_merge_down": merge}
    monkeypatch.setattr(rs, "resolve_action", make_resolver(actions))
    monkeypatch.setattr(parent, "addChildNode", _merge_watcher(parent, doc, merge, active))

    assert rs.apply_luminosity_overlay(doc, App(doc, window=Window(view), actions=actions), active, view) is True

    temp = [n for n in doc.created if n.name() == "Refine_Lum_Temp"][0]
    assert temp._blending == "luminize"
    assert temp._inherit_alpha is True
    assert temp not in parent._children, "temp layer must be merged away"
    assert view.activeNode() is active, "view must be re-targeted at the merged result"


def test_luminosity_overlay_parenting_failure(wire):
    active = Node("ink", empty=False)
    parent = Group("parent", [active])
    parent.addChildNode_ok = False
    doc = Doc(active, root=parent)
    assert rs.apply_luminosity_overlay(doc, App(doc), active, None) is False
    assert wire["warning"]


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
    assert rs.apply_luminosity_overlay(doc, App(doc), active, None) is False
    assert wire["error"]
    assert doc.created[0].removed, "temp layer must be removed when its fill throws"


def test_luminosity_overlay_set_pixel_data_rejected(wire):
    class _RejectDoc(Doc):
        def createNode(self, name, ntype):
            n = Node(name, ntype)
            n.setPixelData_ok = False
            self.created.append(n)
            return n

    active = Node("ink", empty=False)
    doc = _RejectDoc(active)
    assert rs.apply_luminosity_overlay(doc, App(doc), active, None) is False
    assert wire["warning"]
    assert doc.created[0].removed


def test_luminosity_overlay_gray_pixel_non4_bytes(wire, monkeypatch):
    class _Sample3(Node):
        def pixelData(self, x, y, w, h):
            return b"\x80\x80\x80"

    class _SampleDoc(Doc):
        def createNode(self, name, ntype):
            n = _Sample3(name, ntype)
            self.created.append(n)
            return n

    active = Node("ink", empty=False)
    doc = _SampleDoc(active)
    monkeypatch.setattr(rs, "resolve_action", lambda app, ids: None)

    rs.apply_luminosity_overlay(doc, App(doc), active, None)

    temp = doc.created[0]
    assert temp._pixel is not None
    assert temp._pixel[0].startswith(b"\x80\x80\x80")
    assert len(temp._pixel[0]) == 3 * 4 * 4


def test_luminosity_overlay_inherit_alpha_error(wire, monkeypatch):
    class _BoomAlpha(Node):
        def setInheritAlpha(self, v):
            raise RuntimeError("inherit fail")

    class _BoomDoc(Doc):
        def createNode(self, name, ntype):
            n = _BoomAlpha(name, ntype)
            self.created.append(n)
            return n

    active = Node("ink", empty=False)
    doc = _BoomDoc(active)
    monkeypatch.setattr(rs, "resolve_action", lambda app, ids: None)

    rs.apply_luminosity_overlay(doc, App(doc), active, None)

    assert any("Inherit Alpha" in str(w[1]) for w in wire["warning"])


def test_luminosity_overlay_view_set_node_error_warns(wire, monkeypatch):
    class _BoomView(View):
        def setActiveNode(self, node):
            raise RuntimeError("view dead")

    active = Node("ink", empty=False)
    parent = Group("parent", [active])
    doc = Doc(active, root=parent)
    actions = {"layer_merge_down": Action()}
    monkeypatch.setattr(rs, "resolve_action", make_resolver(actions))

    rs.apply_luminosity_overlay(doc, App(doc, window=Window(_BoomView())), active, _BoomView())

    assert any("sync active node" in str(w[1]) for w in wire["warning"])


def test_luminosity_overlay_disabled_merge_removes_gray_sheet(wire, monkeypatch):
    """The catastrophic silent failure: a disabled merge must not leave gray behind."""
    active = Node("ink", empty=False)
    parent = Group("parent", [active])
    doc = Doc(active, root=parent)
    merge = Action(enabled=False)
    actions = {"layer_merge_down": merge}
    monkeypatch.setattr(rs, "resolve_action", make_resolver(actions))

    assert rs.apply_luminosity_overlay(doc, App(doc, actions=actions), active, View()) is False

    assert merge.triggered == 0
    assert [c.name() for c in parent._children] == ["ink"], "no gray sheet may survive"
    assert wire["warning"]


def test_luminosity_overlay_missing_merge_action_removes_gray_sheet(wire, monkeypatch):
    active = Node("ink", empty=False)
    parent = Group("parent", [active])
    doc = Doc(active, root=parent)
    monkeypatch.setattr(rs, "resolve_action", lambda app, ids: None)

    assert rs.apply_luminosity_overlay(doc, App(doc), active, None) is False
    assert [c.name() for c in parent._children] == ["ink"]


# ── _renumber_siblings ───────────────────────────────────────────────────────


def test_renumber_siblings_skips_protected(wire):
    parent = Group("parent", [Node("a"), Node("B&W"), Node("b")])
    target = Node("t")
    target._parent = parent
    parent._children.append(target)

    rs._renumber_siblings(target)

    names = [c.name() for c in parent._children]
    assert names == ["1", "B&W", "2", "3"]


def test_renumber_siblings_no_parent(wire):
    rs._renumber_siblings(Node("orphan"))  # must not raise


def test_is_detached_tolerates_a_dangling_node(wire):
    """A freed C++ layer makes childNodes() unusable; that must not read as 'done'."""

    class _DanglingParent(Group):
        def childNodes(self):
            raise RuntimeError("dangling")

    node = Node("temp")
    assert rs._is_detached(node, _DanglingParent("p", [])) is False


# ── execute_refine_sketch ────────────────────────────────────────────────────


def test_refine_reports_failed_reflay(monkeypatch, wire, warnings):
    active = Node("ink", empty=False)
    doc = Doc(active)
    app = App(doc, actions={})
    monkeypatch.setattr(rs, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))
    monkeypatch.setattr(rs, "apply_duplicate_reflay", lambda *a: (a[2], False))

    result = rs.execute_refine_sketch(duplicate_reflay=True)

    assert result[0] is False
    assert "RefLay" in result[1]
    assert not wire["info"]


def test_refine_no_doc(monkeypatch, warnings):
    monkeypatch.setattr(rs, "Krita", type("_S", (), {"instance": staticmethod(lambda: App(None))}))
    assert rs.execute_refine_sketch() is False
    assert len(warnings) == 1


def test_refine_no_node(monkeypatch, warnings):
    app = App(Doc(None))
    monkeypatch.setattr(rs, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))
    assert rs.execute_refine_sketch() is False
    assert len(warnings) == 1


def test_refine_group_selected(monkeypatch, warnings):
    app = App(Doc(Group("g", [])))
    monkeypatch.setattr(rs, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))
    assert rs.execute_refine_sketch() is False
    assert warnings and "Group" in str(warnings[0])


def test_refine_empty_layer(monkeypatch, warnings, wire):
    app = App(Doc(Node("empty")))
    monkeypatch.setattr(rs, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))
    assert rs.execute_refine_sketch() is False
    assert warnings and "empty" in str(warnings[0])


def test_refine_reports_cut_paste_loss(monkeypatch, wire, warnings):
    """A lost cut must surface as a failure, not 'Triggered: Refine Sketch'."""
    active = Node("ink", empty=False)
    doc = Doc(active)
    doc._selection = Selection(4, 4)
    actions = {"edit_cut": Action(), "edit_paste": Action()}
    monkeypatch.setattr(rs, "resolve_action", make_resolver(actions))
    app = App(doc, actions=actions)
    monkeypatch.setattr(rs, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))

    result = rs.execute_refine_sketch()

    assert result[0] is False
    assert "Ctrl+V" in result[1]
    assert not wire["info"], "must not log success"


def test_refine_reports_failed_pixel_fill(monkeypatch, wire, warnings):
    active = Node("ink", empty=False)
    doc = Doc(active)
    doc._color_depth = "U16"
    app = App(doc, actions={})
    monkeypatch.setattr(rs, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))

    result = rs.execute_refine_sketch()

    assert result[0] is False
    assert result[1] == rs._PAINTED_PIXELS
    assert not wire["info"]


def test_refine_reports_failed_overlay(monkeypatch, wire, warnings):
    active = Node("ink", empty=False)
    parent = Group("parent", [active])
    doc = Doc(active, root=parent)
    merge = Action(enabled=False)
    actions = {"layer_merge_down": merge}
    monkeypatch.setattr(rs, "resolve_action", make_resolver(actions))
    app = App(doc, window=Window(View()), actions=actions)
    monkeypatch.setattr(rs, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))

    result = rs.execute_refine_sketch()

    assert result[0] is False
    assert result[1] == rs._LUMINANCE_OVERLAY
    assert not wire["info"]
    assert [c.name() for c in parent._children] == ["ink"]


def test_refine_reports_failed_new_layer(monkeypatch, wire, warnings):
    active = Node("ink", empty=False)
    parent = Group("parent", [active])
    doc = Doc(active, root=parent)
    merge = Action()
    actions = {"layer_merge_down": merge, "reset_fg_bg": Action()}
    monkeypatch.setattr(rs, "resolve_action", make_resolver(actions))
    app = App(doc, window=Window(View()), actions=actions)
    monkeypatch.setattr(rs, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))

    monkeypatch.setattr(parent, "addChildNode", _merge_watcher(parent, doc, merge, active))
    monkeypatch.setattr(rs, "create_incremental_layer", lambda d, layer, view=None: None)

    result = rs.execute_refine_sketch()

    assert result[0] is False
    assert "could not be created" in result[1]
    assert not wire["info"]


def _run_full_refine(monkeypatch, duplicate_reflay=False, active_node=None, view=None):
    active = active_node if active_node is not None else Node("ink", empty=False)
    parent = Group("parent", [active, Node("WHITE", locked=True)])
    doc = Doc(active, root=parent)
    view = view or View()
    reset = Action()
    merge = Action()
    actions = {
        "reset_fg_bg": reset,
        "layer_merge_down": merge,
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
    monkeypatch.setattr(rs.random, "random", lambda: 0.25)
    # Every merge-down really consumes the layer it was given.
    monkeypatch.setattr(parent, "addChildNode", _merge_watcher(parent, doc, merge, active))
    monkeypatch.setattr(rs, "create_incremental_layer", lambda d, layer, view=None: new_layer)
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
    monkeypatch.setattr(rs, "log_warning", lambda *a: wire.setdefault("warn", []).append(a))

    result = rs.execute_refine_sketch(duplicate_reflay=duplicate_reflay)

    return doc, active, parent, view, reset, new_layer, preset, logs, wire, result


def test_refine_full_flow(monkeypatch):
    doc, active, parent, view, reset, new_layer, preset, logs, wire, result = _run_full_refine(
        monkeypatch
    )
    assert result is True, "a clean run must report success"
    assert active._alpha_locked is True
    assert active._pixel is not None, "HSL byte fill must have run"
    assert doc.active[-1] is new_layer
    assert view.resources == [preset]
    assert reset.triggered == 1
    assert logs
    names = [c.name() for c in parent._children]
    assert names.count("WHITE") == 1


def test_refine_full_flow_with_duplicate_reflay(monkeypatch):
    doc, active, parent, view, reset, new_layer, preset, logs, wire, result = _run_full_refine(
        monkeypatch, duplicate_reflay=True
    )
    assert result is True
    assert len(doc.active) > 1
    assert doc.refreshed >= 2


def test_refine_alpha_lock_error_logs_warning(monkeypatch):
    class _BoomAlpha(Node):
        def setAlphaLocked(self, v):
            raise RuntimeError("alpha lock fail")

    *_, wire, result = _run_full_refine(
        monkeypatch, active_node=_BoomAlpha("ink", empty=False)
    )
    assert any("alpha locked" in str(w[1]) for w in wire["warn"])
    assert result is True


def test_refine_brush_activation_error_logs_warning(monkeypatch):
    class _BoomView(View):
        def activateResource(self, preset):
            raise RuntimeError("activate fail")

    *_, wire, result = _run_full_refine(monkeypatch, view=_BoomView())
    assert any("brush preset" in str(w[1]) for w in wire["warn"])
    assert result is True
