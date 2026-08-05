
import dummy_docker.dummy_docker as dd
from dummy_docker.dummy_docker import DummyDocker


class _Signal:
    def connect(self, cb):
        self.cb = cb


class _Label:
    def __init__(self, *args, **kwargs):
        self.texts = []

    def setText(self, text):
        self.texts.append(text)


class _Btn:
    def __init__(self, *args, **kwargs):
        self.clicked = _Signal()


class _Doc:
    def __init__(self, node=None):
        self._node = node

    def activeNode(self):
        return self._node


class _App:
    def __init__(self, doc=None):
        self._doc = doc

    def activeDocument(self):
        return self._doc


def _docker(monkeypatch, app=None):
    monkeypatch.setattr(dd, "QLabel", _Label)
    monkeypatch.setattr(dd, "QPushButton", _Btn)
    if app is not None:
        monkeypatch.setattr(dd.Krita, "instance", staticmethod(lambda: app))
    return DummyDocker()


def test_init_builds_widgets(monkeypatch):
    d = _docker(monkeypatch)
    assert isinstance(d.info_label, _Label)
    assert isinstance(d.action_button, _Btn)
    assert d.action_button.clicked.cb == d.on_btn_click


def test_canvas_changed_none(monkeypatch):
    d = _docker(monkeypatch)
    d.canvasChanged(None)
    assert d.info_label.texts == ["Canvas: None"]


def test_canvas_changed_with_doc(monkeypatch):
    class _SizedDoc(_Doc):
        def width(self):
            return 12

        def height(self):
            return 34

    d = _docker(monkeypatch, _App(_SizedDoc()))
    d.canvasChanged(object())
    assert d.info_label.texts == ["Canvas Active: 12x34 px"]


def test_canvas_changed_no_doc(monkeypatch):
    d = _docker(monkeypatch, _App())
    d.canvasChanged(object())
    assert d.info_label.texts == ["Canvas Ready"]


def test_on_btn_click_no_document(monkeypatch):
    d = _docker(monkeypatch, _App())
    d.on_btn_click()
    assert d.info_label.texts == ["Status: No Active Document"]


def test_on_btn_click_with_node(monkeypatch):
    class _Node:
        def name(self):
            return "Ink"

    d = _docker(monkeypatch, _App(_Doc(_Node())))
    d.on_btn_click()
    assert d.info_label.texts == ["Active Layer: Ink"]


def test_on_btn_click_without_node(monkeypatch):
    d = _docker(monkeypatch, _App(_Doc()))
    d.on_btn_click()
    assert d.info_label.texts == ["Active Layer: None"]
