import importlib
from typing import List, Tuple

import pytest

# Every plugin module must import cleanly headlessly (conftest stubs krita/PyQt5).
# This catches import-time breakage that compileall/mypy would miss, e.g. the
# extension registrations executed at import time in __init__.py files.
ALL_MODULES: List[str] = [
    "krita_pie_menu",
    "krita_pie_menu.logger",
    "krita_pie_menu.utils",
    "krita_pie_menu.geometry",
    "krita_pie_menu.pie_widget",
    "krita_pie_menu.toast_notification",
    "krita_pie_menu.base_config_dialog",
    "krita_pie_menu.base_extension",
    "filters_pie_menu",
    "filters_pie_menu.filters_pie_menu",
    "filters_pie_menu.config_dialog",
    "operations_pie_menu",
    "operations_pie_menu.operations_pie_menu",
    "operations_pie_menu.config_dialog",
    "conditions_pie_menu",
    "conditions_pie_menu.conditions_pie_menu",
    "conditions_pie_menu.config_dialog",
    "quick_script_engine",
    "quick_script_engine.quick_script_engine",
    "dummy_docker",
    "dummy_docker.dummy_docker",
]


@pytest.mark.parametrize("module_name", ALL_MODULES)
def test_module_imports(module_name: str):
    importlib.import_module(module_name)


def test_full_import_surface(module_names=ALL_MODULES):
    """Collects every failure in one go instead of one error per module."""
    failed: List[Tuple[str, str]] = []
    for module_name in ALL_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001 - report all import failures
            failed.append((module_name, f"{type(exc).__name__}: {exc}"))
    assert not failed, "\n".join(f"{name} -> {err}" for name, err in failed)
