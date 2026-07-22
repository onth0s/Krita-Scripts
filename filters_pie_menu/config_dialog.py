import os
import json
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QLabel, QComboBox, QPushButton, QMessageBox)

FILTER_OPTIONS = [
    ("HSV Adjustment...", "hsv_adjustment"),
    ("Color Curves...", "color_curves"),
    ("Color Balance...", "color_balance"),
    ("Slope, Offset, Power...", "slope_offset_power"),
    ("Desaturate...", "desaturate"),
    ("Auto Contrast", "auto_contrast"),
    ("Levels...", "levels"),
    ("Invert", "invert"),
    ("Threshold...", "threshold"),
    ("Dodge...", "dodge"),
    ("Burn...", "burn"),
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

class SectorConfigDialog(QDialog):
    """
    Interactive PyQt dialog for reordering and customizing the 8-sector Filters Pie Menu.
    """
    def __init__(self, config_path, on_save_callback, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Filters Pie Menu Layout")
        self.setMinimumWidth(440)
        self.config_path = config_path
        self.on_save_callback = on_save_callback
        self.combos = {}

        self.current_config = self.load_current_config()
        self.init_ui()

    def load_current_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def init_ui(self):
        layout = QVBoxLayout(self)

        title_label = QLabel("Reassign or move filters across pie menu sectors:", self)
        title_label.setStyleSheet("font-weight: bold; font-size: 13px; margin-bottom: 10px;")
        layout.addWidget(title_label)

        grid = QGridLayout()
        grid.setSpacing(10)

        for idx, (code, name) in enumerate(SECTOR_NAMES):
            lbl = QLabel(f"<b>{name}:</b>", self)
            combo = QComboBox(self)

            # Populate combo box
            for label, act_id in FILTER_OPTIONS:
                combo.addItem(label, act_id)

            # Set current value if present in config
            if code in self.current_config:
                curr_act = self.current_config[code].get('action_id', '')
                index = combo.findData(curr_act)
                if index >= 0:
                    combo.setCurrentIndex(index)
                else:
                    # Match by index if fallback
                    combo.setCurrentIndex(idx % len(FILTER_OPTIONS))
            else:
                combo.setCurrentIndex(idx % len(FILTER_OPTIONS))

            self.combos[code] = combo
            grid.addWidget(lbl, idx, 0)
            grid.addWidget(combo, idx, 1)

        layout.addLayout(grid)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("Save & Apply", self)
        btn_save.setStyleSheet("background-color: #3182CE; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px;")
        btn_save.clicked.connect(self.save_config)

        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def save_config(self):
        new_config = {}
        for code, _ in SECTOR_NAMES:
            combo = self.combos[code]
            label = combo.currentText()
            action_id = combo.currentData()
            new_config[code] = {
                "label": label,
                "action_id": action_id
            }

        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, indent=2)
            
            QMessageBox.information(self, "Success", "Filters Pie Menu layout updated successfully!")
            if self.on_save_callback:
                self.on_save_callback(new_config)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save configuration:\n{str(e)}")
