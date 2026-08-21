"""
Pytest bootstrap that makes the Krita plugins importable headlessly.

When run inside Krita the real ``krita`` and PyQt5 modules are used. When run
from a plain interpreter (CI / local), minimal stand-ins are injected into
``sys.modules`` so that only *imports* resolve.

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


def _register(module_name, names):
    mod = ModuleType(module_name)
    for name in names:
        setattr(mod, name, _QtWidgetStub)
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


try:
    import PyQt5.QtWidgets  # noqa: F401
except ImportError:
    _install_pyqt5_stubs()

try:
    import krita  # noqa: F401
except ImportError:
    _install_krita_stub()
