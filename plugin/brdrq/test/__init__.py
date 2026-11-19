# Import QGIS first so it sets the correct SIP API version.
import os
import sys

import qgis  # pylint: disable=W0611  # NOQA

# The Processing plugin is shipped beside QGIS's Python package. Resolve it
# from the active QGIS installation instead of hard-coding a QGIS 3 path.
qgis_plugins_path = os.path.join(
    os.path.dirname(os.path.dirname(qgis.__file__)), "plugins"
)
if os.path.isdir(qgis_plugins_path) and qgis_plugins_path not in sys.path:
    sys.path.append(qgis_plugins_path)

#TODO: https://github.com/gis-ops/tutorials/blob/master/qgis/QGIS_PluginTesting.md 
