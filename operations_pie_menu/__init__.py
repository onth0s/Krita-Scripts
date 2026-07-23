from krita import Krita

from .operations_pie_menu import OperationsPieMenuExtension

Krita.instance().addExtension(OperationsPieMenuExtension(Krita.instance()))
