from krita import Krita
from .conditions_pie_menu import ConditionsPieMenuExtension

Krita.instance().addExtension(ConditionsPieMenuExtension(Krita.instance()))
