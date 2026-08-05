"""Shared fake Krita layer-tree primitives for headless operation tests."""


class Bounds:
    def __init__(self, x, y, w, h):
        self._v = (x, y, w, h)

    def x(self):
        return self._v[0]

    def y(self):
        return self._v[1]

    def width(self):
        return self._v[2]

    def height(self):
        return self._v[3]


class Node:
    def __init__(self, name, ntype="paintlayer", empty=True, locked=False):
        self._name = name
        self._type = ntype
        self._empty = empty
        self._locked = locked
        self._visible = True
        self._bounds = Bounds(0, 0, 2, 2)
        self._parent = None
        self._opacity = 255
        self._pixel = None
        self._blending = None
        self._alpha_locked = None
        self._inherit_alpha = None
        self.removed = False

    def name(self):
        return self._name

    def setName(self, n):
        self._name = n

    def type(self):
        return self._type

    def locked(self):
        return self._locked

    def setLocked(self, v):
        self._locked = v

    def visible(self):
        return self._visible

    def setVisible(self, v):
        self._visible = v

    def bounds(self):
        return self._bounds

    def parentNode(self):
        return self._parent

    def childNodes(self):
        return []

    def remove(self):
        self.removed = True
        if self._parent is not None:
            self._parent._children.remove(self)

    def duplicate(self):
        dup = Node(self._name + "_copy", self._type, empty=self._empty, locked=self._locked)
        dup._bounds = self._bounds
        return dup

    def setAlphaLocked(self, v):
        self._alpha_locked = v

    def setOpacity(self, v):
        self._opacity = v

    def setBlendingMode(self, mode):
        self._blending = mode

    def setInheritAlpha(self, v):
        self._inherit_alpha = v

    def setPixelData(self, *args):
        self._pixel = args

    def pixelData(self, x, y, w, h):
        if self._pixel is not None:
            return bytes(self._pixel[0])
        return b"\xff" * (w * h * 4)


class Group(Node):
    def __init__(self, name, children):
        super().__init__(name, ntype="grouplayer")
        self._children = list(children)
        for child in self._children:
            child._parent = self

    def childNodes(self):
        return list(self._children)

    def addChildNode(self, node, reference):
        node._parent = self
        if reference is None:
            self._children.append(node)
        else:
            idx = self._children.index(reference)
            self._children.insert(idx + 1, node)

    def projectionPixelData(self, x, y, w, h):
        return bytes(range(w * h * 4))


class Selection:
    def __init__(self, width, height):
        self._w = width
        self._h = height

    def width(self):
        return self._w

    def height(self):
        return self._h


class Doc:
    def __init__(self, node, root=None):
        self._node = node
        self._root = root if root is not None else Group("root", [node] if node else [])
        self.created = []
        self.active = []
        self.refreshed = 0
        self._selection = None
        self._u8rgba = True
        self._color_depth = "U8"
        self.done_waits = 0

    def activeNode(self):
        return self._node

    def rootNode(self):
        return self._root

    def topLevelNodes(self):
        return list(self._root.childNodes())

    def createNode(self, name, ntype):
        n = Node(name, ntype)
        self.created.append(n)
        return n

    def createGroupLayer(self, name):
        g = Group(name, [])
        self.created.append(g)
        return g

    def setActiveNode(self, node):
        self.active.append(node)
        self._node = node

    def refreshProjection(self):
        self.refreshed += 1

    def waitForDone(self):
        self.done_waits += 1

    def width(self):
        return 4

    def height(self):
        return 4

    def colorModel(self):
        return "RGBA"

    def colorDepth(self):
        return self._color_depth

    def selection(self):
        return self._selection

    def setSelection(self, sel):
        self._selection = sel


class Action:
    def __init__(self, checked=False):
        self.checked = checked
        self.triggered = 0

    def isChecked(self):
        return self.checked

    def trigger(self):
        self.triggered += 1


class View:
    def __init__(self):
        self.active_nodes = []
        self.resources = []

    def setActiveNode(self, node):
        self.active_nodes.append(node)

    def activateResource(self, preset):
        self.resources.append(preset)


class Window:
    def __init__(self, view=None):
        self._view = view

    def activeView(self):
        return self._view


class App:
    def __init__(self, doc=None, window=None, actions=None):
        self._doc = doc
        self._window = window
        self.actions = actions or {}

    def activeDocument(self):
        return self._doc

    def activeWindow(self):
        return self._window

    def action(self, name):
        return self.actions.get(name)


def make_resolver(actions):
    """Return a `resolve_action` stand-in backed by a {action_id: Action} map."""
    return lambda app, ids: actions.get(ids[0])
