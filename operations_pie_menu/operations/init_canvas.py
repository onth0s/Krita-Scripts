from typing import Any, List

from krita import Krita
from PyQt5.QtCore import QByteArray
from PyQt5.QtWidgets import QMessageBox

from krita_pie_menu import (
    OperationResult,
    find_brush_preset,
    is_u8_rgba,
    log_error,
    log_info,
    log_warning,
    make_doc_active_validator,
    reset_drawing_tool,
    resolve_action,
    set_foreground_black,
)

validate_init_canvas = make_doc_active_validator()


def execute_init_canvas() -> OperationResult:
    """
    Init Canvas (South Operation):
    - Prompts 'Nuke Document?' if >1 layer present.
    - Sets base layer to solid white 75% opacity named 'WHITE'.
    - Creates group 'LINES' containing paint layer '1'.
    - Activates Freehand Brush tool, activates '0 STD DRW' brush, resets color to black.
    """
    app = Krita.instance()
    doc = app.activeDocument()
    if not doc:
        QMessageBox.warning(None, "Operations Pie Menu", "No active document open.")
        return (False, "No active document open.")

    if not is_u8_rgba(doc):
        log_warning(
            "init_canvas",
            f"Init Canvas requires an 8-bit RGBA document (got {doc.colorModel()}/{doc.colorDepth()}).",
        )
        QMessageBox.warning(
            None,
            "Operations Pie Menu",
            "Init Canvas requires an 8-bit RGBA document.\nPlease convert the image color model/depth first.",
        )
        return (False, "Init Canvas requires an 8-bit RGBA document.")

    def count_all_nodes(node: Any) -> List[Any]:
        nodes = []
        for child in node.childNodes():
            nodes.append(child)
            nodes.extend(count_all_nodes(child))
        return nodes

    all_nodes = count_all_nodes(doc.rootNode())

    if len(all_nodes) > 1:
        reply = QMessageBox.question(
            None, "Nuke Document?", "Nuke Document?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return (False, "Canvas initialization cancelled.")

        for n in all_nodes:
            try:
                n.setLocked(False)
                n.setAlphaLocked(False)
                n.remove()
            except Exception as e:
                log_warning("init_canvas", f"Could not remove node '{n.name()}': {e}")

    elif len(all_nodes) == 1:
        single = all_nodes[0]
        if single.name().strip().upper() != "WHITE":
            reply = QMessageBox.question(
                None,
                "Replace Layer?",
                f"Replace existing layer '{single.name()}' with a WHITE base layer?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return (False, "Canvas initialization cancelled.")

    # Prepare base layer
    top_nodes = doc.topLevelNodes()
    if top_nodes:
        base_layer = top_nodes[0]
    else:
        base_layer = doc.createNode("WHITE", "paintlayer")
        doc.rootNode().addChildNode(base_layer, None)

    try:
        base_layer.setLocked(False)
        base_layer.setAlphaLocked(False)
        base_layer.setVisible(True)
    except Exception as e:
        log_warning("init_canvas", f"Failed to adjust base layer locks/visibility: {e}")

    # 1. Fill base layer with solid white (#FFFFFF)
    w, h = doc.width(), doc.height()
    try:
        sample = base_layer.pixelData(0, 0, 1, 1)
        p_len = len(sample) if sample else 4
        white_bytes = b"\xff" * (w * h * p_len)
        base_layer.setPixelData(QByteArray(white_bytes), 0, 0, w, h)
    except Exception as e:
        log_error("init_canvas", "Failed filling base layer with white", e)

    # 2. Rename base layer to "WHITE"
    base_layer.setName("WHITE")

    # 3. Set opacity to 75% (191 / 255)
    base_layer.setOpacity(191)

    # 4. Lock the WHITE base layer
    base_layer.setLocked(True)

    # 5. Create Group Layer "LINES"
    lines_group = doc.createGroupLayer("LINES")
    doc.rootNode().addChildNode(lines_group, None)

    # 5. Create Paint Layer "1" inside "LINES"
    layer_1 = doc.createNode("1", "paintlayer")
    lines_group.addChildNode(layer_1, None)
    layer_1.setOpacity(255)

    # 6. Set active layer to layer "1"
    doc.setActiveNode(layer_1)
    doc.refreshProjection()

    # 7. Reset tools, color to black & brush preset
    window = app.activeWindow()
    view = window.activeView() if window else None
    reset_drawing_tool(
        app,
        doc,
        view,
        action_resolver=resolve_action,
        brush_finder=find_brush_preset,
        color_setter=set_foreground_black,
        warning_logger=log_warning,
    )

    log_info("init_canvas", "Successfully initialized canvas structure.")
    return True
