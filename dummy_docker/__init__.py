from krita import DockWidgetFactory, DockWidgetFactoryBase, Krita

from .dummy_docker import DummyDocker

DOCKER_ID = "dummy_docker"

factory = DockWidgetFactory(DOCKER_ID, DockWidgetFactoryBase.DockRight, DummyDocker)
Krita.instance().addDockWidgetFactory(factory)
