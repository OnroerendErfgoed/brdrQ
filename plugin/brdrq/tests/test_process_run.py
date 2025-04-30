import os
import sys
import unittest

from qgis.core import QgsProcessing
from qgis.core import (
     QgsApplication,
     QgsProcessingFeedback,
     QgsVectorLayer
)

from ..brdrq_provider import BrdrQProvider

#from ..brdrq_provider import BrdrQProvider

# See https://gis.stackexchange.com/a/155852/4972 for details about the prefix
#QgsApplication.setPrefixPath('/usr', True)
class TestProcess(unittest.TestCase):
    def test_autocorrectborders(self):
        qgs = QgsApplication([], True)
        qgs.initQgis()

        # Append the path where processing plugin can be found
        sys.path.append("C:/Program Files/QGIS 3.38.1/apps/qgis/python/plugins")

        import processing
        from processing.core.Processing import Processing
        Processing.initialize()

        path = os.path.join(os.path.dirname(__file__), "themelayer.geojson")
        themelayername1 = "themelayer1"
        layer_theme_1 = QgsVectorLayer(path, themelayername1)
        themelayername2 = "themelayer2"
        layer_theme_2 = QgsVectorLayer(path, themelayername2)

        # You can see what parameters are needed by the algorithm
        # using: processing.algorithmHelp("qgis:union")
        params = {
            'INPUT' : layer_theme_1,
            'OVERLAY' : layer_theme_2,
            'OUTPUT' : QgsProcessing.TEMPORARY_OUTPUT
        }
        feedback = QgsProcessingFeedback()

        # See https://gis.stackexchange.com/a/276979/4972 for a list of algorithms
        res = processing.run('qgis:union', params, feedback=feedback)
        res['OUTPUT'] # Access your output layer

        # Add our own algorithm provider
        provider = BrdrQProvider()
        QgsApplication.processingRegistry().addProvider(provider)

        # Run our custom algorithm
        path = os.path.join(os.path.dirname(__file__), "themelayer.geojson")
        themelayername1 = "themelayer1"
        layer_theme_1 = QgsVectorLayer(path, themelayername1)
        params = {'INPUT': layer_theme_1}
        res = processing.run("brdrqprovider:my_algorithm", params)
        print("RESULT:", res['OUTPUT'])
