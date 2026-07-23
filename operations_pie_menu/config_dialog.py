from PyQt5.QtWidgets import QGridLayout, QLabel, QLineEdit

from krita_pie_menu import SECTOR_NAMES, BasePieConfigDialog


class OperationsConfigDialog(BasePieConfigDialog):
    """
    Interactive PyQt dialog for configuring action IDs and labels of the Operations Pie Menu.
    """

    def __init__(self, config_path, on_save_callback=None, parent=None):
        self.inputs = {}
        super().__init__(
            config_path=config_path,
            title="Configure Operations Pie Menu",
            on_save_callback=on_save_callback,
            parent=parent,
            accent_color="#805AD5",
        )

    def build_sector_editors(self, grid: QGridLayout):
        for idx, (code, name) in enumerate(SECTOR_NAMES):
            data = self.current_config.get(code, {})
            lbl = QLabel(f"<b>{name} ({code}):</b>", self)

            lbl_edit = QLineEdit(data.get("label", ""), self)
            lbl_edit.setPlaceholderText("Button Label")

            act_edit = QLineEdit(data.get("action_id", ""), self)
            act_edit.setPlaceholderText("Action ID or custom command")

            grid.addWidget(lbl, idx, 0)
            grid.addWidget(lbl_edit, idx, 1)
            grid.addWidget(act_edit, idx, 2)

            self.inputs[code] = (lbl_edit, act_edit)

    def collect_config(self):
        cfg = {}
        for code, (lbl_edit, act_edit) in self.inputs.items():
            cfg[code] = {"label": lbl_edit.text().strip(), "action_id": act_edit.text().strip()}
        return cfg
