import os
import time
import unittest

from matplotlib import pyplot as plt
# sys.path.append("C:/Program Files/QGIS 3.38.1/apps/qgis/python/plugins")
from processing.core.Processing import Processing
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import (
    QApplication,
    QDialog,
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


def dialog_ok_button():
    value = getattr(QDialogButtonBox, "Ok", None)
    if value is not None:
        return value
    std = getattr(QDialogButtonBox, "StandardButton", None)
    if std is not None and hasattr(std, "Ok"):
        return std.Ok
    raise AttributeError("QDialogButtonBox Ok enum not available")


def left_mouse_button():
    value = getattr(Qt, "LeftButton", None)
    if value is not None:
        return value
    mouse_button = getattr(Qt, "MouseButton", None)
    if mouse_button is not None and hasattr(mouse_button, "LeftButton"):
        return mouse_button.LeftButton
    raise AttributeError("Qt LeftButton enum not available")


def open_settings_dialog_and_auto_accept(widget, delay_ms=2000):
    settings_dialog = widget.settingsDialog
    assert settings_dialog is not None

    def _accept_dialog():
        if settings_dialog is None:
            return
        settings_ok_button: QPushButton = settings_dialog.buttonBox_settings.button(
            dialog_ok_button()
        )
        if settings_ok_button is not None:
            QTest.mouseClick(settings_ok_button, left_mouse_button())
            return
        settings_dialog.accept()

    QTimer.singleShot(delay_ms, _accept_dialog)
    widget.show_settings_dialog()


def open_wkt_dialog_and_auto_close(widget, delay_ms=2000):
    def _close_active_modal():
        modal = QApplication.activeModalWidget()
        if modal is None:
            return
        if isinstance(modal, QDialog):
            modal.accept()
            return
        modal.close()

    QTimer.singleShot(delay_ms, _close_active_modal)
    return widget.get_wkt()


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
        try:
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
            open_settings_dialog_and_auto_accept(widget, delay_ms=2000)
            self.assertFalse(settingsDialog.isVisible())

            # kies themelayer in widget
            widget.mMapLayerComboBox.setLayer(None)
            widget.mMapLayerComboBox.setLayer(layer_theme)
            feature_table = widget.tableFeatures
            print(str(feature_table.rowCount()))
            print("current_layer: " + widget.mMapLayerComboBox.currentLayer().name())
            for x in range(feature_table.rowCount()):
                widget.onFeatureActivated(x)
            layers = project.mapLayers(validOnly=True)
            self.assertEqual(len(layers), 5)
            wkt = open_wkt_dialog_and_auto_close(widget, delay_ms=2000)
            print(wkt)
            widget.get_graphic()
            time.sleep(2)
            plt.close("all")
            widget.get_visualisation()
            time.sleep(2)
            plt.close("all")
        finally:
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
        try:
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
            open_settings_dialog_and_auto_accept(widget, delay_ms=2000)
            self.assertFalse(settingsDialog.isVisible())

            # kies themelayer in widget
            widget.mMapLayerComboBox.setLayer(None)
            widget.mMapLayerComboBox.setLayer(layer_theme)
            feature_table = widget.tableFeatures
            print(str(feature_table.rowCount()))
            print("current_layer: " + widget.mMapLayerComboBox.currentLayer().name())
            for x in range(feature_table.rowCount()):
                widget.onFeatureActivated(x)
            layers = project.mapLayers(validOnly=True)
            self.assertEqual(len(layers), 5)
        finally:
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
