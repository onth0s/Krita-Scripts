import pytest

from operations_pie_menu.operations import (
    bw_preview,
    duplicate_layer,
    fit_layer,
    init_canvas,
    merge_to_black,
    refine_sketch,
    sanitize_group,
)


class _Node:
    def __init__(self, node_type="paintlayer", parent=None, name="L", locked=False, width=100, height=100):
        self._type = node_type
        self._parent = parent
        self._name = name
        self._locked = locked
        self._w = width
        self._h = height

    def type(self):
        return self._type

    def parentNode(self):
        return self._parent

    def name(self):
        return self._name

    def locked(self):
        return self._locked

    def bounds(self):
        return _Bounds(self._w, self._h)


class _Bounds:
    def __init__(self, w, h):
        self._w = w
        self._h = h

    def width(self):
        return self._w

    def height(self):
        return self._h


class _Doc:
    def __init__(self, node=None, color_model="RGBA", color_depth="U8"):
        self._node = node
        self._cm = color_model
        self._cd = color_depth

    def activeNode(self):
        return self._node

    def colorModel(self):
        return self._cm

    def colorDepth(self):
        return self._cd


class _App:
    def __init__(self, doc=None):
        self._doc = doc

    def activeDocument(self):
        return self._doc


def _patch_app(monkeypatch, module, doc):
    monkeypatch.setattr(module.Krita, "instance", staticmethod(lambda: _App(doc)))


def _assert_validator(monkeypatch, module, validator_name, doc, expected_ok):
    _patch_app(monkeypatch, module, doc)
    ok, reason = getattr(module, validator_name)()
    assert ok is expected_ok
    assert isinstance(reason, str)


# ---- plain make_doc_active_validator() operations ---------------------------

@pytest.mark.parametrize(
    "module,validator_name",
    [
        (bw_preview, "validate_bw_preview"),
        (duplicate_layer, "validate_duplicate_layer"),
        (fit_layer, "validate_fit_layer"),
        (init_canvas, "validate_init_canvas"),
    ],
)
def test_simple_validators_require_doc_and_layer(monkeypatch, module, validator_name):
    _assert_validator(monkeypatch, module, validator_name, None, expected_ok=False)
    _assert_validator(monkeypatch, module, validator_name, _Doc(node=None), expected_ok=False)
    _assert_validator(monkeypatch, module, validator_name, _Doc(node=_Node()), expected_ok=True)


# ---- refine_sketch -----------------------------------------------------------

def test_validate_refine_sketch(monkeypatch):
    v = "validate_refine_sketch"
    _assert_validator(monkeypatch, refine_sketch, v, None, expected_ok=False)
    _assert_validator(monkeypatch, refine_sketch, v, _Doc(node=_Node("grouplayer")), expected_ok=False)
    _assert_validator(monkeypatch, refine_sketch, v, _Doc(node=_Node("paintlayer", width=0, height=0)), expected_ok=False)
    _assert_validator(monkeypatch, refine_sketch, v, _Doc(node=_Node()), expected_ok=True)


# ---- merge_to_black ----------------------------------------------------------

def test_validate_merge_to_black(monkeypatch):
    v = "validate_merge_to_black"
    _assert_validator(monkeypatch, merge_to_black, v, None, expected_ok=False)
    _assert_validator(monkeypatch, merge_to_black, v, _Doc(node=_Node("grouplayer")), expected_ok=True)
    group = _Node("grouplayer")
    inside = _Node("paintlayer", parent=group)
    _assert_validator(monkeypatch, merge_to_black, v, _Doc(node=inside), expected_ok=True)
    _assert_validator(monkeypatch, merge_to_black, v, _Doc(node=_Node("paintlayer")), expected_ok=False)


def test_is_preserved_node():
    assert merge_to_black._is_preserved(_Node(name="WHITE")) is True
    assert merge_to_black._is_preserved(_Node(name="B&W")) is True
    assert merge_to_black._is_preserved(_Node(locked=True)) is True
    assert merge_to_black._is_preserved(_Node()) is False


# ---- sanitize_group -----------------------------------------------------------

def test_validate_sanitize_group(monkeypatch):
    _assert_validator(monkeypatch, sanitize_group, "validate_sanitize_group", None, expected_ok=False)
    _assert_validator(monkeypatch, sanitize_group, "validate_sanitize_group", _Doc(node=None), expected_ok=False)
    _assert_validator(monkeypatch, sanitize_group, "validate_sanitize_group", _Doc(node=_Node("grouplayer")), expected_ok=True)
    group = _Node("grouplayer")
    inside = _Node("paintlayer", parent=group)
    _assert_validator(monkeypatch, sanitize_group, "validate_sanitize_group", _Doc(node=inside), expected_ok=True)
    _assert_validator(monkeypatch, sanitize_group, "validate_sanitize_group", _Doc(node=_Node("paintlayer")), expected_ok=False)


# ---- execute guards (H1/H2: early returns before any mutation) --------------

@pytest.fixture
def qmessage_warning(monkeypatch):
    calls = []
    for module in (fit_layer, merge_to_black):
        monkeypatch.setattr(module.QMessageBox, "warning", staticmethod(lambda *a, **k: calls.append(a)))
        monkeypatch.setattr(module.QMessageBox, "information", staticmethod(lambda *a, **k: calls.append(a)))
    return calls


@pytest.mark.parametrize(
    "module,execute_name",
    [(fit_layer, "execute_fit_layer"), (merge_to_black, "execute_merge_to_black")],
)
def test_execute_guard_no_doc(monkeypatch, qmessage_warning, module, execute_name):
    _patch_app(monkeypatch, module, None)
    getattr(module, execute_name)()
    assert len(qmessage_warning) == 1


@pytest.mark.parametrize(
    "module,execute_name",
    [(fit_layer, "execute_fit_layer"), (merge_to_black, "execute_merge_to_black")],
)
def test_execute_guard_no_node(monkeypatch, qmessage_warning, module, execute_name):
    _patch_app(monkeypatch, module, _Doc(node=None))
    getattr(module, execute_name)()
    assert len(qmessage_warning) == 1


@pytest.mark.parametrize(
    "module,execute_name",
    [(fit_layer, "execute_fit_layer"), (merge_to_black, "execute_merge_to_black")],
)
def test_execute_guard_non_u8_returns_early(monkeypatch, qmessage_warning, module, execute_name):
    logged = []
    monkeypatch.setattr(module, "log_warning", lambda *a: logged.append(a))
    _patch_app(monkeypatch, module, _Doc(node=_Node(), color_model="CMYK", color_depth="U8"))
    getattr(module, execute_name)()
    assert len(qmessage_warning) == 1
    assert any("8-bit RGBA" in str(call) for call in qmessage_warning)
    assert len(logged) == 1
