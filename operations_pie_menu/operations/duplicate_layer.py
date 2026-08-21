from krita import Krita
from PyQt5.QtWidgets import QApplication, QMessageBox

from krita_pie_menu import (
    log_error,
    log_info,
    make_doc_active_validator,
    read_condition_flag,
    resolve_action,
)

validate_duplicate_layer = make_doc_active_validator()


def execute_duplicate_layer() -> None:
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
        return

    node = doc.activeNode()
    if not node:
        QMessageBox.warning(None, "Operations Pie Menu", "No active layer selected.")
        return

    try:
        sel = doc.selection()
        if sel and sel.width() > 0 and sel.height() > 0:
            use_cut = read_condition_flag("duplicate_cut", True)
            action_candidates = ["edit_cut", "cut"] if use_cut else ["edit_copy", "copy"]
            clip_act = resolve_action(app, action_candidates)
            paste_act = resolve_action(app, ["edit_paste", "paste"])

            if clip_act and paste_act:
                # Lock and hide original node as a backup working copy, matching full layer duplication
                node.setLocked(True)
                node.setVisible(False)

                clip_act.trigger()
                QApplication.processEvents()
                doc.waitForDone()

                paste_act.trigger()
                QApplication.processEvents()
                doc.waitForDone()

                pasted_layer = doc.activeNode()
                if pasted_layer and pasted_layer != node:
                    pasted_layer.setVisible(True)
                    pasted_layer.setLocked(False)
                    doc.setActiveNode(pasted_layer)

                deselect_act = app.action("deselect")
                if deselect_act:
                    deselect_act.trigger()
                else:
                    doc.setSelection(None)
                QApplication.processEvents()
                doc.waitForDone()

                doc.refreshProjection()
                op_mode = "Cut+Pasted" if use_cut else "Copied+Pasted"
                log_info("duplicate_layer", f"{op_mode} active selection to new layer from '{node.name()}'.")
                return

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

    except Exception as e:
        log_error("duplicate_layer", "Failed to duplicate layer", e)
        QMessageBox.warning(None, "Operations Pie Menu", f"Failed to duplicate layer: {e}")

