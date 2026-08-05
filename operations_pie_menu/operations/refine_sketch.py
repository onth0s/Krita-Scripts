import colorsys
import random
from typing import Any, Tuple

from krita import Krita
from PyQt5.QtCore import QByteArray
from PyQt5.QtWidgets import QApplication, QMessageBox

from krita_pie_menu import (
    create_incremental_layer,
    find_brush_preset,
    is_empty_paint_layer,
    is_protected_layer,
    log_error,
    log_info,
    log_warning,
    make_doc_active_validator,
    resolve_action,
    set_foreground_black,
)


def _refine_sketch_extra_checks(doc: Any, node: Any) -> Tuple[bool, str]:
    if node.type() == "grouplayer":
        return False, "Refine Sketch requires a Paint Layer (Group selected)."
    if is_empty_paint_layer(node):
        return False, "Active layer is empty."
    return True, ""


validate_refine_sketch = make_doc_active_validator(_refine_sketch_extra_checks)


def handle_selection_cut_paste(doc: Any, app: Any, active_layer: Any) -> Any:
    """
    If active selection exists, cut it, paste onto new layer with incremental name, and deselect.
    """
    sel = doc.selection()
    if not sel or sel.width() <= 0 or sel.height() <= 0:
        return active_layer

    cut_act = resolve_action(app, ["edit_cut", "cut"])
    paste_act = resolve_action(app, ["edit_paste", "paste"])

    if cut_act and paste_act:
        cut_act.trigger()
        QApplication.processEvents()
        doc.waitForDone()

        paste_act.trigger()
        QApplication.processEvents()
        doc.waitForDone()

        pasted_layer = doc.activeNode()
        if pasted_layer and pasted_layer != active_layer:
            active_layer = pasted_layer

        deselect_act = app.action("deselect")
        if deselect_act:
            deselect_act.trigger()
        else:
            doc.setSelection(None)
        QApplication.processEvents()
        doc.waitForDone()

    return active_layer


def fill_layer_random_hsl(doc: Any, layer: Any) -> None:
    """
    Fills sketch layer line pixels with a perceptually distinct random HSL color.
    Checks color depth and color model before manipulating bytes.
    """
    if doc.colorDepth() != "U8":
        log_warning("refine_sketch", f"Skipping direct byte fill for non-U8 color depth: {doc.colorDepth()}")
        return

    _GOLDEN_RATIO = 0.618033988749895
    hue_norm = (random.random() + _GOLDEN_RATIO) % 1.0
    r, g, b = colorsys.hls_to_rgb(hue_norm, 0.5, 1.0)
    r_byte = int(r * 255)
    g_byte = int(g * 255)
    b_byte = int(b * 255)

    w, h = doc.width(), doc.height()
    try:
        pix_data = bytearray(layer.pixelData(0, 0, w, h))
        if len(pix_data) == w * h * 4:
            for i in range(0, len(pix_data), 4):
                if pix_data[i + 3] > 0:  # Alpha > 0
                    pix_data[i] = b_byte
                    pix_data[i + 1] = g_byte
                    pix_data[i + 2] = r_byte
            layer.setPixelData(QByteArray(pix_data), 0, 0, w, h)
    except Exception as e:
        log_error("refine_sketch", "Failed byte fill of HSL color on layer", e)


def apply_duplicate_reflay(doc: Any, app: Any, active_layer: Any) -> Any:
    """
    Duplicates active layer and merges down if duplicate_reflay condition is True.
    """
    try:
        dup_node = active_layer.duplicate()
        parent_node = active_layer.parentNode() or doc.rootNode()
        parent_node.addChildNode(dup_node, active_layer)
        doc.setActiveNode(dup_node)
        doc.refreshProjection()
        QApplication.processEvents()
        doc.waitForDone()

        merge_act = resolve_action(app, ["layer_merge_down", "merge_layer_down", "merge_layer"])
        if merge_act:
            merge_act.trigger()
            QApplication.processEvents()
            doc.waitForDone()

        return doc.activeNode() or active_layer
    except Exception as e:
        log_error("refine_sketch", "Failed during duplicate_reflay step", e)
        return active_layer


