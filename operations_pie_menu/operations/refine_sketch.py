import colorsys
import random
from typing import Any, Tuple

from krita import Krita
from PyQt5.QtCore import QByteArray
from PyQt5.QtWidgets import QMessageBox

from krita_pie_menu import (
    OperationResult,
    action_is_enabled,
    create_incremental_layer,
    find_brush_preset,
    is_empty_paint_layer,
    is_protected_layer,
    is_u8_rgba,
    log_error,
    log_info,
    log_warning,
    make_doc_active_validator,
    pump_events,
    resolve_action,
    set_foreground_black,
    trigger_action_verified,
)

MERGE_ACTION_IDS = ["layer_merge_down", "merge_layer_down", "merge_layer"]
CUT_ACTION_IDS = ["edit_cut", "cut"]
PASTE_ACTION_IDS = ["edit_paste", "paste"]
DESELECT_ACTION_IDS = ["deselect"]

_PAINTED_PIXELS = "painted pixels could not be written"
_LUMINANCE_OVERLAY = "luminance overlay could not be applied"


def _refine_sketch_extra_checks(doc: Any, node: Any) -> Tuple[bool, str]:
    if node.type() == "grouplayer":
        return False, "Refine Sketch requires a Paint Layer (Group selected)."
    if is_empty_paint_layer(node):
        return False, "Active layer is empty."
    return True, ""


validate_refine_sketch = make_doc_active_validator(_refine_sketch_extra_checks)


def _is_detached(node: Any, parent: Any) -> bool:
    """
    True when `node` is no longer among `parent`'s children (i.e. it was merged away).

    Guards against a dangling libkis node whose C++ layer was freed by the merge:
    comparing it would raise, and an unverifiable state must never count as done.
    """
    try:
        return node not in list(parent.childNodes())
    except Exception:
        return False


def _sync_active(doc: Any, view: Any, node: Any) -> None:
    """
    Point the document *and* the view at `node`.

    Krita actions such as merge-down act on the view's active node, so updating
    only `doc.setActiveNode()` lets the action target the wrong layer.
    """
    doc.setActiveNode(node)
    if view is not None:
        try:
            view.setActiveNode(node)
        except Exception as e:
            log_warning("refine_sketch", f"Could not sync active node on the view: {e}")


def _clear_selection(doc: Any, app: Any) -> None:
    deselect_act = resolve_action(app, DESELECT_ACTION_IDS)
    if deselect_act:
        deselect_act.trigger()
    else:
        doc.setSelection(None)
    pump_events(doc)


def handle_selection_cut_paste(doc: Any, app: Any, active_layer: Any) -> Tuple[Any, bool]:
    """
    If active selection exists, cut it, paste onto new layer and deselect.

    Returns ``(layer, ok)``. ``ok`` is False only when a selection existed *and*
    the cut succeeded but the paste produced no new layer. In that case the pixels
    have already left the canvas, so the caller must abort instead of refining a
    layer that has silently lost its content.
    """
    sel = doc.selection()
    if not sel or sel.width() <= 0 or sel.height() <= 0:
        return active_layer, True

    cut_act = resolve_action(app, CUT_ACTION_IDS)
    paste_act = resolve_action(app, PASTE_ACTION_IDS)

    if not cut_act or not paste_act:
        log_warning("refine_sketch", "Selection present but cut/paste unavailable; leaving selection untouched.")
        return active_layer, True

    if not action_is_enabled(cut_act) or not action_is_enabled(paste_act):
        log_warning("refine_sketch", "Selection present but cut/paste disabled here; leaving selection untouched.")
        return active_layer, True

    cut_act.trigger()
    pump_events(doc)

    paste_act.trigger()
    pump_events(doc)

    pasted_layer = doc.activeNode()
    _clear_selection(doc, app)

    if not pasted_layer or pasted_layer == active_layer:
        log_error(
            "refine_sketch",
            "Selection was cut but paste produced no new layer; the cut pixels are still on the clipboard",
        )
        return active_layer, False

    return pasted_layer, True


