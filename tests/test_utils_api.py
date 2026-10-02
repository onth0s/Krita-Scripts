
import pytest

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
    def __init__(self, ok=True):
        self.added = []
        self.ok = ok

    def addChildNode(self, node, reference_node):
        # Mirrors libkis: returns bool, False when adding the node failed.
        if not self.ok:
            return False
        self.added.append((node, reference_node))
        return True


class _FakeView:
    def __init__(self):
        self.active_nodes = []
        self.boom = False

    def setActiveNode(self, node):
        if self.boom:
            raise RuntimeError("view gone")
        self.active_nodes.append(node)


class _FakeDoc:
    def __init__(self, active_node=None, root=None):
        self._active = active_node
        self._root = root if root is not None else _FakeParent()
        self.created = []
        self.refreshed = 0
        self.active_set = []

    def activeNode(self):
        return self._active

    def rootNode(self):
        return self._root

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


def test_create_incremental_layer_falls_back_to_root_node():
    doc = _FakeDoc()
    ref = _FakeNode("sketch_3")  # no parent -> parentNode() returns None
    created = utils.create_incremental_layer(doc, ref)

    assert created.name() == "4"
    assert doc.active_set == [created]
    assert doc.refreshed == 1


def test_create_incremental_layer_syncs_view_when_supplied():
    doc = _FakeDoc()
    parent = _FakeParent()
    ref = _FakeNode("sketch_3")
    ref.setParent(parent)
    view = _FakeView()

    created = utils.create_incremental_layer(doc, ref, view=view)

    assert view.active_nodes == [created], "merge-down acts on the view's active node"


def test_create_incremental_layer_swallows_view_error():
    doc = _FakeDoc()
    parent = _FakeParent()
    ref = _FakeNode("sketch_3")
    ref.setParent(parent)
    view = _FakeView()
    view.boom = True

    created = utils.create_incremental_layer(doc, ref, view=view)

    assert created is not None
    assert doc.active_set == [created]


def test_create_incremental_layer_returns_none_when_parenting_fails(monkeypatch):
    warned = []
    monkeypatch.setattr(utils, "log_warning", lambda mod, msg: warned.append(msg))

    doc = _FakeDoc()
    parent = _FakeParent(ok=False)
    ref = _FakeNode("sketch_3")
    ref.setParent(parent)

    assert utils.create_incremental_layer(doc, ref) is None
    assert doc.active_set == [], "must not activate a layer that was never parented"
    assert warned


def test_create_incremental_layer_returns_none_when_no_parent_anywhere():
    class _NoParent(_FakeNode):
        def parentNode(self):
            return None

    doc = _FakeDoc(root=None)
    doc._root = None
    ref = _NoParent("sketch_3")
    assert utils.create_incremental_layer(doc, ref) is None


# ── sibling numbering: keeps_layer_name / numbered_sibling_name ───────────────


@pytest.mark.parametrize(
    "name,expected",
    [
        ("INK", True),
        ("CANAL A", True),
        ("REFLAY 2", True),
        ("A1", True),
        ("ink", False),
        ("Ink", False),
        ("refLay 2", False),
        ("_top_", False),
        # No a-z character at all -> nothing to preserve, so no "1_1".
        ("1", False),
        ("23", False),
        ("_", False),
        ("", False),
        # Strictly ASCII a-z: only 'a' in "Ação" disqualifies it, so "AÇÃO" is kept.
        # These fail if the patterns are switched to re.IGNORECASE, which case-folds
        # 'Ç'/'Ã' into the [a-z] range.
        ("Ação", False),
        ("ÇAO", True),
        ("AÇÃO", True),
        ("CANAL AÇÃO", True),
        # Non-ASCII lowercase does not disqualify: only ASCII a-z counts.
        ("CANAL AçãO", True),
    ],
)
def test_keeps_layer_name(name, expected):
    assert utils.keeps_layer_name(name) is expected


@pytest.mark.parametrize(
    "current,index,expected",
    [
        # lowercase anywhere -> bare index
        ("ink", 2, "2"),
        ("Ink", 1, "1"),
        ("refLay 2", 3, "3"),
        ("_top_", 3, "3"),
        # no a-z at all -> bare index
        ("1", 2, "2"),
        ("23", 1, "1"),
        ("", 1, "1"),
        # all a-z capitalized -> keep the name
        ("INK", 2, "2_INK"),
        ("CANAL A", 5, "5_CANAL A"),
        # an old "<digits>_" prefix is replaced, never stacked
        ("1_INK", 2, "2_INK"),
        ("12_INK3", 2, "2_INK3"),
        (" 3_INK ", 4, "4_INK"),
    ],
)
def test_numbered_sibling_name(current, index, expected):
    assert utils.numbered_sibling_name(current, index) == expected


class _Named:
    """Minimal node that records setName calls, so no-ops are observable."""

    def __init__(self, name):
        self._name = name
        self.setname_calls = []

    def name(self):
        return self._name

    def setName(self, name):
        self._name = name
        self.setname_calls.append(name)


