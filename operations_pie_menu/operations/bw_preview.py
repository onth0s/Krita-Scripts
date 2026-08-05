from typing import Any, Optional

from krita import Krita
from PyQt5.QtCore import QByteArray
from PyQt5.QtWidgets import QMessageBox

from krita_pie_menu import log_error, log_info, log_warning, make_doc_active_validator

validate_bw_preview = make_doc_active_validator()


def execute_bw_preview() -> None:
    """
    B&W Preview (SE Operation):
    - Toggles visibility of top-level 'B&W' layer if present.
    - Otherwise, creates paint layer 'B&W' with 'color' blend mode filled with solid black.
    """
    app = Krita.instance()
    doc = app.activeDocument()
    if not doc:
        QMessageBox.warning(None, "Operations Pie Menu", "No active document open.")
        return

    initial_layer = doc.activeNode()

    def find_bw_node(node: Any) -> Optional[Any]:
        for child in node.childNodes():
            if child.name().strip().upper() == "B&W":
                return child
            found = find_bw_node(child)
            if found:
                return found
        return None

    bw_layer = find_bw_node(doc.rootNode())

    if bw_layer:
        try:
            bw_layer.setLocked(True)
            bw_layer.setVisible(not bw_layer.visible())
            doc.refreshProjection()
            log_info("bw_preview", f"Toggled B&W layer visibility to {bw_layer.visible()}")
        except Exception as e:
            log_error("bw_preview", "Failed toggling B&W layer visibility", e)
        return

    try:
        bw_layer = doc.createNode("B&W", "paintlayer")
        doc.rootNode().addChildNode(bw_layer, None)
        bw_layer.setLocked(True)

        try:
            bw_layer.setBlendingMode("color")
        except Exception as e:
            log_warning("bw_preview", f"Failed to set 'color' blending mode: {e}")

        w, h = doc.width(), doc.height()
        sample = bw_layer.pixelData(0, 0, 1, 1)
        p_len = len(sample) if sample else 4
        if p_len == 4:
            black_pixel = b"\x00\x00\x00\xff"
        else:
            black_pixel = b"\x00" * (p_len - 1) + b"\xff"
        black_bytes = black_pixel * (w * h)
        bw_layer.setPixelData(QByteArray(black_bytes), 0, 0, w, h)

        if initial_layer:
            doc.setActiveNode(initial_layer)

        doc.refreshProjection()
        log_info("bw_preview", "Created B&W preview layer")
    except Exception as e:
        log_error("bw_preview", "Failed creating B&W preview layer", e)
        QMessageBox.warning(None, "Operations Pie Menu", f"Failed to create B&W preview layer: {e}")
