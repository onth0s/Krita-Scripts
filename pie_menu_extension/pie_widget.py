from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QWidget, QPushButton, QLabel

class PieMenuWidget(QWidget):
    """
    Blender-style radial Pie Menu widget displayed at mouse position.
    Triggers the highlighted action upon releasing the trigger key (Space) or clicking.
    """
    def __init__(self, callbacks, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Popup | Qt.NoDropShadowWindowHint)
        self.setObjectName("PieMenuWidget")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setMouseTracking(True)
        self.callbacks = callbacks
        self.buttons = {}
        self.init_ui()

    def init_ui(self):
        self.setFixedSize(360, 360)

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
            QPushButton:hover, QPushButton:focus {
                background-color: rgba(66, 153, 225, 230);
                color: #FFFFFF;
                border: 2px solid #63B3ED;
            }
            QPushButton:pressed {
                background-color: rgba(49, 130, 206, 255);
            }
        """
        self.setStyleSheet(btn_style)

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
            btn.setMouseTracking(True)
            if cb:
                btn.clicked.connect(self.make_handler(cb))
            self.buttons[key] = btn

    def make_handler(self, callback):
        def handler():
            self.cleanup_and_close()
            callback()
        return handler

    def show_at_cursor(self):
        cursor_pos = QCursor.pos()
        self.move(cursor_pos.x() - 180, cursor_pos.y() - 180)
        self.show()
        self.activateWindow()
        self.grabKeyboard()

    def mouseMoveEvent(self, event):
        self.update_hover_state()
        super().mouseMoveEvent(event)

    def update_hover_state(self):
        cursor_pos = QCursor.pos()
        for key, btn in self.buttons.items():
            if btn.rect().contains(btn.mapFromGlobal(cursor_pos)):
                btn.setFocus()
                break

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat():
            event.ignore()
            return

        # When Space (or Return/Enter) is released, execute highlighted option if hovering
        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.trigger_hovered_action()
        else:
            super().keyReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            event.ignore()
            return

        if event.key() == Qt.Key_Escape:
            self.cleanup_and_close()
        else:
            super().keyPressEvent(event)

    def trigger_hovered_action(self):
        cursor_pos = QCursor.pos()
        target_cb = None
        for key, btn in self.buttons.items():
            if btn.rect().contains(btn.mapFromGlobal(cursor_pos)):
                target_cb = self.callbacks.get(key)
                break
        
        self.cleanup_and_close()
        if target_cb:
            target_cb()

    def cleanup_and_close(self):
        try:
            self.releaseKeyboard()
        except Exception:
            pass
        self.close()
