import os
from typing import Any, Callable, Dict, Tuple

from krita import Krita
from PyQt5.QtWidgets import QMessageBox

from krita_pie_menu import BasePieMenuExtension, make_doc_active_validator

from .config_dialog import SectorConfigDialog


def _filter_extra_checks(doc: Any, node: Any) -> Tuple[bool, str]:
    if node.type() == "grouplayer":
        return False, "Filters cannot be applied directly to a Group Layer."
    return True, ""


validate_filter_context = make_doc_active_validator(_filter_extra_checks)

DEFAULT_FILTERS_CONFIG = {
    "N": {"label": "HSV Adjustment", "action_id": "hsv_adjustment"},
    "NE": {"label": "Color Curves", "action_id": "color_curves"},
    "E": {"label": "Color Balance", "action_id": "color_balance"},
    "SE": {"label": "Slope, Offset, Power", "action_id": "slope_offset_power"},
    "S": {"label": "Desaturate", "action_id": "desaturate"},
    "SW": {"label": "Auto Contrast", "action_id": "auto_contrast"},
    "W": {"label": "Levels", "action_id": "levels"},
    "NW": {"label": "Invert", "action_id": "invert"},
}


class FiltersPieMenuExtension(BasePieMenuExtension):
    def __init__(self, parent: Any) -> None:
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        super().__init__(
            parent,
            config_path=config_path,
            default_config=DEFAULT_FILTERS_CONFIG,
            accent_color="#3182CE",
            object_name="FiltersPieWidget",
        )

    def createActions(self, window: Any) -> None:
        action = window.createAction("trigger_filters_pie_menu", "Filters Pie Menu", "tools/scripts")
        action.triggered.connect(self.show_pie_menu)

        cfg_action = window.createAction("configure_filters_pie_menu", "Configure Filters Pie Menu", "tools/scripts")
        cfg_action.triggered.connect(self.open_config_dialog)

    def build_pie_config(self) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        config = self.load_config()
        callbacks = {}
        items_meta = {}
        validators = {}

        for code in config.keys():
            validators[code] = validate_filter_context

        for code, data in config.items():
            act_id = data.get("action_id", "")
            label = data.get("label", "")
            items_meta[code] = (label, act_id)
            callbacks[code] = self.make_trigger_callback(act_id, label)

        return callbacks, items_meta, validators, {}

    def make_trigger_callback(self, action_id: str, fallback_text: str) -> Callable[[], bool]:
        return lambda: self.trigger_action(action_id, fallback_text)

    def open_config_dialog(self) -> None:
        dlg = SectorConfigDialog(self.config_path, on_save_callback=None)
        dlg.exec_()

    def trigger_action(self, action_id: str, fallback_text: str) -> bool:
        app = Krita.instance()
        doc = app.activeDocument()
        if doc and doc.activeNode() and doc.activeNode().type() == "grouplayer":
            QMessageBox.warning(
                None,
                "Filters Pie Menu",
                "Filters cannot be applied directly to a Group Layer.\nPlease select a Paint Layer inside the group.",
            )
            return False

        raw_id = action_id.replace("krita_filter_", "")
        candidates = [
            action_id,
            f"krita_filter_{raw_id}",
            f"krita_filter_{raw_id.replace('_', '')}",
            "krita_filter_perchannel" if "curve" in fallback_text.lower() else "",
            "krita_filter_hsvadjustment" if "hsv" in fallback_text.lower() else "",
            "krita_filter_gradientmap" if "gradient" in fallback_text.lower() else "",
            "krita_filter_gradient_map" if "gradient" in fallback_text.lower() else "",
            "krita_filter_colortoalpha" if "alpha" in fallback_text.lower() else "",
            "krita_filter_color_to_alpha" if "alpha" in fallback_text.lower() else "",
            "krita_filter_gaussian_blur" if "blur" in fallback_text.lower() else "",
            "krita_filter_blur" if "blur" in fallback_text.lower() else "",
            "krita_filter_sharpen" if "sharpen" in fallback_text.lower() else "",
            "krita_filter_gaussian_high_pass" if "high" in fallback_text.lower() else "",
        ]

        for cid in candidates:
            if not cid:
                continue
            action = app.action(cid)
            if action:
                action.trigger()
                return True

        # Fallback search across all registered Krita actions
        search_target = fallback_text.replace(".", "").replace("&", "").strip().lower()
        for act in app.actions():
            act_text = act.text().replace("&", "").replace(".", "").strip().lower()
            act_id = act.objectName().lower()
            if search_target and (search_target in act_text or act_text in search_target):
                act.trigger()
                return True
            if raw_id and raw_id in act_id:
                act.trigger()
                return True
        return False
