import os

from krita_pie_menu import SECTOR_CODES, BasePieMenuExtension, ToastNotification

from .config_dialog import ConditionsConfigDialog

DEFAULT_CONDITIONS_CONFIG = {
    "duplicate_reflay": False,
    "keep_aspect_ratio": False,
    "N": {"label": "Stub North", "action_id": "cond_stub_n"},
    "NE": {"label": "Duplicate RefLay", "action_id": "cond_toggle_duplicate_reflay"},
    "E": {"label": "Stub East", "action_id": "cond_stub_e"},
    "SE": {"label": "Stub South East", "action_id": "cond_stub_se"},
    "S": {"label": "Stub South", "action_id": "cond_stub_s"},
    "SW": {"label": "Stub South West", "action_id": "cond_stub_sw"},
    "W": {"label": "Keep Aspect Ratio (Fit)", "action_id": "cond_toggle_keep_aspect_ratio"},
    "NW": {"label": "Stub North West", "action_id": "cond_stub_nw"},
}


class ConditionsPieMenuExtension(BasePieMenuExtension):
    """
    Blender-style 8-sector radial Pie Menu for managing global workflow conditions and flags.
    Mapped to Ctrl+Tab.
    """

    def __init__(self, parent):
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        super().__init__(
            parent,
            config_path=config_path,
            default_config=DEFAULT_CONDITIONS_CONFIG,
            accent_color="#D69E2E",
            object_name="ConditionsPieWidget",
        )

    def createActions(self, window):
        action = window.createAction("trigger_conditions_pie_menu", "Conditions Pie Menu", "tools/scripts")
        action.triggered.connect(self.show_pie_menu)

        cfg_action = window.createAction(
            "configure_conditions_pie_menu", "Configure Conditions Pie Menu", "tools/scripts"
        )
        cfg_action.triggered.connect(self.open_config_dialog)

    def get_condition(self, key: str, default: bool = False) -> bool:
        cfg = self.load_config()
        return bool(cfg.get(key, default))

    def toggle_condition(self, key: str) -> bool:
        cfg = self.load_config()
        new_val = not cfg.get(key, False)
        cfg[key] = new_val
        self.save_config(cfg)
        return new_val

    def build_pie_config(self):
        cfg = self.load_config()
        callbacks = {}
        items_meta = {}
        validators = {}
        toggle_states = {}

        def disabled_stub():
            return False, "Stub condition not configured."

        # 6 stubs: all sectors except the NE/W toggles
        for code in [c for c in SECTOR_CODES if c not in ("NE", "W")]:
            validators[code] = disabled_stub
            callbacks[code] = self.make_stub_callback(code)

        # NE sector: Duplicate RefLay toggle
        dup_state = cfg.get("duplicate_reflay", False)
        toggle_states["NE"] = dup_state
        callbacks["NE"] = self.toggle_duplicate_reflay

        # W sector: Keep Aspect Ratio toggle
        ar_state = cfg.get("keep_aspect_ratio", False)
        toggle_states["W"] = ar_state
        callbacks["W"] = self.toggle_keep_aspect_ratio

        # Build items_meta
        for code in SECTOR_CODES:
            data = cfg.get(code, {})
            label = data.get("label", code)
            act_id = data.get("action_id", "")
            items_meta[code] = (label, act_id)

        return callbacks, items_meta, validators, toggle_states

    def toggle_duplicate_reflay(self):
        new_state = self.toggle_condition("duplicate_reflay")
        status_str = "ON" if new_state else "OFF"
        ToastNotification.show_toast(f"Duplicate RefLay: {status_str}", toast_type="info")

    def toggle_keep_aspect_ratio(self):
        new_state = self.toggle_condition("keep_aspect_ratio")
        status_str = "ON" if new_state else "OFF"
        ToastNotification.show_toast(f"Keep Aspect Ratio (Fit): {status_str}", toast_type="info")

    def make_stub_callback(self, code: str):
        return lambda: ToastNotification.show_toast(f"Condition [{code}] stub not implemented", toast_type="info")

    def open_config_dialog(self):
        dlg = ConditionsConfigDialog(self.config_path, on_save_callback=None)
        dlg.exec_()
