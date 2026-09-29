from typing import Any, Optional

from krita import Krita
from PyQt5.QtCore import QByteArray
from PyQt5.QtWidgets import QMessageBox

from krita_pie_menu import (
    OperationResult,
    is_u8_rgba,
    log_error,
    log_info,
    log_warning,
    make_doc_active_validator,
    pump_events,
)

validate_bw_preview = make_doc_active_validator()

BW_LAYER_NAME = "B&W"

_NOT_U8 = "B&W Preview needs an 8-bit RGBA document."


def find_bw_node(node: Any) -> Optional[Any]:
    """
    Depth-first search for the 'B&W' layer anywhere in the tree.

    `childNodes()` is bottom-to-top (AGENTS.md 8.1), so this returns the lowest
    match. It is deterministic, which matters because the toggle path depends on
    finding the *same* layer on every press.
    """
    for child in node.childNodes():
        if child.name().strip().upper() == BW_LAYER_NAME:
            return child
        found = find_bw_node(child)
        if found:
            return found
    return None


def _has_pixels(layer: Any) -> bool:
    """False when the layer's bounds are empty, i.e. it holds no pixels at all."""
    try:
        box = layer.bounds()
        return box.width() > 0 and box.height() > 0
    except Exception:
        return False


def _fill_black(doc: Any, layer: Any) -> bool:
    """
    Fills `layer` with opaque black over the whole canvas.

    Requires an 8-bit RGBA document. The old code inferred the byte-per-pixel
    count from `len(pixelData(0, 0, 1, 1))`, which is 8 for U16/F16 and 4 for F32
    -- producing a wrongly-sized buffer. `setPixelData` then returned False and
    **that return value was ignored**, so the run still "succeeded": a fully
    transparent 'B&W' layer was left behind that every later press kept toggling
    while producing no visible change.
    """
    if not is_u8_rgba(doc):
        log_warning("bw_preview", f"{_NOT_U8} (got {doc.colorModel()}/{doc.colorDepth()})")
        return False

    w, h = doc.width(), doc.height()
    if w <= 0 or h <= 0:
        log_warning("bw_preview", "B&W Preview skipped: the document has no extent to fill.")
        return False

    try:
        black_bytes = b"\x00\x00\x00\xff" * (w * h)
        if not layer.setPixelData(QByteArray(black_bytes), 0, 0, w, h):
            log_warning("bw_preview", "Krita rejected the black fill.")
            return False
    except Exception as e:
        log_error("bw_preview", "Failed filling the B&W layer", e)
        return False

    return True


def _toggle_bw(doc: Any, bw_layer: Any) -> OperationResult:
    """Flips the B&W layer's visibility, then repaints deterministically."""
    try:
        bw_layer.setVisible(not bw_layer.visible())
        doc.refreshProjection()
        pump_events(doc)
        log_info("bw_preview", f"Toggled B&W layer visibility to {bw_layer.visible()}")
        return True
    except Exception as e:
        log_error("bw_preview", "Failed toggling B&W layer visibility", e)
        return (False, "B&W layer visibility could not be changed.")


def _refill_bw(doc: Any, bw_layer: Any) -> OperationResult:
    """
    Repairs a 'B&W' layer that holds no pixels.

    Such a layer is a leftover from a run whose pixel write was rejected (see
    `_fill_black`). Toggling it can never show anything, so refill it in place
    rather than reporting success. Non-destructive: the layer is reused, so no
    user work is lost and no manual cleanup is needed.
    """
    log_warning("bw_preview", "Existing B&W layer is empty; refilling it instead of toggling.")
    if not _fill_black(doc, bw_layer):
        return (False, _NOT_U8)
    try:
        doc.refreshProjection()
        pump_events(doc)
    except Exception:
        pass
    log_info("bw_preview", "Refilled the empty B&W preview layer")
    return True


def _create_bw(doc: Any, initial_layer: Any) -> OperationResult:
    """Creates the 'B&W' layer: solid black, 'color' blend mode, locked."""
    try:
        bw_layer = doc.createNode(BW_LAYER_NAME, "paintlayer")
    except Exception as e:
        log_error("bw_preview", "Failed creating the B&W layer", e)
        return (False, "B&W layer could not be created.")

    if not doc.rootNode().addChildNode(bw_layer, None):
        log_warning("bw_preview", "Could not insert the B&W layer; aborting.")
        return (False, "B&W layer could not be added to the document.")

    bw_layer.setLocked(True)

    try:
        bw_layer.setBlendingMode("color")
    except Exception as e:
        log_warning("bw_preview", f"Failed to set 'color' blending mode: {e}")

    if not _fill_black(doc, bw_layer):
        # Never leave an unparentable or unfilled 'B&W' behind: `find_bw_node`
        # matches it by name forever, so every later press would toggle a layer
        # that can never display anything.
        bw_layer.remove()
        return (False, _NOT_U8)

    if initial_layer:
        doc.setActiveNode(initial_layer)

    doc.refreshProjection()
    pump_events(doc)
    log_info("bw_preview", "Created B&W preview layer")
    return True


def execute_bw_preview() -> OperationResult:
    """
    B&W Preview (SE Operation):
    - Toggles visibility of the 'B&W' layer if it holds pixels.
    - Refills it if it exists but is empty (a leftover from a failed run).
    - Otherwise creates it: solid black, 'color' blend mode, locked.

    Returns True on success or (False, reason) on a verified failure. It used to
    return None, so every one of the failure modes above toasted "Triggered" and
    none of them reached the log.
    """
    app = Krita.instance()
    doc = app.activeDocument()
    if not doc:
        QMessageBox.warning(None, "Operations Pie Menu", "No active document open.")
        return False

    initial_layer = doc.activeNode()
    bw_layer = find_bw_node(doc.rootNode())

    if bw_layer is None:
        return _create_bw(doc, initial_layer)

    if not _has_pixels(bw_layer):
        return _refill_bw(doc, bw_layer)

    return _toggle_bw(doc, bw_layer)
