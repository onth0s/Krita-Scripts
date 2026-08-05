import json

from krita_pie_menu import utils


class _FakeBounds:
    def __init__(self, width, height):
        self._w = width
        self._h = height

    def width(self):
        return self._w

    def height(self):
        return self._h


class _FakeNode:
    def __init__(self, name, node_type="paintlayer", width=100, height=100):
        self._name = name
        self._type = node_type
        self.bounds = lambda: _FakeBounds(width, height)

    def name(self):
        return self._name

    def type(self):
        return self._type


class _FakeDoc:
    def __init__(self, color_model="RGBA", color_depth="U8"):
        self._cm = color_model
        self._cd = color_depth

    def colorModel(self):
        return self._cm

    def colorDepth(self):
        return self._cd


def test_is_protected_layer():
    assert utils.is_protected_layer(_FakeNode("WHITE"))
    assert utils.is_protected_layer(_FakeNode("  b&w "))
    assert utils.is_protected_layer(_FakeNode("LINES"))
    assert not utils.is_protected_layer(_FakeNode("sketch"))
    assert not utils.is_protected_layer(None)


def test_is_u8_rgba():
    assert utils.is_u8_rgba(_FakeDoc("RGBA", "U8"))
    assert not utils.is_u8_rgba(_FakeDoc("RGBA", "U16"))
    assert not utils.is_u8_rgba(_FakeDoc("CMYK", "U8"))
    assert not utils.is_u8_rgba(None)


def test_is_empty_paint_layer():
    assert utils.is_empty_paint_layer(_FakeNode("empty", width=0, height=0))
    assert utils.is_empty_paint_layer(_FakeNode("empty", width=5, height=0))
    assert not utils.is_empty_paint_layer(_FakeNode("drawn", width=100, height=100))
    assert not utils.is_empty_paint_layer(_FakeNode("group", node_type="group", width=0, height=0))
    assert not utils.is_empty_paint_layer(None)


def test_get_incremental_layer_name():
    assert utils.get_incremental_layer_name("sketch_3") == "4"
    assert utils.get_incremental_layer_name("v10.2") == "3"
    assert utils.get_incremental_layer_name("untitled") == "1"
    assert utils.get_incremental_layer_name("  ") == "1"


def test_load_config_deep_merges_defaults(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"sector": {"new_key": "file_value"}}), encoding="utf-8")
    defaults = {
        "sector": {
            "new_key": "default_value",
            "surviving_key": "default",
        },
        "missing_key": "from_defaults",
    }
    loaded = utils.load_config(str(cfg), defaults)
    assert loaded["sector"]["new_key"] == "file_value"
    assert loaded["sector"]["surviving_key"] == "default"
    assert loaded["missing_key"] == "from_defaults"


def test_load_config_missing_file_returns_defaults(tmp_path):
    defaults = {"a": 1, "b": {"c": 2}}
    assert utils.load_config(str(tmp_path / "nope.json"), defaults) == defaults


def test_load_config_unreadable_file_returns_defaults(tmp_path):
    cfg = tmp_path / "bad.json"
    cfg.write_text("{ not json", encoding="utf-8")
    defaults = {"a": 1}
    assert utils.load_config(str(cfg), defaults) == defaults


def test_condition_flag_roundtrip(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    monkeypatch.setattr(utils, "CONDITIONS_CONFIG_PATH", str(cfg))

    assert utils.get_condition_flag("duplicate_reflay") is False
    utils.save_config(str(cfg), {"duplicate_reflay": True, "other": 1})
    assert utils.get_condition_flag("duplicate_reflay") is True
    assert utils.read_condition_flag("other", default=9) == 1
    assert utils.read_condition_flag("missing", default=True) is True


def test_save_config_creates_parent_dirs(tmp_path):
    target = tmp_path / "nested" / "deep" / "config.json"
    assert utils.save_config(str(target), {"k": "v"}) is True
    assert json.loads(target.read_text(encoding="utf-8")) == {"k": "v"}
