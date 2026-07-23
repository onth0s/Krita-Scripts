from PyQt5.QtWidgets import QLabel, QComboBox, QGridLayout
from krita_pie_menu import BasePieConfigDialog

FILTER_OPTIONS = [
    ("HSV Adjustment...", "krita_filter_hsvadjustment"),
    ("Color Curves...", "krita_filter_perchannel"),
    ("Color Balance...", "krita_filter_colorbalance"),
    ("Slope, Offset, Power...", "krita_filter_slope_offset_power"),
    ("Desaturate...", "krita_filter_desaturate"),
    ("Auto Contrast", "krita_filter_autocontrast"),
    ("Levels...", "krita_filter_levels"),
    ("Invert", "krita_filter_invert"),
    ("Gradient Map...", "krita_filter_gradientmap"),
    ("Sharpen...", "krita_filter_sharpen"),
    ("Gaussian High Pass...", "krita_filter_gaussian_high_pass"),
    ("Color to Alpha...", "krita_filter_colortoalpha"),
    ("Gaussian Blur...", "krita_filter_gaussian_blur"),
    ("Threshold...", "krita_filter_threshold"),
    ("Dodge...", "krita_filter_dodge"),
    ("Burn...", "krita_filter_burn"),
]

SECTOR_NAMES = [
    ("N",  "North (Up)"),
    ("NE", "North-East"),
    ("E",  "East (Right)"),
    ("SE", "South-East"),
    ("S",  "South (Down)"),
    ("SW", "South-West"),
    ("W",  "West (Left)"),
    ("NW", "North-West"),
]

class SectorConfigDialog(BasePieConfigDialog):
    """
    Interactive PyQt dialog for reordering and customizing the 8-sector Filters Pie Menu.
    """
    def __init__(self, config_path, on_save_callback=None, parent=None):
        self.combos = {}
        super().__init__(
            config_path=config_path,
            title="Configure Filters Pie Menu Layout",
            on_save_callback=on_save_callback,
            parent=parent,
            accent_color="#3182CE"
        )

    def build_sector_editors(self, grid: QGridLayout):
        for idx, (code, name) in enumerate(SECTOR_NAMES):
            lbl = QLabel(f"<b>{name}:</b>", self)
            combo = QComboBox(self)

            for label, act_id in FILTER_OPTIONS:
                combo.addItem(label, act_id)

            if code in self.current_config:
                curr_act = self.current_config[code].get('action_id', '')
                index = combo.findData(curr_act)
                if index >= 0:
                    combo.setCurrentIndex(index)
                else:
                    combo.setCurrentIndex(idx % len(FILTER_OPTIONS))
            else:
                combo.setCurrentIndex(idx % len(FILTER_OPTIONS))

            self.combos[code] = combo
            grid.addWidget(lbl, idx, 0)
            grid.addWidget(combo, idx, 1)

    def collect_config(self):
        new_config = {}
        for code, _ in SECTOR_NAMES:
            combo = self.combos[code]
            label = combo.currentText()
            action_id = combo.currentData()
            new_config[code] = {
                "label": label,
                "action_id": action_id
            }
        return new_config
