from krita import Krita
from .pie_menu_extension import PieMenuExtension

app = Krita.instance()
app.addExtension(PieMenuExtension(app))
