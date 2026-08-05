import pytest
from fakes import Action, App, Doc, Group, Node, View, Window, make_resolver

from operations_pie_menu.operations import init_canvas as ic

YES, NO = 1, 0


@pytest.fixture
def warnings(monkeypatch):
    calls = []
    monkeypatch.setattr(ic.QMessageBox, "warning", staticmethod(lambda *a, **k: calls.append(a)))
    return calls


def _wire(monkeypatch, answer=YES):
    monkeypatch.setattr(ic.QMessageBox, "Yes", YES)
    monkeypatch.setattr(ic.QMessageBox, "No", NO)
    monkeypatch.setattr(
        ic.QMessageBox, "question", staticmethod(lambda *a, **k: answer)
    )
    monkeypatch.setattr(ic, "QByteArray", lambda data: data)
    logged = {"info": [], "warning": [], "error": []}
    monkeypatch.setattr(ic, "log_info", lambda *a: logged["info"].append(a))
    monkeypatch.setattr(ic, "log_warning", lambda *a: logged["warning"].append(a))
    monkeypatch.setattr(ic, "log_error", lambda *a: logged["error"].append(a))
    return logged


def _base_doc(children):
    root = Group("root", children)
    first = children[0] if children else None
    doc = Doc(first, root=root)
    return doc, root


def test_init_no_doc(monkeypatch, warnings):
    monkeypatch.setattr(ic, "Krita", type("_S", (), {"instance": staticmethod(lambda: App(None))}))
    ic.execute_init_canvas()
    assert len(warnings) == 1


def test_init_nuke_declined(monkeypatch):
    doc, root = _base_doc([Node("a"), Node("b")])
    logged = _wire(monkeypatch, answer=NO)
    app = App(doc)
    monkeypatch.setattr(ic, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))

    ic.execute_init_canvas()

    assert not logged["info"], "must abort when user declines nuke"
    assert [c.name() for c in root.childNodes()] == ["a", "b"]


def test_init_nuke_accepted(monkeypatch):
    doc, root = _base_doc([Node("a"), Node("b")])
    logged = _wire(monkeypatch, answer=YES)
    reset = Action()
    actions = {"reset_fg_bg": reset}
    view = View()
    app = App(doc, window=Window(view), actions=actions)
    monkeypatch.setattr(ic, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))
    monkeypatch.setattr(ic, "resolve_action", make_resolver({}))
    monkeypatch.setattr(ic, "set_foreground_black", lambda d, v: None)
    monkeypatch.setattr(ic, "find_brush_preset", lambda a, n: None)

    ic.execute_init_canvas()

    # old nodes purged, fresh WHITE + LINES group with layer '1' remain
    assert [c.name() for c in root.childNodes()] == ["WHITE", "LINES"]
    assert logged["info"]
    white = [n for n in doc.created if n.name() == "WHITE"][0]
    assert white._opacity == 191 and white._locked is True
    lines = [n for n in doc.created if n.name() == "LINES"][0]
    layer1 = [n for n in doc.created if n.name() == "1"][0]
    assert layer1._parent is lines and layer1._opacity == 255
    assert doc.active[-1] is layer1
    assert reset.triggered == 1


def test_init_single_white_node(monkeypatch):
    white = Node("WHITE", locked=True)
    doc, root = _base_doc([white])
    logged = _wire(monkeypatch, answer=NO)
    app = App(doc)
    monkeypatch.setattr(ic, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))
    monkeypatch.setattr(ic, "resolve_action", make_resolver({}))
    monkeypatch.setattr(ic, "set_foreground_black", lambda d, v: None)
    monkeypatch.setattr(ic, "find_brush_preset", lambda a, n: None)

    ic.execute_init_canvas()

    assert logged["info"]
    assert white.name() == "WHITE"
    assert white._locked is True and white._opacity == 191
    layer1 = [n for n in doc.created if n.name() == "1"][0]
    assert doc.active[-1] is layer1


def test_init_single_node_replace_declined(monkeypatch):
    ink = Node("ink", locked=True)
    doc, root = _base_doc([ink])
    logged = _wire(monkeypatch, answer=NO)
    app = App(doc)
    monkeypatch.setattr(ic, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))

    ic.execute_init_canvas()

    assert not logged["info"]
    assert ink.name() == "ink"


def test_init_single_node_replace_accepted(monkeypatch):
    ink = Node("ink", locked=True)
    doc, root = _base_doc([ink])
    logged = _wire(monkeypatch, answer=YES)
    app = App(doc)
    monkeypatch.setattr(ic, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))
    monkeypatch.setattr(ic, "resolve_action", make_resolver({}))
    monkeypatch.setattr(ic, "set_foreground_black", lambda d, v: None)
    monkeypatch.setattr(ic, "find_brush_preset", lambda a, n: None)

    ic.execute_init_canvas()

    assert logged["info"]
    assert ink.name() == "WHITE"
    assert ink._opacity == 191 and ink._locked is True


def test_init_nuke_error_logs_warning(monkeypatch):
    class _Boom(Node):
        def __init__(self, name):
            super().__init__(name)
            self.lock_calls = 0

        def setLocked(self, v):
            self.lock_calls += 1
            if self.lock_calls == 1:
                raise RuntimeError("lock fail")
            super().setLocked(v)

    a = _Boom("a")
    b = Node("b")
    doc, root = _base_doc([a, b])
    logged = _wire(monkeypatch, answer=YES)
    app = App(doc)
    monkeypatch.setattr(ic, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))
    monkeypatch.setattr(ic, "resolve_action", make_resolver({}))
    monkeypatch.setattr(ic, "set_foreground_black", lambda d, v: None)
    monkeypatch.setattr(ic, "find_brush_preset", lambda a, n: None)

    ic.execute_init_canvas()

    assert logged["warning"]
    assert logged["info"]


def test_init_brush_preset_activation_error(monkeypatch):
    class _BoomView(View):
        def activateResource(self, preset):
            raise RuntimeError("activate fail")

    doc, root = _base_doc([Node("WHITE", locked=True)])
    logged = _wire(monkeypatch)
    app = App(doc, window=Window(_BoomView()))
    monkeypatch.setattr(ic, "Krita", type("_S", (), {"instance": staticmethod(lambda: app)}))
    monkeypatch.setattr(ic, "resolve_action", make_resolver({}))
    monkeypatch.setattr(ic, "set_foreground_black", lambda d, v: None)
    monkeypatch.setattr(ic, "find_brush_preset", lambda a, n: object())

    ic.execute_init_canvas()

    assert logged["warning"]
    assert logged["info"]
