import math
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QCursor, QPainter, QPen, QBrush, QColor
from PyQt5.QtWidgets import QWidget, QPushButton

class PieMenuWidget(QWidget):
    """
    Blender-style 8-sector radial Filters Pie Menu widget.
    Supports Space key hold-gesture, F11/Right-Click/Esc interrupt cancellation,
    and circular neutral deadzone.
    """
    def __init__(self, callbacks, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Popup | Qt.NoDropShadowWindowHint)
        self.setObjectName("PieMenuWidget")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setMouseTracking(True)
        self.callbacks = callbacks
        self.buttons = {}
        self.active_direction = None
        self.is_interrupted = False
        self.init_ui()

    def init_ui(self):
        # 480x480 widget area with (240, 240) center
        self.setFixedSize(480, 480)

        btn_style = """
            QWidget#PieMenuWidget {
                background: transparent;
            }
            QPushButton {
                background-color: rgba(36, 40, 44, 235);
                color: #E2E8F0;
                border: 2px solid #4A5568;
                border-radius: 10px;
                padding: 6px 12px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton[active="true"] {
                background-color: rgba(66, 153, 225, 240);
                color: #FFFFFF;
                border: 2px solid #63B3ED;
            }
            QPushButton:pressed {
                background-color: rgba(49, 130, 206, 255);
            }
        """
        self.setStyleSheet(btn_style)

        center_x, center_y = 240, 240
        btn_w, btn_h = 150, 36

        # 8 Directional Positions relative to center (240, 240)
        positions = {
            'N':  (center_x - btn_w // 2, center_y - 150),  # North
            'NE': (center_x + 70,         center_y - 110),  # North-East
            'E':  (center_x + 80,         center_y - btn_h // 2), # East
            'SE': (center_x + 70,         center_y + 74),   # South-East
            'S':  (center_x - btn_w // 2, center_y + 114),  # South
            'SW': (center_x - 220,        center_y + 74),   # South-West
            'W':  (center_x - 230,        center_y - btn_h // 2), # West
            'NW': (center_x - 220,        center_y - 110),  # North-West
        }

        items = [
            ('N',  "HSV Adjustment... (Alt+1)",      self.callbacks.get('N')),
            ('NE', "Color Curves... (Ctrl+2)",        self.callbacks.get('NE')),
            ('E',  "Color Balance... (Alt+5)",       self.callbacks.get('E')),
            ('SE', "Slope, Offset, Power... (Alt+8)", self.callbacks.get('SE')),
            ('S',  "Desaturate... (Alt+7)",          self.callbacks.get('S')),
            ('SW', "Auto Contrast (Ctrl+Shift+1)",   self.callbacks.get('SW')),
            ('W',  "Levels... (Ctrl+1)",             self.callbacks.get('W')),
            ('NW', "Invert (Ctrl+I)",                self.callbacks.get('NW')),
        ]

        for key, text, cb in items:
            x, y = positions[key]
            btn = QPushButton(text, self)
            btn.setGeometry(x, y, btn_w, btn_h)
            btn.setMouseTracking(True)
            if cb:
                btn.clicked.connect(self.make_click_handler(key, cb))
            self.buttons[key] = btn

    def make_click_handler(self, key, callback):
        def handler():
            self.cleanup_and_close()
            callback()
        return handler

    def show_at_cursor(self):
        cursor_pos = QCursor.pos()
        self.move(cursor_pos.x() - 240, cursor_pos.y() - 240)
        self.show()
        self.activateWindow()
        self.grabKeyboard()
        self.update_selection_from_mouse()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center = QPoint(240, 240)
        
        # Circular neutral center zone rendering (Radius 30px)
        if self.active_direction is None:
            painter.setPen(QPen(QColor(160, 174, 192, 140), 2))
            painter.setBrush(QBrush(QColor(26, 32, 44, 200)))
            painter.drawEllipse(center, 26, 26)
        else:
            painter.setPen(QPen(QColor(99, 179, 237, 240), 2))
            painter.setBrush(QBrush(QColor(49, 130, 206, 180)))
            painter.drawEllipse(center, 26, 26)

    def mouseMoveEvent(self, event):
        self.update_selection_from_mouse()
        super().mouseMoveEvent(event)

    def update_selection_from_mouse(self):
        cursor_pos = self.mapFromGlobal(QCursor.pos())
        dx = cursor_pos.x() - 240
        dy = cursor_pos.y() - 240
        dist = math.hypot(dx, dy)

        old_direction = self.active_direction

        # Circular neutral deadzone (radius 40px)
        if dist < 40:
            self.active_direction = None
        else:
            angle = math.degrees(math.atan2(dy, dx))
            # 8 Sectors of 45 degrees each
            if -112.5 <= angle < -67.5:
                self.active_direction = 'N'
            elif -67.5 <= angle < -22.5:
                self.active_direction = 'NE'
            elif -22.5 <= angle < 22.5:
                self.active_direction = 'E'
            elif 22.5 <= angle < 67.5:
                self.active_direction = 'SE'
            elif 67.5 <= angle < 112.5:
                self.active_direction = 'S'
            elif 112.5 <= angle < 157.5:
                self.active_direction = 'SW'
            elif angle >= 157.5 or angle < -157.5:
                self.active_direction = 'W'
            elif -157.5 <= angle < -112.5:
                self.active_direction = 'NW'

        if self.active_direction != old_direction:
            self.update_button_highlights()
            self.update()

    def update_button_highlights(self):
        for key, btn in self.buttons.items():
            is_active = (key == self.active_direction)
            btn.setProperty("active", is_active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def interrupt_and_wait_for_release(self):
        """Visually hide the menu on interrupt, but keep listening until Space is released."""
        if not getattr(self, 'is_interrupted', False):
            self.is_interrupted = True
            self.active_direction = None
            self.hide()

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat():
            event.ignore()
            return

        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            if getattr(self, 'is_interrupted', False):
                self.cleanup_and_close()
            else:
                self.trigger_selected_action()
        else:
            super().keyReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            event.ignore()
            return

        # F11 or Escape interrupts the Pie call and waits for Space release
        if event.key() in (Qt.Key_F11, Qt.Key_Escape):
            self.interrupt_and_wait_for_release()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        # Right Click interrupts the Pie call and waits for Space release
        if event.button() == Qt.RightButton:
            self.interrupt_and_wait_for_release()
        else:
            super().mousePressEvent(event)

    def trigger_selected_action(self):
        self.update_selection_from_mouse()
        target_direction = self.active_direction
        target_cb = self.callbacks.get(target_direction) if target_direction else None
        
        self.cleanup_and_close()
        if target_cb:
            target_cb()

    def cleanup_and_close(self):
        try:
            self.releaseKeyboard()
        except Exception:
            pass
        self.close()
