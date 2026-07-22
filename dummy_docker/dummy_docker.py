from krita import DockWidget, Krita
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton

class DummyDocker(DockWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dummy Docker Panel")

        main_widget = QWidget(self)
        layout = QVBoxLayout(main_widget)

        self.info_label = QLabel("No Canvas Active", main_widget)
        self.action_button = QPushButton("Check Active Canvas", main_widget)
        self.action_button.clicked.connect(self.on_btn_click)

        layout.addWidget(self.info_label)
        layout.addWidget(self.action_button)
        main_widget.setLayout(layout)

        self.setWidget(main_widget)

    def canvasChanged(self, canvas):
        if canvas is None:
            self.info_label.setText("Canvas: None")
        else:
            doc = Krita.instance().activeDocument()
            if doc:
                self.info_label.setText(f"Canvas Active: {doc.width()}x{doc.height()} px")
            else:
                self.info_label.setText("Canvas Ready")

    def on_btn_click(self):
        doc = Krita.instance().activeDocument()
        if doc is None:
            self.info_label.setText("Status: No Active Document")
        else:
            node = doc.activeNode()
            node_name = node.name() if node else "None"
            self.info_label.setText(f"Active Layer: {node_name}")
