from krita import Krita
from PyQt5.QtCore import QByteArray
from PyQt5.QtWidgets import QMessageBox
from krita_pie_menu import (
    log_error,
    log_info,
    log_warning,
    resolve_action,
    find_brush_preset,
    set_foreground_black
)

def execute_init_canvas():
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
        return

    def count_all_nodes(node):
        nodes = []
        for child in node.childNodes():
            nodes.append(child)
            nodes.extend(count_all_nodes(child))
        return nodes

    all_nodes = count_all_nodes(doc.rootNode())

    if len(all_nodes) > 1:
        reply = QMessageBox.question(
            None,
            "Nuke Document?",
            "Nuke Document?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        for n in all_nodes:
            try:
                n.setLocked(False)
                n.setAlphaLocked(False)
                n.remove()
            except Exception as e:
                log_warning("init_canvas", f"Could not remove node '{n.name()}': {e}")

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
        white_bytes = b'\xff' * (w * h * p_len)
        base_layer.setPixelData(QByteArray(white_bytes), 0, 0, w, h)
    except Exception as e:
        log_error("init_canvas", "Failed filling base layer with white", e)

    # 2. Rename base layer to "WHITE"
    base_layer.setName("WHITE")

    # 3. Set opacity to 75% (191 / 255)
    base_layer.setOpacity(191)

    # 4. Create Group Layer "LINES"
    lines_group = doc.createGroupLayer("LINES")
    doc.rootNode().addChildNode(lines_group, None)

    # 5. Create Paint Layer "1" inside "LINES"
    layer_1 = doc.createNode("1", "paintlayer")
    lines_group.addChildNode(layer_1, None)
    layer_1.setOpacity(255)

    # 6. Set active layer to layer "1"
    doc.setActiveNode(layer_1)
    doc.refreshProjection()

    # 7. Turn off Eraser mode if active
    erase_act = app.action("erase_action")
    if erase_act and erase_act.isChecked():
        erase_act.trigger()

    # 8. Set active tool to Freehand Brush
    brush_act = resolve_action(app, ["KritaShape/KritaShapeFreehand", "KritaShapeFreehand"])
    if brush_act:
        brush_act.trigger()

    # 9. Reset FG/BG and set black color & brush preset
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
                    log_warning("init_canvas", f"Failed activating brush preset: {e}")

    log_info("init_canvas", "Successfully initialized canvas structure.")
