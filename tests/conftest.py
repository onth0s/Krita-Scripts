"""
Pytest bootstrap that makes the Krita plugins importable headlessly.

Stand-ins for ``krita`` and PyQt5 are injected into ``sys.modules`` **unconditionally**
-- including on machines where the real PyQt5 is installed. See the block at the
bottom of this file for why that is mandatory rather than merely convenient.
Set ``KRITA_PYTEST_REAL_QT=1`` to opt out and use the real bindings.

Every exposed name is the same ``_QtWidgetStub`` class: subclassing works
(``class PieMenuWidget(QWidget)``), instances accept any constructor signature,
and unknown attributes / enum members (``Qt.FramelessWindowHint``,
``QPainter.Antialiasing``) resolve via metaclass/instance ``__getattr__`` to a
callable ``_Stub``. Pure-logic tests can then construct widgets and exercise
flow control without a Qt event loop.
"""
import os
import sys
from types import ModuleType

# Plain `pytest` does not add the repo root to sys.path (only `python -m pytest`
# does). Insert it so `import krita_pie_menu` / `operations_pie_menu` resolve
# identically on CI and locally regardless of how pytest was launched.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


class _Stub:
    """Stand-in for enum members and unknown attributes; no-ops and returns itself."""

    def __getattr__(self, name):
        return _Stub()

    def __call__(self, *args, **kwargs):
        return _Stub()

    def __or__(self, other):
        return self

    def __ror__(self, other):
        return self

    def __xor__(self, other):
        return self

    def __rxor__(self, other):
        return self

    def __and__(self, other):
        return self

    def __rand__(self, other):
        return self

    # Qt geometry math mixes enum-typed values with ints (e.g. cursor pos math);
    # allow any arithmetic so stub-backed code paths run through to the asserts.
    def __add__(self, other):
        return self

    def __radd__(self, other):
        return self

    def __sub__(self, other):
        return self

    def __rsub__(self, other):
        return self

    def __mul__(self, other):
        return self

    def __rmul__(self, other):
        return self

    def __truediv__(self, other):
        return self

    def __rtruediv__(self, other):
        return self

    def __neg__(self):
        return self

    def __lt__(self, other):
        return False

    def __le__(self, other):
        return False

    def __gt__(self, other):
        return False

    def __ge__(self, other):
        return False

    def __int__(self):
        return 0

    def __bool__(self):
        return False

    def __eq__(self, other):
        return self is other

    def __ne__(self, other):
        return self is not other


class _StubMeta(type):
    def __getattr__(cls, name):
        return _Stub()


class _QtWidgetStub(metaclass=_StubMeta):
    """Real class stand-in for every Qt/krita widget, dialog, timer and base type."""

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return _Stub()


# True when the stub path is active (i.e. KRITA_PYTEST_REAL_QT is not "1").
# Read by _register so a real module that landed in sys.modules before conftest
# ran is replaced rather than silently kept.
_USE_STUBS = os.environ.get("KRITA_PYTEST_REAL_QT") != "1"


def _register(module_name, names, force=None):
    mod = ModuleType(module_name)
    for name in names:
        setattr(mod, name, _QtWidgetStub)
    if force if force is not None else _USE_STUBS:
        # Drop any real module that slipped into sys.modules before conftest ran
        # (e.g. an installed pytest plugin importing PyQt5). `setdefault` alone
        # would silently leave the real Qt in place and reintroduce the crash.
        sys.modules.pop(module_name, None)
        parent, _, leaf = module_name.rpartition(".")
        if parent in sys.modules:
            setattr(sys.modules[parent], leaf, mod)
    sys.modules.setdefault(module_name, mod)


def _install_krita_stub():
    _register(
        "krita",
        [
            "Krita",
            "ManagedColor",
            "Extension",
            "DockWidget",
            "DockWidgetFactory",
            "DockWidgetFactoryBase",
        ],
    )


def _install_pyqt5_stubs():
    _register(
        "PyQt5.QtCore",
        ["QPoint", "QRect", "Qt", "QEasingCurve", "QPropertyAnimation", "QTimer", "QByteArray"],
    )
    _register(
        "PyQt5.QtGui",
        ["QBrush", "QColor", "QCursor", "QFont", "QPainter", "QPainterPath", "QPen", "QImage"],
    )
    _register(
        "PyQt5.QtWidgets",
        [
            "QApplication",
            "QCheckBox",
            "QComboBox",
            "QDialog",
            "QDockWidget",
            "QGridLayout",
            "QGraphicsOpacityEffect",
            "QHBoxLayout",
            "QLabel",
            "QLineEdit",
            "QMainWindow",
            "QMessageBox",
            "QPushButton",
            "QVBoxLayout",
            "QWidget",
        ],
    )


if _USE_STUBS:
    # The stubs are installed UNCONDITIONALLY, even when PyQt5 is importable.
    #
    # Constructing any QWidget subclass before a QApplication exists does not
    # raise the documented "Must construct a QApplication before a QWidget"
    # RuntimeError -- it aborts the interpreter via __fastfail (0xC0000409).
    # Verified for QWidget, QDialog, QPushButton, QLabel and QMessageBox.
    # QDockWidget additionally raises TypeError when handed a stub as a parent.
    #
    # So a machine that has PyQt5 installed (i.e. every Krita developer) would
    # crash rather than run. This suite is pure logic: config persistence, layer
    # tree semantics, dispatch control flow. It never needs real rendering, and
    # real Qt is not "more realistic" here, it is strictly incompatible.
    _install_pyqt5_stubs()
    _install_krita_stub()
