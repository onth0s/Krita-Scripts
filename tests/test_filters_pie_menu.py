
from filters_pie_menu.config_dialog import FILTER_OPTIONS
from filters_pie_menu.filters_pie_menu import DEFAULT_FILTERS_CONFIG, FiltersPieMenuExtension, _filter_extra_checks
from krita_pie_menu import SECTOR_CODES


class _Node:
    def __init__(self, node_type):
        self._type = node_type

    def type(self):
        return self._type


class _Doc:
    def __init__(self, node=None):
        self._node = node

    def activeNode(self):
        return self._node


class _App:
    def __init__(self, doc=None, actions=None):
        self._doc = doc
        self._actions = actions or {}

    def activeDocument(self):
        return self._doc

    def action(self, act_id):
        return self._actions.get(act_id)


def test_default_config_ids_are_prefixed_and_known():
    known_ids = {known_id for _, known_id in FILTER_OPTIONS}
    for code in SECTOR_CODES:
        act_id = DEFAULT_FILTERS_CONFIG[code]["action_id"]
        assert act_id.startswith("krita_filter_")
        assert act_id in known_ids


def test_filter_extra_checks_rejects_groups():
    ok, reason = _filter_extra_checks(_Doc(), _Node("grouplayer"))
    assert ok is False
    assert "Group" in reason
    ok, _ = _filter_extra_checks(_Doc(), _Node("paintlayer"))
    assert ok is True


def test_trigger_action_success(monkeypatch):
    ext = FiltersPieMenuExtension(parent=None)
    triggered = []

    class _Act:
        def trigger(self):
            triggered.append(1)

    app = _App(doc=_Doc(_Node("paintlayer")), actions={"krita_filter_levels": _Act()})
    monkeypatch.setattr("filters_pie_menu.filters_pie_menu.Krita.instance", staticmethod(lambda: app))

    assert ext.trigger_action("krita_filter_levels", "Levels") is True
    assert triggered == [1]


def test_trigger_action_missing_action_returns_false(monkeypatch):
    ext = FiltersPieMenuExtension(parent=None)
    app = _App(doc=_Doc(_Node("paintlayer")))
    monkeypatch.setattr("filters_pie_menu.filters_pie_menu.Krita.instance", staticmethod(lambda: app))

    assert ext.trigger_action("krita_filter_nonexistent", "Nope") is False


def test_trigger_action_group_node_blocked_before_lookup(monkeypatch):
    ext = FiltersPieMenuExtension(parent=None)
    app = _App(doc=_Doc(_Node("grouplayer")))
    monkeypatch.setattr("filters_pie_menu.filters_pie_menu.Krita.instance", staticmethod(lambda: app))

    assert ext.trigger_action("krita_filter_levels", "Levels") is False


def test_trigger_action_does_not_scan_app_actions(monkeypatch):
    # Regression: the old fallback scanned app.actions(); ensure a fake app
    # without that attribute is never touched (only app.action(id) is probed).
    ext = FiltersPieMenuExtension(parent=None)

    class _NoScanApp(_App):
        pass

    app = _NoScanApp(doc=_Doc(_Node("paintlayer")))
    monkeypatch.setattr("filters_pie_menu.filters_pie_menu.Krita.instance", staticmethod(lambda: app))

    assert ext.trigger_action("krita_filter_does_not_exist_xyz", "Nothing") is False


def test_trigger_action_fallback_synonyms(monkeypatch):
    # "perchannel" (Color Curves) resolves through the FILTER_OPTIONS synonym even
    # when the configured id itself is unknown.
    ext = FiltersPieMenuExtension(parent=None)
    triggered = []

    class _Act:
        def trigger(self):
            triggered.append(1)

    app = _App(doc=_Doc(_Node("paintlayer")), actions={"krita_filter_perchannel": _Act()})
    monkeypatch.setattr("filters_pie_menu.filters_pie_menu.Krita.instance", staticmethod(lambda: app))

    assert ext.trigger_action("krita_filter_curves", "Color Curves") is True
    assert triggered == [1]


def test_make_trigger_callback_returns_bool(monkeypatch):
    ext = FiltersPieMenuExtension(parent=None)
    app = _App(doc=_Doc(_Node("paintlayer")))
    monkeypatch.setattr("filters_pie_menu.filters_pie_menu.Krita.instance", staticmethod(lambda: app))

    cb = ext.make_trigger_callback("krita_filter_nope", "Nope")
    assert callable(cb)
    assert cb() is False


def test_build_pie_config_full_sectors(monkeypatch, tmp_path):
    ext = FiltersPieMenuExtension(parent=None)
    monkeypatch.setattr(ext, "config_path", str(tmp_path / "config.json"))

    callbacks, items_meta, validators, toggle_states = ext.build_pie_config()

    assert set(callbacks) == set(SECTOR_CODES)
    assert set(items_meta) == set(SECTOR_CODES)
    assert set(validators) == set(SECTOR_CODES)
    assert set(toggle_states) == set()


def test_create_actions_registers_both_actions(tmp_path, monkeypatch):
    class _Signal:
        def __init__(self):
            self.cb = None

        def connect(self, cb):
            self.cb = cb

    class _Action:
        def __init__(self):
            self.triggered = _Signal()

    created = []

    class _Win:
        def createAction(self, aid, text, category):
            created.append((aid, text, category))
            return _Action()

    ext = FiltersPieMenuExtension(parent=None)
    monkeypatch.setattr(ext, "config_path", str(tmp_path / "config.json"))
    ext.createActions(_Win())

    assert created == [
        ("trigger_filters_pie_menu", "Filters Pie Menu", "tools/scripts"),
        ("configure_filters_pie_menu", "Configure Filters Pie Menu", "tools/scripts"),
    ]


def test_open_config_dialog_constructs_and_executes(tmp_path, monkeypatch):
    import filters_pie_menu.filters_pie_menu as fmod

    ext = FiltersPieMenuExtension(parent=None)
    monkeypatch.setattr(ext, "config_path", str(tmp_path / "config.json"))
    executed = []

    class _Dlg:
        def __init__(self, path, on_save_callback=None):
            self.path = path

        def exec_(self):
            executed.append(self.path)

    monkeypatch.setattr(fmod, "SectorConfigDialog", _Dlg)
    ext.open_config_dialog()

    assert len(executed) == 1
    assert executed[0].endswith("config.json")
