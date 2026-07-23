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
        accent_color = "#ECC94B" if toast_type == "warning" else "#4299E1"
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 16, 10)
        
        self.label = QLabel(message, self)
        self.label.setStyleSheet(f"""
            QLabel {{
                color: #F7FAFC;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
                font-weight: 600;
            }}
        """)
        layout.addWidget(self.label)
        
        self.setStyleSheet(f"""
            QWidget#ToastNotification {{
                background-color: rgba(26, 32, 44, 240);
                border-left: 4px solid {accent_color};
                border-top: 1px solid rgba(255, 255, 255, 0.1);
                border-right: 1px solid rgba(255, 255, 255, 0.1);
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
            }}
        """)
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)
        
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
    def show_toast(cls, message, parent=None, duration_ms=2500, toast_type="warning"):
        if cls._active_toast:
            try:
                cls._active_toast.close()
            except Exception:
                pass
            cls._active_toast = None
            
        toast = cls(message, parent=parent, duration_ms=duration_ms, toast_type=toast_type)
        cls._active_toast = toast
        
        # Position toast at bottom-left corner of parent or main window/screen
        toast.adjustSize()
        margin_x = 24
        margin_y = 40
        
        if parent:
            geo = parent.geometry()
            pos_x = geo.x() + margin_x
            pos_y = geo.y() + geo.height() - toast.height() - margin_y
        else:
            from PyQt5.QtWidgets import QApplication
            screen = QApplication.primaryScreen().geometry()
            pos_x = screen.x() + margin_x
            pos_y = screen.y() + screen.height() - toast.height() - margin_y
            
        toast.move(pos_x, pos_y)
        toast.show()
        toast.fade_in()
