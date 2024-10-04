# -*- coding: utf-8 -*-

"""
***************************************************************************
*   name: brdrQ - Autocorrectborders
*   version: v0.9.8
*   author: Karel Dieussaert
*   Docs and Code- repo: https://github.com/OnroerendErfgoed/brdrQ/
*   history:
*            -initial version based on pyQGIS
*            -added exclusion of circles
*            -more efficient merge/union-logical
*            -removed resulting group layer (to prevent crashing of QGIS) - extra research needed
*            -add logic for openbaar domein (od_strategy)
*            -intermediate layers added as an advanced parameter
*            -Native processes as child_algorithms
*            -Process NonThreaded to fix QGIS from crashing
*            -Added advanced parameter for processing input-multipolygons as single polygons
*            -rewriting to use Aligner (shapely-python)
*            -cleanup and added docs to Aligner
*            -resulting output made available for further QGIS-modelling
*            -added enum - parameter to download actual GRB (adp-gbg-knw)
*            -added enum - parameter for od-strategy
*            -changes implemented for refactored brdr
*            -uses new version of brdr (0.2.0?)
*            -refactoring of functions to brdr-functions
*            -possibility to use predictor-function in brdr
*            -refactoring of functions to brdr-functions for v0.4.0

MIT LICENSE:
Copyright (c) 2023-2024 Flanders Heritage Agency

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify,
merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the
following conditions:

The above copyright notice and this permission notice shall be included in all copies
or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR
THE USE OR OTHER DEALINGS IN THE SOFTWARE.
***************************************************************************
"""
import datetime
import json
import os
import site
import subprocess
import sys

import numpy as np
from qgis import processing
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsCoordinateReferenceSystem
from qgis.core import QgsFeatureRequest
from qgis.core import QgsGeometry
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingException
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingOutputVectorLayer
from qgis.core import QgsProcessingParameterBoolean
from qgis.core import QgsProcessingParameterDefinition
from qgis.core import QgsProcessingParameterEnum
from qgis.core import QgsProcessingParameterFeatureSource
from qgis.core import QgsProcessingParameterField
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProject
from qgis.core import QgsSimpleLineSymbolLayer, QgsFillSymbol, \
    QgsSingleSymbolRenderer, QgsMapLayer, QgsLayerTreeNode, QgsLayerTreeGroup
from qgis.core import QgsStyle
from qgis.core import QgsVectorLayer
from qgis.utils import iface


# helper function to find embedded python
# path in windows. Based on
# https://github.com/qgis/QGIS/issues/45646
def find_python():
    if sys.platform != "win32":
        return sys.executable

    for path in sys.path:
        assumed_path = os.path.join(path, "python.exe")
        if os.path.isfile(assumed_path):
            return assumed_path

    raise Exception("Python executable not found")


sys.path.insert(0, site.getusersitepackages())
python_exe = find_python()

try:
    from shapely import (
        Polygon,
        from_wkt,
        to_wkt,
        unary_union,
        make_valid
    )
    from shapely.geometry import shape
except (ModuleNotFoundError):
    print("Module shapely not found. Installing from PyPi.")
    subprocess.check_call([python_exe,
                           '-m', 'pip', 'install', 'shapely'])
    from shapely import (
        Polygon,
        from_wkt,
        to_wkt,
        unary_union,
        make_valid
    )
    from shapely.geometry import shape

try:
    import brdr

    if brdr.__version__ != "0.4.0":
        raise ValueError("Version mismatch")

except (ModuleNotFoundError, ValueError):
    subprocess.check_call([python_exe,
                           '-m', 'pip', 'install', 'brdr==0.4.0'])
    import brdr

    print(brdr.__version__)

from brdr.aligner import Aligner
from brdr.loader import DictLoader
from brdr.enums import OpenbaarDomeinStrategy, GRBType, AlignerInputType, AlignerResultType
from brdr.geometry_utils import geojson_polygon_to_multipolygon
from brdr.grb import GRBActualLoader, GRBFiscalParcelLoader, update_to_actual_grb
from brdr.constants import FORMULA_FIELD_NAME


