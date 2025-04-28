import os
import sys
import unittest
from qgis.core import QgsApplication
from qgis.utils import loadPlugin, startPlugin, plugins

from .utilities import get_qgis_app

QGIS_APP, CANVAS, IFACE, PARENT = get_qgis_app()
class TestPluginActivation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        # Laad en start de plugin
        plugin_name = 'QuickWKT'
        loadPlugin(plugin_name)
        startPlugin(plugin_name)

    @classmethod
    def tearDownClass(cls):
        # Exit QGIS application
        QGIS_APP.exitQgis()

    def test_plugin_activation(self):
        # Controleer of de plugin is geladen
        plugin_name = 'QuickWKT'
        # self.assertIn(plugin_name, plugins)

        # Activeer de plugin
        plugin = plugins[plugin_name]
        plugin.initGui()

        # Controleer of de plugin correct is geactiveerd
        self.assertTrue(plugin.is_active)

        # Voer een specifieke functie van de plugin uit
        result = plugin.version()
        self.assertEqual(result, "0.10.0")

if __name__ == '__main__':
    unittest.main()
