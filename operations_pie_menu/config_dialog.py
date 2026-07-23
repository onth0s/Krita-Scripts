import os
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox
)

class OperationsConfigDialog(QDialog):
    def __init__(self, config_path, on_save_callback=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Operations Pie Menu")
        self.config_path = config_path
        self.on_save_callback = on_save_callback
        self.inputs = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        grid = QGridLayout()

        labels_map = {
            'N': 'North',
            'NE': 'North East',
            'E': 'East',
            'SE': 'South East',
            'S': 'South (Bottom)',
            'SW': 'South West',
            'W': 'West',
            'NW': 'North West'
        }

        cfg = self.load_config()

        row = 0
        for code in ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']:
            data = cfg.get(code, {})
            lbl = QLabel(f"{labels_map[code]} ({code}):")
            
            lbl_edit = QLineEdit(data.get('label', ''))
            lbl_edit.setPlaceholderText("Button Label")

            act_edit = QLineEdit(data.get('action_id', ''))
            act_edit.setPlaceholderText("Action ID or custom command")

            grid.addWidget(lbl, row, 0)
            grid.addWidget(lbl_edit, row, 1)
            grid.addWidget(act_edit, row, 2)

            self.inputs[code] = (lbl_edit, act_edit)
            row += 1

        layout.addLayout(grid)

        btn_box = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_config)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        btn_box.addWidget(save_btn)
        btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_config(self):
        cfg = {}
        for code, (lbl_edit, act_edit) in self.inputs.items():
            cfg[code] = {
                "label": lbl_edit.text().strip(),
                "action_id": act_edit.text().strip()
            }

        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2)
            if self.on_save_callback:
                self.on_save_callback()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {e}")
