import importlib
import os
from typing import List, Tuple

import pytest

# Every plugin module must import cleanly headlessly (conftest stubs krita/PyQt5).
# This catches import-time breakage that compileall/mypy would miss, e.g. the
# extension registrations executed at import time in __init__.py files.
#
# The list is DISCOVERED from disk rather than hand-maintained. A hand-written
# list silently rotted before: krita_pie_menu.sync and all eight modules under
# operations_pie_menu.operations were missing from it, so none of them were
# import-checked. Discovery removes the drift class entirely.
PLUGIN_DIRS = [
    "krita_pie_menu",
    "filters_pie_menu",
    "operations_pie_menu",
    "conditions_pie_menu",
    "quick_script_engine",
    "dummy_docker",
]

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _discover_modules() -> List[str]:
    found: List[str] = []
    for plugin in PLUGIN_DIRS:
        base = os.path.join(_REPO_ROOT, plugin)
        for dirpath, _dirnames, filenames in os.walk(base):
            if "__pycache__" in dirpath:
                continue
            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                rel = os.path.relpath(os.path.join(dirpath, filename), _REPO_ROOT)
                dotted = rel[: -len(".py")].replace(os.sep, ".")
                if dotted.endswith(".__init__"):
                    dotted = dotted[: -len(".__init__")]
                found.append(dotted)
    return sorted(found)


ALL_MODULES: List[str] = _discover_modules()


def test_discovery_finds_every_plugin_module():
    """Sanity check on discovery itself: a walk that silently returns nothing is worse than none."""
    assert len(ALL_MODULES) >= 25, f"discovery only found {len(ALL_MODULES)} modules: {ALL_MODULES}"
    # Spot-check the two groups a hand-written list had been missing.
    assert "krita_pie_menu.sync" in ALL_MODULES
    assert "operations_pie_menu.operations.refine_sketch" in ALL_MODULES
    assert "operations_pie_menu.operations.bw_preview" in ALL_MODULES


def test_stub_invariant_qt_widget_is_the_stub():
    """
    The suite must never bind real Qt.

    Constructing any QWidget subclass before a QApplication exists does not
    raise a Python exception -- it aborts the interpreter via __fastfail
    (0xC0000409). Verified for QWidget, QDialog, QPushButton, QLabel and
    QMessageBox; QDockWidget additionally raises TypeError when handed a stub
    as a parent. Five test files died that way whenever PyQt5 was installed.
    """
    import PyQt5.QtWidgets as widgets
    from conftest import _QtWidgetStub

    for name in ("QWidget", "QDialog", "QPushButton", "QMessageBox", "QDockWidget"):
        assert getattr(widgets, name) is _QtWidgetStub, (
            f"PyQt5.QtWidgets.{name} is not the conftest stub. The suite must run "
            "against stubs unconditionally; only KRITA_PYTEST_REAL_QT=1 may bypass it."
        )


def test_stub_invariant_krita_is_the_stub():
    import krita
    from conftest import _QtWidgetStub

    assert krita.Krita is _QtWidgetStub


@pytest.mark.parametrize("module_name", ALL_MODULES)
def test_module_imports(module_name: str):
    importlib.import_module(module_name)


def test_full_import_surface(module_names=ALL_MODULES):
    """Collects every failure in one go instead of one error per module."""
    failed: List[Tuple[str, str]] = []
    for module_name in module_names:
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001 - report all import failures
            failed.append((module_name, f"{type(exc).__name__}: {exc}"))
    assert not failed, "\n".join(f"{name} -> {err}" for name, err in failed)