def apply_luminosity_overlay(doc: Any, app: Any, active_layer: Any, view: Any) -> None:
    """
    Creates temporary neutral gray layer, sets Luminosity blend mode & Inherit Alpha, and merges down.
    """
    parent = active_layer.parentNode() or doc.rootNode()
    temp_lum_layer = doc.createNode("Refine_Lum_Temp", "paintlayer")
    parent.addChildNode(temp_lum_layer, active_layer)
    doc.setActiveNode(temp_lum_layer)

    w, h = doc.width(), doc.height()
    try:
        sample = temp_lum_layer.pixelData(0, 0, 1, 1)
        p_len = len(sample) if sample else 4
        if p_len == 4:
            gray_pixel = b"\x80\x80\x80\xff"
        else:
            gray_pixel = b"\x80\x80\x80" + b"\xff" * (p_len - 3)
        gray_bytes = gray_pixel * (w * h)
        temp_lum_layer.setPixelData(QByteArray(gray_bytes), 0, 0, w, h)
    except Exception as e:
        log_error("refine_sketch", "Failed creating neutral gray overlay", e)

    temp_lum_layer.setBlendingMode("luminize")

    try:
        temp_lum_layer.setInheritAlpha(True)
    except Exception as e:
        log_warning("refine_sketch", f"Failed setting Inherit Alpha: {e}")

    doc.setActiveNode(temp_lum_layer)
    if view:
        try:
            view.setActiveNode(temp_lum_layer)
        except Exception:
            pass
    doc.refreshProjection()
    QApplication.processEvents()
    doc.waitForDone()

    merge_act = resolve_action(app, ["layer_merge_down", "merge_layer_down", "merge_layer"])
    if merge_act:
        merge_act.trigger()
        QApplication.processEvents()
        doc.waitForDone()


def execute_refine_sketch(duplicate_reflay: bool = False) -> None:
    """
    Refine Sketch (North Operation):
    1. Validates active layer is not empty.
    2. Cuts/pastes selection if present.
    3. Enables Alpha Lock and fills lines with random HSL.
    4. Duplicates layer and merges down if `duplicate_reflay` is True.
    5. Creates neutral gray overlay layer with Luminosity blend mode and merges down.
    6. Creates a new paint layer directly above (+1 protocol).
    7. Activates new layer, sets '0 STD DRW' brush, and resets color to black.
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

    if active_layer.type() == "grouplayer":
        QMessageBox.warning(
            None,
            "Operations Pie Menu",
            "Refine Sketch operation cannot be run on a Group Layer.\nPlease select a Paint Layer.",
        )
        return

    if is_empty_paint_layer(active_layer):
        QMessageBox.warning(
            None,
            "Operations Pie Menu",
            "Refine Sketch cannot be run on an empty layer.\nPlease draw something on the layer first.",
        )
        return

    window = app.activeWindow()
    view = window.activeView() if window else None

    # Step 0: Handle selection cut/paste
    active_layer = handle_selection_cut_paste(doc, app, active_layer)

    # Step 1: Enable alpha lock
    try:
        active_layer.setAlphaLocked(True)
    except Exception as e:
        log_warning("refine_sketch", f"Could not set alpha locked: {e}")

    # Step 2: Fill with random HSL
    fill_layer_random_hsl(doc, active_layer)

    # Step 2b: Duplicate RefLay if enabled
    if duplicate_reflay:
        active_layer = apply_duplicate_reflay(doc, app, active_layer)

    # Step 3-6: Luminosity overlay merge
    apply_luminosity_overlay(doc, app, active_layer, view)

    # Step 7: Create incremental new layer
    curr_layer = doc.activeNode() or active_layer
    new_layer = create_incremental_layer(doc, curr_layer)

    # Step 7b: Renumber all siblings to 1..N, skipping protected layers (WHITE/B&W/LINES)
    parent = new_layer.parentNode() or doc.rootNode()
    counter = 1
    for child in parent.childNodes():
        if is_protected_layer(child):
            continue  # leave protected layers alone (see AGENTS.md ┬º8.3)
        child.setName(str(counter))
        counter += 1
    doc.setActiveNode(new_layer)

    # Step 8: Reset tools & brush preset
    reset_act = app.action("reset_fg_bg")
    if reset_act:
        reset_act.trigger()

    if view:
        set_foreground_black(doc, view)
        preset = find_brush_preset(app, "0 STD DRW")
        if preset:
            try:
                view.activateResource(preset)
            except Exception as e:
                log_warning("refine_sketch", f"Failed activating brush preset: {e}")

    log_info("refine_sketch", f"Successfully refined sketch into new layer '{new_layer.name() if new_layer else ''}'")
