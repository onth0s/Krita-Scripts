import os
import json
from krita import Extension, Krita
from krita_pie_menu import PieMenuWidget
from .config_dialog import SectorConfigDialog

class FiltersPieMenuExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)
        self.pie_widget = None
        self.config_path = os.path.join(os.path.dirname(__file__), 'config.json')

    def setup(self):
        pass

    def createActions(self, window):
        action = window.createAction("trigger_filters_pie_menu", "Filters Pie Menu", "tools/scripts")
        action.triggered.connect(self.show_pie_menu)

        cfg_action = window.createAction("configure_filters_pie_menu", "Configure Filters Pie Menu", "tools/scripts")
        cfg_action.triggered.connect(self.open_config_dialog)

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        # Default layout fallback
        return {
            "N":  { "label": "HSV Adjustment...",       "action_id": "hsv_adjustment" },
            "NE": { "label": "Color Curves...",         "action_id": "color_curves" },
            "E":  { "label": "Color Balance...",        "action_id": "color_balance" },
            "SE": { "label": "Slope, Offset, Power...",  "action_id": "slope_offset_power" },
            "S":  { "label": "Desaturate...",           "action_id": "desaturate" },
            "SW": { "label": "Auto Contrast",           "action_id": "auto_contrast" },
            "W":  { "label": "Levels...",               "action_id": "levels" },
            "NW": { "label": "Invert",                  "action_id": "invert" }
        }

    def show_pie_menu(self):
        try:
            if self.pie_widget is not None:
                if self.pie_widget.isVisible() or getattr(self.pie_widget, 'is_interrupted', False):
                    return
        except (RuntimeError, ReferenceError):
            self.pie_widget = None

        config = self.load_config()
        callbacks = {}
        items_meta = {}
        validators = {}

        def validate_filter_context():
            app = Krita.instance()
            doc = app.activeDocument()
            if not doc:
                return False, "No active document."
            node = doc.activeNode()
            if not node:
                return False, "No active layer selected."
            if node.type() == "grouplayer":
                return False, "Filters cannot be applied directly to a Group Layer."
            return True, ""

        for code in config.keys():
            validators[code] = validate_filter_context

        for code, data in config.items():
            act_id = data.get('action_id', '')
            label = data.get('label', '')
            items_meta[code] = (label, act_id)
            callbacks[code] = self.make_trigger_callback(act_id, label)

        self.pie_widget = PieMenuWidget(callbacks, items_meta=items_meta, validators=validators, object_name="FiltersPieWidget")
        self.pie_widget.show_at_cursor()

    def make_trigger_callback(self, action_id, fallback_text):
        return lambda: self.trigger_action(action_id, fallback_text)

    def open_config_dialog(self):
        dlg = SectorConfigDialog(self.config_path, on_save_callback=None)
        dlg.exec_()

    def trigger_action(self, action_id, fallback_text):
        app = Krita.instance()
        doc = app.activeDocument()
        if doc and doc.activeNode() and doc.activeNode().type() == "grouplayer":
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
                None,
                "Filters Pie Menu",
                "Filters cannot be applied directly to a Group Layer.\nPlease select a Paint Layer inside the group."
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
        search_target = fallback_text.replace('.', '').replace('&', '').strip().lower()
        for act in app.actions():
            act_text = act.text().replace('&', '').replace('.', '').strip().lower()
            act_id = act.objectName().lower()
            if search_target and (search_target in act_text or act_text in search_target):
                act.trigger()
                return True
            if raw_id and raw_id in act_id:
                act.trigger()
                return True
        return False
