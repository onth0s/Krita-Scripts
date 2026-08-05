from krita import Krita
from PyQt5.QtWidgets import QMessageBox

from krita_pie_menu import (
    log_error,
    log_info,
    make_doc_active_validator,
)

validate_duplicate_layer = make_doc_active_validator()


def execute_duplicate_layer() -> None:
    """
    Duplicate (NW Operation):
    Locks and hides the active layer or group layer, duplicates it above the
    original, then activates the duplicate with visibility and unlock restored.
    The original remains as a hidden, locked backup.
    """
    app = Krita.instance()
    doc = app.activeDocument()
    if not doc:
        QMessageBox.warning(None, "Operations Pie Menu", "No active document open.")
        return

    node = doc.activeNode()
    if not node:
        QMessageBox.warning(None, "Operations Pie Menu", "No active layer selected.")
        return

    try:
        parent = node.parentNode() or doc.rootNode()

        node.setLocked(True)
        node.setVisible(False)

        duplicate = node.duplicate()
        parent.addChildNode(duplicate, node)

        duplicate.setVisible(True)
        duplicate.setLocked(False)

        doc.setActiveNode(duplicate)
        doc.refreshProjection()
        log_info("duplicate_layer", f"Duplicated '{node.name()}' as active working copy.")

    except Exception as e:
        log_error("duplicate_layer", "Failed to duplicate layer", e)
        QMessageBox.warning(None, "Operations Pie Menu", f"Failed to duplicate layer: {e}")
