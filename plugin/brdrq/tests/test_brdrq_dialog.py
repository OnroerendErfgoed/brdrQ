# coding=utf-8
"""Dialog tests.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""
from __future__ import absolute_import

__author__ = 'suporte.dsgtools@dsg.eb.mil.br'
__date__ = '2015-04-07'
__copyright__ = 'Copyright 2015, Brazilian Army - Geographic Service Bureau'

import unittest

from PyQt5.QtTest import QTest
from qgis.PyQt.QtWidgets import QDialogButtonBox, QDialog

from ..brdrq_dockwidget_featurealigner import brdrQDockWidgetFeatureAligner

from .utilities import get_qgis_app
QGIS_APP = get_qgis_app()


class brdrQDockWidgetFeatureAlignerTest(unittest.TestCase):
    """Test dialog works."""

    def setUp(self):
        """Runs before each tests."""
        self.dialog = brdrQDockWidgetFeatureAligner(None)

    def tearDown(self):
        """Runs after each tests."""
        self.dialog = None

    def test_dialog_ok(self):
        """Test we can click OK."""
        self.dialog.startDock()
        self.dialog.pushButton_settings.click()
        QTest.mouseClick(self.dialog.pushButton_settings)
        pass
        # button = self.dialog.button_box.button(QDialogButtonBox.Ok)
        # button.click()
        # result = self.dialog.result()
        # self.assertEqual(result, QDialog.Accepted)

    def test_dialog_cancel(self):
        """Test we can click cancel."""
        pass
        # button = self.dialog.button_box.button(QDialogButtonBox.Cancel)
        # button.click()
        # result = self.dialog.result()
        # self.assertEqual(result, QDialog.Rejected)

if __name__ == "__main__":
    suite = unittest.makeSuite(brdrQDockWidgetFeatureAlignerTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
