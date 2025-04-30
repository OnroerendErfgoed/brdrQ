import os
import sys
from qgis.core import (
     QgsApplication, 
     QgsVectorLayer
)

from ..brdrq_provider import BrdrQProvider

# See https://gis.stackexchange.com/a/155852/4972 for details about the prefix
# QgsApplication.setPrefixPath('/docs/dev/qgis/core/QGIS/build_master/output', True)
qgs = QgsApplication([], False)
qgs.initQgis()

# Append the path where processing plugin can be found
sys.path.append("C:/Program Files/QGIS 3.38.1/apps/qgis/python/plugins")

import processing
from processing.core.Processing import Processing
Processing.initialize()

# Add our own algorithm provider
provider = BrdrQProvider()
QgsApplication.processingRegistry().addProvider(provider)

# Run our custom algorithm
path = os.path.join(os.path.dirname(__file__), "themelayer.geojson")
themelayername1 = "themelayer1"
layer_theme_1 = QgsVectorLayer(path, themelayername1)
params = {'INPUT': layer_theme_1}
print("RESULT:", processing.run("brdrqprovider:my_algorithm", params)['OUTPUT'])
