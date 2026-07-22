from krita import Krita
from .hello_extension import HelloExtension

app = Krita.instance()
app.addExtension(HelloExtension(app))
