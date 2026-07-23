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
    Removes empty layers, ensures an empty paint layer at top, sets it active,
    then renames all direct child layers to sequential integers 1..N.
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
        def is_layer_empty(node):
            b = node.bounds()
            return b.width() <= 0 or b.height() <= 0

        # Remove all empty layers
        for child in reversed(group_layer.childNodes()):
            if is_layer_empty(child):
                child.remove()

        # Re-fetch children after removal
        children = group_layer.childNodes()

        # Ensure the top layer is an empty paint layer
        if not children or not is_layer_empty(children[0]):
            placeholder = doc.createNode("temp", "paintlayer")
            group_layer.addChildNode(placeholder, children[0] if children else None)
            top = placeholder
        else:
            top = children[0]

        doc.setActiveNode(top)

        # Renumber remaining layers to 1..N
        children = group_layer.childNodes()
        for idx, child in enumerate(children, start=1):
            child.setName(str(idx))

        doc.refreshProjection()
        log_info("sanitize_group", f"Sanitized {len(children)} child layers in group '{group_layer.name()}'")
    except Exception as e:
        log_error("sanitize_group", "Error during group sanitization", e)
        QMessageBox.warning(None, "Operations Pie Menu", f"Failed to sanitize group: {e}")
