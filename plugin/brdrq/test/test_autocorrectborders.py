import os
import unittest

import processing
from processing.core.Processing import Processing
from qgis.core import (
    QgsProcessingException,
    QgsMapLayer,
    QgsProcessingFeatureSourceDefinition,
)
from qgis.core import QgsProcessingParameterFolderDestination
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
)
from qgis.gui import QgsMapCanvas

from .utilities import get_qgis_app
from ..brdrq_provider import BrdrQProvider

CANVAS: QgsMapCanvas
QGISAPP, CANVAS, IFACE, PARENT = get_qgis_app()
Processing.initialize()

class TestAutoCorrectBorders(unittest.TestCase):
    def setUp(self):
        self.provider = BrdrQProvider()
        QGISAPP.processingRegistry().addProvider(self.provider)

    def tearDown(self):
        QGISAPP.processingRegistry().removeProvider(self.provider)
        QgsProject.instance().clear()
    def test_autocorrectborders(self):
        # See https://gis.stackexchange.com/a/276979/4972 for a list of algorithms
        foldername = QgsProcessingParameterFolderDestination(name="brdrQ").generateTemporaryDestination()

        path = os.path.join(os.path.dirname(__file__), "themelayer_test.geojson")
        themelayername = "themelayer_test"
        layer_theme = QgsVectorLayer(path, themelayername)
        QgsProject.instance().addMapLayer(layer_theme)

        output = processing.run(
            "brdrqprovider:brdrqautocorrectborders",
            {
                "INPUT_THEMATIC": themelayername,
                "COMBOBOX_ID_THEME": "theme_identifier",
                "RELEVANT_DISTANCE": 2,
                "ENUM_REFERENCE": 1,
                "INPUT_REFERENCE": None,
                "COMBOBOX_ID_REFERENCE": "",
                "WORK_FOLDER": foldername,
                "ENUM_OD_STRATEGY": 1,
                "THRESHOLD_OVERLAP_PERCENTAGE": 50,
                "REVIEW_PERCENTAGE": 10,
                "ADD_FORMULA": True,
                "STABILITY": True,
                "ADD_ATTRIBUTES": True,
                "SHOW_INTERMEDIATE_LAYERS": True,
                "PREDICTIONS": False,
                "SHOW_LOG_INFO": False,
            },
        )
        featurecount = layer_theme.featureCount()
        assert len(output)==5
        for o in output.values():
            assert isinstance(o,QgsVectorLayer)
            assert o.featureCount()==featurecount

    def test_autocorrectborders_fiscal(self):
        # See https://gis.stackexchange.com/a/276979/4972 for a list of algorithms
        foldername = QgsProcessingParameterFolderDestination(name="brdrQ").generateTemporaryDestination()

        path = os.path.join(os.path.dirname(__file__), "themelayer_test.geojson")
        themelayername = "themelayer_test"
        layer_theme = QgsVectorLayer(path, themelayername)
        QgsProject.instance().addMapLayer(layer_theme)

        output = processing.run(
            "brdrqprovider:brdrqautocorrectborders",
            {
                "INPUT_THEMATIC": themelayername,
                "COMBOBOX_ID_THEME": "theme_identifier",
                "RELEVANT_DISTANCE": 2,
                "ENUM_REFERENCE": 30,  # fiscal2023
                "INPUT_REFERENCE": None,
                "COMBOBOX_ID_REFERENCE": "",
                "WORK_FOLDER": foldername,
                "ENUM_OD_STRATEGY": 1,
                "THRESHOLD_OVERLAP_PERCENTAGE": 50,
                "REVIEW_PERCENTAGE": 10,
                "ADD_FORMULA": True,
                "STABILITY": True,
                "ADD_ATTRIBUTES": True,
                "SHOW_INTERMEDIATE_LAYERS": True,
                "PREDICTIONS": False,
                "SHOW_LOG_INFO": False,
            },
        )
        featurecount = layer_theme.featureCount()
        assert len(output)==5
        for o in output.values():
            assert isinstance(o,QgsVectorLayer)
            assert o.featureCount()==featurecount

    def test_autocorrectborders_selection(self):
        # See https://gis.stackexchange.com/a/276979/4972 for a list of algorithms
        foldername = QgsProcessingParameterFolderDestination(name="brdrQ").generateTemporaryDestination()

        path = os.path.join(os.path.dirname(__file__), "themelayer_test.geojson")
        themelayername = "themelayer_test"
        layer_theme = QgsVectorLayer(path, themelayername)
        QgsProject.instance().addMapLayer(layer_theme)

        if (
            layer_theme
            and layer_theme.type() == QgsMapLayer.VectorLayer
            and layer_theme.featureCount() > 0
        ):
            first_feature = next(
                layer_theme.getFeatures()
            )  # Haalt de eerste feature op
            layer_theme.select(first_feature.id())
        source = QgsProcessingFeatureSourceDefinition(
            layer_theme.id(), selectedFeaturesOnly=True, featureLimit=-1
        )

        output = processing.run(
            "brdrqprovider:brdrqautocorrectborders",
            {
                "INPUT_THEMATIC": source,
                "COMBOBOX_ID_THEME": "theme_identifier",
                "RELEVANT_DISTANCE": 2,
                "ENUM_REFERENCE": 1,
                "INPUT_REFERENCE": None,
                "COMBOBOX_ID_REFERENCE": "",
                "WORK_FOLDER": foldername,
                "ENUM_OD_STRATEGY": 1,
                "THRESHOLD_OVERLAP_PERCENTAGE": 50,
                "REVIEW_PERCENTAGE": 10,
                "ADD_FORMULA": True,
                "STABILITY": True,
                "ADD_ATTRIBUTES": True,
                "SHOW_INTERMEDIATE_LAYERS": True,
                "PREDICTIONS": False,
                "SHOW_LOG_INFO": False,
            },
        )
        featurecount = layer_theme.featureCount()
        assert len(output)==5
        for o in output.values():
            assert isinstance(o,QgsVectorLayer)
            assert o.featureCount()==featurecount

    def test_autocorrectborders_local_referencelayer(self):
        # See https://gis.stackexchange.com/a/276979/4972 for a list of algorithms
        foldername = QgsProcessingParameterFolderDestination(name="brdrQ").generateTemporaryDestination()

        path = os.path.join(os.path.dirname(__file__), "themelayer_test.geojson")
        themelayername = "themelayer_test"
        layer_theme = QgsVectorLayer(path, themelayername)
        QgsProject.instance().addMapLayer(layer_theme)

        path = os.path.join(os.path.dirname(__file__), "referencelayer_test.geojson")
        referencelayername = "referencelayer_test"
        layer_reference = QgsVectorLayer(path, referencelayername)
        QgsProject.instance().addMapLayer(layer_reference)

        output = processing.run(
            "brdrqprovider:brdrqautocorrectborders",
            {
                "INPUT_THEMATIC": themelayername,
                "COMBOBOX_ID_THEME": "theme_identifier",
                "RELEVANT_DISTANCE": 2,
                "ENUM_REFERENCE": 0,
                "INPUT_REFERENCE": referencelayername,
                "COMBOBOX_ID_REFERENCE": "CAPAKEY",
                "WORK_FOLDER": foldername,
                "ENUM_OD_STRATEGY": 1,
                "THRESHOLD_OVERLAP_PERCENTAGE": 50,
                "REVIEW_PERCENTAGE": 10,
                "ADD_FORMULA": False,
                "STABILITY": True,
                "ADD_ATTRIBUTES": True,
                "SHOW_INTERMEDIATE_LAYERS": True,
                "PREDICTIONS": False,
                "SHOW_LOG_INFO": False,
            },
        )
        featurecount = layer_theme.featureCount()
        assert len(output)==5
        for o in output.values():
            assert isinstance(o,QgsVectorLayer)
            assert o.featureCount()==featurecount

    def test_autocorrectborders_predictions(self):
        foldername = QgsProcessingParameterFolderDestination(name="brdrQ").generateTemporaryDestination()
        path = os.path.join(os.path.dirname(__file__), "themelayer_test.geojson")
        themelayername = "themelayer_test"
        layer_theme = QgsVectorLayer(path, themelayername)
        QgsProject.instance().addMapLayer(layer_theme)

        output = processing.run(
            "brdrqprovider:brdrqautocorrectborders",
            {
                "INPUT_THEMATIC": themelayername,
                "COMBOBOX_ID_THEME": "theme_identifier",
                "RELEVANT_DISTANCE": 5,
                "ENUM_REFERENCE": 1,
                "INPUT_REFERENCE": None,
                "COMBOBOX_ID_REFERENCE": "",
                "WORK_FOLDER": foldername,
                "ENUM_OD_STRATEGY": 1,
                "THRESHOLD_OVERLAP_PERCENTAGE": 50,
                "REVIEW_PERCENTAGE": 10,
                "ADD_FORMULA": True,
                "STABILITY": True,
                "ADD_ATTRIBUTES": True,
                "SHOW_INTERMEDIATE_LAYERS": True,
                "PREDICTIONS": True,
                "SHOW_LOG_INFO": False,
            },
        )
        featurecount = layer_theme.featureCount()
        assert len(output)==5
        for o in output.values():
            assert isinstance(o,QgsVectorLayer)
            assert o.featureCount()>=featurecount

    def test_autocorrectborders_wrong_input(self):
        with self.assertRaises(QgsProcessingException):
            foldername = QgsProcessingParameterFolderDestination(
                name="brdrQ"
            ).generateTemporaryDestination()
            path = os.path.join(os.path.dirname(__file__), "themelayer_test.geojson")
            themelayername = "themelayer_test"
            layer_theme = QgsVectorLayer(path, themelayername)
            QgsProject.instance().addMapLayer(layer_theme)
            processing.run(
                "brdrqprovider:brdrqautocorrectborders",
                {
                    "INPUT_THEMATIC": themelayername,
                    "COMBOBOX_ID_THEME": "theme_identifier",
                    "RELEVANT_DISTANCE": 2,
                    "ENUM_REFERENCE": 1,
                    "INPUT_REFERENCE": None,
                    "COMBOBOX_ID_REFERENCE": "",
                    "WORK_FOLDER": foldername,
                    "ENUM_OD_STRATEGY": 8,
                    "THRESHOLD_OVERLAP_PERCENTAGE": 50,
                    "REVIEW_PERCENTAGE": 10,
                    "ADD_FORMULA": True,
                    "STABILITY": True,
                    "ADD_ATTRIBUTES": True,
                    "SHOW_INTERMEDIATE_LAYERS": True,
                    "PREDICTIONS": False,
                    "SHOW_LOG_INFO": False,
                },
            )
