# -*- coding: utf-8 -*-

"""
***************************************************************************
*   name: brdrQ - Autocorrectborders
*   author: Karel Dieussaert
*   Docs, history and Code- repo: https://github.com/OnroerendErfgoed/brdrQ/

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
import inspect
import os
import sys
from datetime import datetime

# TODO QGIS4
from PyQt5.QtCore import QVariant
from brdr.be.grb.enums import GRBType
from brdr.be.grb.loader import GRBFiscalParcelLoader, GRBActualLoader
from brdr.configs import ProcessorConfig, AlignerConfig
from brdr.constants import (
    STABILITY,
    SYMMETRICAL_AREA_CHANGE,
    SYMMETRICAL_AREA_PERCENTAGE_CHANGE,
    METADATA_FIELD_NAME,
    ID_THEME_FIELD_NAME,
)
from brdr.geometry_utils import safe_unary_union
from brdr.osm.loader import OSMLoader
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
    QgsFillSymbol,
)
from qgis.core import QgsField
from qgis.core import QgsProcessingFeatureSourceDefinition
from qgis.core import QgsVectorFileWriter, QgsVectorLayer

from .brdrq_utils import (
    ENUM_REFERENCE_OPTIONS,
    ENUM_OD_STRATEGY_OPTIONS,
    ADPF_VERSIONS,
    geom_qgis_to_shapely,
    featurecollection_to_layer,
    get_workfolder,
    thematic_preparation,
    get_reference_params,
    PREFIX_LOCAL_LAYER,
    DICT_ADPF_VERSIONS,
    move_to_group,
    BRDRQ_STATE_FIELDNAME,
    BrdrQState,
    set_layer_visibility,
    BRDRQ_ORIGINAL_WKT_FIELDNAME,
    remove_layer_by_name,
    is_field_in_layer,
    OSM_TYPES,
    DICT_OSM_TYPES,
    ENUM_FULL_REFERENCE_STRATEGY_OPTIONS,
    ENUM_PREDICTION_STRATEGY_OPTIONS,
    get_processor_by_id,
    Processor,
    ENUM_PROCESSOR_OPTIONS,
    read_setting,
    write_setting,
    get_valid_layer,
)

cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]
if cmd_folder not in sys.path:
    sys.path.insert(0, cmd_folder)

import numpy as np
from qgis import processing
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtCore import QDate, QDateTime
from qgis.core import QgsFeatureRequest
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingOutputVectorLayer
from qgis.core import QgsProcessingParameterBoolean
from qgis.core import QgsProcessingParameterDefinition
from qgis.core import QgsProcessingParameterEnum
from qgis.core import QgsProcessingParameterFeatureSource
from qgis.core import QgsProcessingParameterField
from qgis.core import QgsProcessingParameterFile
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingException
from qgis.core import QgsProject
from qgis.core import QgsStyle

from brdr.aligner import Aligner
from brdr.loader import DictLoader
from brdr.enums import (
    OpenDomainStrategy,
    AlignerResultType,
    FullReferenceStrategy,
    PredictionStrategy,
)


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
    ID_THEME_BRDRQ_FIELDNAME = (
        ""  # parameters that holds the fieldname of the unique theme id
    )
    LAYER_THEMATIC = None  # reference to the thematic input QgisVectorLayer

    # REFERENCE PARAMETERS
    INPUT_REFERENCE = "INPUT_REFERENCE"  # reference to the combobox for choosing the reference input layer
    LAYER_REFERENCE = None  # reference to the local reference QgisVectorLayer
    LAYER_REFERENCE_NAME = (
        "LAYER_REFERENCE_NAME"  # Name of the local referencelayer in the TOC
    )
    ID_REFERENCE_BRDRQ_FIELDNAME = None  # field that holds the fieldname of the unique reference id,defaults to CAPAKEY
    SELECTED_REFERENCE = None  # parameter that holds the chosen reference layer (0 means that a local reference layer is used)

    # ENUM for choosing the OD-strategy

    # LAYER parameters
    PREFIX = "brdrQ"  # prefix used for all layers and group layers
    SUFFIX = ""  # parameter for composing a suffix for the layers
    GROUP_LAYER = PREFIX  # parameter for group layer
    GROUP_LAYER_ACTUAL = (
        PREFIX + "_ACTUAL"
    )  # parameter for group layer when calculating an actualisation to actual GRB
    LAYER_RESULT = "RESULT"  # parameter that holds the TOC layername of the result
    LAYER_RESULT_DIFF = (
        "DIFF"  # parameter that holds the TOC layername of the resulting diff
    )
    LAYER_RESULT_DIFF_PLUS = (
        "DIFF_PLUS"  # parameter that holds the TOC layername of the resulting diff_plus
    )
    LAYER_RESULT_DIFF_MIN = (
        "DIFF_MIN"  # parameter that holds the TOC layername of the resulting diff_min
    )

    LAYER_CORRECTION = (
        "CORRECTION"  # parameter that holds the TOC layername of the correction_layer
    )
    LAYER_RELEVANT_INTERSECTION = "RLVNT_ISECT"  # parameter that holds the TOC layername of the relevant intersection
    LAYER_RELEVANT_DIFFERENCE = "RLVNT_DIFF"  # parameter that holds the TOC layername of the relevant difference

    LAYER_RESULT_ACTUAL = "RESULT_ACTUAL"  # parameter that holds the TOC layername of the actualised result
    LAYER_RESULT_ACTUAL_DIFF = "RESULT_ACTUAL_DIFF"  # parameter that holds the TOC layername of the actualised resulting diff

    # ALIGNER parameters
    OD_STRATEGY = None  # default OD_STRATEGY for the aligner,updated by user-choice
    FULL_REFERENCE_STRATEGY = None
    PREDICTION_STRATEGY = None
    PROCESSOR = None
    THRESHOLD_OVERLAP_PERCENTAGE = None  # default THRESHOLD_OVERLAP_PERCENTAGE for the aligner,updated by user-choice
    REVIEW_PERCENTAGE = None  # default - features that changes more than this % wil be moved to review lisr
    RELEVANT_DISTANCE = None  # RELEVANT_DISTANCE for the aligner
    # CHECKBOXs
    SHOW_INTERMEDIATE_LAYERS = None
    ADD_METADATA = None
    ATTRIBUTES = None
    PREDICTIONS = None
    SHOW_LOG_INFO = None
    WORKFOLDER = None

    # OTHER non UI parameters
    MULTI_AS_SINGLE_MODUS = True  # default MULTI_AS_SINGLE_MODUS for the aligner
    CORR_DISTANCE = 0.01  # default CORR_DISTANCE for the aligner
    CRS = "EPSG:31370"  # default CRS for the aligner,updated by CRS of thematic inputlayer
    MAX_AREA_FOR_DOWNLOADING_REFERENCE = 550000000  # maximum area of the unioned Thematic input to use on-the fly downloading reference layers. (Default number based on the biggest municipality BBOX of Flanders)

    def flags(self):
        return super().flags() | QgsProcessingAlgorithm.FlagNoThreading

    @staticmethod
    def tr(string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate(__class__.__name__, string)

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

    def helpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it.
        """
        return self.tr(
            "This process aligns your thematic data to reference data, based on the chosen parameters. <br> See <a href='https://onroerenderfgoed.github.io/brdrQ/autocorrectborders.html'>https://onroerenderfgoed.github.io/brdrQ/</a> for documentation of the brdrQ-plugin"
        )

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it.
        """
        return self.tr(
            "This process aligns your thematic data to reference data, based on the chosen parameters. <br> See <a href='https://onroerenderfgoed.github.io/brdrQ/autocorrectborders.html'>https://onroerenderfgoed.github.io/brdrQ/</a> for documentation of the brdrQ-plugin"
        )

    def helpUrl(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it.
        """
        return self.tr(
            "https://onroerenderfgoed.github.io/brdrQ/autocorrectborders.html"
        )

    # def checkParameterValues(self, parameters, context):
    #     """
    #     Validates all parameters. If a value is invalid (like a 'ghost layer'
    #     from settings), it falls back to the defined default value.
    #     """
    #     # Iterate through all parameter definitions for this algorithm
    #     for param_def in self.parameterDefinitions():
    #         param_name = param_def.name()
    #         value = parameters.get(param_name)
    #         # checkNextValueIsAcceptable is the Python API method to verify
    #         # if the current value is valid for this specific parameter type
    #         if not param_def.checkValueIsAcceptable(value, context):
    #             # The value is invalid (e.g., missing layer, out-of-bounds enum, etc.)
    #             # Reset the value to the default defined in initAlgorithm
    #             parameters[param_name] = self.params_default_dict[param_name]
    #
    #     # After replacing invalid values, call the superclass validation
    #     return super().checkParameterValues(parameters, context)

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """
        # Read settings saved to project/profile
        self.read_default_settings()

        # standard parameters
        parameter = QgsProcessingParameterFeatureSource(
            self.INPUT_THEMATIC,
            '<b>THEMATIC DATA</b><br><i style="color: gray;">Choose your thematic layer to align and its unique ID</i><br><br>Thematic Layer',
            [QgsProcessing.TypeVectorAnyGeometry],
            defaultValue=self.default_theme_layer,
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        parameter = QgsProcessingParameterField(
            "COMBOBOX_ID_THEME",
            "Thematic ID (unique!)",
            defaultValue=self.default_theme_layer_id,
            parentLayerParameterName=self.INPUT_THEMATIC,
        )

        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        parameter = QgsProcessingParameterEnum(
            "ENUM_REFERENCE",
            '<br><b>REFERENCE DATA</b><br><i style="color: gray;">Choose the reference data. You can choose for on-the-fly download of prepared reference-data OR a local reference layer (LOCREF)</i><br><br>Reference',
            options=ENUM_REFERENCE_OPTIONS,
            defaultValue=self.default_reference,  # Index of the default option (e.g., 'Option A')
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        parameter = QgsProcessingParameterFeatureSource(
            self.INPUT_REFERENCE,
            '<br>Local reference layer<br><i style="color: gray;">If LOCREF, Choose reference layer. Otherwise this will be ignored.</i>',
            [QgsProcessing.TypeVectorAnyGeometry],
            defaultValue=self.default_reference_layer,
            optional=True,
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        parameter = QgsProcessingParameterField(
            "COMBOBOX_ID_REFERENCE",
            '<br>Reference ID (unique!)<br><i style="color: gray;">If LOCREF, Choose unique Reference ID for reference layer. Otherwise this will be ignored.</i>',
            defaultValue=self.default_reference_layer_id,  # defaults to CAPAKEY
            parentLayerParameterName=self.INPUT_REFERENCE,
            optional=True,
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        parameter = QgsProcessingParameterNumber(
            "RELEVANT_DISTANCE",
            '<br><b>RELEVANT DISTANCE (units: meter)</b><br><i style="color: gray;">This distance in meters determines what the max amount of change will be allowed when aligning your data</i><br><br>Relevant distance (m)',
            type=QgsProcessingParameterNumber.Double,
            defaultValue=self.default_relevant_distance,
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
        self.addOutput(
            QgsProcessingOutputVectorLayer(
                "OUTPUT_CORRECTION",
                self.LAYER_CORRECTION,
                QgsProcessing.TypeVectorAnyGeometry,
            )
        )
        # advanced parameters

        parameter = QgsProcessingParameterEnum(
            "PREDICTIONS",
            '<br><b>PREDICTION SETTINGS</b><br><i style="color: gray;">Predictions uses a range of relevant distances to predict the best alignment. This results in better alignment results, but (!) increases (!) processing time</i><br><br>Use predictions',
            options=["NO_PREDICTIONS", "PREDICTIONS"],
            defaultValue=self.default_predictions,
        )

        parameter.setFlags(
            parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(parameter)

        parameter = QgsProcessingParameterEnum(
            "PREDICTION_STRATEGY",
            '<br>Prediction Strategy<br><i style="color: gray;">When using Predictions, the prediction strategy determines which predictions are returned in the output: All predictions, only the BEST prediction, or the ORIGINAL if there are multiple predictions</i>',
            options=ENUM_PREDICTION_STRATEGY_OPTIONS,
            defaultValue=self.default_prediction_strategy,
            # optional=True,
        )
        parameter.setFlags(
            parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(parameter)
        parameter = QgsProcessingParameterEnum(
            "FULL_REFERENCE_STRATEGY",
            '<br>Full Reference Strategy<br><i style="color: gray;">When using Predictions, the Full Reference strategy determines how predictions are handled that are fully covered by reference-data </i>',
            options=ENUM_FULL_REFERENCE_STRATEGY_OPTIONS,
            defaultValue=self.default_full_reference_strategy,
            # optional=True,
        )
        parameter.setFlags(
            parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(parameter)

        parameter = QgsProcessingParameterEnum(
            "ENUM_PROCESSOR",
            '<br><b>PROCESSOR_SETTINGS</b><br><i style="color: gray;">These settings determine the Processor (algorithm) & Processing-parameters to execute the alignment</i><br><br>Processor',
            options=ENUM_PROCESSOR_OPTIONS,
            defaultValue=self.default_processor,  # Index of the default option (e.g., 'ALIGNER')
        )
        parameter.setFlags(
            parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(parameter)

        parameter = QgsProcessingParameterEnum(
            "ENUM_OD_STRATEGY",
            '<br>Open Domain Strategy<br><i style="color: gray;">Strategy how the processing-algorithm handles the parts that are not covered by reference features (=Open Domain). You can choose to Exclude, Leave it AS IS, or ALIGN it to the reference features</i>',
            options=ENUM_OD_STRATEGY_OPTIONS,
            defaultValue=self.default_od_strategy,  # Index of the default option (e.g., 'SNAP_ALL_SIDE')
        )
        parameter.setFlags(
            parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(parameter)

        parameter = QgsProcessingParameterNumber(
            "THRESHOLD_OVERLAP_PERCENTAGE",
            '<br>Threshold overlap percentage<br><i style="color: gray;">In the exceptional case that the algorithm cannot determine if a reference feature is relevant, this fallback-parameter is used to determine to include/exclude a reference based on overlap-percentage</i>',
            type=QgsProcessingParameterNumber.Double,
            defaultValue=self.default_threshold_overlap_percentage,
        )
        parameter.setFlags(
            parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(parameter)

        parameter = QgsProcessingParameterFile(
            "WORK_FOLDER",
            '<br><b>OUTPUT SETTINGS</b><br><i style="color: gray;"> Settings to determine how the output will appear</i><br><br>Work Folder',
            behavior=QgsProcessingParameterFile.Folder,
            defaultValue=self.default_workfolder,
            optional=True,
        )
        parameter.setFlags(
            parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(parameter)

        parameter = QgsProcessingParameterNumber(
            "REVIEW_PERCENTAGE",
            '<br>REVIEW_PERCENTAGE (%)<br><i style="color: gray;">results with a higher change % move to review-list </i>',
            type=QgsProcessingParameterNumber.Double,
            defaultValue=self.default_review_percentage,
        )
        parameter.setFlags(
            parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(parameter)

        parameter = QgsProcessingParameterBoolean(
            "ADD_METADATA",
            "Add METADATA to output",
            defaultValue=self.default_add_metadata,
        )
        parameter.setFlags(
            parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(parameter)

        parameter = QgsProcessingParameterBoolean(
            "ADD_ATTRIBUTES",
            "Add ATTRIBUTES to output",
            defaultValue=self.default_add_attributes,
        )
        parameter.setFlags(
            parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(parameter)

        parameter = QgsProcessingParameterBoolean(
            "SHOW_INTERMEDIATE_LAYERS",
            "Show Intermediate processing results (if provided by processor)",
            defaultValue=self.default_intermediate_layers,
        )
        parameter.setFlags(
            parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(parameter)

        parameter = QgsProcessingParameterBoolean(
            "SHOW_LOG_INFO",
            "Show extra logging (from brdr-log)",
            defaultValue=self.default_extra_logging,
        )
        parameter.setFlags(
            parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(parameter)

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        print(str(parameters))
        print(str(context))
        feedback_steps = 6
        feedback = QgsProcessingMultiStepFeedback(feedback_steps, feedback)
        feedback.pushInfo("START")
        feedback.setCurrentStep(1)
        self.prepare_parameters(parameters, context)
        thematic, thematic_buffered, self.CRS = thematic_preparation(
            self.LAYER_THEMATIC, self.RELEVANT_DISTANCE, context, feedback
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
            id_theme = feature.attribute(self.ID_THEME_BRDRQ_FIELDNAME)
            dict_thematic[id_theme] = geom_qgis_to_shapely(feature_geom)
            if self.ATTRIBUTES:
                # dict_thematic_properties[id_theme] = feature.__geo_interface__["properties"]
                attributes = feature.attributeMap()
                attributes_dict = {}
                for key, value in attributes.items():
                    if isinstance(value, QDate):
                        attributes_dict[key] = value.toPyDate()
                    elif isinstance(value, QDateTime):
                        attributes_dict[key] = value.toPyDateTime()
                    else:
                        attributes_dict[key] = value
                dict_thematic_properties[id_theme] = attributes_dict
        # minx, miny, maxx, maxy = GeometryCollection(list(dict_thematic.values())).bounds
        # area = (maxx - minx) * (maxy - miny)
        area = safe_unary_union(list(dict_thematic.values())).area
        feedback.pushInfo("Unioned Area of thematic zone: " + str(area))

        if (
            self.SELECTED_REFERENCE != 0
            and area > self.MAX_AREA_FOR_DOWNLOADING_REFERENCE
        ):
            raise QgsProcessingException(
                "The area of all unioned thematic geometries is bigger than threshold ("
                + str(self.MAX_AREA_FOR_DOWNLOADING_REFERENCE)
                + " m²) to use the on-the-fly downloads: "
                + str(area)
                + "(m² unioned thematic area) "
                + "Please make use of a local REFERENCELAYER (for performance reasons)"
            )
        feedback.pushInfo("1) PREPROCESSING - Thematic layer fixed")
        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # REFERENCE PREPARATION
        if self.SELECTED_REFERENCE == 0:
            reference = self._reference_preparation(
                thematic_buffered, context, feedback, parameters
            )

            # Load reference into a shapely_dict:
            dict_reference = {}
            features = reference.getFeatures()
            for current, feature in enumerate(features):
                if feedback.isCanceled():
                    return {}
                id_reference = feature.attribute(self.ID_REFERENCE_BRDRQ_FIELDNAME)
                dict_reference[id_reference] = geom_qgis_to_shapely(feature.geometry())
        feedback.pushInfo("2) PREPROCESSING - Reference layer fixed")
        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # Aligner IMPLEMENTATION
        if self.SHOW_LOG_INFO:
            log_info = feedback
        else:
            log_info = None

        processor_config = ProcessorConfig()
        processor_config.od_strategy = self.OD_STRATEGY
        processor_config.multi_as_single_modus = self.MULTI_AS_SINGLE_MODUS
        processor_config.correction_distance = self.CORR_DISTANCE
        processor_config.threshold_overlap_percentage = (
            self.THRESHOLD_OVERLAP_PERCENTAGE
        )
        processor = get_processor_by_id(
            processor_id=self.PROCESSOR.value, config=processor_config
        )
        aligner_config = AlignerConfig()
        aligner_config.log_metadata = self.ADD_METADATA
        if self.PREDICTIONS:
            aligner_config.add_observations = self.ADD_METADATA
        else:
            aligner_config.add_observations = (
                True  # Set always to True when NO_predictions
            )
        aligner = Aligner(
            feedback=log_info,
            crs=self.CRS,
            processor=processor,
            config=aligner_config,
        )

        feedback.pushInfo("Load thematic data")
        aligner.load_thematic_data(DictLoader(dict_thematic, dict_thematic_properties))
        aligner.name_thematic_id = self.ID_THEME_BRDRQ_FIELDNAME

        feedback.pushInfo("Load reference data")
        if self.SELECTED_REFERENCE == 0:
            aligner.load_reference_data(DictLoader(dict_reference))
            # aligner.reference_data.id_fieldname = self.ID_REFERENCE_FIELDNAME
            aligner.reference_data.source = {
                "source": PREFIX_LOCAL_LAYER + "_" + self.LAYER_REFERENCE_NAME,
                "version_date": "unknown",
            }
        elif self.SELECTED_REFERENCE in ADPF_VERSIONS:
            year = DICT_ADPF_VERSIONS[self.SELECTED_REFERENCE]
            aligner.load_reference_data(
                GRBFiscalParcelLoader(year=str(year), aligner=aligner, partition=1000)
            )
        elif self.SELECTED_REFERENCE in OSM_TYPES:
            tags = DICT_OSM_TYPES[self.SELECTED_REFERENCE]
            aligner.load_reference_data(OSMLoader(osm_tags=tags, aligner=aligner))
        else:
            aligner.load_reference_data(
                GRBActualLoader(
                    grb_type=GRBType(self.SELECTED_REFERENCE.value),
                    partition=1000,
                    aligner=aligner,
                )
            )
        feedback.setCurrentStep(4)
        feedback.pushInfo("START PROCESSING")
        feedback.pushInfo(
            "calculation for relevant distance (m): "
            + str(self.RELEVANT_DISTANCE)
            + " - Predictions: "
            + str(self.PREDICTIONS)
        )
        if self.RELEVANT_DISTANCE < 0:
            raise QgsProcessingException("Please provide a RELEVANT DISTANCE >=0")
        if not self.PREDICTIONS:
            relevant_distances = [self.RELEVANT_DISTANCE]
            aligner_result = aligner.predict(
                relevant_distances=relevant_distances,
            )
            fcs = aligner_result.get_results_as_geojson(
                aligner=aligner,
                result_type=AlignerResultType.PROCESSRESULTS,
                add_metadata=self.ADD_METADATA,
                add_original_attributes=self.ATTRIBUTES,
            )
        else:
            relevant_distances = (
                np.arange(0, self.RELEVANT_DISTANCE * 100, 10, dtype=int) / 100
            )

            if self.PREDICTION_STRATEGY == PredictionStrategy.BEST:
                max_predictions = 1
                multi_to_best_prediction = True
            elif self.PREDICTION_STRATEGY == PredictionStrategy.ALL:
                max_predictions = -1
                multi_to_best_prediction = False
            elif self.PREDICTION_STRATEGY == PredictionStrategy.ORIGINAL:
                max_predictions = 1
                multi_to_best_prediction = False
            else:
                raise Exception("Unknown PREDICTION_STRATEGY")

            aligner_result = aligner.evaluate(
                relevant_distances=relevant_distances,
                max_predictions=max_predictions,
                multi_to_best_prediction=multi_to_best_prediction,
                full_reference_strategy=self.FULL_REFERENCE_STRATEGY,
            )
            fcs = aligner_result.get_results_as_geojson(
                aligner=aligner,
                result_type=AlignerResultType.EVALUATED_PREDICTIONS,
                add_metadata=self.ADD_METADATA,
                add_original_attributes=self.ATTRIBUTES,
            )
        if "result" not in fcs:
            feedback.pushInfo("No results found")
            feedback.pushInfo("END")

            return {}

        feedback.pushInfo("END PROCESSING")

        # write results to output-layers
        feedback.setCurrentStep(5)
        feedback.pushInfo("WRITING RESULTS")

        # MAKE TEMPORARY LAYERS
        if self.SELECTED_REFERENCE != 0:
            reference_geojson = aligner.reference_data.to_geojson()
            featurecollection_to_layer(
                self.LAYER_REFERENCE_NAME,
                reference_geojson,
                "reference",
                True,
                self.GROUP_LAYER,
                self.WORKFOLDER,
            )

        if self.SHOW_INTERMEDIATE_LAYERS:
            if "result_relevant_intersection" in fcs.keys():
                featurecollection_to_layer(
                    self.LAYER_RELEVANT_INTERSECTION,
                    fcs["result_relevant_intersection"],
                    QgsStyle.defaultStyle().symbol("gradient green fill"),
                    False,
                    self.GROUP_LAYER,
                    self.WORKFOLDER,
                )
            if "result_relevant_diff" in fcs.keys():
                featurecollection_to_layer(
                    self.LAYER_RELEVANT_DIFFERENCE,
                    fcs["result_relevant_diff"],
                    QgsStyle.defaultStyle().symbol("gradient red fill"),
                    False,
                    self.GROUP_LAYER,
                    self.WORKFOLDER,
                )
        result_diff = "result_diff"
        geojson_result_diff = fcs[result_diff]
        featurecollection_to_layer(
            self.LAYER_RESULT_DIFF,
            geojson_result_diff,
            result_diff,
            False,
            self.GROUP_LAYER,
            self.WORKFOLDER,
        )
        result_diff_plus = "result_diff_plus"
        geojson_result_diff_plus = fcs[result_diff_plus]
        featurecollection_to_layer(
            self.LAYER_RESULT_DIFF_PLUS,
            geojson_result_diff_plus,
            result_diff_plus,
            False,
            self.GROUP_LAYER,
            self.WORKFOLDER,
        )
        result_diff_min = "result_diff_min"
        geojson_result_diff_min = fcs[result_diff_min]
        featurecollection_to_layer(
            self.LAYER_RESULT_DIFF_MIN,
            geojson_result_diff_min,
            result_diff_min,
            False,
            self.GROUP_LAYER,
            self.WORKFOLDER,
        )
        result = "result"
        geojson_result = fcs[result]
        featurecollection_to_layer(
            self.LAYER_RESULT,
            geojson_result,
            result,
            False,
            self.GROUP_LAYER,
            self.WORKFOLDER,
        )

        result = QgsProject.instance().mapLayersByName(self.LAYER_RESULT)[0]
        result_diff = QgsProject.instance().mapLayersByName(self.LAYER_RESULT_DIFF)[0]
        result_diff_plus = QgsProject.instance().mapLayersByName(
            self.LAYER_RESULT_DIFF_PLUS
        )[0]
        result_diff_min = QgsProject.instance().mapLayersByName(
            self.LAYER_RESULT_DIFF_MIN
        )[0]
        correction_layer = None
        if not self.PREDICTIONS or self.PREDICTION_STRATEGY != PredictionStrategy.ALL:
            feedback.pushInfo("Generating correction layer")
            try:
                correction_layer = self.generate_correction_layer(thematic, result)
            except:
                print("problem generating correction layer")
        else:
            feedback.pushInfo(
                "No correction layer generated when predictions with predictionStrategy ALL is activated"
            )

        QgsProject.instance().reloadAllLayers()
        if feedback.isCanceled():
            return {}
        feedback.pushInfo("END: RESULTS CALCULATED")
        # feedback.setCurrentStep(6) #removed so the script will end before 100%-progressbar is reached
        return {
            "OUTPUT_RESULT": result,
            "OUTPUT_RESULT_DIFF": result_diff,
            "OUTPUT_RESULT_DIFF_PLUS": result_diff_plus,
            "OUTPUT_RESULT_DIFF_MIN": result_diff_min,
            "OUTPUT_CORRECTION": correction_layer,
        }

    def generate_correction_layer(self, input, result):

        source_layer = input
        results_layer = result

        # Copy source layer to gpkg-layers
        correction_layer_name = "CORRECTION" + self.SUFFIX
        remove_layer_by_name(correction_layer_name)
        correction_layer = self.generate_gpkg_layer(source_layer, correction_layer_name)

        set_layer_visibility(correction_layer, True)
        move_to_group(correction_layer, self.GROUP_LAYER)
        QgsProject.instance().reloadAllLayers()

        # Make a dictionary with ID to geometry from the resultslayer
        id_geom_map = {}
        id_diff_index_map = {}
        id_diff_perc_index_map = {}
        id_metadata_map = {}
        ids_to_review = []
        ids_to_align = []
        ids_not_changed = []
        stability_field_available = False
        if is_field_in_layer(STABILITY, results_layer):
            stability_field_available = True
        for feat in results_layer.getFeatures():
            key = feat[ID_THEME_FIELD_NAME]
            if key in id_geom_map.keys():
                # when key not unique and multiple predictions, the last prediction is added to the list and the status is set to review
                ids_to_review.append(key)
            id_geom_map[key] = feat.geometry()
            if self.ADD_METADATA:
                id_metadata_map[key] = feat[METADATA_FIELD_NAME]
            id_diff_index_map[key] = feat[SYMMETRICAL_AREA_CHANGE]
            id_diff_perc_index_map[key] = feat[SYMMETRICAL_AREA_PERCENTAGE_CHANGE]
            if stability_field_available and not feat[STABILITY]:
                ids_to_align.append(key)
            elif feat[SYMMETRICAL_AREA_PERCENTAGE_CHANGE] > self.REVIEW_PERCENTAGE:
                ids_to_review.append(key)
            elif feat[SYMMETRICAL_AREA_CHANGE] < 0.01:
                ids_not_changed.append(key)

        # 4. Update geometries in duplicated layer
        correction_layer.startEditing()
        correction_layer.dataProvider().addAttributes(
            [
                QgsField(METADATA_FIELD_NAME, QVariant.String),
                QgsField(BRDRQ_STATE_FIELDNAME, QVariant.String),
                QgsField(BRDRQ_ORIGINAL_WKT_FIELDNAME, QVariant.String),
                QgsField(SYMMETRICAL_AREA_CHANGE, QVariant.Double),
                QgsField(SYMMETRICAL_AREA_PERCENTAGE_CHANGE, QVariant.Double),
            ]
        )
        correction_layer.updateFields()
        for feat in correction_layer.getFeatures():
            fid = feat[self.ID_THEME_BRDRQ_FIELDNAME]
            if self.ADD_METADATA:
                feat[METADATA_FIELD_NAME] = id_metadata_map[fid]
            feat[SYMMETRICAL_AREA_CHANGE] = id_diff_index_map[fid]
            feat[SYMMETRICAL_AREA_PERCENTAGE_CHANGE] = id_diff_perc_index_map[fid]
            feat[BRDRQ_ORIGINAL_WKT_FIELDNAME] = feat.geometry().asWkt()
            state = str(BrdrQState.NONE.value)
            if fid in id_geom_map and fid not in ids_to_align:
                feat.setGeometry(id_geom_map[fid])
                state = str(BrdrQState.AUTO_UPDATED.value)
            if fid in ids_not_changed:
                state = str(BrdrQState.NOT_CHANGED.value)
            if fid in ids_to_review:
                state = str(BrdrQState.TO_REVIEW.value)
            if fid in ids_to_align:
                feat[SYMMETRICAL_AREA_CHANGE] = -1
                feat[SYMMETRICAL_AREA_PERCENTAGE_CHANGE] = -1
                state = str(BrdrQState.TO_UPDATE.value)
            feat[BRDRQ_STATE_FIELDNAME] = state
            correction_layer.updateFeature(feat)
        correction_layer.commitChanges()

        self.style_outputlayer(correction_layer, BRDRQ_STATE_FIELDNAME)
        return correction_layer

    def style_outputlayer(self, layer, field_name):
        # Define categories
        categories = []

        # Not changed
        symbol_not_changed = QgsFillSymbol.createSimple(
            {
                "outline_color": "#b2df8a",
                "outline_style": "solid",
                "outline_width": "2",
                "color": "transparent",
            }
        )
        value = str(BrdrQState.NOT_CHANGED.value)
        categories.append(QgsRendererCategory(value, symbol_not_changed, value))

        # Auto-updated
        symbol_auto = QgsFillSymbol.createSimple(
            {
                "outline_color": "green",
                "outline_style": "solid",
                "outline_width": "2",
                "color": "transparent",
            }
        )
        value = str(BrdrQState.AUTO_UPDATED.value)
        categories.append(QgsRendererCategory(value, symbol_auto, value))
        # manual update
        symbol_manual_update = QgsFillSymbol.createSimple(
            {
                "outline_color": "blue",
                "outline_style": "solid",
                "outline_width": "2",
                "color": "transparent",
            }
        )
        value = str(BrdrQState.MANUAL_UPDATED.value)
        categories.append(QgsRendererCategory(value, symbol_manual_update, value))
        # To Review
        symbol_review = QgsFillSymbol.createSimple(
            {
                "outline_color": "orange",
                "outline_style": "solid",
                "outline_width": "2",
                "color": "transparent",
            }
        )
        value = str(BrdrQState.TO_REVIEW.value)
        categories.append(QgsRendererCategory(value, symbol_review, value))

        symbol_todo = QgsFillSymbol.createSimple(
            {
                "outline_color": "red",
                "outline_style": "solid",
                "outline_width": "2",
                "color": "transparent",
            }
        )
        value = str(BrdrQState.TO_UPDATE.value)
        categories.append(QgsRendererCategory(value, symbol_todo, value))

        # Set Renderer
        renderer = QgsCategorizedSymbolRenderer(field_name, categories)
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    def generate_gpkg_layer(self, source_layer, layername) -> QgsVectorLayer:
        file = layername + ".gpkg"
        path = os.path.join(self.WORKFOLDER, file)
        QgsVectorFileWriter.writeAsVectorFormat(
            source_layer, path, "UTF-8", source_layer.crs(), "GPKG"
        )
        layer = QgsVectorLayer(path + "|layername=" + layername, layername, "ogr")
        QgsProject.instance().addMapLayer(layer)
        return layer

    def _reference_preparation(self, thematic_buffered, context, feedback, parameters):
        outputs = {}
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

    def read_default_settings(self):
        # print ('read_settings')
        prefix = self.name() + "/"
        project = QgsProject.instance()

        # Initial default settings
        self.params_default_dict = {
            self.INPUT_THEMATIC: "themelayer",
            "COMBOBOX_ID_THEME": "id",
            "ENUM_REFERENCE": 0,
            self.INPUT_REFERENCE: None,
            "COMBOBOX_ID_REFERENCE": None,
            "RELEVANT_DISTANCE": 3,
            "PREDICTIONS": 0,
            "PREDICTION_STRATEGY": 1,
            "FULL_REFERENCE_STRATEGY": 2,
            "ENUM_PROCESSOR": 0,
            "ENUM_OD_STRATEGY": 3,
            "THRESHOLD_OVERLAP_PERCENTAGE": 50,
            "WORK_FOLDER": "brdrQ",
            "REVIEW_PERCENTAGE": 10,
            "ADD_METADATA": False,
            "ADD_ATTRIBUTES": False,
            "SHOW_INTERMEDIATE_LAYERS": False,
            "SHOW_LOG_INFO": False,
        }
        self.default_theme_layer = self.params_default_dict[self.INPUT_THEMATIC]
        self.default_theme_layer_id = self.params_default_dict["COMBOBOX_ID_THEME"]
        self.default_reference = self.params_default_dict["ENUM_REFERENCE"]
        self.default_reference_layer = self.params_default_dict[self.INPUT_REFERENCE]
        self.default_reference_layer_id = self.params_default_dict[
            "COMBOBOX_ID_REFERENCE"
        ]
        self.default_relevant_distance = self.params_default_dict["RELEVANT_DISTANCE"]
        self.default_predictions = self.params_default_dict["PREDICTIONS"]
        self.default_prediction_strategy = self.params_default_dict[
            "PREDICTION_STRATEGY"
        ]
        self.default_full_reference_strategy = self.params_default_dict[
            "FULL_REFERENCE_STRATEGY"
        ]
        self.default_processor = self.params_default_dict["ENUM_PROCESSOR"]
        self.default_od_strategy = self.params_default_dict["ENUM_OD_STRATEGY"]
        self.default_threshold_overlap_percentage = self.params_default_dict[
            "THRESHOLD_OVERLAP_PERCENTAGE"
        ]
        self.default_workfolder = self.params_default_dict["WORK_FOLDER"]
        self.default_review_percentage = self.params_default_dict["REVIEW_PERCENTAGE"]
        self.default_add_metadata = self.params_default_dict["ADD_METADATA"]
        self.default_add_attributes = self.params_default_dict["ADD_ATTRIBUTES"]
        self.default_intermediate_layers = self.params_default_dict[
            "SHOW_INTERMEDIATE_LAYERS"
        ]
        self.default_extra_logging = self.params_default_dict["SHOW_LOG_INFO"]

        # READ FROM SAVED SETTINGS (QSettings))
        self.default_theme_layer = read_setting(
            prefix, "theme_layer", self.default_theme_layer
        )
        self.default_theme_layer_id = read_setting(
            prefix, "default_theme_layer_id", self.default_theme_layer_id
        )
        self.default_reference = read_setting(
            prefix, "default_reference", self.default_reference
        )
        self.default_reference_layer = read_setting(
            prefix, "default_reference_layer", self.default_reference_layer
        )
        self.default_reference_layer_id = read_setting(
            prefix, "default_reference_layer_id", self.default_reference_layer_id
        )
        self.default_relevant_distance = read_setting(
            prefix, "relevant_distance", self.default_relevant_distance
        )
        self.default_predictions = read_setting(
            prefix, "default_predictions", self.default_predictions
        )
        self.default_prediction_strategy = read_setting(
            prefix, "default_prediction_strategy", self.default_prediction_strategy
        )
        self.default_full_reference_strategy = read_setting(
            prefix,
            "default_full_reference_strategy",
            self.default_full_reference_strategy,
        )
        self.default_processor = read_setting(
            prefix, "default_processor", self.default_processor
        )
        self.default_od_strategy = read_setting(
            prefix, "default_od_strategy", self.default_od_strategy
        )
        self.default_threshold_overlap_percentage = read_setting(
            prefix,
            "default_threshold_overlap_percentage",
            self.default_threshold_overlap_percentage,
        )
        self.default_workfolder = read_setting(
            prefix, "default_workfolder", self.default_workfolder
        )
        self.default_review_percentage = read_setting(
            prefix, "default_review_percentage", self.default_review_percentage
        )
        self.default_add_metadata = read_setting(
            prefix, "default_add_metadata", self.default_add_metadata
        )
        self.default_add_attributes = read_setting(
            prefix, "default_add_attributes", self.default_add_attributes
        )
        self.default_intermediate_layers = read_setting(
            prefix, "default_intermediate_layers", self.default_intermediate_layers
        )
        self.default_extra_logging = read_setting(
            prefix, "default_extra_logging", self.default_extra_logging
        )

        # Validate defaults
        if not get_valid_layer(self.default_theme_layer):
            self.default_theme_layer = self.params_default_dict[self.INPUT_THEMATIC]
        if not get_valid_layer(self.default_reference_layer):
            self.default_reference_layer = self.params_default_dict[
                self.INPUT_REFERENCE
            ]

    def write_settings(self):
        # print ('write_settings')
        prefix = self.name() + "/"

        write_setting(prefix, "theme_layer", self.default_theme_layer)
        write_setting(prefix, "default_theme_layer_id", self.default_theme_layer_id)
        write_setting(prefix, "default_reference", self.default_reference)
        write_setting(prefix, "default_reference_layer", self.default_reference_layer)
        write_setting(
            prefix, "default_reference_layer_id", self.default_reference_layer_id
        )
        write_setting(prefix, "relevant_distance", self.default_relevant_distance)
        write_setting(prefix, "default_predictions", self.default_predictions)
        write_setting(
            prefix, "default_prediction_strategy", self.default_prediction_strategy
        )
        write_setting(
            prefix,
            "default_full_reference_strategy",
            self.default_full_reference_strategy,
        )
        write_setting(prefix, "default_processor", self.default_processor)
        write_setting(prefix, "default_od_strategy", self.default_od_strategy)
        write_setting(
            prefix,
            "default_threshold_overlap_percentage",
            self.default_threshold_overlap_percentage,
        )
        write_setting(prefix, "default_workfolder", self.default_workfolder)
        write_setting(
            prefix, "default_review_percentage", self.default_review_percentage
        )
        write_setting(prefix, "default_add_metadata", self.default_add_metadata)
        write_setting(prefix, "default_add_attributes", self.default_add_attributes)
        write_setting(
            prefix, "default_intermediate_layers", self.default_intermediate_layers
        )
        write_setting(prefix, "default_extra_logging", self.default_extra_logging)

    def prepare_parameters(self, parameters, context):
        # PARAMETER PREPARATION
        self.default_theme_layer = parameters[self.INPUT_THEMATIC]
        self.default_theme_layer_id = parameters["COMBOBOX_ID_THEME"]
        self.default_reference = parameters["ENUM_REFERENCE"]
        self.default_reference_layer = parameters[self.INPUT_REFERENCE]
        self.default_reference_layer_id = parameters["COMBOBOX_ID_REFERENCE"]
        self.default_relevant_distance = parameters["RELEVANT_DISTANCE"]
        self.default_predictions = parameters["PREDICTIONS"]
        self.default_prediction_strategy = parameters["PREDICTION_STRATEGY"]
        self.default_full_reference_strategy = parameters["FULL_REFERENCE_STRATEGY"]
        self.default_processor = parameters["ENUM_PROCESSOR"]
        self.default_od_strategy = parameters["ENUM_OD_STRATEGY"]
        self.default_threshold_overlap_percentage = parameters[
            "THRESHOLD_OVERLAP_PERCENTAGE"
        ]
        self.default_workfolder = parameters["WORK_FOLDER"]
        self.default_review_percentage = parameters["REVIEW_PERCENTAGE"]
        self.default_add_metadata = parameters["ADD_METADATA"]
        self.default_add_attributes = parameters["ADD_ATTRIBUTES"]
        self.default_intermediate_layers = parameters["SHOW_INTERMEDIATE_LAYERS"]
        self.default_extra_logging = parameters["SHOW_LOG_INFO"]

        # WORKFOLDER
        wrkfldr = self.default_workfolder
        if wrkfldr is None or str(wrkfldr) == "" or str(wrkfldr) == "NULL":
            wrkfldr = self.WORKFOLDER
        self.WORKFOLDER = get_workfolder(wrkfldr, name=self.name(), temporary=False)

        self.RELEVANT_DISTANCE = self.default_relevant_distance

        if isinstance(self.default_theme_layer, QgsProcessingFeatureSourceDefinition):
            self.LAYER_THEMATIC = self.default_theme_layer
            crs = (
                QgsProject.instance()
                .mapLayer(self.default_theme_layer.toVariant()["source"]["val"])
                .sourceCrs()
                .authid()
            )
        else:
            self.LAYER_THEMATIC = self.parameterAsVectorLayer(
                parameters, self.INPUT_THEMATIC, context
            )
            crs = (
                self.LAYER_THEMATIC.sourceCrs().authid()
            )  # set CRS for the calculations, based on the THEMATIC input layer
        self.CRS = crs
        self.ID_THEME_BRDRQ_FIELDNAME = self.default_theme_layer_id

        self.THRESHOLD_OVERLAP_PERCENTAGE = self.default_threshold_overlap_percentage
        self.REVIEW_PERCENTAGE = self.default_review_percentage
        self.OD_STRATEGY = OpenDomainStrategy[
            ENUM_OD_STRATEGY_OPTIONS[self.default_od_strategy]
        ]
        self.PROCESSOR = Processor[ENUM_PROCESSOR_OPTIONS[self.default_processor]]
        self.FULL_REFERENCE_STRATEGY = FullReferenceStrategy[
            ENUM_FULL_REFERENCE_STRATEGY_OPTIONS[self.default_full_reference_strategy]
        ]
        self.PREDICTION_STRATEGY = PredictionStrategy[
            ENUM_PREDICTION_STRATEGY_OPTIONS[self.default_prediction_strategy]
        ]
        self.ADD_METADATA = self.default_add_metadata
        self.ATTRIBUTES = self.default_add_attributes
        self.SHOW_INTERMEDIATE_LAYERS = self.default_intermediate_layers
        if self.default_predictions:
            self.PREDICTIONS = True  # 1 means PREDICTION
        else:
            self.PREDICTIONS = False  # 0 means NO_PREDICTION

        self.SHOW_LOG_INFO = self.default_extra_logging

        # REFERENCE
        ref = ENUM_REFERENCE_OPTIONS[self.default_reference]
        print(self.default_reference_layer)

        if self.default_reference_layer is None or self.default_reference_layer == -1:
            self.LAYER_REFERENCE = None
            self.ID_REFERENCE_BRDRQ_FIELDNAME = None
            self.default_reference_layer = None
            self.default_reference_layer_id = None
        else:
            self.LAYER_REFERENCE = self.parameterAsVectorLayer(
                parameters, self.INPUT_REFERENCE, context
            )
            self.ID_REFERENCE_BRDRQ_FIELDNAME = self.default_reference_layer_id
        # Set the referenceparameters
        self.SELECTED_REFERENCE, self.LAYER_REFERENCE_NAME, ref_suffix = (
            get_reference_params(
                ref, self.LAYER_REFERENCE, self.ID_REFERENCE_BRDRQ_FIELDNAME, self.CRS
            )
        )
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        self.SUFFIX = (
            "_DIST_" + str(self.RELEVANT_DISTANCE) + "_" + ref_suffix + "_" + timestamp
        )
        self.SUFFIX = self.SUFFIX.replace(".", "_")
        self.SUFFIX = self.SUFFIX.replace(" ", "_")
        if self.PREDICTIONS:
            self.SUFFIX = self.SUFFIX + "_PREDICTIONS"
        self.LAYER_RELEVANT_INTERSECTION = (
            self.LAYER_RELEVANT_INTERSECTION + self.SUFFIX
        )
        self.LAYER_RELEVANT_DIFFERENCE = self.LAYER_RELEVANT_DIFFERENCE + self.SUFFIX
        self.LAYER_RESULT = self.LAYER_RESULT + self.SUFFIX
        self.LAYER_RESULT_DIFF = self.LAYER_RESULT_DIFF + self.SUFFIX
        self.LAYER_RESULT_DIFF_PLUS = self.LAYER_RESULT_DIFF_PLUS + self.SUFFIX
        self.LAYER_RESULT_DIFF_MIN = self.LAYER_RESULT_DIFF_MIN + self.SUFFIX
        self.GROUP_LAYER = self.GROUP_LAYER + self.SUFFIX
        self.GROUP_LAYER_ACTUAL = self.GROUP_LAYER_ACTUAL + self.SUFFIX
        self.LAYER_REFERENCE_NAME = self.LAYER_REFERENCE_NAME + self.SUFFIX

        # write settings to project/profile
        self.write_settings()
