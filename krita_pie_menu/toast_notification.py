from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout, QGraphicsOpacityEffect

class ToastNotification(QWidget):
    """
    Sleek, animated Toast Notification widget positioned at the bottom-left of Krita main window.
    """
    _active_toast = None

    def __init__(self, message, parent=None, duration_ms=2500, toast_type="warning"):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint)
        self.setObjectName("ToastNotification")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.duration_ms = duration_ms
        self.toast_type = toast_type
        
        # Border accent color based on toast type
        if toast_type == "success":
            accent_hex = "#48BB78"
        elif toast_type == "info":
            accent_hex = "#4299E1"
        else:
            accent_hex = "#ECC94B"
            
        self.accent_color = QColor(accent_hex)
        self.bg_color = QColor(18, 24, 34, 245)
        self.border_color = QColor(255, 255, 255, 40)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 10, 16, 10)
        
        self.label = QLabel(message, self)
        self.label.setStyleSheet("""
            QLabel {
                color: #F7FAFC;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
                font-weight: 600;
                background: transparent;
            }
        """)
        layout.addWidget(self.label)
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)

    def paintEvent(self, event):
        from PyQt5.QtGui import QPainter, QPainterPath, QPen, QBrush
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(0, 0, -1, -1)
        r = 6.0  # border radius

        # Outer background path
        path = QPainterPath()
        path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), r, r)

        # Fill background
        painter.fillPath(path, QBrush(self.bg_color))

        # Draw subtle outer border outline
        painter.setPen(QPen(self.border_color, 1))
        painter.drawPath(path)

        # Left accent bar path (clipped to left rounded corners)
        accent_bar_w = 5.0
        accent_path = QPainterPath()
        accent_path.moveTo(rect.x() + r, rect.y())
        accent_path.lineTo(rect.x() + accent_bar_w, rect.y())
        accent_path.lineTo(rect.x() + accent_bar_w, rect.y() + rect.height())
        accent_path.lineTo(rect.x() + r, rect.y() + rect.height())
        accent_path.arcTo(rect.x(), rect.y() + rect.height() - 2*r, 2*r, 2*r, 270, -90)
        accent_path.lineTo(rect.x(), rect.y() + r)
        accent_path.arcTo(rect.x(), rect.y(), 2*r, 2*r, 180, -90)
        accent_path.closeSubpath()

        painter.fillPath(accent_path, QBrush(self.accent_color))
        
    def fade_in(self):
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(200)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.start()
        
        # Schedule fade out
        QTimer.singleShot(self.duration_ms, self.fade_out)

    def fade_out(self):
        self.anim_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim_out.setDuration(300)
        self.anim_out.setStartValue(1.0)
        self.anim_out.setEndValue(0.0)
        self.anim_out.setEasingCurve(QEasingCurve.InCubic)
        self.anim_out.finished.connect(self.close)
        self.anim_out.start()

    @classmethod
    def get_left_dockers_offset(cls):
        """
        Calculate maximum right boundary of visible dockers attached to LeftDockWidgetArea in Krita main window.
        """
        try:
            from krita import Krita
            app = Krita.instance()
            win = app.activeWindow()
            if not win:
                return 0
            qwin = win.qwindow()
            if not qwin:
                return 0
            
            from PyQt5.QtWidgets import QDockWidget, QMainWindow
            # Check if qwin is or contains QMainWindow
            main_window = qwin if isinstance(qwin, QMainWindow) else qwin.findChild(QMainWindow)
            if not main_window:
                # Search up or down for QMainWindow instance
                parent = qwin.parent()
                while parent:
                    if isinstance(parent, QMainWindow):
                        main_window = parent
                        break
                    parent = parent.parent()
            
            if not main_window:
                return 0
                
            max_right = 0
            docks = main_window.findChildren(QDockWidget)
            for dock in docks:
                if dock.isVisible() and not dock.isFloating():
                    if main_window.dockWidgetArea(dock) == Qt.LeftDockWidgetArea:
                        # Convert dock geometry relative to main window
                        dock_geo = dock.geometry()
                        dock_right = dock_geo.x() + dock_geo.width()
                        if dock_right > max_right:
                            max_right = dock_right
            return max_right
        except Exception:
            return 0

    @classmethod
    def show_toast(cls, message, parent=None, duration_ms=2500, toast_type="warning"):
        if cls._active_toast:
            try:
                cls._active_toast.close()
            except Exception:
                pass
            cls._active_toast = None
            
        toast = cls(message, parent=parent, duration_ms=duration_ms, toast_type=toast_type)
        cls._active_toast = toast
        
        toast.adjustSize()
        margin_x = 20
        margin_y = 40
        
        left_dock_offset = cls.get_left_dockers_offset()
        
        if parent:
            geo = parent.geometry()
            pos_x = geo.x() + max(margin_x, left_dock_offset + 12)
            pos_y = geo.y() + geo.height() - toast.height() - margin_y
        else:
            from PyQt5.QtWidgets import QApplication
            app_inst = QApplication.instance()
            active_win = app_inst.activeWindow() if app_inst else None
            
            if active_win:
                win_geo = active_win.geometry()
                pos_x = win_geo.x() + max(margin_x, left_dock_offset + 12)
                pos_y = win_geo.y() + win_geo.height() - toast.height() - margin_y
            else:
                screen = QApplication.primaryScreen().geometry()
                pos_x = screen.x() + max(margin_x, left_dock_offset + 12)
                pos_y = screen.y() + screen.height() - toast.height() - margin_y
            
        toast.move(pos_x, pos_y)
        toast.show()
        toast.fade_in()
