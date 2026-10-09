from krita import Krita
from PyQt5.QtWidgets import QMessageBox

from krita_pie_menu import (
    OperationResult,
    action_is_enabled,
    log_error,
    log_info,
    make_doc_active_validator,
    pump_events,
    read_condition_flag,
    resolve_action,
)

validate_duplicate_layer = make_doc_active_validator()


def execute_duplicate_layer() -> OperationResult:
    """
    Duplicate (NW Operation):
    - If an active selection exists:
      Performs Cut+Paste (if 'duplicate_cut' condition flag is True, the default)
      or Copy+Paste (if 'duplicate_cut' is False), clears the selection, and activates
      the newly pasted layer.
    - If no active selection exists:
      Locks and hides the active layer or group layer, duplicates it above the
      original, then activates the duplicate with visibility and unlock restored.
      The original remains as a hidden, locked backup.
    """
    app = Krita.instance()
    doc = app.activeDocument()
    if not doc:
        QMessageBox.warning(None, "Operations Pie Menu", "No active document open.")
        return (False, "No active document open.")

    node = doc.activeNode()
    if not node:
        QMessageBox.warning(None, "Operations Pie Menu", "No active layer selected.")
        return (False, "No active layer selected.")

    try:
        sel = doc.selection()
        if sel and sel.width() > 0 and sel.height() > 0:
            use_cut = read_condition_flag("duplicate_cut", True)
            clip_act = resolve_action(app, ["edit_cut", "cut"] if use_cut else ["edit_copy", "copy"])
            paste_act = resolve_action(app, ["edit_paste", "paste"])

            if clip_act and paste_act and action_is_enabled(clip_act) and action_is_enabled(paste_act):
                # Execute cut or copy on the current active layer selection
                clip_act.trigger()
                pump_events(doc)

                # Paste creates a new paint layer containing the cut/copied selection
                paste_act.trigger()
                pump_events(doc)

                pasted_layer = doc.activeNode()
                if pasted_layer and pasted_layer != node:
                    if use_cut:
                        # Lock and hide the first pasted cut layer as backup
                        pasted_layer.setLocked(True)
                        pasted_layer.setVisible(False)

                        # Create working duplicate directly above the locked pasted layer
                        parent = pasted_layer.parentNode() or doc.rootNode()
                        dup_layer = pasted_layer.duplicate()
                        parent.addChildNode(dup_layer, pasted_layer)

                        dup_layer.setVisible(True)
                        dup_layer.setLocked(False)
                        doc.setActiveNode(dup_layer)
                    else:
                        pasted_layer.setVisible(True)
                        pasted_layer.setLocked(False)
                        doc.setActiveNode(pasted_layer)

                deselect_act = app.action("deselect")
                if deselect_act:
                    deselect_act.trigger()
                else:
                    doc.setSelection(None)
                pump_events(doc)

                doc.refreshProjection()
                op_mode = "Cut+Duplicated" if use_cut else "Copied+Pasted"
                log_info("duplicate_layer", f"{op_mode} active selection from '{node.name()}'.")
                return True

        parent = node.parentNode() or doc.rootNode()

        node.setLocked(True)
        node.setVisible(False)

        duplicate = node.duplicate()
        parent.addChildNode(duplicate, node)

        duplicate.setVisible(True)
        duplicate.setLocked(False)

        doc.setActiveNode(duplicate)
        doc.refreshProjection()
        log_info("duplicate_layer", f"Duplicated '{node.name()}' as active working copy.")
        return True

    except Exception as e:
        log_error("duplicate_layer", "Failed to duplicate layer", e)
        QMessageBox.warning(None, "Operations Pie Menu", f"Failed to duplicate layer: {e}")
        return (False, f"Failed to duplicate layer: {e}")

