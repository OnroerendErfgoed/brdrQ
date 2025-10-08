import unittest

from processing.core.Processing import Processing
from qgis.gui import QgsMapCanvas

from .utilities import get_qgis_app
from ..brdrq_dockwidget_featurealigner import brdrQDockWidgetFeatureAligner
from ..brdrq_plugin import BrdrQPlugin

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
        #widget.get_wkt()


