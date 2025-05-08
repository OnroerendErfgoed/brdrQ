import os
import unittest

import processing
from processing.core.Processing import Processing
from qgis.core import QgsApplication
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
)
from qgis.gui import QgsMapCanvas

from .utilities import get_qgis_app
from ..brdrq_provider import BrdrQProvider
from ..brdrq_dockwidget_featurealigner import brdrQDockWidgetFeatureAligner
from .utilities import get_qgis_app
from ..brdrq_dockwidget_featurealigner import brdrQDockWidgetFeatureAligner
from ..brdrq_plugin import BrdrQPlugin
from ..brdrq_utils import get_layer_by_name
CANVAS: QgsMapCanvas
QGISAPP, CANVAS, IFACE, PARENT = get_qgis_app()
Processing.initialize()


class TestAutocorrectBorders(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        print("setup TestClass")


    @classmethod
    def tearDownClass(cls) -> None:
        print("start tearDown TestClass")
        print("end tearDown TestClass")


    def test_brdrQDockWidgetFeatureAligner(self):
        brdrqplugin = BrdrQPlugin(IFACE)
        widget = brdrQDockWidgetFeatureAligner(brdrqplugin, None)
        widget.get_graphic()


