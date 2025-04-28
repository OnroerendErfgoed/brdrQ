# coding=utf-8
"""Tests for QGIS functionality.


.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""
__author__ = 'tim@linfiniti.com'
__date__ = '20/01/2011'
__copyright__ = ('Copyright 2012, Australia Indonesia Facility for '
                 'Disaster Reduction')

import os
import unittest

from qgis._core import QgsVectorLayer, QgsProject
from qgis.core import (
    QgsProviderRegistry,
    QgsCoordinateReferenceSystem,
    QgsRasterLayer)
from qgis.utils import iface, loadPlugin, startPlugin
from qgis.utils import plugins

from ..brdrq_dockwidget_featurealigner import brdrQDockWidgetFeatureAligner
from ..brdrq_plugin import BrdrQPlugin
from ..brdrq_utils import get_layer_by_name
from .utilities import get_qgis_app

QGIS_APP, CANVAS, IFACE, PARENT = get_qgis_app()


class QGISTest(unittest.TestCase):
    """Test the QGIS Environment"""

    def test_qgis_environment(self):
        """QGIS environment has the expected providers"""

        r = QgsProviderRegistry.instance()
        self.assertIn('gdal', r.providerList())
        self.assertIn('ogr', r.providerList())
        # self.assertIn('postgres', r.providerList())

    def test_qgis_brdrq_integration(self):
        """QGIS environment has the expected providers"""

        layer = get_layer_by_name("unexisting_layer")
        assert layer is None
        # add layer
        layer = get_layer_by_name("unexisting_layer")
        assert layer is None

    def test_qgis_brdrq_layer_utils(self):
        """QGIS environment has the expected providers"""
        #get_qgis_app()
        layer = get_layer_by_name("unexisting_layer")
        assert layer is None
        # add layer
        path = os.path.join(os.path.dirname(__file__), 'themelayer.geojson')
        title = 'themelayer'
        layer_theme = QgsVectorLayer(path, title)
        QgsProject.instance().addMapLayer(layer_theme)
        layer_theme = get_layer_by_name(title)
        assert layer_theme.name() == title

        project = QgsProject.instance()
        project.read('tests.qgz')
        print(project.fileName())

        plugin_name = "brdrq"

        loadPlugin(plugin_name)
        startPlugin(plugin_name)
        # Zorg ervoor dat de plugin is geladen

        # self.assertIn(plugin_name, plugins)

        # Activeer de plugin
        plugin = plugins[plugin_name]
        plugin.initGui()

        # Controleer of de plugin correct is geactiveerd
        self.assertTrue(plugin.is_active)

        # Voer een specifieke functie van de plugin uit
        version = plugin.version()
        expected_version = "0.10.0"
        self.assertEqual(version, expected_version)

    def test_projection(self):
        """Test that QGIS properly parses a wkt string.
        """
        crs = QgsCoordinateReferenceSystem()
        wkt = (
            'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
            'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
            'PRIMEM["Greenwich",0.0],UNIT["Degree",'
            '0.0174532925199433]]')
        crs.createFromWkt(wkt)
        auth_id = crs.authid()
        expected_auth_id = 'EPSG:4326'
        self.assertEqual(auth_id, expected_auth_id)

        # now tests for a loaded layer
        path = os.path.join(os.path.dirname(__file__), 'tenbytenraster.asc')
        title = 'TestRaster'
        layer = QgsRasterLayer(path, title)
        auth_id = layer.crs().authid()
        # self.assertEqual(auth_id, expected_auth_id)


if __name__ == '__main__':
    unittest.main()
