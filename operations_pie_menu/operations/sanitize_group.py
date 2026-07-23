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
    - Purges unused intermediate empty paint layers.
    - Guarantees an empty paint layer at the VERY TOP of the group stack.
    - Sets that top empty paint layer as the ACTIVE node.
    - Renumbers all direct child layers sequentially 1..N (bottom=1, top=N).
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
        # Group is completely empty: create first paint layer at top
        new_top = doc.createNode("1", "paintlayer")
        group_layer.addChildNode(new_top, None)
        doc.setActiveNode(new_top)
        doc.refreshProjection()
        log_info("sanitize_group", f"Created initial active layer '1' in empty group '{group_layer.name()}'")
        return

    try:
        def is_layer_empty(node_to_check):
            if node_to_check.type() != "paintlayer":
                return False
            b = node_to_check.bounds()
            return b.width() <= 0 or b.height() <= 0

        # Topmost layer in panel is the last element in Krita's childNodes()
        topmost = children[-1]

        # Purge intermediate empty paint layers (excluding the topmost layer)
        for child in list(children):
            if child != topmost and is_layer_empty(child):
                child.remove()

        # Refresh children after cleanup
        children = group_layer.childNodes()

        # Ensure the layer at the VERY TOP is an empty paint layer
        if not children or not is_layer_empty(children[-1]):
            placeholder = doc.createNode("temp", "paintlayer")
            # Passing None as second parameter places placeholder at the VERY TOP of group
            group_layer.addChildNode(placeholder, None)

        # Renumber all direct child layers sequentially from bottom (1) to top (N)
        children = group_layer.childNodes()
        for idx, child in enumerate(children, start=1):
            child.setName(str(idx))

        # Set the layer at the VERY TOP (children[-1]) as the active node
        top_node = children[-1]
        doc.setActiveNode(top_node)
        doc.refreshProjection()

        log_info("sanitize_group", f"Sanitized group '{group_layer.name()}': {len(children)} layers, active node set to top layer '{top_node.name()}'")
    except Exception as e:
        log_error("sanitize_group", "Error during group sanitization", e)
        QMessageBox.warning(None, "Operations Pie Menu", f"Failed to sanitize group: {e}")
