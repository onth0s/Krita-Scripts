from krita import Krita
from .quick_script_engine import QuickScriptEngineExtension

Krita.instance().addExtension(QuickScriptEngineExtension(Krita.instance()))
