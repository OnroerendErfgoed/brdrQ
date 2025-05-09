import os
import unittest

import processing
from processing.core.Processing import Processing
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

    def tearDown(self):
        QGISAPP.processingRegistry().removeProvider(self.provider)
        QgsProject.instance().clear()

    def test_autoupdateborders(self):

        foldername = QgsProcessingParameterFolderDestination(name="brdrQ").generateTemporaryDestination()

        path = os.path.join(os.path.dirname(__file__), "themelayer_test.geojson")
        themelayername = "themelayer_test"
        layer_theme = QgsVectorLayer(path, themelayername)
        QgsProject.instance().addMapLayer(layer_theme)
        output =processing.run(
            "brdrqprovider:brdrqautoupdateborders",
            {
                "INPUT_THEMATIC": themelayername,
                "COMBOBOX_ID_THEME": "theme_identifier",
                "ENUM_REFERENCE": 0,
                "FORMULA_FIELD": "",
                "MAX_RELEVANT_DISTANCE": 5,
                "WORK_FOLDER": foldername,
                "BEST_PREDICTION": True,
                "SHOW_LOG_INFO": True,
            },
        )

        featurecount = layer_theme.featureCount()
        assert len(output)==4
        for o in output.values():
            assert isinstance(o,QgsVectorLayer)
            assert o.featureCount()==featurecount

