# -*- coding: utf-8 -*-

"""
/***************************************************************************
 BrdrQ
                                 A QGIS plugin
 brdrQ, a QGIS-plugin for aligning thematic borders to reference borders.
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2024-10-11
        copyright            : (C) 2024 by Karel Dieussaert / Onroerend Erfgoed
        email                : karel.dieussaert@vlaanderen.be
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'Karel Dieussaert / Onroerend Erfgoed'
__date__ = '2024-10-11'
__copyright__ = '(C) 2024 by Karel Dieussaert / Onroerend Erfgoed'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import inspect
import os
import sys

import numpy as np
from PyQt5.QtCore import Qt, QCoreApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QMessageBox
from brdr.loader import DictLoader
from qgis.core import QgsApplication
from shapely.io import from_wkt

from .brdrq_dockwidget import brdrQDockWidget
from .brdrq_provider import BrdrQProvider
from .brdrq_utils import plot_series, show_map, geom_shapely_to_qgis

cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]

if cmd_folder not in sys.path:
    sys.path.insert(0, cmd_folder)

import brdr
# try:
#     import brdr
# except:
#     import brdr
#     print("Module brdr not found. Please install it manually: pip install brdr==0.4.0")

from brdr.aligner import Aligner
from brdr.grb import GRBActualLoader
from brdr.enums import GRBType


class BrdrQPlugin(object):

    def __init__(self, iface):
        self.provider = None
        self.iface = iface
        self.dockwidget = None
        self.pluginIsActive = False
        self.actions = []
        # self.menu = self.tr('brdrQ')
        self.toolbar = self.iface.addToolBar('brdrQ')
        self.toolbar.setObjectName('brdrQ')

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('brdrQ', message)

    def initProcessing(self):
        """Init Processing provider for QGIS >= 3.8."""

        self.provider = BrdrQProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()
        icon = os.path.join(os.path.join(cmd_folder, 'icon.png'))
        action = QAction(QIcon(icon), 'brdrQ - Align borders', self.iface.mainWindow())
        action.triggered.connect(self.openDock)
        self.iface.addToolBarIcon(action)
        self.iface.addPluginToMenu("brdQ menu", action)
        self.toolbar.addAction(action)
        self.actions.append(action)
        # show the dockwidget
        # self.openDock()

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""
        pass
        # print "** CLOSING brdrQ"

        # disconnects
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)

        # remove this statement if dockwidget is to remain
        # for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe
        # when closing the docked window:
        # self.dockwidget = None

        self.pluginIsActive = False

    def unload(self):
        QgsApplication.processingRegistry().removeProvider(self.provider)
        for action in self.actions:
            self.iface.removePluginMenu('brdrQ',
                                        action)
            self.iface.removeToolBarIcon(action)
            self.toolbar.removeAction(action)
            self.iface.removePluginMenu("brdQ menu", action)
            del action
        # remove the toolbar
        del self.toolbar

    def openDock(self):
        if not self.pluginIsActive:
            self.pluginIsActive = True

            # print "** STARTING brdrQ"

            # dockwidget may not exist if:
            #    first run of plugin
            #    removed on close (see self.onClosePlugin method)
            if self.dockwidget == None:
                # Create the dockwidget (after translation) and keep reference
                self.dockwidget = brdrQDockWidget()

            # connect to provide cleanup on closing of dockwidget
            self.dockwidget.closingPlugin.connect(self.onClosePlugin)
            self.dockwidget.pushButton_grafiek.clicked.connect(self.get_graphic)
            self.dockwidget.pushButton_visualisatie.clicked.connect(self.get_visualisation)
            self.dockwidget.pushButton_geometrie.clicked.connect(self.change_geometry)
            self.dockwidget.mMapLayerComboBox.layerChanged.connect(self.setIds)
            self.dockwidget.mFeaturePickerWidget.featureChanged.connect(self.zoomToFeature)

            #
            # def select_feature():
            #     layer = self.iface.activeLayer()
            #     layer.removeSelection()
            #
            #     feature = picker.feature()
            #
            #     # Do whatever you need with feature
            #
            #     # For example, select the feature
            #     layer.select(feature.id())
            #
            # button = self.dlg.pushButton
            # button.clicked.connect(select_feature)

            # show the dockwidget
            # TODO: fix to allow choice of dock location
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
            self.dockwidget.show()

    def setIds(self):
        picker = self.dockwidget.mFeaturePickerWidget
        layer = self.dockwidget.mMapLayerComboBox.currentLayer()
        picker.setLayer(layer)
        picker.setDisplayExpression('$id')  # show ids in combobox

    def zoomToFeature(self,feature):
        box = feature.geometry().boundingBox()
        self.iface.mapCanvas().setExtent(box)
        self.iface.mapCanvas().refresh()

    def get_graphic(self):
        self._align(graphic=True)

    def get_visualisation(self):
        self._align(visualisation=True)

    def change_geometry(self):
        self._align(changeGeometry=True)

    def _align(self, graphic=False, visualisation=False,changeGeometry=False):
        print("alignment_start")
        brdr_version = str(brdr.__version__)
        feat = self.dockwidget.mFeaturePickerWidget.feature()
        selectedFeatures =[]
        if feat is not None:
            selectedFeatures.append(feat)
        #selectedFeatures = layer.selectedFeatures()
        if len(selectedFeatures) == 0:
            self.dockwidget.textEdit_output.setText("Geen features geselecteerd. Gelieve een feature te selecteren uit de actieve laag")
            return
        # take selected feature(s)
        # run brdr (to actual GRB) for this feature
        list = []
        aligner = Aligner()

        i = 0
        dict_to_load = {}

        for feature in selectedFeatures:
            i = i + 1
            feature_geom = feature.geometry()
            wkt = feature_geom.asWkt()
            geom_shapely = from_wkt(wkt)
            dict_to_load[i] = geom_shapely
        # Load thematic &reference data
        aligner.load_thematic_data(DictLoader(dict_to_load))
        loader = GRBActualLoader(grb_type=GRBType.ADP, partition=1000, aligner=aligner)
        aligner.load_reference_data(loader)
        series = np.arange(0, 300, 10, dtype=int) / 100
        dict_series, dict_predictions, diffs_dict = aligner.predictor(relevant_distances=series)

        for key in dict_predictions:
            for predicted_dist, result in dict_predictions[key].items():

                if graphic:
                    plot_series(series, {key: diffs_dict[key]})
                if visualisation:
                    show_map(
                        {key: dict_predictions[key]},
                        {key: aligner.dict_thematic[key]},
                        aligner.dict_reference,
                    )
                if changeGeometry:
                    resulting_geom = result['result']
                    layer = self.dockwidget.mMapLayerComboBox.currentLayer()
                    layer.startEditing()
                    print(layer)
                    print (feat)
                    print(feat.id())
                    qgis_geom = geom_shapely_to_qgis(resulting_geom)
                    print(qgis_geom)
                    print(resulting_geom.wkt)
                    #feat.setGeometry(geom_shapely_to_qgis(resulting_geom))
                    layer.changeGeometry(feat.id(), qgis_geom)
                    print (feat.geometry())
                    layer.commitChanges()
                    self.iface.messageBar().pushMessage("geometrie aangepast")
            outputMessage = "Voorspelde relevante afstanden: " + str(dict_predictions[key].keys())

            self.dockwidget.textEdit_output.setText(outputMessage)
            self.iface.messageBar().pushMessage(outputMessage)

                #mb = QMessageBox()

                # mb.setText('Brdr_version: ' + brdr_version + "//Predicted geometry at : " + str(
                #     predicted_dist) + " // Found wkt: " + str(resulting_geom.wkt))
                # mb.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
                # return_value = mb.exec()
                # if return_value == QMessageBox.Ok:
                #     print(str(resulting_geom.wkt))
                # elif return_value == QMessageBox.Cancel:
                #     print('You pressed Cancel')

