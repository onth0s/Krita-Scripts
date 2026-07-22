from krita import Extension, Krita
from .pie_widget import PieMenuWidget

class FiltersPieMenuExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)
        self.pie_widget = None

    def setup(self):
        pass

    def createActions(self, window):
        action = window.createAction("trigger_filters_pie_menu", "Filters Pie Menu", "tools/scripts")
        action.triggered.connect(self.show_pie_menu)

    def show_pie_menu(self):
        try:
            if self.pie_widget is not None:
                if self.pie_widget.isVisible() or getattr(self.pie_widget, 'is_interrupted', False):
                    return
        except (RuntimeError, ReferenceError):
            self.pie_widget = None

        callbacks = {
            'N':  lambda: self.trigger_action('hsv_adjustment', "HSV Adjustment..."),
            'NE': lambda: self.trigger_action('color_curves', "Color Adjustment curves..."),
            'E':  lambda: self.trigger_action('color_balance', "Color Balance..."),
            'SE': lambda: self.trigger_action('slope_offset_power', "Slope, Offset, Power..."),
            'S':  lambda: self.trigger_action('desaturate', "Desaturate..."),
            'SW': lambda: self.trigger_action('auto_contrast', "Auto Contrast"),
            'W':  lambda: self.trigger_action('levels', "Levels..."),
            'NW': lambda: self.trigger_action('invert', "Invert"),
        }
        self.pie_widget = PieMenuWidget(callbacks)
        self.pie_widget.show_at_cursor()

    def trigger_action(self, action_id, fallback_text):
        app = Krita.instance()
        action = app.action(action_id)
        if action:
            action.trigger()
            return True

        # Fallback: search registered actions by name or label text
        search_target = fallback_text.replace('.', '').replace('&', '').strip().lower()
        for act in app.actions():
            act_text = act.text().replace('&', '').replace('.', '').strip().lower()
            act_id = act.objectName().lower()
            if search_target in act_text or action_id.lower() in act_id:
                act.trigger()
                return True
        return False
