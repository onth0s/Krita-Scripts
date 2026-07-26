import math
from typing import Any, Callable, Dict, Optional, Tuple

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtGui import QBrush, QColor, QCursor, QPainter, QPen
from PyQt5.QtWidgets import QPushButton, QWidget

from .toast_notification import ToastNotification

WIDGET_SIZE = 520
CENTER_OFFSET = 260
BUTTON_WIDTH = 150
BUTTON_HEIGHT = 36
DEADZONE_RADIUS = 45


class PieMenuWidget(QWidget):
    """
    Generic Blender-style 8-sector radial Pie Menu widget for Krita plugins.
    Supports Space key hold-gesture, F11/Right-Click/Esc interrupt cancellation,
    circular neutral deadzone, accent colors, toggle states with visual indicators,
    and greyed-out disabled sector state polling with Toast Notifications.
    """

    def __init__(
        self,
        callbacks: Dict[str, Callable[[], None]],
        items_meta: Optional[Dict[str, Tuple[str, str]]] = None,
        validators: Optional[Dict[str, Callable[[], Any]]] = None,
        toggle_states: Optional[Dict[str, bool]] = None,
        accent_color: str = "#3182CE",
        object_name: str = "PieMenuWidget",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Popup | Qt.NoDropShadowWindowHint)
        self.setObjectName(object_name)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setMouseTracking(True)
        self.callbacks = callbacks
        self.items_meta = items_meta or {}
        self.validators = validators or {}
        self.toggle_states = toggle_states or {}
        self.accent_color = accent_color
        self.sector_states: Dict[str, Tuple[bool, str]] = {}
        self.buttons: Dict[str, QPushButton] = {}
        self.active_direction: Optional[str] = None
        self.is_interrupted: bool = False
        self.evaluate_sector_states()
        self.init_ui()

    def evaluate_sector_states(self):
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        for key in directions:
            validator = self.validators.get(key)
            if validator:
                try:
                    res = validator()
                    if isinstance(res, tuple):
                        is_enabled, reason = res
                    else:
                        is_enabled, reason = bool(res), "Action not available in current context."
                except Exception as e:
                    is_enabled, reason = False, f"Action error: {e}"
                self.sector_states[key] = (is_enabled, reason)
            else:
                self.sector_states[key] = (True, "")

    def init_ui(self):
        # 520x520 widget area with (260, 260) center
        self.setFixedSize(520, 520)

        obj_name = self.objectName()
        accent = QColor(self.accent_color)
        accent_hex = accent.name()
        # Lighter tint of the accent used for toggle underscore indicators
        light_accent = accent.lighter(170)
        la_r, la_g, la_b = light_accent.red(), light_accent.green(), light_accent.blue()

        btn_style = f"""
            QWidget#{obj_name} {{
                background: transparent;
            }}
            QPushButton {{
                background-color: rgba(30, 34, 40, 235);
                color: #E2E8F0;
                border: 2px solid {accent_hex};
                border-radius: 10px;
                padding: 6px 12px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton[disabled_sector="true"] {{
                background-color: rgba(22, 25, 30, 190);
                color: #718096;
                border: 2px solid rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.35);
            }}
            QPushButton[active="true"] {{
                background-color: rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.85);
                color: #FFFFFF;
                border: 2px solid #FFFFFF;
            }}
            QPushButton[active="true"][disabled_sector="true"] {{
                background-color: rgba(60, 68, 80, 190);
                color: #CBD5E0;
                border: 2px solid rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.6);
            }}
            QPushButton[toggle_on="true"] {{
                border-bottom: 4px solid rgba({la_r}, {la_g}, {la_b}, 220);
                color: rgba({la_r}, {la_g}, {la_b}, 255);
            }}
            QPushButton[active="true"][toggle_on="true"] {{
                border-bottom: 4px solid rgba({la_r}, {la_g}, {la_b}, 255);
                background-color: rgba({accent.red()}, {accent.green()}, {accent.blue()}, 0.9);
                color: #FFFFFF;
            }}
            QPushButton:pressed {{
                background-color: rgba({accent.red()}, {accent.green()}, {accent.blue()}, 1.0);
            }}
        """
        self.setStyleSheet(btn_style)

        center_x, center_y = 260, 260
        btn_w, btn_h = 150, 36

        # 8 Directional Positions relative to center (260, 260)
        positions = {
            "N": (center_x - btn_w // 2, center_y - 150),  # North
            "NE": (center_x + 75, center_y - 95),  # North-East
            "E": (center_x + 95, center_y - btn_h // 2),  # East
            "SE": (center_x + 75, center_y + 59),  # South-East
            "S": (center_x - btn_w // 2, center_y + 114),  # South
            "SW": (center_x - 225, center_y + 59),  # South-West
            "W": (center_x - 245, center_y - btn_h // 2),  # West
            "NW": (center_x - 225, center_y - 95),  # North-West
        }

        for key, (x, y) in positions.items():
            if key in self.items_meta:
                base_text = self.items_meta[key][0]
            else:
                base_text = key

            is_toggle = key in self.toggle_states
            is_on = self.toggle_states.get(key, False)
            text = base_text

            cb = self.callbacks.get(key)
            is_enabled, _ = self.sector_states.get(key, (True, ""))

            btn = QPushButton(text, self)
            btn.setGeometry(x, y, btn_w, btn_h)
            btn.setMouseTracking(True)
            if not is_enabled:
                btn.setProperty("disabled_sector", True)
            if is_toggle:
                btn.setProperty("is_toggle", True)
                btn.setProperty("toggle_on", is_on)

            if cb or not is_enabled:
                btn.clicked.connect(self.make_click_handler(key, cb))
            self.buttons[key] = btn

    def make_click_handler(self, key, callback):
        def handler():
            is_enabled, reason = self.sector_states.get(key, (True, ""))
            label = self.items_meta[key][0] if key in self.items_meta else key
            self.cleanup_and_close()
            if is_enabled:
                ToastNotification.show_toast(f"Triggered: {label}", toast_type="info")
                if callback:
                    callback()
            else:
                ToastNotification.show_toast(reason or "Action is disabled in current context.", toast_type="warning")

        return handler

    def show_at_cursor(self):
        self.evaluate_sector_states()
        for key, btn in self.buttons.items():
            is_enabled, _ = self.sector_states.get(key, (True, ""))
            btn.setProperty("disabled_sector", not is_enabled)
            if key in self.toggle_states:
                is_on = self.toggle_states[key]
                btn.setProperty("toggle_on", is_on)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        cursor_pos = QCursor.pos()
        self.origin_pos = cursor_pos
        self.move(cursor_pos.x() - 260, cursor_pos.y() - 260)
        self.active_direction = None
        self.is_interrupted = False
        self.update_button_highlights()
        self.setWindowOpacity(1.0)
        self.show()
        self.activateWindow()
        self.grabKeyboard()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center = QPoint(260, 260)

        # Circular neutral center zone rendering (Radius 26px)
        accent = QColor(self.accent_color)
        if self.active_direction is None:
            painter.setPen(QPen(QColor(160, 174, 192, 140), 2))
            painter.setBrush(QBrush(QColor(26, 32, 44, 200)))
            painter.drawEllipse(center, 26, 26)
        else:
            is_enabled, _ = self.sector_states.get(self.active_direction, (True, ""))
            if is_enabled:
                painter.setPen(QPen(QColor(255, 255, 255, 240), 2))
                painter.setBrush(QBrush(QColor(accent.red(), accent.green(), accent.blue(), 200)))
            else:
                painter.setPen(QPen(QColor(113, 128, 150, 200), 2))
                painter.setBrush(QBrush(QColor(45, 55, 72, 180)))
            painter.drawEllipse(center, 26, 26)

        # Draw visual underscore bar for toggle buttons using a lighter tint of the accent
        accent_color = QColor(self.accent_color)
        light = accent_color.lighter(170)
        for key, btn in self.buttons.items():
            if key in self.toggle_states:
                is_on = self.toggle_states[key]
                geo = btn.geometry()
                if is_on:
                    painter.setPen(QPen(QColor(light.red(), light.green(), light.blue(), 230), 3))
                    painter.drawLine(geo.left() + 8, geo.bottom() - 3, geo.right() - 8, geo.bottom() - 3)
                else:
                    painter.setPen(QPen(QColor(light.red(), light.green(), light.blue(), 55), 2))
                    painter.drawLine(geo.left() + 20, geo.bottom() - 3, geo.right() - 20, geo.bottom() - 3)

    def mouseMoveEvent(self, event):
        self.update_selection_from_mouse()
        super().mouseMoveEvent(event)

    def update_selection_from_mouse(self):
        cursor_pos = QCursor.pos()
        origin = getattr(self, "origin_pos", None)
        if origin is None:
            origin = self.mapToGlobal(QPoint(260, 260))

        dx = cursor_pos.x() - origin.x()
        dy = cursor_pos.y() - origin.y()
        dist = math.hypot(dx, dy)

        old_direction = self.active_direction

        # Circular neutral deadzone (radius 45px)
        if dist < 45:
            self.active_direction = None
        else:
            angle = math.degrees(math.atan2(dy, dx))
            # 8 Sectors of 45 degrees each
            if -112.5 <= angle < -67.5:
                self.active_direction = "N"
            elif -67.5 <= angle < -22.5:
                self.active_direction = "NE"
            elif -22.5 <= angle < 22.5:
                self.active_direction = "E"
            elif 22.5 <= angle < 67.5:
                self.active_direction = "SE"
            elif 67.5 <= angle < 112.5:
                self.active_direction = "S"
            elif 112.5 <= angle < 157.5:
                self.active_direction = "SW"
            elif angle >= 157.5 or angle < -157.5:
                self.active_direction = "W"
            elif -157.5 <= angle < -112.5:
                self.active_direction = "NW"

        if self.active_direction != old_direction:
            self.update_button_highlights()
            self.update()

    def update_button_highlights(self):
        for key, btn in self.buttons.items():
            is_active = key == self.active_direction
            btn.setProperty("active", is_active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def interrupt_and_wait_for_release(self):
        """Visually hide the menu on interrupt, but keep listening in the background until key release."""
        if not getattr(self, "is_interrupted", False):
            self.is_interrupted = True
            self.active_direction = None
            self.setWindowOpacity(0.0)
            self.move(-10000, -10000)

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat():
            event.ignore()
            return

        trigger_keys = (
            Qt.Key_Space,
            Qt.Key_Tab,
            Qt.Key_Control,
            Qt.Key_Alt,
            Qt.Key_Return,
            Qt.Key_Enter,
        )

        if getattr(self, "is_interrupted", False):
            # Only close on release of trigger activation keys (e.g. Space/Tab/Ctrl/Alt).
            # Ignore release of interrupt keys (e.g. F11/Escape) to keep listening until onSpaceRelease!
            if event.key() in trigger_keys:
                self.cleanup_and_close()
            return

        if event.key() in trigger_keys:
            self.trigger_selected_action()
        else:
            super().keyReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            event.ignore()
            return

        # F11 or Escape interrupts the Pie call and waits for release
        if event.key() in (Qt.Key_F11, Qt.Key_Escape):
            self.interrupt_and_wait_for_release()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        # Right Click or Left Click outside effective range interrupts the Pie call and waits for release
        if event.button() == Qt.RightButton:
            self.interrupt_and_wait_for_release()
        elif event.button() == Qt.LeftButton:
            if self.active_direction is None:
                self.interrupt_and_wait_for_release()
            else:
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def trigger_selected_action(self):
        self.update_selection_from_mouse()
        target_direction = self.active_direction
        is_enabled, reason = self.sector_states.get(target_direction, (True, "")) if target_direction else (True, "")
        target_cb = self.callbacks.get(target_direction) if target_direction else None
        label = (
            self.items_meta[target_direction][0]
            if target_direction and target_direction in self.items_meta
            else target_direction
        )

        self.cleanup_and_close()
        if target_direction:
            if is_enabled:
                ToastNotification.show_toast(f"Triggered: {label}", toast_type="info")
                if target_cb:
                    target_cb()
            else:
                ToastNotification.show_toast(reason or "Action is disabled in current context.", toast_type="warning")

    def cleanup_and_close(self):
        self.is_interrupted = False
        try:
            self.releaseKeyboard()
        except Exception:
            pass
        self.close()
