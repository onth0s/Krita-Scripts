from krita import Krita
from PyQt5.QtWidgets import QMessageBox
from krita_pie_menu import log_error, log_info, ToastNotification


_PROTECTED_NAMES = {"WHITE"}


def _is_protected(node) -> bool:
    return node.name().strip().upper() in _PROTECTED_NAMES


def _is_empty_paint_layer(node) -> bool:
    if node.type() != "paintlayer":
        return False
    b = node.bounds()
    return b.width() <= 0 or b.height() <= 0


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
    - Purges intermediate empty paint layers that are NOT protected.
    - Ensures a fresh empty paint layer at the top of the group.
    - Renumbers non-protected layers 1..N (bottom-to-top in the UI).
    - Protected layer names (e.g. "WHITE") are never renamed or removed.
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

    try:
        # ── 1. Purge empty non-protected paint layers ────────────────────────
        # We must iterate a snapshot (list()) — modifying the live tree during
        # iteration causes Krita to skip or double-visit nodes.
        for child in list(group_layer.childNodes()):
            if not _is_protected(child) and _is_empty_paint_layer(child):
                child.remove()

        # ── 2. Add a fresh empty paint layer at the absolute top ─────────────
        # addChildNode(new, above=None) inserts at the TOP of the stack.
        fresh = doc.createNode("_top_", "paintlayer")
        group_layer.addChildNode(fresh, None)

        # ── 3. Renumber non-protected layers bottom-to-top (1, 2, 3 … N) ─────
        # childNodes() order: index 0 = bottom of the UI panel,
        #                     index -1 = top of the UI panel.
        # We name them so the bottom-most non-protected layer becomes "1" and
        # the topmost non-protected layer becomes "N".
        counter = 1
        for child in group_layer.childNodes():          # bottom → top
            if _is_protected(child):
                continue                                # leave "WHITE" alone
            child.setName(str(counter))
            counter += 1

        # ── 4. Activate the fresh layer (now the topmost in the group) ────────
        doc.setActiveNode(fresh)
        doc.refreshProjection()

        log_info("sanitize_group",
                 f"Sanitized '{group_layer.name()}': "
                 f"{len(group_layer.childNodes())} layers, "
                 f"active → '{fresh.name()}'")

    except Exception as e:
        log_error("sanitize_group", "Error during group sanitization", e)
        QMessageBox.warning(None, "Operations Pie Menu",
                            f"Failed to sanitize group: {e}")
