from krita import Krita

from .filters_pie_menu import FiltersPieMenuExtension

Krita.instance().addExtension(FiltersPieMenuExtension(Krita.instance()))
