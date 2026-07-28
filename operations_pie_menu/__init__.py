"""
Operations Pie Menu extension registration module for Krita.
"""

from krita import Krita

from .operations_pie_menu import OperationsPieMenuExtension

Krita.instance().addExtension(OperationsPieMenuExtension(Krita.instance()))
