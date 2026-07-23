import re
from krita import Extension, Krita
from PyQt5.QtWidgets import QMessageBox
from krita_pie_menu import ToastNotification

class QuickScriptEngineExtension(Extension):
    """
    General purpose arbitrary script engine for Krita workflow automation.
    """
    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        pass

    def createActions(self, window):
        action = window.createAction("create_incremental_layer_action", "Create Incremental Layer", "tools/scripts")
        action.triggered.connect(self.create_incremental_layer)

    def create_incremental_layer(self):
        """
        Creates a new paint layer directly above the active node.
        Parses active node name for an integer:
        - If found, increments integer by +1 for new layer name.
        - If not found, starts at 1.
        """
        app = Krita.instance()
        doc = app.activeDocument()
        if not doc:
            ToastNotification.show_toast("No active document open.", toast_type="warning")
            return

        active_layer = doc.activeNode()
        if not active_layer:
            ToastNotification.show_toast("No active layer selected.", toast_type="warning")
            return

        curr_name = active_layer.name().strip()
        matches = re.findall(r'\d+', curr_name)
        if matches:
            next_num = int(matches[-1]) + 1
        else:
            next_num = 1

        new_layer_name = str(next_num)

        # Create new paint layer directly above active_layer
        new_layer = doc.createNode(new_layer_name, "paintlayer")
        parent = active_layer.parentNode()
        if not parent:
            parent = doc.rootNode()
        parent.addChildNode(new_layer, active_layer)

        # Set active layer to new layer and refresh
        doc.setActiveNode(new_layer)
        doc.refreshProjection()

        ToastNotification.show_toast(f"Created Layer '{new_layer_name}'", toast_type="info")
