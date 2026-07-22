from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QCursor, QFont
from PyQt5.QtWidgets import QWidget, QPushButton, QVBoxLayout, QLabel

class PieMenuWidget(QWidget):
    """
    Blender-style radial Pie Menu widget displayed at the mouse position.
    """
    def __init__(self, callbacks, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Popup)
        self.setObjectName("PieMenuWidget")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.callbacks = callbacks
        self.init_ui()

    def init_ui(self):
        # Size of the pie widget canvas area
        self.setFixedSize(360, 360)

        # Style definition for Blender-esque dark rounded pie slice buttons
        btn_style = """
            QWidget#PieMenuWidget {
                background: transparent;
            }
            QPushButton {
                background-color: rgba(36, 40, 44, 230);
                color: #E2E8F0;
                border: 2px solid #4A5568;
                border-radius: 12px;
                padding: 10px 16px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(66, 153, 225, 230);
                color: #FFFFFF;
                border: 2px solid #63B3ED;
            }
            QPushButton:pressed {
                background-color: rgba(49, 130, 206, 255);
            }
        """
        self.setStyleSheet(btn_style)

        # 4 Directional Positions (North, East, South, West) relative to (180, 180) center
        center_x, center_y = 180, 180
        btn_w, btn_h = 140, 40

        positions = {
            'north': (center_x - btn_w // 2, center_y - 120),
            'east':  (center_x + 30,         center_y - btn_h // 2),
            'south': (center_x - btn_w // 2, center_y + 80),
            'west':  (center_x - btn_w - 30, center_y - btn_h // 2),
        }

        # Center indicator label
        center_label = QLabel("PIE", self)
        center_label.setStyleSheet("color: #A0AEC0; font-weight: bold; font-size: 11px;")
        center_label.setGeometry(center_x - 15, center_y - 10, 30, 20)
        center_label.setAlignment(Qt.AlignCenter)

        # Create 4 directional slice buttons
        items = [
            ('north', "Rousseau (North)", self.callbacks.get('north')),
            ('east',  "Descartes (East)",  self.callbacks.get('east')),
            ('south', "Socrates (South)",  self.callbacks.get('south')),
            ('west',  "Nietzsche (West)",  self.callbacks.get('west')),
        ]

        for key, text, cb in items:
            x, y = positions[key]
            btn = QPushButton(text, self)
            btn.setGeometry(x, y, btn_w, btn_h)
            if cb:
                btn.clicked.connect(self.make_handler(cb))

    def make_handler(self, callback):
        def handler():
            self.close()
            callback()
        return handler

    def show_at_cursor(self):
        cursor_pos = QCursor.pos()
        # Center the 360x360 widget over the cursor
        self.move(cursor_pos.x() - 180, cursor_pos.y() - 180)
        self.show()
        self.activateWindow()

    def keyPressEvent(self, event):
        # Escape key closes the pie menu
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
