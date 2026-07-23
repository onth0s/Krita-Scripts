from PyQt5.QtWidgets import QCheckBox, QGridLayout, QLabel, QLineEdit

from krita_pie_menu import SECTOR_NAMES, BasePieConfigDialog


class ConditionsConfigDialog(BasePieConfigDialog):
    """
    Interactive PyQt dialog for configuring condition flags and sector labels of the Conditions Pie Menu.
    """

    def __init__(self, config_path, on_save_callback=None, parent=None):
        self.inputs = {}
        self.chk_dup_reflay = None
        self.chk_keep_ar = None
        super().__init__(
            config_path=config_path,
            title="Configure Conditions Pie Menu",
            on_save_callback=on_save_callback,
            parent=parent,
            accent_color="#D69E2E",
        )

    def build_sector_editors(self, grid: QGridLayout):
        # 1. Condition flag check boxes
        self.chk_dup_reflay = QCheckBox("Enable Duplicate RefLay by Default", self)
        self.chk_dup_reflay.setChecked(bool(self.current_config.get("duplicate_reflay", False)))
        grid.addWidget(self.chk_dup_reflay, 0, 0, 1, 3)

        self.chk_keep_ar = QCheckBox("Enable Keep Aspect Ratio (Fit Layer) by Default", self)
        self.chk_keep_ar.setChecked(bool(self.current_config.get("keep_aspect_ratio", False)))
        grid.addWidget(self.chk_keep_ar, 1, 0, 1, 3)

        # 2. Sector label / action_id editors
        for idx, (code, name) in enumerate(SECTOR_NAMES, start=2):
            data = self.current_config.get(code, {})
            lbl = QLabel(f"<b>{name}:</b>", self)

            lbl_edit = QLineEdit(data.get("label", ""), self)
            lbl_edit.setPlaceholderText("Condition Label")

            act_edit = QLineEdit(data.get("action_id", ""), self)
            act_edit.setPlaceholderText("Action ID")

            grid.addWidget(lbl, idx, 0)
            grid.addWidget(lbl_edit, idx, 1)
            grid.addWidget(act_edit, idx, 2)

            self.inputs[code] = (lbl_edit, act_edit)

    def collect_config(self):
        cfg = {
            "duplicate_reflay": self.chk_dup_reflay.isChecked(),
            "keep_aspect_ratio": self.chk_keep_ar.isChecked(),
        }
        for code, (lbl_edit, act_edit) in self.inputs.items():
            cfg[code] = {"label": lbl_edit.text().strip(), "action_id": act_edit.text().strip()}
        return cfg
