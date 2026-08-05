from krita import Krita
from PyQt5.QtCore import QByteArray, Qt
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QMessageBox

from krita_pie_menu import (
    is_u8_rgba,
    log_error,
    log_info,
    log_warning,
    make_doc_active_validator,
    read_condition_flag,
)


def _is_keep_aspect_ratio_enabled() -> bool:
    return read_condition_flag("keep_aspect_ratio", False)


validate_fit_layer = make_doc_active_validator()


def execute_fit_layer() -> None:
    """
    Fit Layer to Canvas (West Operation):
    Scales and centers active layer or group layer content to canvas dimensions while preserving aspect ratio.
    """
    app = Krita.instance()
    doc = app.activeDocument()
    if not doc:
        QMessageBox.warning(None, "Operations Pie Menu", "No active document open.")
        return

    active_layer = doc.activeNode()
    if not active_layer:
        QMessageBox.warning(None, "Operations Pie Menu", "No active layer selected.")
        return

    if not is_u8_rgba(doc):
        log_warning(
            "fit_layer",
            f"Fit Layer requires an 8-bit RGBA document (got {doc.colorModel()}/{doc.colorDepth()}).",
        )
        QMessageBox.warning(
            None,
            "Operations Pie Menu",
            "Fit Layer requires an 8-bit RGBA document.\nPlease convert the image color model/depth first.",
        )
        return

    doc_w = doc.width()
    doc_h = doc.height()

    bounds = active_layer.bounds()
    gx, gy, gw, gh = bounds.x(), bounds.y(), bounds.width(), bounds.height()

    if gw <= 0 or gh <= 0:
        QMessageBox.information(None, "Operations Pie Menu", "Active layer is empty.")
        return

    keep_ar = _is_keep_aspect_ratio_enabled()
    scale_w = doc_w / gw
    scale_h = doc_h / gh

    if keep_ar:
        scale = min(scale_w, scale_h)
        target_gw = max(1, int(gw * scale))
        target_gh = max(1, int(gh * scale))
        target_gx = (doc_w - target_gw) // 2
        target_gy = (doc_h - target_gh) // 2
    else:
        scale = 1.0
        target_gw = doc_w
        target_gh = doc_h
        target_gx = 0
        target_gy = 0

    try:
        if active_layer.type() == "grouplayer":
            parent = active_layer.parentNode() or doc.rootNode()
            scaled_group = active_layer.duplicate()

            child_paint_layers = scaled_group.findChildNodes("", True, False, "paintlayer")
            if not child_paint_layers:
                QMessageBox.information(None, "Operations Pie Menu", "Group Layer contains no paint layers.")
                return

            for child in child_paint_layers:
                cbounds = child.bounds()
                cx, cy, cw, ch = cbounds.x(), cbounds.y(), cbounds.width(), cbounds.height()
                if cw <= 0 or ch <= 0:
                    continue

                rel_x = (cx - gx) / gw
                rel_y = (cy - gy) / gh
                if keep_ar:
                    new_cw = max(1, int(cw * scale))
                    new_ch = max(1, int(ch * scale))
                else:
                    new_cw = max(1, int(cw * scale_w))
                    new_ch = max(1, int(ch * scale_h))
                new_cx = target_gx + int(rel_x * target_gw)
                new_cy = target_gy + int(rel_y * target_gh)

                raw_bytes = bytearray(child.pixelData(cx, cy, cw, ch))
                img = QImage(raw_bytes, cw, ch, cw * 4, QImage.Format_ARGB32).copy()

                scaled_img = img.scaled(new_cw, new_ch, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                if scaled_img.format() != QImage.Format_ARGB32:
                    scaled_img = scaled_img.convertToFormat(QImage.Format_ARGB32)

                actual_w = scaled_img.width()
                actual_h = scaled_img.height()

                ptr = scaled_img.constBits()
                ptr.setsize(actual_w * actual_h * 4)
                new_bytes = QByteArray(bytes(ptr))

                clear_bytes = b"\x00" * (cw * ch * 4)
                child.setPixelData(QByteArray(clear_bytes), cx, cy, cw, ch)
                child.setPixelData(new_bytes, new_cx, new_cy, actual_w, actual_h)

            parent.addChildNode(scaled_group, active_layer)
            active_layer.remove()

            doc.setActiveNode(scaled_group)
            doc.refreshProjection()
            log_info("fit_layer", f"Fitted group layer '{scaled_group.name()}' to canvas.")

        else:
            raw_bytes = bytearray(active_layer.pixelData(gx, gy, gw, gh))
            img = QImage(raw_bytes, gw, gh, gw * 4, QImage.Format_ARGB32).copy()

            scaled_img = img.scaled(target_gw, target_gh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            if scaled_img.format() != QImage.Format_ARGB32:
                scaled_img = scaled_img.convertToFormat(QImage.Format_ARGB32)

            actual_w = scaled_img.width()
            actual_h = scaled_img.height()

            ptr = scaled_img.constBits()
            ptr.setsize(actual_w * actual_h * 4)
            new_bytes = QByteArray(bytes(ptr))

            parent = active_layer.parentNode() or doc.rootNode()

            scaled_layer = doc.createNode(active_layer.name(), "paintlayer")
            scaled_layer.setPixelData(new_bytes, target_gx, target_gy, actual_w, actual_h)

            try:
                scaled_layer.setAlphaLocked(active_layer.alphaLocked())
            except Exception as e:
                log_warning("fit_layer", f"Could not restore alpha lock: {e}")
            try:
                scaled_layer.setOpacity(active_layer.opacity())
            except Exception as e:
                log_warning("fit_layer", f"Could not restore opacity: {e}")
            try:
                scaled_layer.setBlendingMode(active_layer.blendingMode())
            except Exception as e:
                log_warning("fit_layer", f"Could not restore blending mode: {e}")
            try:
                scaled_layer.setVisible(active_layer.visible())
            except Exception as e:
                log_warning("fit_layer", f"Could not restore visibility: {e}")
            try:
                scaled_layer.setLocked(active_layer.locked())
            except Exception as e:
                log_warning("fit_layer", f"Could not restore locked state: {e}")
            try:
                scaled_layer.setInheritAlpha(active_layer.inheritAlpha())
            except Exception as e:
                log_warning("fit_layer", f"Could not restore inherit alpha: {e}")

            parent.addChildNode(scaled_layer, active_layer)
            active_layer.remove()

            doc.setActiveNode(scaled_layer)
            doc.refreshProjection()
            log_info("fit_layer", f"Fitted layer '{scaled_layer.name()}' to canvas.")

    except Exception as e:
        log_error("fit_layer", "Failed to fit layer to canvas", e)
        QMessageBox.warning(None, "Operations Pie Menu", f"Failed to fit layer to canvas: {e}")
