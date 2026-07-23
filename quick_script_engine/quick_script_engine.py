from krita import Extension, Krita
from krita_pie_menu import ToastNotification, create_incremental_layer

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

        new_layer = create_incremental_layer(doc, active_layer)
        if new_layer:
            ToastNotification.show_toast(f"Created Layer '{new_layer.name()}'", toast_type="info")
