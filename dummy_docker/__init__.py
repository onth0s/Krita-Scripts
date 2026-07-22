from krita import Krita, DockWidgetFactory, DockWidgetFactoryBase
from .dummy_docker import DummyDocker

DOCKER_ID = 'dummy_docker'

instance = Krita.instance()
factory = DockWidgetFactory(DOCKER_ID, DockWidgetFactoryBase.DockRight, DummyDocker)
instance.addDockWidgetFactory(factory)