def fill_layer_random_hsl(doc: Any, layer: Any) -> bool:
    """
    Fills sketch layer line pixels with a perceptually distinct random HSL color.

    Operates on the layer's own bounds rather than the whole canvas: the loop is
    pure Python, and on a full-size document the canvas-wide variant froze the UI
    for seconds, which starved Krita of event-loop time and made the subsequent
    merge-down action far more likely to be a no-op.

    Returns True when the pixels were written.
    """
    if not is_u8_rgba(doc):
        log_warning(
            "refine_sketch",
            f"Skipping byte fill: needs an 8-bit RGBA document (got {doc.colorModel()}/{doc.colorDepth()}).",
        )
        return False

    _GOLDEN_RATIO = 0.618033988749895
    hue_norm = (random.random() + _GOLDEN_RATIO) % 1.0
    r, g, b = colorsys.hls_to_rgb(hue_norm, 0.5, 1.0)
    r_byte = int(r * 255)
    g_byte = int(g * 255)
    b_byte = int(b * 255)

    box = layer.bounds()
    x, y, w, h = box.x(), box.y(), box.width(), box.height()
    if w <= 0 or h <= 0:
        log_warning("refine_sketch", "Skipping byte fill: layer has no extent to paint.")
        return False

    try:
        pix_data = bytearray(layer.pixelData(x, y, w, h))
        if len(pix_data) != w * h * 4:
            log_warning(
                "refine_sketch",
                f"Skipping byte fill: unexpected buffer size {len(pix_data)} for {w}x{h} RGBA.",
            )
            return False
        for i in range(0, len(pix_data), 4):
            if pix_data[i + 3] > 0:  # Alpha > 0
                pix_data[i] = b_byte
                pix_data[i + 1] = g_byte
                pix_data[i + 2] = r_byte
        if not layer.setPixelData(QByteArray(pix_data), x, y, w, h):
            log_warning("refine_sketch", "Krita rejected the recolored pixel buffer.")
            return False
    except Exception as e:
        log_error("refine_sketch", "Failed byte fill of HSL color on layer", e)
        return False

    return True


def apply_duplicate_reflay(doc: Any, app: Any, active_layer: Any, view: Any = None) -> Tuple[Any, bool]:
    """
    Duplicates active layer and merges down if duplicate_reflay condition is True.

    Returns ``(layer, ok)``. The merge is verified: an unverified trigger would
    leave the duplicate sitting in the stack and silently redirect every later
    step onto the copy instead of the original.
    """
    dup_node = None
    try:
        dup_node = active_layer.duplicate()
        if dup_node is None:
            log_warning("refine_sketch", "Could not duplicate the active layer.")
            return active_layer, False

        parent_node = active_layer.parentNode() or doc.rootNode()
        if not parent_node.addChildNode(dup_node, active_layer):
            log_warning("refine_sketch", "Could not parent the duplicate; aborting reflay.")
            dup_node.remove()
            return active_layer, False

        _sync_active(doc, view, dup_node)
        doc.refreshProjection()
        pump_events(doc)

        merged = trigger_action_verified(
            app,
            MERGE_ACTION_IDS,
            lambda: _is_detached(dup_node, parent_node),
            doc=doc,
            label="refine_sketch merge-down (reflay)",
        )
        if not merged:
            log_warning("refine_sketch", "Reflay merge-down did not complete; removing the duplicate.")
            if not _is_detached(dup_node, parent_node):
                dup_node.remove()
            _sync_active(doc, view, active_layer)
            return active_layer, False

        return doc.activeNode() or active_layer, True
    except Exception as e:
        log_error("refine_sketch", "Failed during duplicate_reflay step", e)
        if dup_node is not None and not _is_detached(dup_node, active_layer.parentNode() or doc.rootNode()):
            try:
                dup_node.remove()
            except Exception:
                pass
        return active_layer, False


def apply_luminosity_overlay(doc: Any, app: Any, active_layer: Any, view: Any) -> bool:
    """
    Creates temporary neutral gray layer, sets Luminosity blend mode & Inherit Alpha,
    merges down, and verifies the result.

    The temp layer covers the whole canvas and is opaque, so a failed merge used
    to leave a solid gray sheet on top of the artwork that the renumbering pass
    then renamed like a normal layer. It is now removed on any failure.
    """
    if not is_u8_rgba(doc):
        log_warning(
            "refine_sketch",
            f"Skipping luminance overlay: needs an 8-bit RGBA document (got {doc.colorModel()}/{doc.colorDepth()}).",
        )
        return False

    parent = active_layer.parentNode() or doc.rootNode()
    temp_lum_layer = doc.createNode("Refine_Lum_Temp", "paintlayer")
    if not parent.addChildNode(temp_lum_layer, active_layer):
        log_warning("refine_sketch", "Could not insert the luminance overlay layer.")
        return False

    _sync_active(doc, view, temp_lum_layer)

    w, h = doc.width(), doc.height()
    try:
        sample = temp_lum_layer.pixelData(0, 0, 1, 1)
        p_len = len(sample) if sample else 4
        if p_len == 4:
            gray_pixel = b"\x80\x80\x80\xff"
        else:
            gray_pixel = b"\x80\x80\x80" + b"\xff" * (p_len - 3)
        gray_bytes = gray_pixel * (w * h)
        if not temp_lum_layer.setPixelData(QByteArray(gray_bytes), 0, 0, w, h):
            log_warning("refine_sketch", "Krita rejected the luminance overlay pixels.")
            temp_lum_layer.remove()
            return False
    except Exception as e:
        log_error("refine_sketch", "Failed creating neutral gray overlay", e)
        temp_lum_layer.remove()
        return False

    temp_lum_layer.setBlendingMode("luminize")

    try:
        temp_lum_layer.setInheritAlpha(True)
    except Exception as e:
        log_warning("refine_sketch", f"Failed setting Inherit Alpha: {e}")

    _sync_active(doc, view, temp_lum_layer)
    doc.refreshProjection()
    pump_events(doc)

    merged = trigger_action_verified(
        app,
        MERGE_ACTION_IDS,
        lambda: _is_detached(temp_lum_layer, parent),
        doc=doc,
        label="refine_sketch merge-down (luminance)",
    )
    if not merged:
        log_warning("refine_sketch", "Luminance merge-down did not complete; removing the temporary layer.")
        if not _is_detached(temp_lum_layer, parent):
            temp_lum_layer.remove()
        _sync_active(doc, view, active_layer)
        doc.refreshProjection()
        return False

    _sync_active(doc, view, doc.activeNode() or active_layer)
    return True


