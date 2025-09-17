import os
import unittest

# sys.path.append("C:/Program Files/QGIS 3.38.1/apps/qgis/python/plugins")
from processing.core.Processing import Processing
from qgis.core import (
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsVectorLayer,
)
from qgis.gui import QgsMapCanvas

from .utilities import get_qgis_app
from ..brdrq_plugin import BrdrQPlugin

CANVAS: QgsMapCanvas
QGISAPP, CANVAS, IFACE, PARENT = get_qgis_app()
Processing.initialize()


class TestFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        print("setup TestClass")
        # QGISAPP.initQgis()

    @classmethod
    def tearDownClass(cls) -> None:
        print("start tearDown TestClass")
        # QGISAPP.exitQgis()
        print("end tearDown TestClass")

    def test_open_version(self):
        """Test the full workflow from opening the dialog to align features"""
        project = QgsProject.instance()
        CRS = QgsCoordinateReferenceSystem.fromEpsgId(31370)
        # CANVAS.setExtent(QgsRectangle(1469703, 6870031, 1506178, 6907693))
        CANVAS.setDestinationCrs(CRS)
        path = os.path.join(os.path.dirname(__file__), "themelayer_e2e.geojson")
        themelayername = "themelayer_e2e"
        layer_theme = QgsVectorLayer(path, themelayername)
        project.addMapLayer(layer_theme)
        # Create and open the dialog
        brdrqplugin = BrdrQPlugin(IFACE)
        brdrqplugin.openInfo()
        brdrqplugin.closeInfo()
