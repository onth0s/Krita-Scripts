from krita import Extension, Krita
from PyQt5.QtWidgets import QMessageBox

class HelloExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        pass

    def createActions(self, window):
        action = window.createAction("hello_world_action", "Hello World Script", "tools/scripts")
        action.triggered.connect(self.run)

    def run(self):
        doc = Krita.instance().activeDocument()
        if doc is None:
            QMessageBox.information(
                None, 
                "Hello Extension", 
                "Hello from Krita Python! (No active document open)"
            )
        else:
            QMessageBox.information(
                None, 
                "Hello Extension", 
                f"Hello from Krita Python!\nActive Document: {doc.name()} ({doc.width()}x{doc.height()} px)"
            )