def test_renumber_layer_name_renames_when_different():
    node = _Named("ink")
    assert utils.renumber_layer_name(node, 2) is True
    assert node.name() == "2"

    caps = _Named("INK")
    assert utils.renumber_layer_name(caps, 3) is True
    assert caps.name() == "3_INK"


def test_renumber_layer_name_is_a_no_op_when_already_correct():
    """
    "No op as long as it is in the proper index": an already-numbered layer must not
    even be written to, so re-running Refine Sketch cannot churn names.
    """
    node = _Named("2")
    assert utils.renumber_layer_name(node, 2) is False
    assert node.setname_calls == []
    assert node.name() == "2"

    kept = _Named("2_INK")
    assert utils.renumber_layer_name(kept, 2) is False
    assert kept.setname_calls == []


def test_renumber_layer_name_moves_a_kept_name_and_stays_idempotent():
    node = _Named("1_INK")
    assert utils.renumber_layer_name(node, 2) is True
    assert node.name() == "2_INK"

    # Second pass at the same index: no further churn.
    assert utils.renumber_layer_name(node, 2) is False
    assert node.setname_calls == ["2_INK"]


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


def test_resolve_action_accepts_a_falsy_but_real_action():
    """
    A truthiness test would skip a genuine action that defines __bool__/__len__
    and report the far more misleading "not found". A sip wrapper whose C++
    object was destroyed is exactly this shape.
    """

    class _Falsy:
        def __bool__(self):
            return False

    class _App:
        def action(self, act_id):
            return _Falsy() if act_id == "x" else None

    found = utils.resolve_action(_App(), ["x"])
    assert found is not None
    assert isinstance(found, _Falsy)


# ── probe_action_ids: the "why" behind a "not found" ──────────────────────────


def test_probe_reports_absent_id():
    class _App:
        def action(self, act_id):
            return None

    report = utils.probe_action_ids(_App(), ["layer_merge_down"])
    assert report == [("layer_merge_down", "returned None (ID absent from the registry)")]


def test_probe_reports_falsy_non_none_object():
    class _Falsy:
        def __bool__(self):
            return False

    class _App:
        def action(self, act_id):
            return _Falsy()

    (_id, verdict), = utils.probe_action_ids(_App(), ["x"])
    assert "falsy non-None" in verdict


def test_probe_reports_a_raising_lookup():
    class _App:
        def action(self, act_id):
            raise RuntimeError("registry gone")

    (_id, verdict), = utils.probe_action_ids(_App(), ["x"])
    assert "lookup raised RuntimeError: registry gone" in verdict


def test_probe_reports_a_resolved_action():
    from fakes import Action

    class _App:
        def action(self, act_id):
            return Action()

    (_id, verdict), = utils.probe_action_ids(_App(), ["x"])
    assert verdict.startswith("resolved -> ")


def test_probe_falls_back_to_krita_instance(monkeypatch):
    class _Inst:
        def action(self, act_id):
            return None

    monkeypatch.setattr(utils.Krita, "instance", staticmethod(lambda: _Inst()))
    assert utils.probe_action_ids(None, ["x"])[0][0] == "x"


# ── describe_action ───────────────────────────────────────────────────────────


def test_describe_action_uses_objectname_and_text():
    class _Act:
        def objectName(self):
            return "layer_merge_down"

        def text(self):
            return "Merge Down"

    described = utils.describe_action(_Act())
    assert "objectName='layer_merge_down'" in described
    assert "text='Merge Down'" in described


def test_describe_action_tolerates_a_destroyed_cpp_object():
    class _Act:
        def objectName(self):
            raise RuntimeError("wrapped C/C++ object has been deleted")

    assert "objectName=<unavailable>" in utils.describe_action(_Act())


def test_describe_action_falls_back_to_repr_when_nothing_is_readable():
    class _Act:
        pass

    assert "object" in utils.describe_action(_Act())


def test_describe_action_skips_missing_and_empty_attributes():
    class _Act:
        def text(self):
            return ""

    act = _Act()
    assert utils.describe_action(act) == repr(act)


# ── keep_action_alive ─────────────────────────────────────────────────────────


def test_keep_action_alive_pins_the_wrapper():
    import gc

    class _Act:
        pass

    act = _Act()
    utils.keep_action_alive(act)
    pinned = utils._ACTION_KEEPALIVE[id(act)]
    del act
    gc.collect()
    assert pinned is not None, "the strong reference must outlive the caller's binding"


def test_keep_action_alive_ignores_none():
    before = len(utils._ACTION_KEEPALIVE)
    utils.keep_action_alive(None)
    assert len(utils._ACTION_KEEPALIVE) == before


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


def test_find_brush_preset_substring_match():
    class _App:
        def resources(self, kind):
            return {"brush 0 std drw v2": "obj"}

    # exact match misses; target "0 std drw" is a substring of the preset name
    assert utils.find_brush_preset(_App(), "0 STD DRW") == "obj"


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