class AutocorrectBordersProcessingAlgorithm(QgsProcessingAlgorithm):
    """
    This script searches for overlap relevance between thematic borders and reference
    borders, and creates a resulting border based on the overlapping areas that are
    relevant.
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    # THEMATIC PARAMETERS
    INPUT_THEMATIC = "INPUT_THEMATIC"  # reference to the combobox for choosing the thematic input layer
    ID_THEME_FIELDNAME = ""  # parameters that holds the fieldname of the unique theme id

    # REFERENCE PARAMETERS
    INPUT_REFERENCE = "INPUT_REFERENCE"  # reference to the combobox for choosing the reference input layer
    LAYER_REFERENCE_NAME = "LAYER_REFERENCE_NAME"  # Name of the local referencelayer in the TOC
    ID_REFERENCE_FIELDNAME = "CAPAKEY"  # field that holds the fieldname of the unique reference id,defaults to CAPAKEY
    # ENUM for choosing the reference
    GRB_TYPES = [e.name for e in GRBType]  # types of actual GRB: parcels, buildings, artwork
    ADPF_VERSIONS = ["Adpf" + str(x) for x in
                     [datetime.datetime.today().year - i for i in range(6)]]  # Fiscal parcels of past 5 years
    ENUM_REFERENCE_OPTIONS = [
                                 "LOCAL REFERENCE LAYER (choose LAYER and ID below)"] + GRB_TYPES + ADPF_VERSIONS  # Options for downloadable reference layers
    SELECTED_REFERENCE = None  # parameter that holds the chosen reference layer (0 means that a local reference layer is used)

    # ENUM for choosing the OD-strategy
    ENUM_OD_STRATEGY_OPTIONS = [e.name for e in OpenbaarDomeinStrategy]  # list with od-strategy-options

    # LAYER parameters
    PREFIX = "brdrQ"  # prefix used for all layers and group layers
    SUFFIX = ""  # parameter for composing a suffix for the layers
    GROUP_LAYER = PREFIX  # parameter for group layer
    GROUP_LAYER_ACTUAL = PREFIX + "_ACTUAL"  # parameter for group layer when calculating an actualisation to actual GRB
    LAYER_RESULT = "RESULT"  # parameter that holds the TOC layername of the result
    LAYER_RESULT_DIFF = "DIFF"  # parameter that holds the TOC layername of the resulting diff
    LAYER_RESULT_DIFF_PLUS = "DIFF_PLUS"  # parameter that holds the TOC layername of the resulting diff_plus
    LAYER_RESULT_DIFF_MIN = "DIFF_MIN"  # parameter that holds the TOC layername of the resulting diff_min
    LAYER_RELEVANT_INTERSECTION = "RLVNT_ISECT"  # parameter that holds the TOC layername of the relevant intersection
    LAYER_RELEVANT_DIFFERENCE = "RLVNT_DIFF"  # parameter that holds the TOC layername of the relevant difference

    LAYER_RESULT_ACTUAL = "RESULT_ACTUAL"  # parameter that holds the TOC layername of the actualised result
    LAYER_RESULT_ACTUAL_DIFF = "RESULT_ACTUAL_DIFF"  # parameter that holds the TOC layername of the actualised resulting diff
    PREFIX_LOCAL_LAYER = "LOCREF"  # prefix for the TOC layername, when a local layer is used

    # ALIGNER parameters
    CRS = "EPSG:31370"  # default CRS for the aligner,updated by CRS of thematic inputlayer
    OD_STRATEGY = 0  # default OD_STRATEGY for the aligner,updated by user-choice
    THRESHOLD_OVERLAP_PERCENTAGE = 50  # default THRESHOLD_OVERLAP_PERCENTAGE for the aligner,updated by user-choice
    RELEVANT_DISTANCE = 0  # default RELEVANT_DISTANCE for the aligner,updated by user-choice
    CORR_DISTANCE = 0.01  # default CORR_DISTANCE for the aligner
    MULTI_AS_SINGLE_MODUS = True  # default MULTI_AS_SINGLE_MODUS for the aligner

    # CHECKBOX parameters defaults
    SHOW_INTERMEDIATE_LAYERS = True
    ADD_FORMULA = True
    ATTRIBUTES = True
    PREDICTIONS = False
    UPDATE_TO_ACTUAL = False
    SHOW_LOG_INFO = False

    # OTHER parameters
    MAX_AREA_FOR_DOWNLOADING_REFERENCE = 2500000  # maximum area that is covered by thematic features for blocking on-the fly downloading reference layers
    MAX_DISTANCE_FOR_ACTUALISATION = 3  # maximum relevant distance that is used in the predictor when trying to update to actual GRB

    def flags(self):
        return super().flags() | QgsProcessingAlgorithm.FlagNoThreading

    @staticmethod
    def tr(string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        return AutocorrectBordersProcessingAlgorithm()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return "brdrqautocorrectborders"

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr("brdrQ - AutoCorrectBorders")

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr("brdrQ")

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return "brdrq"

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it.
        """
        return self.tr(
            "This script searches for overlap relevance between thematic borders and "
            "reference borders, and creates a resulting border based on the overlapping "
            "areas that are relevant."
            "Documentation can be found at: https://github.com/OnroerendErfgoed/brdrQ/ "
        )

    def geom_shapely_to_qgis(self, geom_shapely):
        """
        Method to convert a Shapely-geometry to a QGIS geometry
        """
        wkt = to_wkt(make_valid(geom_shapely), rounding_precision=-1, output_dimension=2)
        geom_qgis = QgsGeometry.fromWkt(wkt)
        return geom_qgis

    def geom_qgis_to_shapely(self, geom_qgis):
        """
        Method to convert a QGIS-geometry to a Shapely-geometry
        """
        if geom_qgis.isNull() or geom_qgis.isEmpty():
            return None
        wkt = geom_qgis.asWkt()
        geom_shapely = from_wkt(wkt)
        return make_valid(geom_shapely)

    def get_layer_by_name(self, layer_name):
        """
        Get the layer-object based on the layername
        """
        layers = QgsProject.instance().mapLayersByName(layer_name)
        return layers[0]

    def move_to_group(self, thing, group, pos=0, expanded=False):
        """Move a layer tree node into a layer tree group.
        docs:https://docs.qgis.org/3.34/en/docs/pyqgis_developer_cookbook/cheat_sheet.html

        Parameter
        ---------

        thing : group name (str), layer id (str), qgis.core.QgsMapLayer, qgis.core.QgsLayerTreeNode

          Thing to move.  Can be a tree node (i.e. a layer or a group) or
          a map layer, the object or the string name/id.

        group : group name (str) or qgis.core.QgsLayerTreeGroup

          Group to move the thing to. If group does not already exist, it
          will be created.

        pos : int

          Position to insert into group. Default is 0.

        extended : bool

          Collapse or expand the thing moved. Default is False.

        Returns
        -------

        Tuple containing the moved thing and the group moved to.

        Note
        ----

        Moving destroys the original thing and creates a copy. It is the
        copy which is returned.

        """

        qinst = QgsProject.instance()
        tree = qinst.layerTreeRoot()

        # thing
        if isinstance(thing, str):
            try:  # group name
                node_object = tree.findGroup(thing)
            except:  # layer id
                node_object = tree.findLayer(thing)
        elif isinstance(thing, QgsMapLayer):
            node_object = tree.findLayer(thing)
        elif isinstance(thing, QgsLayerTreeNode):
            node_object = thing  # tree layer or group

        # group
        if isinstance(group, QgsLayerTreeGroup):
            group_name = group.name()
        else:  # group is str
            group_name = group

        group_object = tree.findGroup(group_name)

        if not group_object:
            group_object = tree.insertGroup(0, group_name)

        # do the move
        node_object_clone = node_object.clone()
        node_object_clone.setExpanded(expanded)
        group_object.insertChildNode(pos, node_object_clone)

        parent = node_object.parent()
        parent.removeChildNode(node_object)

        return (node_object_clone, group_object)

    def get_renderer(self, fill_symbol):
        """
        Get a QGIS renderer to add symbology to a QGIS-layer
        """
        # to get all properties of symbol:
        # print(layer.renderer().symbol().symbolLayers()[0].properties())
        # see: https://opensourceoptions.com/loading-and-symbolizing-vector-layers
        if isinstance(fill_symbol, str):
            fill_symbol = QgsStyle.defaultStyle().symbol(fill_symbol)
        if fill_symbol is None:
            fill_symbol = QgsFillSymbol([QgsSimpleLineSymbolLayer.create()])
        if isinstance(fill_symbol, QgsFillSymbol):
            return QgsSingleSymbolRenderer(fill_symbol.clone()).clone()
        return None

    def geojson_to_layer(self, name, geojson, symbol, visible, group):
        """
        Add a geojson to a QGIS-layer to add it to the TOC
        """
        qinst = QgsProject.instance()
        lyrs = qinst.mapLayersByName(name)
        root = qinst.layerTreeRoot()

        if len(lyrs) != 0:
            for lyr in lyrs:
                root.removeLayer(lyr)
                qinst.removeMapLayer(lyr.id())

        fcString = json.dumps(geojson_polygon_to_multipolygon(geojson), default=str)

        vl = QgsVectorLayer(fcString, name, "ogr")
        vl.setCrs(QgsCoordinateReferenceSystem(self.CRS))
        # pr = vl.dataProvider()
        vl.updateFields()
        # styling
        # vl.setOpacity(0.5)

        if symbol is not None and vl.renderer() is not None:
            vl.renderer().setSymbol(symbol)

        # adding layer to TOC
        qinst.addMapLayer(
            vl, False
        )  # False so that it doesn't get inserted at default position

        root.insertLayer(0, vl)

        node = root.findLayer(vl.id())
        if node:
            new_state = Qt.Checked if visible else Qt.Unchecked
            node.setItemVisibilityChecked(new_state)

        self.move_to_group(vl, group)
        vl.triggerRepaint()
        iface.layerTreeView().refreshLayerSymbology(vl.id())
        return vl

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # standard parameters
        parameter = QgsProcessingParameterFeatureSource(
            self.INPUT_THEMATIC,
            self.tr("THEMATIC LAYER"),
            [QgsProcessing.TypeVectorAnyGeometry],
            defaultValue="themelayer",
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)
        parameter = QgsProcessingParameterField(
            "COMBOBOX_ID_THEME",
            "Choose thematic ID",
            "theme_identifier",
            self.INPUT_THEMATIC,
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        parameter = QgsProcessingParameterNumber(
            "RELEVANT_DISTANCE",
            "RELEVANT_DISTANCE (meter)",
            type=QgsProcessingParameterNumber.Double,
            defaultValue=2,
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        parameter = QgsProcessingParameterEnum(
            "ENUM_REFERENCE",
            "Select Reference Layer:",
            options=self.ENUM_REFERENCE_OPTIONS,
            defaultValue=0,  # Index of the default option (e.g., 'Option A')
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        parameter = QgsProcessingParameterFeatureSource(
            self.INPUT_REFERENCE,
            self.tr("REFERENCE LAYER"),
            [QgsProcessing.TypeVectorAnyGeometry],
            # defaultValue="referencelayer",
            optional=True
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        parameter = QgsProcessingParameterField(
            "COMBOBOX_ID_REFERENCE",
            "Choose reference ID",
            self.ID_REFERENCE_FIELDNAME,  # defaults to CAPAKEY
            self.INPUT_REFERENCE,
            optional=True,
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        self.addOutput(
            QgsProcessingOutputVectorLayer(
                "OUTPUT_RESULT",
                self.LAYER_RESULT,
                QgsProcessing.TypeVectorAnyGeometry,
            )
        )
        self.addOutput(
            QgsProcessingOutputVectorLayer(
                "OUTPUT_RESULT_DIFF",
                self.LAYER_RESULT_DIFF,
                QgsProcessing.TypeVectorAnyGeometry,
            )
        )
        self.addOutput(
            QgsProcessingOutputVectorLayer(
                "OUTPUT_RESULT_DIFF_PLUS",
                self.LAYER_RESULT_DIFF_PLUS,
                QgsProcessing.TypeVectorAnyGeometry,
            )
        )
        self.addOutput(
            QgsProcessingOutputVectorLayer(
                "OUTPUT_RESULT_DIFF_MIN",
                self.LAYER_RESULT_DIFF_MIN,
                QgsProcessing.TypeVectorAnyGeometry,
            )
        )
        # advanced parameters

        parameter = QgsProcessingParameterEnum(
            "ENUM_OD_STRATEGY",
            'Select OD-STRATEGY:',
            options=self.ENUM_OD_STRATEGY_OPTIONS,
            defaultValue=5  # Index of the default option (e.g., 'SNAP_FULL_AREA_ALL_SIDE')
        )
        parameter.setFlags(parameter.flags() |
                           QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter)

        parameter = QgsProcessingParameterNumber(
            "THRESHOLD_OVERLAP_PERCENTAGE",
            "THRESHOLD_OVERLAP_PERCENTAGE (%)",
            type=QgsProcessingParameterNumber.Double,
            defaultValue=50,
        )
        parameter.setFlags(parameter.flags() |
                           QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter)

        parameter = QgsProcessingParameterBoolean(
            "ADD_FORMULA", "ADD_FORMULA", defaultValue=self.ADD_FORMULA
        )
        parameter.setFlags(parameter.flags() |
                           QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter)

        parameter = QgsProcessingParameterBoolean(
            "ADD_ATTRIBUTES", "ADD_ATTRIBUTES", defaultValue=self.ATTRIBUTES
        )
        parameter.setFlags(parameter.flags() |
                           QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter)

        parameter = QgsProcessingParameterBoolean(
            "SHOW_INTERMEDIATE_LAYERS", "SHOW_INTERMEDIATE_LAYERS", defaultValue=self.SHOW_INTERMEDIATE_LAYERS
        )
        parameter.setFlags(parameter.flags() |
                           QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter)

        parameter = QgsProcessingParameterBoolean(
            "PREDICTIONS", "GET_ALL_PREDICTIONS_FOR_RELEVANT_DISTANCE", defaultValue=self.PREDICTIONS
        )
        parameter.setFlags(parameter.flags() |
                           QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter)

        parameter = QgsProcessingParameterBoolean(
            "UPDATE_TO_ACTUAL", "UPDATE_TO_ACTUAL_GRB_ADP_VERSION (adp-parcels only)",
            defaultValue=self.UPDATE_TO_ACTUAL
        )
        parameter.setFlags(parameter.flags() |
                           QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter)

        parameter = QgsProcessingParameterNumber(
            "MAX_DISTANCE_FOR_ACTUALISATION",
            "MAX_DISTANCE_FOR_ACTUALISATION (meter)",
            type=QgsProcessingParameterNumber.Double,
            defaultValue=2,
            optional=True
        )
        parameter.setFlags(parameter.flags() |
                           QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter)

        parameter = QgsProcessingParameterBoolean(
            "SHOW_LOG_INFO", "SHOW_LOG_INFO (brdr-log)", defaultValue=self.SHOW_LOG_INFO
        )
        parameter.setFlags(parameter.flags() |
                           QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter)

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        feedback_steps = 6
        feedback = QgsProcessingMultiStepFeedback(feedback_steps, feedback)
        feedback.pushInfo("START")
        feedback.setCurrentStep(1)
        outputs = {}

        self.prepare_parameters(parameters)

        thematic, thematic_buffered = self._thematic_preparation(
            context, feedback, outputs, parameters
        )
        if thematic is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.test))

        # Load thematic into a shapely_dict:
        dict_thematic = {}
        dict_thematic_properties = {}
        features = thematic.getFeatures()
        for current, feature in enumerate(features):
            feature_geom = feature.geometry()
            if feedback.isCanceled():
                return {}
            id_theme = feature.attribute(self.ID_THEME_FIELDNAME)
            dict_thematic[id_theme] = self.geom_qgis_to_shapely(feature_geom)
            if self.ATTRIBUTES:
                dict_thematic_properties[id_theme] = feature.__geo_interface__["properties"]
                # json.loads(QgsJsonUtils.exportAttributes(feature))

        area = make_valid(unary_union(list(dict_thematic.values()))).area
        feedback.pushInfo("Area of thematic zone: " + str(area))
        if self.SELECTED_REFERENCE != 0 and area > self.MAX_AREA_FOR_DOWNLOADING_REFERENCE:
            raise QgsProcessingException(
                "Unioned area of thematic geometries bigger than threshold (" + str(
                    self.MAX_AREA_FOR_DOWNLOADING_REFERENCE) + " m²) to use the on-the-fly downloads: " + str(
                    area) + "(m²) " +
                "Please make use of a local REFERENCELAYER (for performance reasons)"
            )
        feedback.pushInfo("1) BEREKENING - Thematic layer fixed")
        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # REFERENCE PREPARATION
        if self.SELECTED_REFERENCE == 0:
            reference = self._reference_preparation(
                thematic_buffered, context, feedback, outputs, parameters
            )

            # Load reference into a shapely_dict:
            dict_reference = {}
            features = reference.getFeatures()
            for current, feature in enumerate(features):
                if feedback.isCanceled():
                    return {}
                id_reference = feature.attribute(self.ID_REFERENCE_FIELDNAME)
                dict_reference[id_reference] = self.geom_qgis_to_shapely(
                    feature.geometry()
                )
        feedback.pushInfo("2) BEREKENING - Reference layer fixed")
        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # Aligner IMPLEMENTATION
        if self.SHOW_LOG_INFO:
            log_info = feedback
        else:
            log_info = None
        aligner = Aligner(feedback=log_info,
                          relevant_distance=self.RELEVANT_DISTANCE,
                          od_strategy=self.OD_STRATEGY,
                          crs=self.CRS,
                          multi_as_single_modus=self.MULTI_AS_SINGLE_MODUS,
                          correction_distance=self.CORR_DISTANCE,
                          threshold_overlap_percentage=self.THRESHOLD_OVERLAP_PERCENTAGE,
                          )

        feedback.pushInfo("Load thematic data")
        aligner.load_thematic_data(DictLoader(dict_thematic, dict_thematic_properties))
        aligner.name_thematic_id = self.ID_THEME_FIELDNAME

        feedback.pushInfo("Load reference data")
        if self.SELECTED_REFERENCE == 0:
            reference_loader = DictLoader(dict_reference)
            aligner.load_reference_data(DictLoader(dict_reference))
            aligner.name_reference_id = self.ID_REFERENCE_FIELDNAME
            aligner.dict_reference_source["source"] = self.PREFIX_LOCAL_LAYER + "_" + self.LAYER_REFERENCE_NAME
            aligner.dict_reference_source["version_date"] = "unknown"
        elif self.SELECTED_REFERENCE in self.ADPF_VERSIONS:
            year = self.SELECTED_REFERENCE.removeprefix("Adpf")
            aligner.load_reference_data(GRBFiscalParcelLoader(year=year, aligner=aligner, partition=1000))
        else:
            aligner.load_reference_data(
                GRBActualLoader(grb_type=GRBType(self.SELECTED_REFERENCE.value), partition=1000, aligner=aligner))
        feedback.setCurrentStep(4)
        feedback.pushInfo("START PROCESSING")
        feedback.pushInfo(
            "calculation for relevant distance (m): " + str(self.RELEVANT_DISTANCE) + " - Predictions: " + str(
                self.PREDICTIONS))
        if self.RELEVANT_DISTANCE < 0:
            raise QgsProcessingException(
                "Please provide a RELEVANT DISTANCE >=0"
            )
        elif self.RELEVANT_DISTANCE >= 0 and not self.PREDICTIONS:
            process_result = aligner.process(
                relevant_distance=self.RELEVANT_DISTANCE, od_strategy=self.OD_STRATEGY,
                threshold_overlap_percentage=self.THRESHOLD_OVERLAP_PERCENTAGE
            )
            fcs = aligner.get_results_as_geojson(formula=self.ADD_FORMULA, attributes=self.ATTRIBUTES)
        else:
            dict_series, dict_predicted, diffs = aligner.predictor(od_strategy=self.OD_STRATEGY,
                                                                   relevant_distances=np.arange(0,
                                                                                                self.RELEVANT_DISTANCE * 100,
                                                                                                10, dtype=int) / 100,
                                                                   threshold_overlap_percentage=self.THRESHOLD_OVERLAP_PERCENTAGE)
            fcs = aligner.get_results_as_geojson(resulttype=AlignerResultType.PREDICTIONS, formula=self.ADD_FORMULA,
                                                 attributes=self.ATTRIBUTES)

        feedback.pushInfo("END PROCESSING")

        if self.UPDATE_TO_ACTUAL:
            feedback.pushInfo("START ACTUALISATION")
            fcs_actualisation = update_to_actual_grb(fcs["result"], id_theme_fieldname=self.ID_THEME_FIELDNAME,
                                                     base_formula_field=FORMULA_FIELD_NAME,
                                                     max_distance_for_actualisation=self.MAX_DISTANCE_FOR_ACTUALISATION,
                                                     feedback=log_info, attributes=self.ATTRIBUTES)
            if fcs_actualisation is not None and fcs_actualisation != {}:
                # Add RESULT TO TOC
                self.geojson_to_layer(self.LAYER_RESULT_ACTUAL, fcs_actualisation["result"],
                                      QgsStyle.defaultStyle().symbol("outline blue"),
                                      True, self.GROUP_LAYER_ACTUAL)
                self.geojson_to_layer(self.LAYER_RESULT_ACTUAL_DIFF, fcs_actualisation["result_diff"],
                                      QgsStyle.defaultStyle().symbol("hashed clbue /"),
                                      False, self.GROUP_LAYER_ACTUAL)
                feedback.pushInfo("Resulterende geometrie berekend")
            else:
                feedback.pushInfo("Geen wijzigingen gedetecteerd binnen tijdspanne in referentielaag (GRB-percelen)")
            if feedback.isCanceled():
                return {}

            feedback.pushInfo("END ACTUALISATION")

        # write results to output-layers
        feedback.setCurrentStep(5)
        feedback.pushInfo("WRITING RESULTS")

        # MAKE TEMPORARY LAYERS
        if self.SELECTED_REFERENCE != 0:
            self.geojson_to_layer(self.LAYER_REFERENCE_NAME,
                                  aligner.get_input_as_geojson(inputtype=AlignerInputType.REFERENCE),
                                  QgsStyle.defaultStyle().symbol("outline black"),
                                  True, self.GROUP_LAYER)

        if self.SHOW_INTERMEDIATE_LAYERS:
            self.geojson_to_layer(self.LAYER_RELEVANT_INTERSECTION, fcs["result_relevant_intersection"],
                                  QgsStyle.defaultStyle().symbol("gradient green fill"),
                                  False, self.GROUP_LAYER)
            self.geojson_to_layer(self.LAYER_RELEVANT_DIFFERENCE, fcs["result_relevant_diff"],
                                  QgsStyle.defaultStyle().symbol("gradient red fill"),
                                  False, self.GROUP_LAYER)

        self.geojson_to_layer(self.LAYER_RESULT_DIFF, fcs["result_diff"],
                              QgsStyle.defaultStyle().symbol("hashed black X"),
                              False, self.GROUP_LAYER)
        self.geojson_to_layer(self.LAYER_RESULT_DIFF_PLUS, fcs["result_diff_plus"],
                              QgsStyle.defaultStyle().symbol("hashed cgreen /"),
                              False, self.GROUP_LAYER)
        self.geojson_to_layer(self.LAYER_RESULT_DIFF_MIN, fcs["result_diff_min"],
                              QgsStyle.defaultStyle().symbol("hashed cred /"),
                              False, self.GROUP_LAYER)
        self.geojson_to_layer(self.LAYER_RESULT, fcs["result"],
                              QgsStyle.defaultStyle().symbol("outline green"),
                              True, self.GROUP_LAYER)

        result = QgsProject.instance().mapLayersByName(self.LAYER_RESULT)[0]
        result_diff = QgsProject.instance().mapLayersByName(
            self.LAYER_RESULT_DIFF
        )[0]
        result_diff_plus = QgsProject.instance().mapLayersByName(
            self.LAYER_RESULT_DIFF_PLUS
        )[0]
        result_diff_min = QgsProject.instance().mapLayersByName(
            self.LAYER_RESULT_DIFF_MIN
        )[0]
        QgsProject.instance().reloadAllLayers()
        feedback.pushInfo("Resulterende geometrie berekend")
        if feedback.isCanceled():
            return {}
        feedback.pushInfo("EINDE: RESULTAAT BEREKEND")
        # feedback.setCurrentStep(6) #removed so the script will end before 100%-progressbar is reached
        return {
            "OUTPUT_RESULT": result,
            "OUTPUT_RESULT_DIFF": result_diff,
            "OUTPUT_RESULT_DIFF_PLUS": result_diff_plus,
            "OUTPUT_RESULT_DIFF_MIN": result_diff_min,
        }

    def _thematic_preparation(self, context, feedback, outputs, parameters):
        # THEMATIC PREPARATION
        context.setInvalidGeometryCheck(QgsFeatureRequest.GeometryNoCheck)
        outputs[self.INPUT_THEMATIC + "_fixed"] = processing.run(
            "native:fixgeometries",
            {"INPUT": parameters[self.INPUT_THEMATIC], "METHOD": 1, "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        thematic = context.getMapLayer(
            outputs[self.INPUT_THEMATIC + "_fixed"]["OUTPUT"]
        )

        outputs[self.INPUT_THEMATIC + "_dropMZ"] = processing.run(
            "native:dropmzvalues",
            {
                "INPUT": thematic,
                "DROP_M_VALUES": True,
                "DROP_Z_VALUES": True,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        thematic = context.getMapLayer(
            outputs[self.INPUT_THEMATIC + "_dropMZ"]["OUTPUT"]
        )
        # buffer the thematic layer to select all plots around it that are relevant to
        # the calculations
        outputs[self.INPUT_THEMATIC + "_buffered"] = processing.run(
            "native:buffer",
            {
                "INPUT": thematic,
                "DISTANCE": 1.01 * self.RELEVANT_DISTANCE,
                "SEGMENTS": 10,
                "END_CAP_STYLE": 0,
                "JOIN_STYLE": 1,
                "MITRE_LIMIT": 10,
                "DISSOLVE": False,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        thematic_buffered = context.getMapLayer(
            outputs[self.INPUT_THEMATIC + "_buffered"]["OUTPUT"]
        )
        return thematic, thematic_buffered

    def _reference_preparation(self, thematic_buffered, context, feedback, outputs, parameters):
        context.setInvalidGeometryCheck(QgsFeatureRequest.GeometryNoCheck)
        outputs[self.INPUT_REFERENCE + "_extract"] = processing.run(
            "native:extractbylocation",
            {
                "INPUT": parameters[self.INPUT_REFERENCE],
                "PREDICATE": [0],
                "INTERSECT": thematic_buffered,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        reference = context.getMapLayer(
            outputs[self.INPUT_REFERENCE + "_extract"]["OUTPUT"]
        )
        feedback.pushInfo("Reference extraction finished")
        outputs[self.INPUT_REFERENCE + "_fixed"] = processing.run(
            "native:fixgeometries",
            {
                "INPUT": reference,
                "METHOD": 1,
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        reference = context.getMapLayer(
            outputs[self.INPUT_REFERENCE + "_fixed"]["OUTPUT"]
        )
        feedback.pushInfo("Reference repair finished")
        outputs[self.INPUT_REFERENCE + "_dropMZ"] = processing.run(
            "native:dropmzvalues",
            {
                "INPUT": reference,
                "DROP_M_VALUES": True,
                "DROP_Z_VALUES": True,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        reference = context.getMapLayer(
            outputs[self.INPUT_REFERENCE + "_dropMZ"]["OUTPUT"]
        )
        feedback.pushInfo("Reference dropMZ finished")
        if reference is None:
            raise QgsProcessingException(
                self.invalidSourceError(parameters, self.INPUT_REFERENCE)
            )
        return reference

    def prepare_parameters(self, parameters):
        # PARAMETER PREPARATION
        self.RELEVANT_DISTANCE = parameters["RELEVANT_DISTANCE"]
        self.CRS = QgsProject.instance().layerTreeRoot().findLayer(
            parameters[
                self.INPUT_THEMATIC]).layer().sourceCrs().authid()  # set CRS for the calculations, based on the THEMATIC input layer
        self.ID_THEME_FIELDNAME = parameters["COMBOBOX_ID_THEME"]
        self.ID_REFERENCE_FIELDNAME = parameters["COMBOBOX_ID_REFERENCE"]
        self.THRESHOLD_OVERLAP_PERCENTAGE = parameters["THRESHOLD_OVERLAP_PERCENTAGE"]
        self.OD_STRATEGY = OpenbaarDomeinStrategy[self.ENUM_OD_STRATEGY_OPTIONS[parameters["ENUM_OD_STRATEGY"]]]
        self.ADD_FORMULA = parameters["ADD_FORMULA"]
        self.ATTRIBUTES = parameters["ADD_ATTRIBUTES"]
        self.SHOW_INTERMEDIATE_LAYERS = parameters["SHOW_INTERMEDIATE_LAYERS"]
        self.PREDICTIONS = parameters["PREDICTIONS"]
        self.UPDATE_TO_ACTUAL = parameters["UPDATE_TO_ACTUAL"]
        if self.PREDICTIONS and self.UPDATE_TO_ACTUAL:
            raise QgsProcessingException(
                "The PREDICTIONS-checkbox and the UPDATE_TO_ACTUAL_GRB-checkbox cannot be checked simultaneously")
        if not self.ADD_FORMULA and self.UPDATE_TO_ACTUAL:
            raise QgsProcessingException(
                "The ADD FORMULA-checkbox must be checked when using the UPDATE_TO_ACTUAL_GRB-checkbox")
        self.SHOW_LOG_INFO = parameters["SHOW_LOG_INFO"]
        self.MAX_DISTANCE_FOR_ACTUALISATION = parameters["MAX_DISTANCE_FOR_ACTUALISATION"]

        ref = self.ENUM_REFERENCE_OPTIONS[parameters["ENUM_REFERENCE"]]

        if ref in self.GRB_TYPES:
            self.SELECTED_REFERENCE = GRBType[ref]
            self.LAYER_REFERENCE_NAME = GRBType[ref]
            ref_suffix = str(ref)
        elif ref in self.ADPF_VERSIONS:
            self.SELECTED_REFERENCE = ref
            self.LAYER_REFERENCE_NAME = ref
            ref_suffix = str(ref)
        else:
            self.SELECTED_REFERENCE = 0

            if parameters[self.INPUT_REFERENCE] is None or self.ID_REFERENCE_FIELDNAME == 'NULL':
                raise QgsProcessingException(
                    "Please choose a REFERENCELAYER from the table of contents, and the associated unique REFERENCE ID")
            layer_reference = QgsProject.instance().layerTreeRoot().findLayer(
                parameters[self.INPUT_REFERENCE]).layer()
            self.LAYER_REFERENCE_NAME = layer_reference.name()
            ref_suffix = self.PREFIX_LOCAL_LAYER + "_" + self.LAYER_REFERENCE_NAME

            if layer_reference.sourceCrs().authid() != self.CRS:
                raise QgsProcessingException(
                    "Thematic layer and ReferenceLayer are in a different CRS. "
                    "Please provide them in the same CRS, with units in meter (f.e. For Belgium in EPSG:31370 or EPSG:3812)"
                )
        self.SUFFIX = "_DIST_" + str(self.RELEVANT_DISTANCE) + "_" + ref_suffix
        if self.PREDICTIONS:
            self.SUFFIX = self.SUFFIX + "_PREDICTIONS"
        self.LAYER_RELEVANT_INTERSECTION = self.LAYER_RELEVANT_INTERSECTION + self.SUFFIX
        self.LAYER_RELEVANT_DIFFERENCE = self.LAYER_RELEVANT_DIFFERENCE + self.SUFFIX
        self.LAYER_RESULT = self.LAYER_RESULT + self.SUFFIX
        self.LAYER_RESULT_DIFF = self.LAYER_RESULT_DIFF + self.SUFFIX
        self.LAYER_RESULT_DIFF_PLUS = self.LAYER_RESULT_DIFF_PLUS + self.SUFFIX
        self.LAYER_RESULT_DIFF_MIN = self.LAYER_RESULT_DIFF_MIN + self.SUFFIX
        self.GROUP_LAYER = self.GROUP_LAYER + self.SUFFIX
        self.GROUP_LAYER_ACTUAL = self.GROUP_LAYER_ACTUAL + self.SUFFIX