def _renumber_siblings(new_layer: Any) -> None:
    """
    Renumber sibling layers 1..N bottom-to-top, skipping protected layers.

    See AGENTS.md sections 8.3 / 8.4: the child list is snapshotted before any
    mutation, and protected names are never touched.
    """
    parent = new_layer.parentNode()
    if parent is None:
        return
    counter = 1
    for child in list(parent.childNodes()):
        if is_protected_layer(child):
            continue  # leave protected layers alone (see AGENTS.md 8.3)
        child.setName(str(counter))
        counter += 1


def execute_refine_sketch(duplicate_reflay: bool = False) -> OperationResult:
    """
    Refine Sketch (North Operation):
    1. Validates active layer is not empty.
    2. Cuts/pastes selection if present.
    3. Enables Alpha Lock and fills lines with random HSL.
    4. Duplicates layer and merges down if `duplicate_reflay` is True.
    5. Creates neutral gray overlay layer with Luminosity blend mode and merges down.
    6. Creates a new paint layer directly above (+1 protocol).
    7. Activates new layer, sets '0 STD DRW' brush, and resets color to black.

    Returns True on success, or (False, reason) on a verified failure so the pie
    widget can tell the user what went wrong instead of always claiming success.

    Re-entrancy is guarded centrally by PieMenuWidget._execute_sector; do not wrap
    this in single_flight as well, since that lock is already held when it runs.
    """
    app = Krita.instance()

    doc = app.activeDocument()
    if not doc:
        QMessageBox.warning(None, "Operations Pie Menu", "No active document open.")
        return False

    active_layer = doc.activeNode()
    if not active_layer:
        QMessageBox.warning(None, "Operations Pie Menu", "No active layer selected.")
        return False

    if active_layer.type() == "grouplayer":
        QMessageBox.warning(
            None,
            "Operations Pie Menu",
            "Refine Sketch operation cannot be run on a Group Layer.\nPlease select a Paint Layer.",
        )
        return False

    if is_empty_paint_layer(active_layer):
        QMessageBox.warning(
            None,
            "Operations Pie Menu",
            "Refine Sketch cannot be run on an empty layer.\nPlease draw something on the layer first.",
        )
        return False

    window = app.activeWindow()
    view = window.activeView() if window else None

    # Step 0: Handle selection cut/paste
    active_layer, cut_ok = handle_selection_cut_paste(doc, app, active_layer)
    if not cut_ok:
        return (False, "Selection was cut but paste failed. Press Ctrl+V to restore it.")

    # Step 1: Enable alpha lock
    try:
        active_layer.setAlphaLocked(True)
    except Exception as e:
        log_warning("refine_sketch", f"Could not set alpha locked: {e}")

    # Step 2: Fill with random HSL
    if not fill_layer_random_hsl(doc, active_layer):
        return (False, _PAINTED_PIXELS)

    # Step 2b: Duplicate RefLay if enabled
    if duplicate_reflay:
        active_layer, reflay_ok = apply_duplicate_reflay(doc, app, active_layer, view)
        if not reflay_ok:
            return (False, "RefLay merge-down did not complete.")

    # Step 3-6: Luminosity overlay merge
    if not apply_luminosity_overlay(doc, app, active_layer, view):
        return (False, _LUMINANCE_OVERLAY)

    # Step 7: Create incremental new layer
    curr_layer = doc.activeNode() or active_layer
    new_layer = create_incremental_layer(doc, curr_layer, view=view)
    if new_layer is None:
        return (False, "New sketch layer could not be created.")

    # Step 7b: Renumber all siblings to 1..N, skipping protected layers (WHITE/B&W/LINES)
    _renumber_siblings(new_layer)
    _sync_active(doc, view, new_layer)

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

    log_info("refine_sketch", f"Successfully refined sketch into new layer '{new_layer.name()}'")
    return True
