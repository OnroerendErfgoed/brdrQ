import os
import sys
import unittest

from qgis.core import QgsApplication, QgsProject
from qgis.core import QgsWkbTypes
from qgis.utils import loadPlugin, startPlugin, plugins, initInterface

from .utilities import get_qgis_app

QGIS_APP, CANVAS, IFACE, PARENT = get_qgis_app()
#TODO https://github.com/heremaps/xyz-qgis-plugin/blob/master/test/mock_iface.py
class TestBrdrqPlugin(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Start QGIS application
        # cls.qgs = QgsApplication([], True)
        #
        # cls.qgs.setPrefixPath(os.environ["QGIS_PREFIX_PATH"], True)
        #
        # cls.qgs.initQgis()
        #initInterface(0)

        # Voeg de plugin directory toe aan sys.path
        sys.path.append("C:/Users/KarelDieussaert/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins")

        # Laad en start de QuickWKT plugin
        plugin_name = 'brdrq'
        loadPlugin(plugin_name)
        startPlugin(plugin_name)

    @classmethod
    def tearDownClass(cls):
        pass
        # Exit QGIS application
        #cls.qgs.exitQgis()

    def test_brdrq(self):
        # Controleer of de plugin is geladen
        plugin_name = 'brdrq'
        self.assertIn(plugin_name, plugins)

        # Activeer de plugin
        plugin = plugins[plugin_name]
        plugin.initGui()


        version =plugin.version()
        assert version == "0.10.0"

if __name__ == '__main__':
    unittest.main()
