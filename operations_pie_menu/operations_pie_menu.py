import os
from typing import Any, Callable, Dict, Tuple

from krita import Krita

from krita_pie_menu import BasePieMenuExtension, ToastNotification, read_condition_flag

from .config_dialog import OperationsConfigDialog
from .operations import (
    execute_bw_preview,
    execute_duplicate_layer,
    execute_fit_layer,
    execute_init_canvas,
    execute_merge_to_black,
    execute_refine_sketch,
    execute_sanitize_group,
    validate_bw_preview,
    validate_duplicate_layer,
    validate_fit_layer,
    validate_init_canvas,
    validate_merge_to_black,
    validate_refine_sketch,
    validate_sanitize_group,
)

DEFAULT_OPERATIONS_CONFIG = {
    "N": {"label": "Refine Sketch", "action_id": "op_refine_sketch"},
    "NE": {"label": "Sanitize Group", "action_id": "op_sanitize_group"},
    "E": {"label": "Stub East", "action_id": "op_placeholder_east"},
    "SE": {"label": "B&W Preview", "action_id": "op_bw_preview"},
    "S": {"label": "Init Canvas", "action_id": "op_setup_canvas"},
    "SW": {"label": "Merge to Black", "action_id": "op_merge_to_black"},
    "W": {"label": "Fit Layer to Canvas", "action_id": "op_fit_layer"},
    "NW": {"label": "Duplicate", "action_id": "op_duplicate_layer"},
}


def _unassigned_validator() -> Tuple[bool, str]:
    """Validator for sectors that have no operation bound (greyed out, like conditions stubs)."""
    return False, "Sector not configured."


def _make_refine_callback(duplicate_reflay: bool) -> Callable[[], None]:
    return lambda: execute_refine_sketch(duplicate_reflay=duplicate_reflay)


OP_HANDLERS: Dict[str, Callable[[], None]] = {
    "op_setup_canvas": execute_init_canvas,
    "op_sanitize_group": execute_sanitize_group,
    "op_merge_to_black": execute_merge_to_black,
    "op_fit_layer": execute_fit_layer,
    "op_bw_preview": execute_bw_preview,
    "op_duplicate_layer": execute_duplicate_layer,
}


class OperationsPieMenuExtension(BasePieMenuExtension):
    def __init__(self, parent):
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        super().__init__(
            parent,
            config_path=config_path,
            default_config=DEFAULT_OPERATIONS_CONFIG,
            accent_color="#805AD5",
            object_name="OperationsPieWidget",
            menu_title="OPERATIONS",
        )

    def createActions(self, window):
        action = window.createAction("trigger_operations_pie_menu", "Operations Pie Menu", "tools/scripts")
        action.triggered.connect(self.show_pie_menu)

        cfg_action = window.createAction(
            "configure_operations_pie_menu", "Configure Operations Pie Menu", "tools/scripts"
        )
        cfg_action.triggered.connect(self.open_config_dialog)

    def _get_duplicate_reflay_condition(self) -> bool:
        return read_condition_flag("duplicate_reflay", False)

    def build_pie_config(self):
        config = self.load_config()
        callbacks: Dict[str, Any] = {}
        items_meta: Dict[str, Any] = {}
        validators: Dict[str, Any] = {
            "N": validate_refine_sketch,
            "NE": validate_sanitize_group,
            "E": _unassigned_validator,
            "SE": validate_bw_preview,
            "S": validate_init_canvas,
            "SW": validate_merge_to_black,
            "W": validate_fit_layer,
            "NW": validate_duplicate_layer,
        }

        dup_reflay = self._get_duplicate_reflay_condition()
        refine_callback = _make_refine_callback(dup_reflay)

        for code, data in config.items():
            act_id = data.get("action_id", "")
            label = data.get("label", "")
            items_meta[code] = (label, act_id)

            if act_id == "op_refine_sketch":
                callbacks[code] = refine_callback
            else:
                callbacks[code] = OP_HANDLERS.get(act_id, self.make_stub_callback(code, label, act_id))

        return callbacks, items_meta, validators, {}

    def make_stub_callback(self, code, label, action_id):
        return lambda: self.execute_stub_action(code, label, action_id)

    def execute_stub_action(self, code, label, action_id):
        app = Krita.instance()
        if action_id:
            act = app.action(action_id)
            if act:
                act.trigger()
                return
        ToastNotification.show_toast(f"Stub [{code}] {label}", toast_type="info")

    def open_config_dialog(self):
        dlg = OperationsConfigDialog(self.config_path, on_save_callback=None)
        dlg.exec_()
