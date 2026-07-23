from krita import Krita
from PyQt5.QtWidgets import QMessageBox
from krita_pie_menu import log_error, log_info

def validate_sanitize_group():
    app = Krita.instance()
    doc = app.activeDocument()
    if not doc:
        return False, "No active document."
    node = doc.activeNode()
    if not node:
        return False, "No active layer selected."
    if node.type() == "grouplayer":
        return True, ""
    parent = node.parentNode()
    if parent and parent.type() == "grouplayer":
        return True, ""
    return False, "Sanitize Group requires a Group Layer (or a layer inside one)."

def execute_sanitize_group():
    """
    Sanitize Group (NE Operation):
    Renames all direct child layers inside the target group to sequential integers 1..N.
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

    if node.type() == "grouplayer":
        group_layer = node
    else:
        parent = node.parentNode()
        if parent and parent.type() == "grouplayer":
            group_layer = parent
        else:
            QMessageBox.warning(None, "Operations Pie Menu", "Sanitize requires a layer inside a Group.")
            return

    children = group_layer.childNodes()
    if not children:
        QMessageBox.information(None, "Operations Pie Menu", "Group layer has no child layers.")
        return

    try:
        for idx, child in enumerate(children, start=1):
            child.setName(str(idx))
        doc.refreshProjection()
        log_info("sanitize_group", f"Sanitized {len(children)} child layers in group '{group_layer.name()}'")
    except Exception as e:
        log_error("sanitize_group", "Error during group sanitization", e)
        QMessageBox.warning(None, "Operations Pie Menu", f"Failed to sanitize group: {e}")
