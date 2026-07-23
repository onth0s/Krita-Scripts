import os
import json
from krita import Extension, Krita
from PyQt5.QtWidgets import QMessageBox
from krita_pie_menu import PieMenuWidget, ToastNotification

class ConditionsPieMenuExtension(Extension):
    """
    Blender-style 8-sector radial Pie Menu for managing global workflow conditions and flags.
    Mapped to Ctrl+Tab.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.pie_widget = None
        self.config_path = os.path.join(os.path.dirname(__file__), 'config.json')

    def setup(self):
        pass

    def createActions(self, window):
        action = window.createAction("trigger_conditions_pie_menu", "Conditions Pie Menu", "tools/scripts")
        action.triggered.connect(self.show_pie_menu)

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "duplicate_reflay": False,
            "N":  { "label": "Stub North",       "action_id": "cond_stub_n" },
            "NE": { "label": "Duplicate RefLay", "action_id": "cond_toggle_duplicate_reflay" },
            "E":  { "label": "Stub East",        "action_id": "cond_stub_e" },
            "SE": { "label": "Stub South East",  "action_id": "cond_stub_se" },
            "S":  { "label": "Stub South",       "action_id": "cond_stub_s" },
            "SW": { "label": "Stub South West",  "action_id": "cond_stub_sw" },
            "W":  { "label": "Stub West",        "action_id": "cond_stub_w" },
            "NW": { "label": "Stub North West",  "action_id": "cond_stub_nw" }
        }

    def save_config(self, cfg):
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass

    def get_condition(self, key, default=False):
        cfg = self.load_config()
        return cfg.get(key, default)

    def toggle_condition(self, key):
        cfg = self.load_config()
        new_val = not cfg.get(key, False)
        cfg[key] = new_val
        self.save_config(cfg)
        return new_val

    def show_pie_menu(self):
        try:
            if self.pie_widget is not None:
                if self.pie_widget.isVisible():
                    return
        except (RuntimeError, ReferenceError):
            self.pie_widget = None

        self.pie_widget = None

        cfg = self.load_config()
        callbacks = {}
        items_meta = {}
        validators = {}
        toggle_states = {}

        def disabled_stub():
            return False, "Stub condition not configured."

        # 7 stubs: N, E, SE, S, SW, W, NW
        for code in ['N', 'E', 'SE', 'S', 'SW', 'W', 'NW']:
            validators[code] = disabled_stub
            callbacks[code] = self.make_stub_callback(code)

        # NE sector: Duplicate RefLay toggle
        dup_state = cfg.get("duplicate_reflay", False)
        toggle_states["NE"] = dup_state
        callbacks["NE"] = self.toggle_duplicate_reflay

        # Build items_meta
        for code in ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']:
            data = cfg.get(code, {})
            label = data.get('label', code)
            act_id = data.get('action_id', '')
            items_meta[code] = (label, act_id)

        self.pie_widget = PieMenuWidget(
            callbacks,
            items_meta=items_meta,
            validators=validators,
            toggle_states=toggle_states,
            accent_color="#D69E2E",
            object_name="ConditionsPieWidget"
        )
        self.pie_widget.show_at_cursor()

    def toggle_duplicate_reflay(self):
        new_state = self.toggle_condition("duplicate_reflay")
        status_str = "ON" if new_state else "OFF"
        ToastNotification.show_toast(f"Duplicate RefLay: {status_str}", toast_type="info")

    def make_stub_callback(self, code):
        return lambda: QMessageBox.information(None, "Conditions Pie Menu", f"Stub clicked: [{code}]")
