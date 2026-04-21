# -*- coding: utf-8 -*-

"""
***************************************************************************
*   name: brdrQ - AutoUpdateBorders
*   author: Karel Dieussaert
*   Docs, history & and Code- repo: https://github.com/OnroerendErfgoed/brdrQ/

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
from datetime import datetime

from brdr.be.grb.grb import update_featurecollection_to_actual_grb
from brdr.constants import BASE_METADATA_FIELD_NAME
from brdr.enums import OpenDomainStrategy, FullReferenceStrategy, SnapStrategy
from brdr.loader import DictLoader
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtCore import QDate, QDateTime
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingException
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterFile
from qgis.core import (
    QgsProcessingParameterNumber,
)
from qgis.core import QgsProject

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
from .brdrq_utils import (
    geom_qgis_to_shapely,
    featurecollection_to_layer,
    get_workfolder,
    GRB_TYPES,
    thematic_preparation,
    ENUM_PREDICTION_STRATEGY_OPTIONS,
    PredictionStrategy,
    ENUM_FULL_REFERENCE_STRATEGY_OPTIONS,
    ENUM_OD_STRATEGY_OPTIONS,
    ENUM_SNAP_STRATEGY_OPTIONS,
    get_reference_params,
    get_processor_by_id,
    Processor,
    ENUM_PROCESSOR_OPTIONS,
    write_setting,
    read_setting,
    get_valid_layer,
    generate_correction_layer,
    set_layer_visibility,
    move_to_group,
    remove_empty_features_from_diff_layers,
)


class AutoUpdateBordersProcessingAlgorithm(QgsProcessingAlgorithm):
    """
    Script to auto-update geometries that are aligned to an old GRB-referencelayer the actual GRB-referencelayer.
    Documentation can be found at: https://github.com/OnroerendErfgoed/brdrQ/
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    INPUT_THEMATIC = "INPUT_THEMATIC"  # reference to the combobox for choosing the thematic input layer
    LAYER_THEMATIC = None  # reference to the thematic input QgisVectorLayer
    ID_THEME_BRDRQ_FIELDNAME = None
    GRB_TYPE = None
    CRS = None
    OD_STRATEGY = None
    SNAP_STRATEGY = None
    THRESHOLD_OVERLAP_PERCENTAGE = None
    REVIEW_PERCENTAGE = None  # default - features that changes more than this % wil be moved to review lisr
    RELEVANT_DISTANCE = None
    PROCESSOR = None
    WORKFOLDER = None
    PREDICTION_STRATEGY = None
    FULL_REFERENCE_STRATEGY = None
    LOG_INFO = None
    METADATA_FIELDNAME = None

    # Non UI -  parameters
    CORR_DISTANCE = 0.01  # default CORR_DISTANCE for the aligner
    MULTI_AS_SINGLE_MODUS = True  # default MULTI_AS_SINGLE_MODUS for the aligner

    PREFIX = "brdrQ_"
    SUFFIX = ""  # parameter for composing a suffix for the layers
    LAYER_RESULT = (
        PREFIX + "RESULT"  # parameter that holds the TOC layername of the result
    )
    LAYER_RESULT_DIFF = (
        PREFIX + "DIFF"  # parameter that holds the TOC layername of the resulting diff
    )
    LAYER_RESULT_DIFF_PLUS = (
        PREFIX + "DIFF_PLUS"  # parameter that holds the TOC layername of the resulting diff_plus
    )
    LAYER_RESULT_DIFF_MIN = (
        PREFIX + "DIFF_MIN"  # parameter that holds the TOC layername of the resulting diff_min
    )
    LAYER_CORRECTION = (
        "CORRECTION"  # parameter that holds the TOC layername of the correction_layer
    )
    GROUP_LAYER = PREFIX + "GRB_UPDATE"

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
        return self.tr("brdrQ - GRB Updater (bulk)")

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

    def helpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it.
        """
        return self.tr(
            "Script to auto-update geometries that are aligned to an old GRB-referencelayer to a newer GRB-referencelayer. Bulk alignment to latest GRB based on predictions and provenance. See <a href='https://onroerenderfgoed.github.io/brdrQ/autoupdateborders.html'>https://onroerenderfgoed.github.io/brdrQ/</a> for documentation of the brdrQ-plugin"
        )

    def helpUrl(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it.
        """
        return self.tr(
            "https://onroerenderfgoed.github.io/brdrQ/autoupdateborders.html"
        )

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it.
        """
        return self.tr(
            "Script to auto-update geometries that are aligned to an old GRB-referencelayer to a newer GRB-referencelayer. Bulk alignment to latest GRB based on predictions and provenance. See <a href='https://onroerenderfgoed.github.io/brdrQ/autoupdateborders.html'>https://onroerenderfgoed.github.io/brdrQ/</a> for documentation of the brdrQ-plugin"
        )

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
            description='<br><b>REFERENCE DATA</b><br><i style="color: gray;">Choose the GRB reference data. The data will be downloaded on-the-fly </i>',
            options=GRB_TYPES,
            default_value=self.default_reference,
        )
        add_number_parameter(
            algorithm=self,
            name="RELEVANT_DISTANCE",
            description='<br><b>RELEVANT DISTANCE (units: meter)</b><br><i style="color: gray;">This distance in meters determines what the max amount of change will be allowed when aligning your data</i><br><br>Relevant distance (m)',
            number_type=QgsProcessingParameterNumber.Double,
            default_value=self.default_relevant_distance,
        )

        # ADVANCED INPUT
        add_enum_parameter(
            algorithm=self,
            name="PREDICTION_STRATEGY",
            description='<br><b>PREDICTION-SETTINGS</b><br><i style="color: gray;">The prediction strategy determines which predictions are returned in the output: All predictions, only the BEST prediction, or the ORIGINAL if there are multiple predictions</i>Prediction Strategy',
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
            description='<br>Threshold overlap percentage<br><i style="color: gray;">In the exceptional case that the algorithm cannot determine if a reference feature is relevant, this fallback-parameter is used to determine to include/exclude a reference based on overlap-percentage</i>',
            number_type=QgsProcessingParameterNumber.Integer,
            default_value=self.default_threshold_overlap_percentage,
            min_value=0,
            max_value=100,
            advanced=True,
        )
        add_field_parameter(
            algorithm=self,
            name="METADATA_FIELD",
            description="brdr_metadata field (optional; field that holds brdr_metadata, used for a better prediction)",
            default_value=self.default_metadata_field,
            parent_layer_parameter_name=self.INPUT_THEMATIC,
            optional=True,
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
            name="LOG_INFO",
            description="Write extra logging (from brdr-log)",
            default_value=self.default_extra_logging,
            advanced=True,
        )

        # OUTPUT

        add_standard_result_outputs(
            algorithm=self,
            layer_result=self.LAYER_RESULT,
            layer_result_diff=self.LAYER_RESULT_DIFF,
            layer_result_diff_plus=self.LAYER_RESULT_DIFF_PLUS,
            layer_result_diff_min=self.LAYER_RESULT_DIFF_MIN,
            layer_correction=self.LAYER_CORRECTION,
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """

        feedback_steps = 6
        feedback = QgsProcessingMultiStepFeedback(feedback_steps, feedback)
        feedback.pushInfo("START")

        self.prepare_parameters(parameters, context)

        thematic, thematic_buffered, self.CRS = thematic_preparation(
            self.LAYER_THEMATIC,
            self.RELEVANT_DISTANCE,
            context,
            feedback,
        )
        if thematic is None:
            raise QgsProcessingException(
                self.invalidSourceError(parameters, self.INPUT_THEMATIC)
            )

        # Load thematic into a shapely_dict:
        dict_thematic = {}
        dict_thematic_properties = {}
        metadata_field_name = self.METADATA_FIELDNAME
        for feature in thematic.getFeatures():
            if feedback.isCanceled():
                return {}

            id_theme = feature.attribute(self.ID_THEME_BRDRQ_FIELDNAME)
            dict_thematic[id_theme] = geom_qgis_to_shapely(feature.geometry())
            attributes_dict = {}
            # The actualisation flow expects the thematic identifier to be present
            # in GeoJSON properties.
            attributes_dict[self.ID_THEME_BRDRQ_FIELDNAME] = id_theme
            # Autoupdate only needs metadata for better prediction quality.
            if metadata_field_name:
                metadata_value = feature.attribute(metadata_field_name)
                if isinstance(metadata_value, QDate):
                    metadata_value = metadata_value.toPyDate()
                elif isinstance(metadata_value, QDateTime):
                    metadata_value = metadata_value.toPyDateTime()
                attributes_dict[metadata_field_name] = metadata_value
            dict_thematic_properties[id_theme] = attributes_dict

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
            log_metadata=True,
            add_observations=True,
        )
        aligner.load_thematic_data(
            DictLoader(
                data_dict=dict_thematic, data_dict_properties=dict_thematic_properties
            )
        )
        fc = aligner.thematic_data.to_geojson()

        feedback.pushInfo("START ACTUALISATION")

        max_predictions, multi_to_best_prediction = get_prediction_strategy_options(
            self.PREDICTION_STRATEGY
        )
        fcs_actualisation = update_featurecollection_to_actual_grb(
            fc,
            id_theme_fieldname=self.ID_THEME_BRDRQ_FIELDNAME,
            base_metadata_field=self.METADATA_FIELDNAME,
            grb_type=self.GRB_TYPE,
            max_distance_for_actualisation=self.RELEVANT_DISTANCE,
            feedback=log_info,
            max_predictions=max_predictions,
            full_reference_strategy=self.FULL_REFERENCE_STRATEGY,
            multi_to_best_prediction=multi_to_best_prediction,
        )
        if fcs_actualisation is None or fcs_actualisation == {}:
            feedback.pushInfo(
                "Geen wijzigingen gedetecteerd binnen tijdspanne in referentielaag (GRB-percelen)"
            )
            feedback.pushInfo("Proces wordt afgesloten")
            return {}

        # Add RESULT TO TOC
        if "result_diff_min" in fcs_actualisation:
            result_diff_min = "result_diff_min"
            geojson_result_diff_min = fcs_actualisation[result_diff_min]
            featurecollection_to_layer(
                self.LAYER_RESULT_DIFF_MIN,
                geojson_result_diff_min,
                result_diff_min,
                True,
                self.GROUP_LAYER,
                self.WORKFOLDER,
            )
        if "result_diff_plus" in fcs_actualisation:
            result_diff_plus = "result_diff_plus"
            geojson_result_diff_plus = fcs_actualisation[result_diff_plus]
            featurecollection_to_layer(
                self.LAYER_RESULT_DIFF_PLUS,
                geojson_result_diff_plus,
                result_diff_plus,
                True,
                self.GROUP_LAYER,
                self.WORKFOLDER,
            )
        if "result_diff" in fcs_actualisation:
            result_diff = "result_diff"
            geojson_result_diff = fcs_actualisation[result_diff]
            featurecollection_to_layer(
                self.LAYER_RESULT_DIFF,
                geojson_result_diff,
                result_diff,
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

        result = "result"
        geojson_result = fcs_actualisation[result]
        featurecollection_to_layer(
            self.LAYER_RESULT,
            geojson_result,
            result,
            True,
            self.GROUP_LAYER,
            self.WORKFOLDER,
        )

        feedback.pushInfo("Resulting geometry calculated")
        feedback.pushInfo("END ACTUALISATION")
        result = self._get_output_layer(self.LAYER_RESULT)
        result_diff = self._get_output_layer(self.LAYER_RESULT_DIFF)
        result_diff_plus = self._get_output_layer(self.LAYER_RESULT_DIFF_PLUS)
        result_diff_min = self._get_output_layer(self.LAYER_RESULT_DIFF_MIN)

        correction_layer = None
        if self.PREDICTION_STRATEGY != PredictionStrategy.ALL:
            feedback.pushInfo("Generating correction layer")
            try:
                correction_layer = generate_correction_layer(thematic, result,id_theme_brdrq_fieldname=self.ID_THEME_BRDRQ_FIELDNAME,workfolder=self.WORKFOLDER, correction_layer_name = "CORRECTION" + self.SUFFIX,review_percentage=self.REVIEW_PERCENTAGE, add_metadata=True)
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
        feedback.pushInfo("Resulting geometry calculated")
        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}

        feedback.pushInfo("END PROCESSING - Results calculated")
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

    def read_default_settings(self):
        # print ('read_settings')
        prefix = self.name()

        self.params_default_dict = {
            self.INPUT_THEMATIC: "themelayer",
            "COMBOBOX_ID_THEME": "id",
            "ENUM_REFERENCE": 0,
            "RELEVANT_DISTANCE": 3,
            "PREDICTION_STRATEGY": 1,
            "FULL_REFERENCE_STRATEGY": 2,
            "ENUM_PROCESSOR": 0,
            "ENUM_OD_STRATEGY": 3,
            "ENUM_SNAP_STRATEGY": 1,
            "THRESHOLD_OVERLAP_PERCENTAGE": 50,
            "REVIEW_PERCENTAGE": 10,
            "WORK_FOLDER": "brdrQ",
            "METADATA_FIELD": BASE_METADATA_FIELD_NAME,
            "LOG_INFO": False,
        }

        initialize_default_attributes(
            self,
            [
                ("default_theme_layer", self.INPUT_THEMATIC),
                ("default_theme_layer_id", "COMBOBOX_ID_THEME"),
                ("default_reference", "ENUM_REFERENCE"),
                ("default_relevant_distance", "RELEVANT_DISTANCE"),
                ("default_prediction_strategy", "PREDICTION_STRATEGY"),
                ("default_full_reference_strategy", "FULL_REFERENCE_STRATEGY"),
                ("default_processor", "ENUM_PROCESSOR"),
                ("default_od_strategy", "ENUM_OD_STRATEGY"),
                ("default_snap_strategy", "ENUM_SNAP_STRATEGY"),
                ("default_threshold_overlap_percentage", "THRESHOLD_OVERLAP_PERCENTAGE"),
                ("default_workfolder", "WORK_FOLDER"),
                ("default_review_percentage", "REVIEW_PERCENTAGE"),
                ("default_metadata_field", "METADATA_FIELD"),
                ("default_extra_logging", "LOG_INFO"),
            ],
        )

        # READ FROM SAVED SETTINGS
        apply_saved_settings(
            self,
            prefix,
            [
                ("default_theme_layer", "theme_layer"),
                ("default_theme_layer_id", "default_theme_layer_id"),
                ("default_reference", "default_reference"),
                ("default_relevant_distance", "relevant_distance", float),
                ("default_prediction_strategy", "default_prediction_strategy"),
                ("default_full_reference_strategy", "default_full_reference_strategy"),
                ("default_od_strategy", "default_od_strategy"),
                ("default_snap_strategy", "default_snap_strategy"),
                ("default_threshold_overlap_percentage", "default_threshold_overlap_percentage"),
                ("default_workfolder", "default_workfolder", None, "global"),
                ("default_review_percentage", "default_review_percentage"),
                ("default_metadata_field", "default_metadata_field"),
                ("default_extra_logging", "default_extra_logging"),
            ],
            read_setting,
        )

        # Validate defaults
        if not get_valid_layer(self.default_theme_layer):
            self.default_theme_layer = self.params_default_dict[self.INPUT_THEMATIC]

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
                ("default_relevant_distance", "relevant_distance"),
                ("default_prediction_strategy", "default_prediction_strategy"),
                ("default_full_reference_strategy", "default_full_reference_strategy"),
                ("default_processor", "default_processor"),
                ("default_od_strategy", "default_od_strategy"),
                ("default_snap_strategy", "default_snap_strategy"),
                ("default_threshold_overlap_percentage", "default_threshold_overlap_percentage"),
                ("default_workfolder", "default_workfolder", "global"),
                ("default_review_percentage", "default_review_percentage"),
                ("default_metadata_field", "default_metadata_field"),
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
                ("default_relevant_distance", "RELEVANT_DISTANCE"),
                ("default_prediction_strategy", "PREDICTION_STRATEGY"),
                ("default_full_reference_strategy", "FULL_REFERENCE_STRATEGY"),
                ("default_review_percentage", "REVIEW_PERCENTAGE"),
                ("default_processor", "ENUM_PROCESSOR"),
                ("default_od_strategy", "ENUM_OD_STRATEGY"),
                ("default_snap_strategy", "ENUM_SNAP_STRATEGY"),
                ("default_threshold_overlap_percentage", "THRESHOLD_OVERLAP_PERCENTAGE"),
                ("default_workfolder", "WORK_FOLDER"),
                ("default_metadata_field", "METADATA_FIELD"),
                ("default_extra_logging", "LOG_INFO"),
            ],
        )

        # Reset run-specific names so repeated runs on the same instance do not
        # keep appending suffixes.
        cls = type(self)
        self.SUFFIX = ""
        self.LAYER_RESULT = cls.LAYER_RESULT
        self.LAYER_RESULT_DIFF = cls.LAYER_RESULT_DIFF
        self.LAYER_RESULT_DIFF_PLUS = cls.LAYER_RESULT_DIFF_PLUS
        self.LAYER_RESULT_DIFF_MIN = cls.LAYER_RESULT_DIFF_MIN
        self.GROUP_LAYER = cls.GROUP_LAYER

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

        ref = GRB_TYPES[parameters["ENUM_REFERENCE"]]
        self.GRB_TYPE, layer_reference_name, ref_suffix = get_reference_params(
            ref, None, None, self.CRS
        )
        self.LOG_INFO = self.default_extra_logging

        self.METADATA_FIELDNAME = self.default_metadata_field
        if str(self.METADATA_FIELDNAME) == "NULL":
            self.METADATA_FIELDNAME = None

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        self.SUFFIX = "_" + ref_suffix + "_" + timestamp
        self.SUFFIX = self.SUFFIX.replace(".", "_")
        self.SUFFIX = self.SUFFIX.replace(" ", "_")

        self.LAYER_RESULT = self.LAYER_RESULT + self.SUFFIX
        self.LAYER_RESULT_DIFF = self.LAYER_RESULT_DIFF + self.SUFFIX
        self.LAYER_RESULT_DIFF_PLUS = self.LAYER_RESULT_DIFF_PLUS + self.SUFFIX
        self.LAYER_RESULT_DIFF_MIN = self.LAYER_RESULT_DIFF_MIN + self.SUFFIX
        self.GROUP_LAYER = self.GROUP_LAYER + self.SUFFIX

        # write settings to project/profile
        self.write_settings()
