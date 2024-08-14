# -*- coding: utf-8 -*-

"""
***************************************************************************
*   name: brdrQ - Autocorrectborders
*   version: v0.9.6
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
import subprocess
import sys
import site
import os
import json
from qgis import processing
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsCoordinateReferenceSystem
from qgis.core import QgsField
from qgis.core import QgsGeometry
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingException
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingOutputVectorLayer
from qgis.core import QgsProcessingParameterBoolean
from qgis.core import QgsProcessingParameterEnum
from qgis.core import QgsProcessingParameterFeatureSource
from qgis.core import QgsProcessingParameterField
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProject
from qgis.core import QgsStyle
from qgis.core import QgsVectorLayer


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
        unary_union
    )
except (ModuleNotFoundError):
    print("Module shapely not found. Installing from PyPi.")
    subprocess.check_call([python_exe,
                           '-m', 'pip', 'install', 'shapely'])
    from shapely import (
        Polygon,
        from_wkt,
        to_wkt,
        unary_union
    )

try:
    import brdr

    if brdr.__version__ != "0.1.1":
        raise ValueError("Version mismatch")

except (ModuleNotFoundError, ValueError):
    subprocess.check_call([python_exe,
                           '-m', 'pip', 'install', 'brdr==0.1.1'])
    import brdr

    print(brdr.__version__)

from brdr.aligner import Aligner
from brdr.utils import multipolygons_to_singles
from brdr.enums import OpenbaarDomeinStrategy
from brdr.enums import GRBType


class AutocorrectBordersProcessingAlgorithm(QgsProcessingAlgorithm):
    """
    This script searches for overlap relevance between thematic borders and reference
    borders, and creates a resulting border based on the overlapping areas that are
    relevant.
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    INPUT_THEMATIC = "INPUT_THEMATIC"
    INPUT_REFERENCE = "INPUT_REFERENCE"

    # ENUM for choosing the reference
    ENUM_REFERENCE = "ENUM_REFERENCE"
    GRB_TYPES = [e.name for e in GRBType]
    ENUM_REFERENCE_OPTIONS = ["LOCAL REFERENCE LAYER (choose LAYER and ID below)"] + GRB_TYPES
    SELECTED_REFERENCE = None

    # ENUM for choosing the OD-strategy
    ENUM_OD_STRATEGY = "ENUM_OD_STRATEGY"
    OD_STRATEGY_TYPES = [e.name for e in OpenbaarDomeinStrategy]
    ENUM_OD_STRATEGY_OPTIONS = OD_STRATEGY_TYPES
    SELECTED_OD_STRATEGY = None

    RESULT = "RESULT"
    RESULT_DIFF = "RESULT_DIFF"
    RESULT_DIFF_PLUS = "RESULT_DIFF_PLUS"
    RESULT_DIFF_MIN = "RESULT_DIFF_MIN"
    OUTPUT_RESULT = "OUTPUT_RESULT"
    OUTPUT_RESULT_DIFF = "OUTPUT_RESULT_DIFF"
    OUTPUT_RESULT_DIFF_PLUS = "OUTPUT_RESULT_DIFF_PLUS"
    OUTPUT_RESULT_DIFF_MIN = "OUTPUT_RESULT_DIFF_MIN"

    INTERMEDIATE_LAYER_GROUP = "INTERMEDIATE_LAYER_GROUP"

    LAYER_RESULT = "brdrQ_RESULT"
    LAYER_RESULT_DIFF = "brdrQ_DIFF"
    LAYER_RESULT_DIFF_PLUS = "brdrQ_DIFF_PLUS"
    LAYER_RESULT_DIFF_MIN = "brdrQ_DIFF_MIN"
    LAYER_RELEVANT_INTERSECTION = "brdrQ_RLVNT_ISECT"
    LAYER_RELEVANT_DIFFERENCE = "brdrQ_RLVNT_DIFF"
    LAYER_REFERENCE = "LAYER_REFERENCE"

    SUFFIX = ""
    # theme_ID (can be a multipolygon)
    ID_THEME = "id_theme"
    ID_REFERENCE = "id_ref"
    OVERLAY_FIELDS_PREFIX = ""
    OD_STRATEGY = 0
    THRESHOLD_OVERLAP_PERCENTAGE = 50
    THRESHOLD_EXCLUSION_AREA = 0
    THRESHOLD_EXCLUSION_PERCENTAGE = 0
    RELEVANT_DISTANCE = 0
    BUFFER_DISTANCE = 0
    THRESHOLD_CIRCLE_RATIO = 0.98
    CORR_DISTANCE = 0.01
    SHOW_INTERMEDIATE_LAYERS = False
    PROCESS_MULTI_AS_SINGLE_POLYGONS = True
    MITRE_LIMIT = 10
    CRS = "EPSG:31370"
    QUAD_SEGS = 5
    BUFFER_MULTIPLICATION_FACTOR = 1.01
    DOWNLOAD_LIMIT = 10000
    MAX_REFERENCE_BUFFER = 10

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
        wkt = to_wkt(geom_shapely, rounding_precision=-1, output_dimension=2)
        geom_qgis = QgsGeometry.fromWkt(wkt)
        return geom_qgis

    def geom_qgis_to_shapely(self, geom_qgis):
        """
        Method to convert a QGIS-geometry to a Shapely-geometry
        """
        wkt = geom_qgis.asWkt()
        geom_shapely = from_wkt(wkt)
        return geom_shapely

    def add_formula_to_layer(self, layername, aligner):
        """this function needs a new version of brdr, because of a logging problem
        """
        layer = self.get_layer_by_name(layername)
        pr = layer.dataProvider()  # need to create a data provider
        pr.addAttributes([QgsField("formula", QVariant.String)])  # define/add field data type
        layer.updateFields()
        caps = pr.capabilities()
        features = layer.getFeatures()
        for current, feature in enumerate(features):
            if caps & pr.ChangeAttributeValues:
                formula = str(aligner.get_formula(self.geom_qgis_to_shapely(feature.geometry())))
                attrs = {1: formula}
                layer.dataProvider().changeAttributeValues({feature.id(): attrs})
        return

    def get_layer_by_name(self, layer_name):
        """
        Get the layer-object based on the layername
        """
        layers = QgsProject.instance().mapLayersByName(layer_name)
        return layers[0]

    def geojson_to_layer(self, name, geojson, style_name, visible):
        qinst = QgsProject.instance()
        lyrs = qinst.mapLayersByName(name)
        root = qinst.layerTreeRoot()
        if len(lyrs) != 0:
            for lyr in lyrs:
                root.removeLayer(lyr)
                qinst.removeMapLayer(lyr.id())
        fcString = json.dumps(geojson)

        vl = QgsVectorLayer(fcString, name, "ogr")
        print(vl)
        vl.setCrs(QgsCoordinateReferenceSystem(self.CRS))
        pr = vl.dataProvider()
        vl.updateFields()
        # styling
        vl.setOpacity(0.5)
        if style_name is None or style_name == "":
            symbol = None
        else:
            symbol = QgsStyle.defaultStyle().symbol(style_name)
        if symbol is not None:
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
        vl.triggerRepaint()
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
            self.ID_THEME,
            "Choose thematic ID",
            "theme_identifier",
            self.INPUT_THEMATIC,
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)
        parameter = QgsProcessingParameterEnum(
            self.ENUM_REFERENCE,
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
            # defaultValue=None
            defaultValue="referencelayer"
            , optional=True
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)
        parameter = QgsProcessingParameterField(
            self.ID_REFERENCE,
            "Choose reference ID",
            "ref_identifier",
            self.INPUT_REFERENCE,
            optional=True
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
            self.ENUM_OD_STRATEGY,
            'Select OD-STRATEGY:',
            options=self.ENUM_OD_STRATEGY_OPTIONS,
            defaultValue=5  # Index of the default option (e.g., 'SNAP_FULL_AREA_ALL_SIDE')
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        self.addOutput(
            QgsProcessingOutputVectorLayer(
                self.OUTPUT_RESULT,
                self.LAYER_RESULT,
                QgsProcessing.TypeVectorAnyGeometry,
            )
        )
        self.addOutput(
            QgsProcessingOutputVectorLayer(
                self.OUTPUT_RESULT_DIFF,
                self.LAYER_RESULT_DIFF,
                QgsProcessing.TypeVectorAnyGeometry,
            )
        )
        self.addOutput(
            QgsProcessingOutputVectorLayer(
                self.OUTPUT_RESULT_DIFF_PLUS,
                self.LAYER_RESULT_DIFF_PLUS,
                QgsProcessing.TypeVectorAnyGeometry,
            )
        )
        self.addOutput(
            QgsProcessingOutputVectorLayer(
                self.OUTPUT_RESULT_DIFF_MIN,
                self.LAYER_RESULT_DIFF_MIN,
                QgsProcessing.TypeVectorAnyGeometry,
            )
        )
        # advanced parameters
        parameter = QgsProcessingParameterNumber(
            "THRESHOLD_OVERLAP_PERCENTAGE",
            "THRESHOLD_OVERLAP_PERCENTAGE (%)",
            type=QgsProcessingParameterNumber.Double,
            defaultValue=50,
        )
        self.addParameter(parameter)
        parameter = QgsProcessingParameterBoolean(
            "PROCESS_MULTI_AS_SINGLE_POLYGONS",
            "PROCESS_MULTI_AS_SINGLE_POLYGONS",
            defaultValue=True,
        )
        # parameter.setFlags(parameter.flags() |
        # QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter)
        parameter = QgsProcessingParameterBoolean(
            "SHOW_INTERMEDIATE_LAYERS", "SHOW_INTERMEDIATE_LAYERS", defaultValue=False
        )
        # parameter.setFlags(parameter.flags() |
        # QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter)

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """

        feedback_steps = 6
        feedback = QgsProcessingMultiStepFeedback(feedback_steps, feedback)
        feedback.pushInfo("START")
        outputs = {}

        self.prepare_parameters(parameters)

        thematic, thematic_buffered = self._thematic_preparation(
            context, feedback, outputs, parameters
        )
        if thematic is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.test))

        # Load thematic into a shapely_dict:
        dict_thematic = {}
        features = thematic.getFeatures()
        for current, feature in enumerate(features):
            if feedback.isCanceled():
                return {}
            id_theme = feature.attribute(self.ID_THEME)
            dict_thematic[id_theme] = self.geom_qgis_to_shapely(feature.geometry())
        if self.PROCESS_MULTI_AS_SINGLE_POLYGONS:
            dict_thematic = multipolygons_to_singles(dict_thematic)
        feedback.pushInfo("1) BEREKENING - Thematic layer fixed")
        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # REFERENCE PREPARATION
        if self.SELECTED_REFERENCE == 0:
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
            if reference.sourceCrs().authid() != self.CRS:
                raise QgsProcessingException(
                    "Thematic layer and ReferenceLayer are in a different CRS. "
                    "Please provide them in the same CRS (EPSG:31370 or EPSG:3812)"
                )
            outputs[self.INPUT_REFERENCE + "_id"] = processing.run(
                "native:fieldcalculator",
                {
                    "INPUT": reference,
                    "FIELD_NAME": self.ID_REFERENCE,
                    "FIELD_TYPE": 2,
                    "FIELD_LENGTH": 0,
                    "FIELD_PRECISION": 0,
                    "FORMULA": "to_string(" + parameters[self.ID_REFERENCE] + ")",
                    "OUTPUT": "TEMPORARY_OUTPUT",
                },
                context=context,
                feedback=feedback,
                is_child_algorithm=True,
            )
            reference = context.getMapLayer(
                outputs[self.INPUT_REFERENCE + "_id"]["OUTPUT"]
            )
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
            if reference is None:
                raise QgsProcessingException(
                    self.invalidSourceError(parameters, self.INPUT_REFERENCE)
                )

            # Load reference into a shapely_dict:
            dict_reference = {}
            features = reference.getFeatures()
            for current, feature in enumerate(features):
                if feedback.isCanceled():
                    return {}
                id_reference = feature.attribute(self.ID_REFERENCE)
                dict_reference[id_reference] = self.geom_qgis_to_shapely(
                    feature.geometry()
                )
            feedback.pushInfo("2) BEREKENING - Reference layer fixed")
            feedback.setCurrentStep(2)
            if feedback.isCanceled():
                return {}

        # Aligner IMPLEMENTATION
        aligner = Aligner(
            feedback=feedback,
            relevant_distance=self.RELEVANT_DISTANCE,
            threshold_overlap_percentage=self.THRESHOLD_OVERLAP_PERCENTAGE,
        )

        # set parameters
        aligner.feedback = feedback
        aligner.relevant_distance = self.RELEVANT_DISTANCE
        aligner.od_strategy = self.OD_STRATEGY
        aligner.THRESHOLD_CIRCLE_RATIO = self.THRESHOLD_CIRCLE_RATIO
        aligner.THRESHOLD_EXCLUSION_AREA = self.THRESHOLD_EXCLUSION_AREA
        aligner.THRESHOLD_EXCLUSION_PERCENTAGE = (
            self.THRESHOLD_EXCLUSION_PERCENTAGE
        )
        aligner.CORR_DISTANCE = self.CORR_DISTANCE
        aligner.MITRE_LIMIT = self.MITRE_LIMIT
        aligner.QUAD_SEGS = self.QUAD_SEGS
        aligner.BUFFER_MULTIPLICATION_FACTOR = self.BUFFER_MULTIPLICATION_FACTOR
        aligner.MAX_REFERENCE_BUFFER = self.MAX_REFERENCE_BUFFER
        aligner.CRS = self.CRS
        aligner.DOWNLOAD_LIMIT = self.DOWNLOAD_LIMIT

        feedback.pushInfo("Load thematic data")
        aligner.load_thematic_data_dict(dict_thematic)

        feedback.pushInfo("Load reference data")
        if self.SELECTED_REFERENCE == 0:
            aligner.load_reference_data_dict(dict_reference)
        else:
            aligner.load_reference_data_grb_actual(grb_type=self.SELECTED_REFERENCE.value)
            #
        feedback.pushInfo("START PROCESSING")
        if self.RELEVANT_DISTANCE >= 0:
            (
                dict_result,
                dict_result_diff,
                dict_result_diff_plus,
                dict_result_diff_min,
                dict_relevant_intersection,
                dict_relevant_diff,
            ) = aligner.process_dict_thematic(
                self.RELEVANT_DISTANCE, self.OD_STRATEGY, self.THRESHOLD_OVERLAP_PERCENTAGE
            )
            fcs = aligner.get_results_as_geojson(formula=True)
        else:
            dict_predicted, diffs = aligner.predictor(od_strategy=self.OD_STRATEGY,
                                                      treshold_overlap_percentage=self.THRESHOLD_OVERLAP_PERCENTAGE)
            fcs = aligner.get_predictions_as_geojson(formula=True)

        feedback.pushInfo("END PROCESSING")

        # write results to output-layers
        feedback.pushInfo("WRITING RESULTS")

        # fcs = aligner.get_results_as_geojson()
        # MAKE TEMPORARY LAYERS
        if self.SELECTED_REFERENCE != 0:
            self.geojson_to_layer(self.LAYER_REFERENCE, aligner.get_reference_as_geojson(), "gray 1 fill", True)
        if self.SHOW_INTERMEDIATE_LAYERS:
            self.geojson_to_layer(self.LAYER_RELEVANT_INTERSECTION, fcs[4], "simple green fill", False)
            self.geojson_to_layer(self.LAYER_RELEVANT_DIFFERENCE, fcs[5], "simple red fill", False)

        self.geojson_to_layer(self.LAYER_RESULT, fcs[0], "outline xpattern", True)
        self.geojson_to_layer(self.LAYER_RESULT_DIFF, fcs[1], "hashed black X", False)
        self.geojson_to_layer(self.LAYER_RESULT_DIFF_PLUS, fcs[2], "hashed cgreen /", False)
        self.geojson_to_layer(self.LAYER_RESULT_DIFF_MIN, fcs[3], "hashed cred /", False)

        # self.add_formula_to_layer(self.LAYER_RESULT,aligner)
        self.RESULT = QgsProject.instance().mapLayersByName(self.LAYER_RESULT)[0]
        self.RESULT_DIFF = QgsProject.instance().mapLayersByName(
            self.LAYER_RESULT_DIFF
        )[0]
        self.RESULT_DIFF_PLUS = QgsProject.instance().mapLayersByName(
            self.LAYER_RESULT_DIFF_PLUS
        )[0]
        self.RESULT_DIFF_MIN = QgsProject.instance().mapLayersByName(
            self.LAYER_RESULT_DIFF_MIN
        )[0]

        QgsProject.instance().reloadAllLayers()

        feedback.pushInfo("Resulterende geometrie berekend")
        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}

        feedback.pushInfo("EINDE: RESULTAAT BEREKEND")
        return {
            self.OUTPUT_RESULT: self.RESULT,
            self.OUTPUT_RESULT_DIFF: self.RESULT_DIFF,
            self.OUTPUT_RESULT_DIFF_PLUS: self.RESULT_DIFF_PLUS,
            self.OUTPUT_RESULT_DIFF_MIN: self.RESULT_DIFF_MIN,
        }

    def _thematic_preparation(self, context, feedback, outputs, parameters):
        # THEMATIC PREPARATION
        outputs[self.INPUT_THEMATIC + "_id"] = processing.run(
            "native:fieldcalculator",
            {
                "INPUT": parameters[self.INPUT_THEMATIC],
                "FIELD_NAME": self.ID_THEME,
                "FIELD_TYPE": 2,
                "FIELD_LENGTH": 0,
                "FIELD_PRECISION": 0,
                "FORMULA": "to_string(" + parameters[self.ID_THEME] + ")",
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        thematic = context.getMapLayer(outputs[self.INPUT_THEMATIC + "_id"]["OUTPUT"])
        self.CRS = (
            thematic.sourceCrs().authid()
        )  # set CRS for the calculations, based on the THEMATIC input layer

        # outputs[self.INPUT_THEMATIC + "_single_id"] = processing.run(
        #     "native:fieldcalculator",
        #     {
        #         "INPUT": thematic,
        #         "FIELD_NAME": self.ID_THEME,
        #         "FIELD_TYPE": 2,
        #         "FIELD_LENGTH": 0,
        #         "FIELD_PRECISION": 0,
        #         "FORMULA": "to_string("
        #                    + parameters[self.ID_THEME_GLOBAL]
        #                    + ")",  # + '_'+ to_string(@id)
        #         "OUTPUT": "TEMPORARY_OUTPUT",
        #     },
        #     context=context,
        #     feedback=feedback,
        #     is_child_algorithm=True,
        # )
        # thematic = context.getMapLayer(
        #     outputs[self.INPUT_THEMATIC + "_single_id"]["OUTPUT"]
        # )
        outputs[self.INPUT_THEMATIC + "_fixed"] = processing.run(
            "native:fixgeometries",
            {"INPUT": thematic, "METHOD": 1, "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        thematic = context.getMapLayer(
            outputs[self.INPUT_THEMATIC + "_fixed"]["OUTPUT"]
        )
        outputs[self.INPUT_THEMATIC + "_enriched"] = processing.run(
            "qgis:exportaddgeometrycolumns",
            {"INPUT": thematic, "CALC_METHOD": 0, "OUTPUT": "TEMPORARY_OUTPUT"},
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        thematic = context.getMapLayer(
            outputs[self.INPUT_THEMATIC + "_enriched"]["OUTPUT"]
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
                "DISTANCE": self.BUFFER_MULTIPLICATION_FACTOR * self.RELEVANT_DISTANCE,
                "SEGMENTS": self.QUAD_SEGS,
                "END_CAP_STYLE": 0,
                "JOIN_STYLE": 1,
                "MITRE_LIMIT": self.MITRE_LIMIT,
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

    def prepare_parameters(self, parameters):
        # PARAMETER PREPARATION
        self.RELEVANT_DISTANCE = parameters["RELEVANT_DISTANCE"]
        self.BUFFER_DISTANCE = self.RELEVANT_DISTANCE / 2
        self.THRESHOLD_OVERLAP_PERCENTAGE = parameters["THRESHOLD_OVERLAP_PERCENTAGE"]
        self.OD_STRATEGY = OpenbaarDomeinStrategy[self.ENUM_OD_STRATEGY_OPTIONS[parameters[self.ENUM_OD_STRATEGY]]]
        self.SHOW_INTERMEDIATE_LAYERS = parameters["SHOW_INTERMEDIATE_LAYERS"]
        self.PROCESS_MULTI_AS_SINGLE_POLYGONS = parameters[
            "PROCESS_MULTI_AS_SINGLE_POLYGONS"
        ]
        self.SUFFIX = "_" + str(self.RELEVANT_DISTANCE) + "_OD_" + str(self.OD_STRATEGY.name)
        self.LAYER_RELEVANT_INTERSECTION = (
                self.LAYER_RELEVANT_INTERSECTION + self.SUFFIX
        )
        self.LAYER_RELEVANT_DIFFERENCE = (
                self.LAYER_RELEVANT_DIFFERENCE + self.SUFFIX
        )
        self.LAYER_RESULT = self.LAYER_RESULT + self.SUFFIX
        self.LAYER_RESULT_DIFF = self.LAYER_RESULT_DIFF + self.SUFFIX
        self.LAYER_RESULT_DIFF_PLUS = self.LAYER_RESULT_DIFF_PLUS + self.SUFFIX
        self.LAYER_RESULT_DIFF_MIN = self.LAYER_RESULT_DIFF_MIN + self.SUFFIX
        ref = self.ENUM_REFERENCE_OPTIONS[parameters[self.ENUM_REFERENCE]]
        if ref in self.GRB_TYPES:
            self.SELECTED_REFERENCE = GRBType[ref]
        else:
            self.SELECTED_REFERENCE = 0
        self.LAYER_REFERENCE = self.SELECTED_REFERENCE
