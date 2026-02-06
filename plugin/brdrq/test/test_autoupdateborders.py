import os
import unittest

import processing
from processing.core.Processing import Processing
from qgis.core import QgsMapLayer
from qgis.core import QgsProcessingFeatureSourceDefinition
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

class TestAutoUpdateBorders(unittest.TestCase):
    def setUp(self):
        self.provider = BrdrQProvider()
        QGISAPP.processingRegistry().addProvider(self.provider)

        # self.settings = QgsSettings()
        #
        # # Reset specifiek jouw plugin/provider settings
        # # Gebruik de juiste prefix die jouw algoritme gebruikt
        # prefix = "brdrqautoupdateborders/"
        #
        # for key in self.settings.allKeys():
        #     if key.startswith(prefix):
        #         self.settings.remove(key)
        # # Forceer het wegschrijven naar schijf/geheugen
        # self.settings.sync()

    def tearDown(self):
        QGISAPP.processingRegistry().removeProvider(self.provider)
        QgsProject.instance().clear()

    def test_autoupdateborders(self):

        foldername = QgsProcessingParameterFolderDestination(name="brdrQ").generateTemporaryDestination()

        path = os.path.join(os.path.dirname(__file__), "themelayer_test.geojson")
        themelayername = "themelayer_test"
        layer_theme = QgsVectorLayer(path, themelayername)
        QgsProject.instance().addMapLayer(layer_theme)
        output = processing.run(
            "brdrqprovider:brdrqautoupdateborders",
            {
                "INPUT_THEMATIC": themelayername,
                "COMBOBOX_ID_THEME": "theme_identifier",
                "ENUM_REFERENCE": 0,
                "METADATA_FIELD": "",
                "RELEVANT_DISTANCE": 5,
                "THRESHOLD_OVERLAP_PERCENTAGE": 50,
                "ENUM_OD_STRATEGY": 2,
                "ENUM_PROCESSOR": 0,
                "WORK_FOLDER": foldername,
                "REVIEW_PERCENTAGE": 10,
                "PREDICTION_STRATEGY": 1,
                "FULL_REFERENCE_STRATEGY": 2,
                "SHOW_LOG_INFO": True,
            },
        )

        featurecount = layer_theme.featureCount()
        assert len(output)==5
        for o in output.values():
            assert isinstance(o,QgsVectorLayer)
            assert o.featureCount()==featurecount

    def test_autoupdateborders_selection(self):

        foldername = QgsProcessingParameterFolderDestination(name="brdrQ").generateTemporaryDestination()

        path = os.path.join(os.path.dirname(__file__), "themelayer_test.geojson")
        themelayername = "themelayer_test"
        layer_theme = QgsVectorLayer(path, themelayername)
        QgsProject.instance().addMapLayer(layer_theme)
        # make a selection of the first feature
        if (
            layer_theme
            and layer_theme.type() == QgsMapLayer.VectorLayer
            and layer_theme.featureCount() > 0
        ):
            first_feature = next(layer_theme.getFeatures())  # Haalt de eerste feature op
            layer_theme.select(first_feature.id())
        source = QgsProcessingFeatureSourceDefinition(
            layer_theme.id(), selectedFeaturesOnly=True, featureLimit=-1
        )

        output = processing.run(
            "brdrqprovider:brdrqautoupdateborders",
            {
                "INPUT_THEMATIC": source,
                "COMBOBOX_ID_THEME": "theme_identifier",
                "ENUM_REFERENCE": 0,
                "METADATA_FIELD": "",
                "RELEVANT_DISTANCE": 5,
                "THRESHOLD_OVERLAP_PERCENTAGE": 50,
                "ENUM_OD_STRATEGY": 2,
                "ENUM_PROCESSOR": 0,
                "WORK_FOLDER": foldername,
                "REVIEW_PERCENTAGE": 10,
                "PREDICTION_STRATEGY": 1,
                "FULL_REFERENCE_STRATEGY": 2,
                "SHOW_LOG_INFO": True,
            },
        )

        featurecount = layer_theme.featureCount()
        assert len(output)==5
        for o in output.values():
            assert isinstance(o,QgsVectorLayer)
            assert o.featureCount()==1
