import os
from krita import Krita
from PyQt5.QtWidgets import QMessageBox
from krita_pie_menu import BasePieMenuExtension, load_config
from .config_dialog import OperationsConfigDialog
from .operations import (
    execute_refine_sketch,
    validate_refine_sketch,
    execute_sanitize_group,
    validate_sanitize_group,
    execute_bw_preview,
    execute_init_canvas,
    execute_fit_layer,
    validate_fit_layer
)

DEFAULT_OPERATIONS_CONFIG = {
    "N":  { "label": "Refine Sketch",       "action_id": "op_refine_sketch" },
    "NE": { "label": "Sanitize Group",      "action_id": "op_sanitize_group" },
    "E":  { "label": "Stub East",           "action_id": "op_stub_east" },
    "SE": { "label": "B&W Preview",         "action_id": "op_bw_preview" },
    "S":  { "label": "Init Canvas",         "action_id": "op_setup_canvas" },
    "SW": { "label": "Stub South West",     "action_id": "op_stub_sw" },
    "W":  { "label": "Fit Layer to Canvas", "action_id": "op_stub_west" },
    "NW": { "label": "Stub North West",     "action_id": "op_stub_nw" }
}

class OperationsPieMenuExtension(BasePieMenuExtension):
    def __init__(self, parent):
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        super().__init__(
            parent,
            config_path=config_path,
            default_config=DEFAULT_OPERATIONS_CONFIG,
            accent_color="#805AD5",
            object_name="OperationsPieWidget"
        )

    def createActions(self, window):
        action = window.createAction("trigger_operations_pie_menu", "Operations Pie Menu", "tools/scripts")
        action.triggered.connect(self.show_pie_menu)

        cfg_action = window.createAction("configure_operations_pie_menu", "Configure Operations Pie Menu", "tools/scripts")
        cfg_action.triggered.connect(self.open_config_dialog)

    def _get_duplicate_reflay_condition(self) -> bool:
        """
        Dynamically query condition state from conditions_pie_menu config if available.
        """
        pykrita_dir = os.path.dirname(os.path.dirname(__file__))
        cond_cfg_path = os.path.join(pykrita_dir, 'conditions_pie_menu', 'config.json')
        cond_cfg = load_config(cond_cfg_path, {})
        return bool(cond_cfg.get("duplicate_reflay", False))

    def build_pie_config(self):
        config = self.load_config()
        callbacks = {}
        items_meta = {}
        validators = {}

        validators['N'] = validate_refine_sketch
        validators['NE'] = validate_sanitize_group
        validators['W'] = validate_fit_layer

        def disabled_stub():
            return False, "Stub operation not configured."

        for code in ['E', 'SW', 'NW']:
            validators[code] = disabled_stub

        dup_reflay = self._get_duplicate_reflay_condition()

        for code, data in config.items():
            act_id = data.get('action_id', '')
            label = data.get('label', '')
            items_meta[code] = (label, act_id)

            if code == 'S' or act_id == 'op_setup_canvas':
                callbacks[code] = execute_init_canvas
            elif code == 'N' or act_id == 'op_refine_sketch' or act_id == 'op_stub_north':
                callbacks[code] = lambda dup=dup_reflay: execute_refine_sketch(duplicate_reflay=dup)
            elif code == 'NE' or act_id == 'op_sanitize_group':
                callbacks[code] = execute_sanitize_group
            elif code == 'W' or act_id == 'op_stub_west':
                callbacks[code] = execute_fit_layer
            elif code == 'SE' or act_id == 'op_bw_preview':
                callbacks[code] = execute_bw_preview
            else:
                callbacks[code] = self.make_stub_callback(code, label, act_id)

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
        QMessageBox.information(None, "Operations Pie Menu", f"Stub clicked: [{code}] {label}")

    def open_config_dialog(self):
        dlg = OperationsConfigDialog(self.config_path, on_save_callback=None)
        dlg.exec_()
