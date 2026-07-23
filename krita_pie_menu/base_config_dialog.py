from typing import Dict, Any, Optional, Callable
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QMessageBox
)
from .utils import load_config, save_config

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

class BasePieConfigDialog(QDialog):
    """
    Base dialog class for customizing pie menu sector layouts and configuration options.
    """
    def __init__(
        self,
        config_path: str,
        title: str,
        on_save_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        parent=None,
        accent_color: str = "#3182CE"
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        self.config_path = config_path
        self.on_save_callback = on_save_callback
        self.accent_color = accent_color
        self.current_config = self.load_current_config()
        self.init_base_ui()

    def load_current_config(self) -> Dict[str, Any]:
        return load_config(self.config_path, {})

    def init_base_ui(self):
        self.main_layout = QVBoxLayout(self)

        title_label = QLabel(self.windowTitle(), self)
        title_label.setStyleSheet("font-weight: bold; font-size: 13px; margin-bottom: 8px;")
        self.main_layout.addWidget(title_label)

        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(10)

        self.build_sector_editors(self.grid_layout)

        self.main_layout.addLayout(self.grid_layout)

        btn_layout = QHBoxLayout()
        btn_save = QPushButton("Save & Apply", self)
        btn_save.setStyleSheet(
            f"background-color: {self.accent_color}; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px;"
        )
        btn_save.clicked.connect(self.handle_save)

        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        self.main_layout.addLayout(btn_layout)

    def build_sector_editors(self, grid: QGridLayout):
        """
        Abstract method for building per-sector UI controls into `grid`.
        """
        raise NotImplementedError("Subclasses must implement build_sector_editors")

    def collect_config(self) -> Dict[str, Any]:
        """
        Abstract method for gathering updated config dictionary from UI elements.
        """
        raise NotImplementedError("Subclasses must implement collect_config")

    def handle_save(self):
        try:
            new_config = self.collect_config()
            # Preserve existing root-level non-sector settings (like boolean flags)
            merged_config = dict(self.current_config)
            merged_config.update(new_config)

            if save_config(self.config_path, merged_config):
                QMessageBox.information(self, "Success", f"{self.windowTitle()} saved successfully!")
                if self.on_save_callback:
                    self.on_save_callback(merged_config)
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Failed to write configuration file.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save configuration:\n{e}")
