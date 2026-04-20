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

from brdr.be.be import BeCadastralParcelLoader
from brdr.be.grb.enums import GRBType
from brdr.be.grb.loader import GRBFiscalParcelLoader, GRBActualLoader
from brdr.enums import (
    OpenDomainStrategy,
    SnapStrategy,
    AlignerResultType,
    FullReferenceStrategy,
    PredictionStrategy,
)
from brdr.geometry_utils import safe_unary_union
from brdr.loader import DictLoader
from brdr.nl.enums import BRKType
from brdr.nl.loader import BRKLoader
from brdr.osm.loader import OSMLoader
import numpy as np
from qgis import processing
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtCore import QDate, QDateTime
from qgis.core import QgsFeatureRequest
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterFile
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingException
from qgis.core import QgsProject
from qgis.core import QgsStyle

from .brdrq_utils import (
    ENUM_REFERENCE_OPTIONS,
    ENUM_OD_STRATEGY_OPTIONS,
    ENUM_SNAP_STRATEGY_OPTIONS,
    ADPF_VERSIONS,
    geom_qgis_to_shapely,
    featurecollection_to_layer,
    get_workfolder,
    thematic_preparation,
    get_reference_params,
    PREFIX_LOCAL_LAYER,
    DICT_ADPF_VERSIONS,
    move_to_group,
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
    generate_correction_layer,
    set_layer_visibility,
    remove_empty_features_from_diff_layers,
    NL_TYPES,
    DICT_NL_TYPES,
    BE_TYPES,
)
from .brdrq_algorithm_common import (
    add_boolean_parameter,
    add_enum_parameter,
    add_feature_source_parameter,
    add_field_parameter,
    add_file_parameter,
    add_number_parameter,
    add_standard_result_outputs,
    apply_saved_settings,
    assign_parameter_values,
    build_aligner,
    build_processor,
    get_log_feedback,
    get_prediction_strategy_options,
    initialize_default_attributes,
    resolve_thematic_layer_and_crs,
    write_saved_settings,
)

cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]
if cmd_folder not in sys.path:
    sys.path.insert(0, cmd_folder)


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
    SNAP_STRATEGY = None
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
    LOG_INFO = None
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
        add_feature_source_parameter(
            algorithm=self,
            name=self.INPUT_THEMATIC,
            description='<b>THEMATIC DATA</b><br><i style="color: gray;">Choose your thematic layer to align and its unique ID</i><br><br>Thematic Layer',
            geometry_types=[QgsProcessing.TypeVectorAnyGeometry],
            default_value=self.default_theme_layer,
        )

        add_field_parameter(
            algorithm=self,
            name="COMBOBOX_ID_THEME",
            description="Thematic ID (unique!)",
            default_value=self.default_theme_layer_id,
            parent_layer_parameter_name=self.INPUT_THEMATIC,
        )
        add_enum_parameter(
            algorithm=self,
            name="ENUM_REFERENCE",
            description='<br><b>REFERENCE DATA</b><br><i style="color: gray;">Choose the reference data. You can choose for on-the-fly download of prepared reference-data OR a local reference layer (LOCREF)</i><br><br>Reference',
            options=ENUM_REFERENCE_OPTIONS,
            default_value=self.default_reference,
        )
        add_feature_source_parameter(
            algorithm=self,
            name=self.INPUT_REFERENCE,
            description='<br>Local reference layer<br><i style="color: gray;">If LOCREF, Choose reference layer. Otherwise this will be ignored.</i>',
            geometry_types=[QgsProcessing.TypeVectorAnyGeometry],
            default_value=self.default_reference_layer,
            optional=True,
        )
        add_field_parameter(
            algorithm=self,
            name="COMBOBOX_ID_REFERENCE",
            description='<br>Reference ID (unique!)<br><i style="color: gray;">If LOCREF, Choose unique Reference ID for reference layer. Otherwise this will be ignored.</i>',
            default_value=self.default_reference_layer_id,
            parent_layer_parameter_name=self.INPUT_REFERENCE,
            optional=True,
        )
        add_number_parameter(
            algorithm=self,
            name="RELEVANT_DISTANCE",
            description='<br><b>RELEVANT DISTANCE (units: meter)</b><br><i style="color: gray;">This distance in meters determines what the max amount of change will be allowed when aligning your data</i><br><br>Relevant distance (m)',
            number_type=QgsProcessingParameterNumber.Double,
            default_value=self.default_relevant_distance,
        )
        add_standard_result_outputs(
            algorithm=self,
            layer_result=self.LAYER_RESULT,
            layer_result_diff=self.LAYER_RESULT_DIFF,
            layer_result_diff_plus=self.LAYER_RESULT_DIFF_PLUS,
            layer_result_diff_min=self.LAYER_RESULT_DIFF_MIN,
            layer_correction=self.LAYER_CORRECTION,
        )
        # advanced parameters

        add_enum_parameter(
            algorithm=self,
            name="PREDICTIONS",
            description='<br><b>PREDICTION SETTINGS</b><br><i style="color: gray;">Predictions uses a range of relevant distances to predict the best alignment. This results in better alignment results, but (!) increases (!) processing time</i><br><br>Use predictions',
            options=["NO_PREDICTIONS", "PREDICTIONS"],
            default_value=self.default_predictions,
            advanced=True,
        )
        add_enum_parameter(
            algorithm=self,
            name="PREDICTION_STRATEGY",
            description='<br>Prediction Strategy<br><i style="color: gray;">When using Predictions, the prediction strategy determines which predictions are returned in the output: All predictions, only the BEST prediction, or the ORIGINAL if there are multiple predictions</i>',
            options=ENUM_PREDICTION_STRATEGY_OPTIONS,
            default_value=self.default_prediction_strategy,
            advanced=True,
        )
        add_enum_parameter(
            algorithm=self,
            name="FULL_REFERENCE_STRATEGY",
            description='<br>Full Reference Strategy<br><i style="color: gray;">When using Predictions, the Full Reference strategy determines how predictions are handled that are fully covered by reference-data </i>',
            options=ENUM_FULL_REFERENCE_STRATEGY_OPTIONS,
            default_value=self.default_full_reference_strategy,
            advanced=True,
        )
        add_enum_parameter(
            algorithm=self,
            name="ENUM_PROCESSOR",
            description='<br><b>PROCESSOR_SETTINGS</b><br><i style="color: gray;">These settings determine the Processor (algorithm) & Processing-parameters to execute the alignment</i><br><br>Processor',
            options=ENUM_PROCESSOR_OPTIONS,
            default_value=self.default_processor,
            advanced=True,
        )
        add_enum_parameter(
            algorithm=self,
            name="ENUM_OD_STRATEGY",
            description='<br>Open Domain Strategy<br><i style="color: gray;">Strategy how the processing-algorithm handles the parts that are not covered by reference features (=Open Domain). You can choose to Exclude, Leave it AS IS, or ALIGN it to the reference features</i>',
            options=ENUM_OD_STRATEGY_OPTIONS,
            default_value=self.default_od_strategy,
            advanced=True,
        )
        add_enum_parameter(
            algorithm=self,
            name="ENUM_SNAP_STRATEGY",
            description='<br>Snap Strategy<br><i style="color: gray;">Strategy for snapping to reference vertices when processing line/point geometries</i>',
            options=ENUM_SNAP_STRATEGY_OPTIONS,
            default_value=self.default_snap_strategy,
            advanced=True,
        )
        add_number_parameter(
            algorithm=self,
            name="THRESHOLD_OVERLAP_PERCENTAGE",
            description='<br>Threshold overlap percentage (%)<br><i style="color: gray;">In the exceptional case that the algorithm cannot determine if a reference feature is relevant, this fallback-parameter is used to determine to include/exclude a reference based on overlap-percentage</i>',
            number_type=QgsProcessingParameterNumber.Integer,
            default_value=self.default_threshold_overlap_percentage,
            min_value=0,
            max_value=100,
            advanced=True,
        )
        add_file_parameter(
            algorithm=self,
            name="WORK_FOLDER",
            description='<br><b>OUTPUT SETTINGS</b><br><i style="color: gray;"> Settings to determine how the output will appear</i><br><br>Work Folder',
            behavior=QgsProcessingParameterFile.Folder,
            default_value=self.default_workfolder,
            optional=True,
            advanced=True,
        )
        add_number_parameter(
            algorithm=self,
            name="REVIEW_PERCENTAGE",
            description='<br>REVIEW_PERCENTAGE (%)<br><i style="color: gray;">results with a higher change % move to review-list </i>',
            number_type=QgsProcessingParameterNumber.Integer,
            default_value=self.default_review_percentage,
            min_value=0,
            max_value=100,
            advanced=True,
        )
        add_boolean_parameter(
            algorithm=self,
            name="ADD_METADATA",
            description="Add METADATA to output",
            default_value=self.default_add_metadata,
            advanced=True,
        )
        add_boolean_parameter(
            algorithm=self,
            name="ADD_ATTRIBUTES",
            description="Add ATTRIBUTES to output",
            default_value=self.default_add_attributes,
            advanced=True,
        )
        add_boolean_parameter(
            algorithm=self,
            name="SHOW_INTERMEDIATE_LAYERS",
            description="Show Intermediate processing results (if provided by processor)",
            default_value=self.default_intermediate_layers,
            advanced=True,
        )
        add_boolean_parameter(
            algorithm=self,
            name="LOG_INFO",
            description="Write extra logging (from brdr-log)",
            default_value=self.default_extra_logging,
            advanced=True,
        )

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
            self.SELECTED_REFERENCE != 0 and
            area > self.MAX_AREA_FOR_DOWNLOADING_REFERENCE
        ):
            raise QgsProcessingException(
                "The area of all unioned thematic geometries is bigger than threshold (" +
                str(self.MAX_AREA_FOR_DOWNLOADING_REFERENCE) +
                " m²) to use the on-the-fly downloads: " +
                str(area) +
                "(m² unioned thematic area) " +
                "Please make use of a local REFERENCELAYER (for performance reasons)"
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
        log_info = get_log_feedback(
            self.LOG_INFO, feedback, workfolder=self.WORKFOLDER
        )
        if self.LOG_INFO and log_info is not None and hasattr(log_info, "log_path"):
            feedback.pushInfo(f"Extra brdr log written to: {log_info.log_path}")
        processor = build_processor(
            processor_enum=self.PROCESSOR,
            od_strategy=self.OD_STRATEGY,
            snap_strategy=self.SNAP_STRATEGY,
            multi_as_single_modus=self.MULTI_AS_SINGLE_MODUS,
            correction_distance=self.CORR_DISTANCE,
            threshold_overlap_percentage=self.THRESHOLD_OVERLAP_PERCENTAGE,
            get_processor_by_id_fn=get_processor_by_id,
        )
        aligner = build_aligner(
            feedback=log_info,
            crs=self.CRS,
            processor=processor,
            log_metadata=self.ADD_METADATA,
            add_observations=self.ADD_METADATA if self.PREDICTIONS else True,
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
        elif self.SELECTED_REFERENCE in BE_TYPES:
            try:
                aligner.load_reference_data(BeCadastralParcelLoader(partition=1000, aligner=aligner))
            except Exception as e:
                raise QgsProcessingException(e)
        elif self.SELECTED_REFERENCE in NL_TYPES:
            try:
                brk_type = BRKType[DICT_NL_TYPES[self.SELECTED_REFERENCE]]
                aligner.load_reference_data(BRKLoader(brk_type=brk_type, partition=1000, aligner=aligner))
            except Exception as e:
                raise QgsProcessingException(e)
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
            "calculation for relevant distance (m): " +
            str(self.RELEVANT_DISTANCE) +
            " - Predictions: " +
            str(self.PREDICTIONS)
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

            max_predictions, multi_to_best_prediction = (
                get_prediction_strategy_options(self.PREDICTION_STRATEGY)
            )

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

        # FILTER empty geometries out of diff layers
        # This does not work for points so we do not add filter for point-layers
        remove_empty_features_from_diff_layers([
            self.LAYER_RESULT_DIFF_MIN,
            self.LAYER_RESULT_DIFF_PLUS,
            self.LAYER_RESULT_DIFF,
        ])

        result = self._get_output_layer(self.LAYER_RESULT)
        result_diff = self._get_output_layer(self.LAYER_RESULT_DIFF)
        result_diff_plus = self._get_output_layer(self.LAYER_RESULT_DIFF_PLUS)
        result_diff_min = self._get_output_layer(self.LAYER_RESULT_DIFF_MIN)

        correction_layer = None
        if not self.PREDICTIONS or self.PREDICTION_STRATEGY != PredictionStrategy.ALL:
            feedback.pushInfo("Generating correction layer")
            try:
                correction_layer = generate_correction_layer(thematic, result,id_theme_brdrq_fieldname=self.ID_THEME_BRDRQ_FIELDNAME,workfolder=self.WORKFOLDER, correction_layer_name = "CORRECTION" + self.SUFFIX,review_percentage=self.REVIEW_PERCENTAGE, add_metadata=self.ADD_METADATA)
                QgsProject.instance().addMapLayer(correction_layer)
                set_layer_visibility(correction_layer, True)
                move_to_group(correction_layer, self.GROUP_LAYER)
            except Exception as e:
                feedback.pushWarning(f"problem generating correction layer: {str(e)}")
        else:
            feedback.pushInfo(
                "No correction layer generated when predictions with predictionStrategy ALL is activated"
            )
        for layer in [result, result_diff, result_diff_plus, result_diff_min, correction_layer]:
            if layer is not None:
                layer.reload()
                layer.triggerRepaint()
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

    def _get_output_layer(self, layer_name):
        layers = QgsProject.instance().mapLayersByName(layer_name)
        if not layers:
            raise QgsProcessingException(
                f"Expected output layer '{layer_name}' was not created."
            )
        return layers[0]

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
        prefix = self.name()

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
            "ENUM_SNAP_STRATEGY": 1,
            "THRESHOLD_OVERLAP_PERCENTAGE": 50,
            "WORK_FOLDER": "brdrQ",
            "REVIEW_PERCENTAGE": 10,
            "ADD_METADATA": False,
            "ADD_ATTRIBUTES": False,
            "SHOW_INTERMEDIATE_LAYERS": False,
            "LOG_INFO": False,
        }
        initialize_default_attributes(
            self,
            [
                ("default_theme_layer", self.INPUT_THEMATIC),
                ("default_theme_layer_id", "COMBOBOX_ID_THEME"),
                ("default_reference", "ENUM_REFERENCE"),
                ("default_reference_layer", self.INPUT_REFERENCE),
                ("default_reference_layer_id", "COMBOBOX_ID_REFERENCE"),
                ("default_relevant_distance", "RELEVANT_DISTANCE"),
                ("default_predictions", "PREDICTIONS"),
                ("default_prediction_strategy", "PREDICTION_STRATEGY"),
                ("default_full_reference_strategy", "FULL_REFERENCE_STRATEGY"),
                ("default_processor", "ENUM_PROCESSOR"),
                ("default_od_strategy", "ENUM_OD_STRATEGY"),
                ("default_snap_strategy", "ENUM_SNAP_STRATEGY"),
                ("default_threshold_overlap_percentage", "THRESHOLD_OVERLAP_PERCENTAGE"),
                ("default_workfolder", "WORK_FOLDER"),
                ("default_review_percentage", "REVIEW_PERCENTAGE"),
                ("default_add_metadata", "ADD_METADATA"),
                ("default_add_attributes", "ADD_ATTRIBUTES"),
                ("default_intermediate_layers", "SHOW_INTERMEDIATE_LAYERS"),
                ("default_extra_logging", "LOG_INFO"),
            ],
        )

        # READ FROM SAVED SETTINGS (QSettings))
        apply_saved_settings(
            self,
            prefix,
            [
                ("default_theme_layer", "theme_layer"),
                ("default_theme_layer_id", "default_theme_layer_id"),
                ("default_reference", "default_reference"),
                ("default_reference_layer", "default_reference_layer"),
                ("default_reference_layer_id", "default_reference_layer_id"),
                ("default_relevant_distance", "relevant_distance", float),
                ("default_predictions", "default_predictions"),
                ("default_prediction_strategy", "default_prediction_strategy"),
                ("default_full_reference_strategy", "default_full_reference_strategy"),
                ("default_od_strategy", "default_od_strategy"),
                ("default_snap_strategy", "default_snap_strategy"),
                ("default_threshold_overlap_percentage", "default_threshold_overlap_percentage"),
                ("default_workfolder", "default_workfolder", None, "global"),
                ("default_review_percentage", "default_review_percentage"),
                ("default_add_metadata", "default_add_metadata"),
                ("default_add_attributes", "default_add_attributes"),
                ("default_intermediate_layers", "default_intermediate_layers"),
                ("default_extra_logging", "default_extra_logging"),
            ],
            read_setting,
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
        prefix = self.name()

        write_saved_settings(
            self,
            prefix,
            [
                ("default_theme_layer", "theme_layer"),
                ("default_theme_layer_id", "default_theme_layer_id"),
                ("default_reference", "default_reference"),
                ("default_reference_layer", "default_reference_layer"),
                ("default_reference_layer_id", "default_reference_layer_id"),
                ("default_relevant_distance", "relevant_distance"),
                ("default_predictions", "default_predictions"),
                ("default_prediction_strategy", "default_prediction_strategy"),
                ("default_full_reference_strategy", "default_full_reference_strategy"),
                ("default_processor", "default_processor"),
                ("default_od_strategy", "default_od_strategy"),
                ("default_snap_strategy", "default_snap_strategy"),
                ("default_threshold_overlap_percentage", "default_threshold_overlap_percentage"),
                ("default_workfolder", "default_workfolder", "global"),
                ("default_review_percentage", "default_review_percentage"),
                ("default_add_metadata", "default_add_metadata"),
                ("default_add_attributes", "default_add_attributes"),
                ("default_intermediate_layers", "default_intermediate_layers"),
                ("default_extra_logging", "default_extra_logging"),
            ],
            write_setting,
        )

    def prepare_parameters(self, parameters, context):
        if "LOG_INFO" not in parameters and "SHOW_LOG_INFO" in parameters:
            parameters["LOG_INFO"] = parameters["SHOW_LOG_INFO"]

        # PARAMETER PREPARATION
        assign_parameter_values(
            self,
            parameters,
            [
                ("default_theme_layer", self.INPUT_THEMATIC),
                ("default_theme_layer_id", "COMBOBOX_ID_THEME"),
                ("default_reference", "ENUM_REFERENCE"),
                ("default_reference_layer", self.INPUT_REFERENCE),
                ("default_reference_layer_id", "COMBOBOX_ID_REFERENCE"),
                ("default_relevant_distance", "RELEVANT_DISTANCE"),
                ("default_predictions", "PREDICTIONS"),
                ("default_prediction_strategy", "PREDICTION_STRATEGY"),
                ("default_full_reference_strategy", "FULL_REFERENCE_STRATEGY"),
                ("default_processor", "ENUM_PROCESSOR"),
                ("default_od_strategy", "ENUM_OD_STRATEGY"),
                ("default_snap_strategy", "ENUM_SNAP_STRATEGY"),
                ("default_threshold_overlap_percentage", "THRESHOLD_OVERLAP_PERCENTAGE"),
                ("default_workfolder", "WORK_FOLDER"),
                ("default_review_percentage", "REVIEW_PERCENTAGE"),
                ("default_add_metadata", "ADD_METADATA"),
                ("default_add_attributes", "ADD_ATTRIBUTES"),
                ("default_intermediate_layers", "SHOW_INTERMEDIATE_LAYERS"),
                ("default_extra_logging", "LOG_INFO"),
            ],
        )

        # Reset run-specific names so repeated runs on the same instance do not
        # keep appending suffixes.
        cls = type(self)
        self.SUFFIX = ""
        self.GROUP_LAYER = cls.GROUP_LAYER
        self.GROUP_LAYER_ACTUAL = cls.GROUP_LAYER_ACTUAL
        self.LAYER_RESULT = cls.LAYER_RESULT
        self.LAYER_RESULT_DIFF = cls.LAYER_RESULT_DIFF
        self.LAYER_RESULT_DIFF_PLUS = cls.LAYER_RESULT_DIFF_PLUS
        self.LAYER_RESULT_DIFF_MIN = cls.LAYER_RESULT_DIFF_MIN
        self.LAYER_RELEVANT_INTERSECTION = cls.LAYER_RELEVANT_INTERSECTION
        self.LAYER_RELEVANT_DIFFERENCE = cls.LAYER_RELEVANT_DIFFERENCE
        self.LAYER_REFERENCE_NAME = cls.LAYER_REFERENCE_NAME

        # WORKFOLDER
        wrkfldr = self.default_workfolder
        if wrkfldr is None or str(wrkfldr) == "" or str(wrkfldr) == "NULL":
            wrkfldr = self.WORKFOLDER
        self.WORKFOLDER = get_workfolder(wrkfldr, name=self.name(), temporary=False)

        self.RELEVANT_DISTANCE = self.default_relevant_distance

        self.LAYER_THEMATIC, self.CRS = resolve_thematic_layer_and_crs(
            algorithm=self,
            default_theme_layer=self.default_theme_layer,
            parameters=parameters,
            input_thematic=self.INPUT_THEMATIC,
            context=context,
        )
        self.ID_THEME_BRDRQ_FIELDNAME = self.default_theme_layer_id

        self.THRESHOLD_OVERLAP_PERCENTAGE = self.default_threshold_overlap_percentage
        self.REVIEW_PERCENTAGE = self.default_review_percentage
        self.OD_STRATEGY = OpenDomainStrategy[
            ENUM_OD_STRATEGY_OPTIONS[self.default_od_strategy]
        ]
        self.SNAP_STRATEGY = SnapStrategy[
            ENUM_SNAP_STRATEGY_OPTIONS[self.default_snap_strategy]
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

        self.LOG_INFO = self.default_extra_logging

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
