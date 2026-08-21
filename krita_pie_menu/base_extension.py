from typing import Any, Dict, Optional, Tuple

from krita import Extension

from .pie_widget import PieMenuWidget
from .utils import load_config, save_config


class BasePieMenuExtension(Extension):
    """
    Abstract base class for Krita radial Pie Menu extensions.
    Handles configuration management, stale widget cleanup, and standard guard patterns.
    """

    def __init__(
        self,
        parent,
        config_path: str,
        default_config: Dict[str, Any],
        accent_color: str = "#3182CE",
        object_name: str = "BasePieWidget",
        menu_title: Optional[str] = None,
    ):
        super().__init__(parent)
        self.pie_widget: Optional[PieMenuWidget] = None
        self.config_path = config_path
        self.default_config = default_config
        self.accent_color = accent_color
        self.object_name = object_name
        self.menu_title = menu_title

    def setup(self):
        pass

    def load_config(self) -> Dict[str, Any]:
        """
        Loads JSON configuration from `self.config_path`, falling back to `self.default_config`.
        """
        return load_config(self.config_path, self.default_config)

    def save_config(self, cfg: Dict[str, Any]) -> bool:
        """
        Saves dictionary configuration to `self.config_path`.
        """
        return save_config(self.config_path, cfg)

    def _on_widget_destroyed(self):
        """
        Qt signal handler triggered when self.pie_widget is garbage collected or destroyed.
        """
        self.pie_widget = None

    def show_pie_menu(self):
        """
        Guarded method to instantiate and show the pie menu at current cursor position.
        """
        try:
            if self.pie_widget is not None:
                if self.pie_widget.isVisible() or getattr(self.pie_widget, "is_interrupted", False):
                    return
        except (RuntimeError, ReferenceError):
            self.pie_widget = None

        self.pie_widget = None

        callbacks, items_meta, validators, toggle_states = self.build_pie_config()

        self.pie_widget = PieMenuWidget(
            callbacks,
            items_meta=items_meta,
            validators=validators,
            toggle_states=toggle_states,
            accent_color=self.accent_color,
            object_name=self.object_name,
            menu_title=self.menu_title,
        )
        try:
            self.pie_widget.destroyed.connect(self._on_widget_destroyed)
        except Exception:
            pass

        self.pie_widget.show_at_cursor()

    def build_pie_config(self) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """
        Abstract method. Must return tuple of (callbacks, items_meta, validators, toggle_states).
        """
        raise NotImplementedError("Subclasses of BasePieMenuExtension must implement build_pie_config()")

    def open_config_dialog(self):
        """
        Abstract method for opening the plugin configuration dialog.
        """
        raise NotImplementedError("Subclasses of BasePieMenuExtension must implement open_config_dialog()")
