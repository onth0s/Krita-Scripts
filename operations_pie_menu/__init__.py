from krita import Krita
from .operations_pie_menu import OperationsPieMenuExtension

app = Krita.instance()
app.addExtension(OperationsPieMenuExtension(app))
