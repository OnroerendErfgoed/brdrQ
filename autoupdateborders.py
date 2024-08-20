# -*- coding: utf-8 -*-

"""
***************************************************************************
*   name: brdrQ - AutoUpdateBorders
*   author: Karel Dieussaert
*   Docs and Code- repo: https://github.com/OnroerendErfgoed/brdrQ/
*   history:
*            -initial version

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
from qgis.PyQt.QtCore import QTextCodec
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsCoordinateReferenceSystem
from qgis.core import QgsFeature
from qgis.core import QgsField
from qgis.core import QgsGeometry
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingException
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingOutputVectorLayer
from qgis.core import QgsProcessingParameterDateTime,QgsProcessingParameterFeatureSource,QgsProcessingParameterField


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
from brdr.grb import get_geoms_affected_by_grb_change


class AutoUpdateBordersProcessingAlgorithm(QgsProcessingAlgorithm):
    """
    Script to auto-update geometries that are aligned to an old GRB-referencelayer to a newer GRB-referencelayer.
    Documentation can be found at: https://github.com/OnroerendErfgoed/brdrQ/
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    START_DATE = "START_DATE"
    END_DATE = "END_DATE"
    INPUT_THEMATIC = "INPUT_THEMATIC"
    ID_THEME = "id_theme"
    MITRE_LIMIT = 10
    CRS = "EPSG:31370"
    QUAD_SEGS = 5
    BUFFER_MULTIPLICATION_FACTOR = 1.01
    RELEVANT_DISTANCE = 1

    def flags(self):
        return super().flags() | QgsProcessingAlgorithm.FlagNoThreading

    @staticmethod
    def tr(string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        return AutoUpdateBordersProcessingAlgorithm()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return "brdrqautoupdateborders"

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr("brdrQ - AutoUpdateBorders")

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This stringgeom
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
            "Script to auto-update geometries that are aligned to an old GRB-referencelayer to a newer GRB-referencelayer"
            "Documentation can be found at: https://github.com/OnroerendErfgoed/brdrQ/ "
        )

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

        # INPUT  standard parameters
        # make your own widget is also possible!
        # https://gis.stackexchange.com/questions/432849/changing-appearence-of-datetime-input-in-qgis-processing-tool-to-international-d
        # https://www.faunalia.eu/en/blog/2019-07-02-custom-processing-widget

        # START DATETIME
        parameter = QgsProcessingParameterDateTime(
            self.START_DATE,
            'StartDate:',
            type=QgsProcessingParameterDateTime.Date
            # ,
            # defaultValue = QDateTime.currentDateTime().addDays(-31)
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        # END DATETIME
        parameter = QgsProcessingParameterDateTime(
            self.END_DATE,
            'EndDate:',
            type=QgsProcessingParameterDateTime.Date
            # ,
            # defaultValue = QDateTime.currentDateTime().addDays(-31)
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """

        feedback_steps = 6
        feedback = QgsProcessingMultiStepFeedback(feedback_steps, feedback)
        feedback.pushInfo("START")
        outputs = {}

        #self.prepare_parameters(parameters)

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

        datetime_start = self.parameterAsDateTime(
            parameters,
            self.START_DATE,
            context
        )

        datetime_end = self.parameterAsDateTime(
            parameters,
            self.START_DATE,
            context
        )
        print(datetime_start)
        dict_affected = get_geoms_affected_by_grb_change(
            dict_thematic,
            grb_type=GRBType.ADP,
            date_start=datetime_start,
            date_end=datetime_end,
            one_by_one=False,
        )
        for key in dict_affected.keys():
            print(key)
            print (dict_affected[key])
        feedback.pushInfo(str(datetime_start))
        feedback.pushInfo("END PROCESSING")
        feedback.pushInfo("EINDE: RESULTAAT BEREKEND")
        return {
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
        pass
        # self.RELEVANT_DISTANCE = parameters["RELEVANT_DISTANCE"]
        # self.BUFFER_DISTANCE = self.RELEVANT_DISTANCE / 2
        # self.THRESHOLD_OVERLAP_PERCENTAGE = parameters["THRESHOLD_OVERLAP_PERCENTAGE"]
        # self.OD_STRATEGY = OpenbaarDomeinStrategy[self.ENUM_OD_STRATEGY_OPTIONS[parameters[self.ENUM_OD_STRATEGY]]]
        # self.SHOW_INTERMEDIATE_LAYERS = parameters["SHOW_INTERMEDIATE_LAYERS"]
        # self.PROCESS_MULTI_AS_SINGLE_POLYGONS = parameters[
        #     "PROCESS_MULTI_AS_SINGLE_POLYGONS"
        # ]
        # self.SUFFIX = "_" + str(self.RELEVANT_DISTANCE) + "_OD_" + str(self.OD_STRATEGY.name)
        # self.LAYER_RELEVANT_INTERSECTION = (
        #         self.LAYER_RELEVANT_INTERSECTION + self.SUFFIX
        # )
        # self.LAYER_RELEVANT_DIFFERENCE = (
        #         self.LAYER_RELEVANT_DIFFERENCE + self.SUFFIX
        # )
        # self.LAYER_RESULT = self.LAYER_RESULT + self.SUFFIX
        # self.LAYER_RESULT_DIFF = self.LAYER_RESULT_DIFF + self.SUFFIX
        # self.LAYER_RESULT_DIFF_PLUS = self.LAYER_RESULT_DIFF_PLUS + self.SUFFIX
        # self.LAYER_RESULT_DIFF_MIN = self.LAYER_RESULT_DIFF_MIN + self.SUFFIX
        # ref = self.ENUM_REFERENCE_OPTIONS[parameters[self.ENUM_REFERENCE]]
        # if ref in self.GRB_TYPES:
        #     self.SELECTED_REFERENCE = GRBType[ref]
        # else:
        #     self.SELECTED_REFERENCE = 0
        # self.LAYER_REFERENCE = self.SELECTED_REFERENCE

