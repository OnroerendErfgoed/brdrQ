import os
import sys
import unittest

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import (
    QPushButton,
    QDialogButtonBox,
)
from qgis.core import QgsApplication
from qgis.core import (
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsVectorLayer,
)
from qgis.gui import QgsMapCanvas

from .utilities import get_qgis_app
from ..brdrq_dockwidget_featurealigner import brdrQDockWidgetFeatureAligner
from ..brdrq_plugin import BrdrQPlugin
from ..brdrq_provider import BrdrQProvider
from ..brdrq_utils import get_layer_by_name

sys.path.append("C:/Program Files/QGIS 3.38.1/apps/qgis/python/plugins")
import processing
from processing.core.Processing import Processing


CANVAS: QgsMapCanvas
QGISAPP, CANVAS, IFACE, PARENT = get_qgis_app()
Processing.initialize()


class TestFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        print("setup TestClass")


    @classmethod
    def tearDownClass(cls) -> None:
        print("start tearDown TestClass")
        print("end tearDown TestClass")

    def test_autocorrectborders(self):
        # See https://gis.stackexchange.com/a/276979/4972 for a list of algorithms
        project = QgsProject.instance()
        path = os.path.join(os.path.dirname(__file__), "themelayer_2.geojson")
        themelayername = "themelayer_2"
        layer_theme = QgsVectorLayer(path, themelayername)
        project.addMapLayer(layer_theme)

        provider = BrdrQProvider()
        QgsApplication.processingRegistry().addProvider(provider)

        processing.run(
            "brdrqprovider:brdrqautocorrectborders",
            {
                "INPUT_THEMATIC": themelayername,
                "COMBOBOX_ID_THEME": "theme_identifier",
                "RELEVANT_DISTANCE": 2,
                "ENUM_REFERENCE": 1,
                "INPUT_REFERENCE": None,
                "COMBOBOX_ID_REFERENCE": "",
                "WORK_FOLDER": "",
                "ENUM_OD_STRATEGY": 4,
                "THRESHOLD_OVERLAP_PERCENTAGE": 50,
                "ADD_FORMULA": True,
                "ADD_ATTRIBUTES": True,
                "SHOW_INTERMEDIATE_LAYERS": True,
                "PREDICTIONS": False,
                "SHOW_LOG_INFO": False,
            },
        )
        assert True
        project.removeAllMapLayers()


    def test_full_success(self):
        """Test the full workflow from opening the dialog to align features"""
        project = QgsProject.instance()
        CRS = QgsCoordinateReferenceSystem.fromEpsgId(31370)
        # CANVAS.setExtent(QgsRectangle(1469703, 6870031, 1506178, 6907693))
        CANVAS.setDestinationCrs(CRS)
        path = os.path.join(os.path.dirname(__file__), "themelayer_2.geojson")
        themelayername = "themelayer_2"
        layer_theme = QgsVectorLayer(path, themelayername)
        project.addMapLayer(layer_theme)

        # Create and open the dialog
        brdrqplugin = BrdrQPlugin(IFACE)
        widget = brdrQDockWidgetFeatureAligner(brdrqplugin, None)
        widget._initi()
        layer_theme = get_layer_by_name(themelayername)
        assert layer_theme.name() == themelayername
        layers = project.mapLayers(validOnly=True)
        self.assertEqual(len(layers), 1)
        # need to import here so that there's already an initialized QGIS app

        helpDialog = widget.helpDialog
        assert helpDialog is not None
        self.assertFalse(helpDialog.isVisible())
        widget.show_help_dialog()
        self.assertTrue(helpDialog.isVisible())
        # # Click the map button which should close the dialog
        help_ok_button: QPushButton = helpDialog.buttonBox.button(QDialogButtonBox.Ok)
        QTest.mouseClick(help_ok_button, Qt.LeftButton)
        self.assertFalse(helpDialog.isVisible())

        # kies themelayer in widget
        widget.mMapLayerComboBox.setLayer(None)
        widget.mMapLayerComboBox.setLayer(layer_theme)
        listwidget_features = widget.listWidget_features
        print(str(listwidget_features.count()))
        print("current_layer: " + widget.mMapLayerComboBox.currentLayer().name())
        for x in range(listwidget_features.count()):
            item = listwidget_features.item(x)
            widget.onFeatureActivated(item)
        layers = project.mapLayers(validOnly=True)
        self.assertEqual(len(layers), 5)
        project.removeAllMapLayers()
        widget.close()