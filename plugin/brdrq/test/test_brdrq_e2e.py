import os
import time
import unittest

from matplotlib import pyplot as plt
# sys.path.append("C:/Program Files/QGIS 3.38.1/apps/qgis/python/plugins")
from processing.core.Processing import Processing
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import (
    QPushButton,
    QDialogButtonBox,
)
from qgis.core import (
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsVectorLayer,
)
from qgis.gui import QgsMapCanvas

from .utilities import get_qgis_app
from ..brdrq_dockwidget_featurealigner import brdrQDockWidgetFeatureAligner
from ..brdrq_plugin import BrdrQPlugin
from ..brdrq_utils import get_layer_by_name

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

    def test_full_success(self):
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
        widget = brdrQDockWidgetFeatureAligner(brdrqplugin, None)
        widget._initialize()
        widget.startDock()
        layer_theme = get_layer_by_name(themelayername)
        assert layer_theme.name() == themelayername
        layers = project.mapLayers(validOnly=True)
        self.assertEqual(len(layers), 1)
        # need to import here so that there's already an initialized QGIS app

        settingsDialog = widget.settingsDialog
        assert settingsDialog is not None
        self.assertFalse(settingsDialog.isVisible())
        widget.show_settings_dialog()
        self.assertTrue(settingsDialog.isVisible())
        # # Click the map button which should close the dialog
        settings_ok_button: QPushButton = settingsDialog.buttonBox_settings.button(
            QDialogButtonBox.Ok
        )
        QTest.mouseClick(settings_ok_button, Qt.LeftButton)
        self.assertFalse(settingsDialog.isVisible())

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
        wkt = widget.get_wkt()
        print(wkt)
        widget.get_graphic()
        time.sleep(2)
        plt.close('all')
        widget.get_visualisation()
        time.sleep(2)
        plt.close("all")
        project.removeAllMapLayers()
        widget.close()

    def test_full_success_brdrq_params(self):
        """Test the full workflow from opening the dialog to align features"""
        project = QgsProject.instance()
        CRS = QgsCoordinateReferenceSystem.fromEpsgId(31370)
        # CANVAS.setExtent(QgsRectangle(1469703, 6870031, 1506178, 6907693))
        CANVAS.setDestinationCrs(CRS)
        path = os.path.join(os.path.dirname(__file__), "themelayer_e2e_brdrq_params.geojson")
        themelayername = "themelayer_e2e"
        layer_theme = QgsVectorLayer(path, themelayername)
        project.addMapLayer(layer_theme)

        # Create and open the dialog
        brdrqplugin = BrdrQPlugin(IFACE)
        widget = brdrQDockWidgetFeatureAligner(brdrqplugin, None)
        widget._initialize()
        widget.startDock()
        layer_theme = get_layer_by_name(themelayername)
        assert layer_theme.name() == themelayername
        layers = project.mapLayers(validOnly=True)
        self.assertEqual(len(layers), 1)
        # need to import here so that there's already an initialized QGIS app

        settingsDialog = widget.settingsDialog
        assert settingsDialog is not None
        self.assertFalse(settingsDialog.isVisible())
        widget.show_settings_dialog()
        self.assertTrue(settingsDialog.isVisible())
        # # Click the map button which should close the dialog
        settings_ok_button: QPushButton = settingsDialog.buttonBox_settings.button(
            QDialogButtonBox.Ok
        )
        QTest.mouseClick(settings_ok_button, Qt.LeftButton)
        self.assertFalse(settingsDialog.isVisible())

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

    # def test_full_error_crs(self):
    #     """Test the full workflow from opening the dialog to align features"""
    #     project = QgsProject.instance()
    #     CRS = QgsCoordinateReferenceSystem.fromEpsgId(31370)
    #     # CANVAS.setExtent(QgsRectangle(1469703, 6870031, 1506178, 6907693))
    #     CANVAS.setDestinationCrs(CRS)
    #     path = os.path.join(os.path.dirname(__file__), "themelayer_e2e_brdrq_params.geojson")
    #     themelayername = "themelayer_e2e"
    #     layer_theme = QgsVectorLayer(path, themelayername)
    #     undefined_crs = QgsCoordinateReferenceSystem(0)
    #     layer_theme.setCrs(undefined_crs)
    #     project.addMapLayer(layer_theme)
    #
    #     # Create and open the dialog
    #     brdrqplugin = BrdrQPlugin(IFACE)
    #     widget = brdrQDockWidgetFeatureAligner(brdrqplugin, None)
    #     widget._initialize()
    #     widget.startDock()
    #     layer_theme = get_layer_by_name(themelayername)
    #     assert layer_theme.name() == themelayername
    #     layers = project.mapLayers(validOnly=True)
    #     self.assertEqual(len(layers), 1)
    #     # kies themelayer in widget
    #     widget.mMapLayerComboBox.setLayer(None)
    #     widget.mMapLayerComboBox.setLayer(layer_theme)
    #     widget.close()
