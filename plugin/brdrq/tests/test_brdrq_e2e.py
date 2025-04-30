import os
import sys
import unittest

from qgis.core import QgsProcessingContext

from ..brdrq_algorithm_autocorrectborders import AutocorrectBordersProcessingAlgorithm

sys.path.append("C:/Program Files/QGIS 3.38.1/apps/qgis/python/plugins")
import processing
from processing.core.Processing import Processing

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import (
    QPushButton,
    QDialogButtonBox,
)
from qgis.core import QgsProcessingFeedback
from qgis.core import QgsApplication
from qgis.core import QgsProcessing
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
from ..brdrq_provider import BrdrQProvider

CANVAS: QgsMapCanvas
QGISAPP, CANVAS, IFACE, PARENT = get_qgis_app()
Processing.initialize()


class TestFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        print("setup TestClass")
        cls.project = QgsProject.instance()

        CRS = QgsCoordinateReferenceSystem.fromEpsgId(31370)
        cls.project = QgsProject.instance()
        # CANVAS.setExtent(QgsRectangle(1469703, 6870031, 1506178, 6907693))
        CANVAS.setDestinationCrs(CRS)

        path = os.path.join(os.path.dirname(__file__), "themelayer.geojson")
        cls.themelayername = "themelayer"
        cls.layer_theme = QgsVectorLayer(path, cls.themelayername)
        cls.project.addMapLayer(cls.layer_theme)

        # Create and open the dialog
        brdrqplugin = BrdrQPlugin(IFACE)
        cls.widget = brdrQDockWidgetFeatureAligner(brdrqplugin, None)
        cls.widget.activate()

    @classmethod
    def tearDownClass(cls) -> None:
        print("start tearDown TestClass")
        cls.project.removeAllMapLayers()
        cls.widget.close()
        # cls.qgs.exitQgis()
        print("end tearDown TestClass")

    def test_autocorrectborders(self):
        # Append the path where processing plugin can be found

        # path = os.path.join(os.path.dirname(__file__), "themelayer.geojson")
        # themelayername1 = "themelayer1"
        # layer_theme_1 = QgsVectorLayer(path, themelayername1)
        # themelayername2 = "themelayer2"
        # layer_theme_2 = QgsVectorLayer(path, themelayername2)
        #
        # # You can see what parameters are needed by the algorithm
        # # using: processing.algorithmHelp("qgis:union")
        # params = {
        #     "INPUT": layer_theme_1,
        #     "OVERLAY": layer_theme_2,
        #     "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
        #     "BLABLA": "test",
        # }
        # feedback = QgsProcessingFeedback()

        # See https://gis.stackexchange.com/a/276979/4972 for a list of algorithms
        # res = processing.run("qgis:union", params, feedback=feedback)
        # res["OUTPUT"]  # Access your output layer
        path = os.path.join(os.path.dirname(__file__), "themelayer.geojson")
        themelayername = "themelayer"
        layer_theme = QgsVectorLayer(path, themelayername)
        QgsProject.instance().addMapLayer(layer_theme)

        provider = BrdrQProvider()
        QgsApplication.processingRegistry().addProvider(provider)

        # Run our custom algorithm
        # path = os.path.join(os.path.dirname(__file__), "themelayer.geojson")
        # themelayername1 = "themelayer1"
        QgsProject.instance()
        # layer_theme_1 = QgsVectorLayer(path, themelayername1)
        params = {'INPUT': themelayername}
        res = processing.run("brdrqprovider:my_algorithm", params)
        print("RESULT:", res['OUTPUT'])

        # output1 = processing.run(
        #     "native:fixgeometries",
        #     {
        #         "INPUT": self.layer_theme,
        #         "METHOD": 1,
        #         "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
        #     },
        #     # context=context,
        #     feedback=feedback,
        #     is_child_algorithm=True,
        # )
        # help = processing.algorithmHelp("brdrqprovider:brdrqautocorrectborders")
        # print(str(help))
        #
        # help = processing.algorithmHelp("brdrqprovider:myscript")
        # print(str(help))
        # alg = QgsApplication.processingRegistry().algorithmById(
        #     "brdrqprovider:myscript"
        # )
        # context=QgsProcessingContext()
        # alg.run({
        #         "INPUT": self.layer_theme,
        #         "OUTPUT": "TEMPORARY_OUTPUT",
        #     }, context, feedback, {}, False)

        # alg = QgsApplication.processingRegistry().algorithmById("brdrqprovider:brdrqautocorrectborders")
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

    def test_full_success(self):
        """Test the full workflow from opening the dialog to align features"""
        layer_theme = get_layer_by_name(self.themelayername)
        assert layer_theme.name() == self.themelayername
        layers = self.project.mapLayers(validOnly=True)
        self.assertEqual(len(layers), 1)
        # need to import here so that there's already an initialized QGIS app
        widget = self.widget

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
        print("current_layer: " + widget.mMapLayerComboBox.currentLayer().name())
        listwidget_features = widget.listWidget_features
        print(str(listwidget_features.count()))
        print("current_layer: " + widget.mMapLayerComboBox.currentLayer().name())
        for x in range(listwidget_features.count()):
            item = listwidget_features.item(x)
            widget.onFeatureActivated(item)
            # listwidget_features.setCurrentItem(item)
            # rect = listwidget_features.visualItemRect(item)
            # QTest.mouseClick(listwidget_features, Qt.LeftButton, pos=rect.center(), delay=3000)
            # time.sleep(5)
            # Check if layers are added (1 + 4)
            layers = self.project.mapLayers(validOnly=True)
            self.assertEqual(len(layers), 5)

        # self.assertIsInstance(CANVAS.mapTool(), PointTool)
        #
        # # Click in the map canvas, which should return the clicked coord,
        # # make the dialog visible again
        # map_releases = QgsMapMouseEvent(
        #     CANVAS,
        #     QEvent.MouseButtonRelease,
        #     QPoint(0, 0),
        #     Qt.LeftButton,
        #     Qt.LeftButton,
        #     Qt.NoModifier,
        # )
        # dlg.point_tool.canvasReleaseEvent(map_releases)
        # self.assertRegex(dlg.lineedit_xy.text(), r"^(\d+\.\d+.+\d+\.\d+)$")
        # self.assertTrue(dlg.isVisible())
        #
        # # Clicking the OK button should load the Nominatim result layer
        # QTest.mouseClick(
        #     dlg.button_box.button(QDialogButtonBox.Ok), Qt.LeftButton
        # )
        # layers = project.mapLayers(validOnly=True)
        # self.assertEqual(len(layers), 1)
        #
        # result_layer: QgsVectorLayer = list(layers.values())[0]
        #
        # # Also should be only one feature
        # result_features: QgsFeatureIterator = result_layer.getFeatures()
        # feat: QgsFeature = next(result_features)
        # self.assertRaises(StopIteration, next, result_features)
        #
        # # Test the attributes and geometry
        # self.assertIn("Havelland,", feat["address"])
        # self.assertIn("OpenStreetMap contributors", feat["license"])
        # self.assertAlmostEqual(
        #     feat.geometry().asPoint().x(), 12.703847, delta=1.0
        # )
        # self.assertAlmostEqual(
        #     feat.geometry().asPoint().y(), 52.590965, delta=1.0
        # )

    # def test_full_failure(self):
    #     """Test failing request"""
    #
    #     # need to import here so that there's already an initialized QGIS app
    #
    #     # first set up a project
    #     CRS = QgsCoordinateReferenceSystem.fromEpsgId(3857)
    #     project = QgsProject.instance()
    #     project.setCrs(CRS)
    #     CANVAS.setExtent(QgsRectangle(258889, 7430342, 509995, 7661955))
    #     CANVAS.setDestinationCrs(CRS)
    #
    #     # Create and open the dialog
    #     dlg = QuickApiDialog(IFACE)
    #     dlg.open()
    #     self.assertTrue(dlg.isVisible())
    #
    #     # Click the map button which should hide the dialog
    #     map_button: QPushButton = dlg.map_button
    #     QTest.mouseClick(map_button, Qt.LeftButton)
    #     self.assertFalse(dlg.isVisible())
    #     self.assertIsInstance(CANVAS.mapTool(), PointTool)
    #
    #     # Click in the map canvas, which should return the clicked coord,
    #     # make the dialog visible again
    #     map_releases = QgsMapMouseEvent(
    #         CANVAS,
    #         QEvent.MouseButtonRelease,
    #         QPoint(0, 0),  # Relative to the canvas' dimensions
    #         Qt.LeftButton,
    #         Qt.LeftButton,
    #         Qt.NoModifier,
    #     )
    #     dlg.point_tool.canvasReleaseEvent(map_releases)
    #     self.assertRegex(dlg.lineedit_xy.text(), r"^(\d+\.\d+.+\d+\.\d+)$")
    #     self.assertTrue(dlg.isVisible())
    #
    #     # Clicking the OK button should result in a QMessageBox.critical dialog
    #     def handle_msgbox():
    #         msgbox: QMessageBox = QApplication.activeWindow()
    #         self.assertIsInstance(msgbox, QMessageBox)
    #         self.assertIn("Unable to geocode", msgbox.text())
    #         QTest.mouseClick(msgbox.button(QMessageBox.Ok), Qt.LeftButton)
    #
    #     # Time the MsgBox tests to 7000 ms after clicking
    #     # the OK button (Nominatim rate limiting for ~6 secs..)
    #     QTimer.singleShot(7000, handle_msgbox)
    #     QTest.mouseClick(
    #         dlg.button_box.button(QDialogButtonBox.Ok), Qt.LeftButton
    #     )
    #
    #     # No layers produced
    #     layers = project.mapLayers(validOnly=True)
    #     self.assertEqual(len(layers), 0)
