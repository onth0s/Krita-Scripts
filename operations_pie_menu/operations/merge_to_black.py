from typing import Any, Tuple

from krita import Krita
from PyQt5.QtCore import QByteArray
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QMessageBox

from krita_pie_menu import (
    find_brush_preset,
    is_protected_layer,
    is_u8_rgba,
    log_error,
    log_info,
    log_warning,
    make_doc_active_validator,
    resolve_action,
    set_foreground_black,
)


def _is_preserved(node: Any) -> bool:
    return is_protected_layer(node) or node.locked()


def _flatten_extra_checks(doc: Any, node: Any) -> Tuple[bool, str]:
    if node.type() == "grouplayer":
        return True, ""
    parent = node.parentNode()
    if parent and parent.type() == "grouplayer":
        return True, ""
    return False, "Merge to Black requires a Group Layer (or a layer inside one)."


validate_merge_to_black = make_doc_active_validator(_flatten_extra_checks)


def execute_merge_to_black() -> None:
    """
    Merge to Black (SW Operation):
    - Identifies target group layer (active group or parent group of active layer).
    - Merges non-protected, unlocked paint layers inside the target group into a single black silhouette layer.
    - Preserves target group identity, structure, and document hierarchy.
    - Strictly restores internal layer stack: WHITE at bottom [0], silhouette layer '1' in middle, B&W at top [-1].
    - Activates layer '1' and sets '0 STD DRW' brush as active with black foreground color.
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

    if not is_u8_rgba(doc):
        log_warning(
            "merge_to_black",
            f"Merge to Black requires an 8-bit RGBA document (got {doc.colorModel()}/{doc.colorDepth()}).",
        )
        QMessageBox.warning(
            None,
            "Operations Pie Menu",
            "Merge to Black requires an 8-bit RGBA document.\nPlease convert the image color model/depth first.",
        )
        return

    if node.type() == "grouplayer":
        group_layer = node
    else:
        parent = node.parentNode()
        if parent and parent.type() == "grouplayer":
            group_layer = parent
        else:
            QMessageBox.warning(None, "Operations Pie Menu", "Merge to Black requires a layer inside a Group.")
            return

    try:
        # 1. Identify preserved (protected/locked) and mergeable paint layers in group_layer
        preserved_nodes = []
        paint_nodes = []
        white_node = None
        bw_node = None

        for child in group_layer.childNodes():
            name_upper = child.name().strip().upper()
            if is_protected_layer(child):
                if name_upper == "WHITE":
                    white_node = child
                elif name_upper == "B&W":
                    bw_node = child

            if _is_preserved(child):
                preserved_nodes.append(child)
            elif child.type() == "paintlayer":
                paint_nodes.append(child)

        if not paint_nodes:
            QMessageBox.information(
                None, "Operations Pie Menu", "Group Layer contains no unlocked paint layers to merge."
            )
            return

        # 2. Compute union bounding box across non-protected paint layers
        min_x, min_y = float("inf"), float("inf")
        max_x, max_y = float("-inf"), float("-inf")
        for pnode in paint_nodes:
            b = pnode.bounds()
            if b.width() > 0 and b.height() > 0:
                min_x = min(min_x, b.x())
                min_y = min(min_y, b.y())
                max_x = max(max_x, b.x() + b.width())
                max_y = max(max_y, b.y() + b.height())

        if min_x >= max_x or min_y >= max_y:
            QMessageBox.information(None, "Operations Pie Menu", "Paint layers in group are empty.")
            return

        gx, gy = int(min_x), int(min_y)
        gw, gh = int(max_x - min_x), int(max_y - min_y)

        # Record original visibility of preserved nodes
        orig_visibility = [(p_node, p_node.visible()) for p_node in preserved_nodes]

        # 3. Temporarily hide preserved layers during composite projection extraction
        for p_node in preserved_nodes:
            p_node.setVisible(False)

        doc.refreshProjection()
        proj_bytes = bytearray(group_layer.projectionPixelData(gx, gy, gw, gh))

        # Restore preserved layers visibility (locked layers retain their original visibility state)
        for p_node, was_visible in orig_visibility:
            if is_protected_layer(p_node):
                p_node.setVisible(True)
            else:
                p_node.setVisible(was_visible)

        # 4. Fill composite RGB channels with solid black (#000000) preserving Alpha
        img = QImage(proj_bytes, gw, gh, gw * 4, QImage.Format_ARGB32)
        if img.format() != QImage.Format_ARGB32:
            img = img.convertToFormat(QImage.Format_ARGB32)

        ptr = img.bits()
        ptr.setsize(gw * gh * 4)
        raw_arr = bytearray(ptr)

        # Process pixels: ARGB32 format in QImage (BGRA in byte order on little-endian x86)
        for i in range(0, len(raw_arr), 4):
            raw_arr[i] = 0  # Blue
            raw_arr[i + 1] = 0  # Green
            raw_arr[i + 2] = 0  # Red

        black_silhouette_bytes = QByteArray(bytes(raw_arr))

        # 5. Purge unpreserved paint layers from group_layer
        for child in list(group_layer.childNodes()):
            if not _is_preserved(child):
                child.remove()

        # Determine non-colliding name for the new silhouette layer to avoid Krita auto-renaming locked layers
        existing_names = {child.name() for child in group_layer.childNodes()}
        target_layer_name = "1"
        if target_layer_name in existing_names:
            target_layer_name = "1_black"
            suffix_counter = 1
            while target_layer_name in existing_names:
                target_layer_name = f"1_black_{suffix_counter}"
                suffix_counter += 1

        # 6. Create new paint layer and set pixel data (simulating alpha lock fill)
        layer_1 = doc.createNode(target_layer_name, "paintlayer")
        layer_1.setAlphaLocked(True)
        layer_1.setPixelData(black_silhouette_bytes, gx, gy, gw, gh)
        layer_1.setAlphaLocked(False)

        # 7. Re-assemble stack inside group_layer in strict hierarchy
        if white_node:
            white_node.remove()
        if bw_node:
            bw_node.remove()

        # Step A: Add WHITE at bottom if present, then layer_1
        if white_node:
            group_layer.addChildNode(white_node, None)
            group_layer.addChildNode(layer_1, white_node)
        else:
            group_layer.addChildNode(layer_1, None)

        # Step B: Add B&W at top if present
        if bw_node:
            group_layer.addChildNode(bw_node, layer_1)

        # 8. Set active node to layer "1"
        doc.setActiveNode(layer_1)
        doc.refreshProjection()

        # 9. Activate Freehand Brush tool, reset color to black, activate '0 STD DRW' brush
        erase_act = app.action("erase_action")
        if erase_act and erase_act.isChecked():
            erase_act.trigger()

        brush_act = resolve_action(app, ["KritaShape/KritaShapeFreehand", "KritaShapeFreehand"])
        if brush_act:
            brush_act.trigger()

        reset_act = app.action("reset_fg_bg")
        if reset_act:
            reset_act.trigger()

        window = app.activeWindow()
        if window:
            view = window.activeView()
            if view:
                set_foreground_black(doc, view)
                preset = find_brush_preset(app, "0 STD DRW")
                if preset:
                    try:
                        view.activateResource(preset)
                    except Exception as e:
                        log_warning("merge_to_black", f"Failed activating brush preset: {e}")

        log_info(
            "merge_to_black",
            f"Successfully merged group '{group_layer.name()}' into black silhouette layer '1'.",
        )

    except Exception as e:
        log_error("merge_to_black", "Error during merge to black operation", e)
        QMessageBox.warning(None, "Operations Pie Menu", f"Failed to merge to black: {e}")
