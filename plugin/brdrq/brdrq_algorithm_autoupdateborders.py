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

from brdr.aligner import Aligner
from brdr.be.grb.grb import update_featurecollection_to_actual_grb
from brdr.configs import ProcessorConfig, AlignerConfig
from brdr.constants import BASE_METADATA_FIELD_NAME
from brdr.enums import OpenDomainStrategy, FullReferenceStrategy
from brdr.loader import DictLoader
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtCore import QDate, QDateTime
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingException
from qgis.core import QgsProcessingFeatureSourceDefinition
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingOutputVectorLayer
from qgis.core import QgsProcessingParameterBoolean
from qgis.core import QgsProcessingParameterEnum, QgsProcessingParameterDefinition
from qgis.core import (
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
)
from qgis.core import QgsProcessingParameterFile
from qgis.core import QgsProject

from .brdrq_utils import (
    geom_qgis_to_shapely,
    geojson_to_layer,
    get_workfolder,
    GRB_TYPES,
    thematic_preparation,
    ENUM_PREDICTION_STRATEGY_OPTIONS,
    PredictionStrategy,
    ENUM_FULL_REFERENCE_STRATEGY_OPTIONS,
    ENUM_OD_STRATEGY_OPTIONS,
    get_reference_params,
    get_processor_by_id,
    Processor,
    ENUM_PROCESSOR_OPTIONS,
    write_setting,
    read_setting,
    get_valid_layer,
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
    THRESHOLD_OVERLAP_PERCENTAGE = None
    RELEVANT_DISTANCE = None
    PROCESSOR = None
    WORKFOLDER = None
    PREDICTION_STRATEGY = None
    FULL_REFERENCE_STRATEGY = None
    SHOW_LOG_INFO = None
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
        PREFIX
        + "DIFF_PLUS"  # parameter that holds the TOC layername of the resulting diff_plus
    )
    LAYER_RESULT_DIFF_MIN = (
        PREFIX
        + "DIFF_MIN"  # parameter that holds the TOC layername of the resulting diff_min
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
            parentLayerParameterName = self.INPUT_THEMATIC,
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        parameter = QgsProcessingParameterEnum(
            "ENUM_REFERENCE",
            '<br><b>REFERENCE DATA</b><br><i style="color: gray;">Choose the GRB reference data. The data will be downloaded on-the-fly </i>',
            options=GRB_TYPES,
            defaultValue=self.default_reference,  # Index of the default option (e.g., 'Option A')
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

        # ADVANCED INPUT
        parameter = QgsProcessingParameterEnum(
            "PREDICTION_STRATEGY",
            '<br><b>PREDICTION-SETTINGS</b><br><i style="color: gray;">The prediction strategy determines which predictions are returned in the output: All predictions, only the BEST prediction, or the ORIGINAL if there are multiple predictions</i>Prediction Strategy',
            options=ENUM_PREDICTION_STRATEGY_OPTIONS,
            defaultValue=self.default_prediction_strategy,
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
            #optional=True,
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

        parameter = QgsProcessingParameterField(
            "METADATA_FIELD",
            "brdr_metadata field (optional; field that holds brdr_metadata, used for a better prediction)",  # (if empty, metadata will not be used)
            defaultValue=self.default_metadata_field,
            parentLayerParameterName = self.INPUT_THEMATIC,
            optional=True,
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

        parameter = QgsProcessingParameterBoolean(
            "SHOW_LOG_INFO",
            "Show extra logging (from brdr-log)",
            defaultValue=self.default_extra_logging
        )
        parameter.setFlags(
            parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(parameter)

        # OUTPUT

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
        features = thematic.getFeatures()

        for current, feature in enumerate(features):
            if feedback.isCanceled():
                return {}

            id_theme = feature.attribute(self.ID_THEME_BRDRQ_FIELDNAME)
            dict_thematic[id_theme] = geom_qgis_to_shapely(feature.geometry())
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

        # Aligner IMPLEMENTATION
        if self.SHOW_LOG_INFO:
            log_info = feedback
        else:
            log_info = None

        processor_config=ProcessorConfig()
        processor_config.od_strategy = self.OD_STRATEGY
        processor_config.multi_as_single_modus = self.MULTI_AS_SINGLE_MODUS
        processor_config.correction_distance = self.CORR_DISTANCE
        processor_config.threshold_overlap_percentage = self.THRESHOLD_OVERLAP_PERCENTAGE
        processor=get_processor_by_id(processor_id=self.PROCESSOR.value,config=processor_config)
        aligner_config = AlignerConfig()
        aligner_config.log_metadata = True
        aligner_config.add_observations = True

        aligner = Aligner(
            feedback=log_info,
        crs = self.CRS,
            processor=processor,
            config=aligner_config,

        )
        aligner.load_thematic_data(
            DictLoader(
                data_dict=dict_thematic, data_dict_properties=dict_thematic_properties
            )
        )
        fc = aligner.thematic_data.to_geojson()

        feedback.pushInfo("START ACTUALISATION")

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
            geojson_to_layer(
                self.LAYER_RESULT_DIFF_MIN,
                geojson_result_diff_min,result_diff_min,
                True,
                self.GROUP_LAYER,
                self.WORKFOLDER,
            )
        if "result_diff_plus" in fcs_actualisation:
            result_diff_plus = "result_diff_plus"
            geojson_result_diff_plus = fcs_actualisation[result_diff_plus]
            geojson_to_layer(
                self.LAYER_RESULT_DIFF_PLUS,
                geojson_result_diff_plus,result_diff_plus,
                True,
                self.GROUP_LAYER,
                self.WORKFOLDER,
            )
        if "result_diff" in fcs_actualisation:
            result_diff = "result_diff"
            geojson_result_diff = fcs_actualisation[result_diff]
            geojson_to_layer(
                self.LAYER_RESULT_DIFF,
                geojson_result_diff, result_diff,
                False,
                self.GROUP_LAYER,
                self.WORKFOLDER,
            )

        result = "result"
        geojson_result = fcs_actualisation[result]
        geojson_to_layer(
            self.LAYER_RESULT,
            geojson_result, result,
            True,
            self.GROUP_LAYER,
            self.WORKFOLDER,
        )

        feedback.pushInfo("Resulterende geometrie berekend")
        feedback.pushInfo("END ACTUALISATION")
        result = QgsProject.instance().mapLayersByName(self.LAYER_RESULT)[0]
        result_diff = QgsProject.instance().mapLayersByName(self.LAYER_RESULT_DIFF)[0]
        result_diff_plus = QgsProject.instance().mapLayersByName(
            self.LAYER_RESULT_DIFF_PLUS
        )[0]
        result_diff_min = QgsProject.instance().mapLayersByName(
            self.LAYER_RESULT_DIFF_MIN
        )[0]
        QgsProject.instance().reloadAllLayers()
        feedback.pushInfo("Resulterende geometrie berekend")
        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}

        feedback.pushInfo("END PROCESSING")
        feedback.pushInfo("EINDE: RESULTAAT BEREKEND")
        return {
            "OUTPUT_RESULT": result,
            "OUTPUT_RESULT_DIFF": result_diff,
            "OUTPUT_RESULT_DIFF_PLUS": result_diff_plus,
            "OUTPUT_RESULT_DIFF_MIN": result_diff_min,
        }

    def read_default_settings(self):
        # print ('read_settings')
        prefix = self.name() + "/"

        self.params_default_dict = {
            self.INPUT_THEMATIC: "themelayer",
            "COMBOBOX_ID_THEME": "id",
            "ENUM_REFERENCE": 0,
            "RELEVANT_DISTANCE": 3,
            "PREDICTION_STRATEGY": 1,
            "FULL_REFERENCE_STRATEGY": 2,
            "ENUM_PROCESSOR": 0,
            "ENUM_OD_STRATEGY": 3,
            "THRESHOLD_OVERLAP_PERCENTAGE": 50,
            "WORK_FOLDER": "brdrQ",
            "METADATA_FIELD": BASE_METADATA_FIELD_NAME,
            "SHOW_LOG_INFO": False,
        }

        #Read from default dict first
        self.default_theme_layer = self.params_default_dict[self.INPUT_THEMATIC]
        self.default_theme_layer_id = self.params_default_dict["COMBOBOX_ID_THEME"]
        self.default_reference = self.params_default_dict["ENUM_REFERENCE"]
        self.default_relevant_distance = self.params_default_dict["RELEVANT_DISTANCE"]
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
        self.default_metadata_field = self.params_default_dict["METADATA_FIELD"]
        self.default_extra_logging = self.params_default_dict["SHOW_LOG_INFO"]

        # READ FROM SAVED SETTINGS
        self.default_theme_layer  = read_setting(prefix,"theme_layer",self.default_theme_layer)
        self.default_theme_layer_id  = read_setting(prefix,"default_theme_layer_id",self.default_theme_layer_id)
        self.default_reference  = read_setting(prefix,"default_reference",self.default_reference)
        self.default_relevant_distance  = read_setting(prefix,"relevant_distance",self.default_relevant_distance)
        self.default_prediction_strategy  = read_setting(prefix,"default_prediction_strategy",self.default_prediction_strategy)
        self.default_full_reference_strategy  = read_setting(prefix,"default_full_reference_strategy",self.default_full_reference_strategy)
        self.default_processor  = read_setting(prefix,"default_processor",self.default_processor)
        self.default_od_strategy  = read_setting(prefix,"default_od_strategy",self.default_od_strategy)
        self.default_threshold_overlap_percentage  = read_setting(prefix,"default_threshold_overlap_percentage",self.default_threshold_overlap_percentage)
        self.default_workfolder  = read_setting(prefix,"default_workfolder",self.default_workfolder)
        self.default_metadata_field  = read_setting(prefix,"default_metadata_field",self.default_metadata_field)
        self.default_extra_logging  = read_setting(prefix, "default_extra_logging", self.default_extra_logging)

        #Validate defaults
        if not get_valid_layer(self.default_theme_layer):
            self.default_theme_layer =self.params_default_dict[self.INPUT_THEMATIC]

    def write_settings(self):
        # print ('write_settings')
        prefix = self.name() + "/"

        write_setting(prefix,"theme_layer",self.default_theme_layer)
        write_setting(prefix,"default_theme_layer_id",self.default_theme_layer_id)
        write_setting(prefix,"default_reference",self.default_reference)
        write_setting(prefix,"relevant_distance",self.default_relevant_distance)
        write_setting(prefix,"default_prediction_strategy",self.default_prediction_strategy)
        write_setting(prefix,"default_full_reference_strategy",self.default_full_reference_strategy)
        write_setting(prefix,"default_processor",self.default_processor)
        write_setting(prefix,"default_od_strategy",self.default_od_strategy)
        write_setting(prefix,"default_threshold_overlap_percentage",self.default_threshold_overlap_percentage)
        write_setting(prefix,"default_workfolder",self.default_workfolder)
        write_setting(prefix,"default_metadata_field",self.default_metadata_field)
        write_setting(prefix, "default_extra_logging", self.default_extra_logging)

    def prepare_parameters(self, parameters, context):

        # PARAMETER PREPARATION
        self.default_theme_layer = parameters[self.INPUT_THEMATIC]
        self.default_theme_layer_id = parameters["COMBOBOX_ID_THEME"]
        self.default_reference = parameters["ENUM_REFERENCE"]
        self.default_relevant_distance = parameters["RELEVANT_DISTANCE"]
        self.default_prediction_strategy = parameters["PREDICTION_STRATEGY"]
        self.default_full_reference_strategy = parameters["FULL_REFERENCE_STRATEGY"]
        self.default_processor = parameters["ENUM_PROCESSOR"]
        self.default_od_strategy= parameters["ENUM_OD_STRATEGY"]
        self.default_threshold_overlap_percentage = parameters["THRESHOLD_OVERLAP_PERCENTAGE"]
        self.default_workfolder = parameters["WORK_FOLDER"]
        self.default_metadata_field= parameters["METADATA_FIELD"]
        self.default_extra_logging= parameters["SHOW_LOG_INFO"]

        wrkfldr = self.default_workfolder
        if wrkfldr is None or str(wrkfldr) == "" or str(wrkfldr) == "NULL":
            wrkfldr = self.WORKFOLDER
        self.WORKFOLDER = get_workfolder(
            wrkfldr, name=self.name(), temporary=False
        )

        self.RELEVANT_DISTANCE = self.default_relevant_distance

        if isinstance(
            self.default_theme_layer, QgsProcessingFeatureSourceDefinition
        ):
            self.LAYER_THEMATIC = self.default_theme_layer
            crs = QgsProject.instance().mapLayer(
                self.default_theme_layer.toVariant()["source"]["val"]).sourceCrs().authid()
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

        ref = GRB_TYPES[parameters["ENUM_REFERENCE"]]
        self.GRB_TYPE, layer_reference_name, ref_suffix = get_reference_params(
            ref, None, None, self.CRS
        )
        self.SHOW_LOG_INFO = parameters["SHOW_LOG_INFO"]


        self.METADATA_FIELDNAME = self.default_metadata_field
        if str(self.METADATA_FIELDNAME) == "NULL":
            self.METADATA_FIELDNAME = None


        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        self.SUFFIX = (
            "_" + ref_suffix + "_" + timestamp
        )
        self.SUFFIX = self.SUFFIX.replace(".", "_")
        self.SUFFIX = self.SUFFIX.replace(" ", "_")

        self.LAYER_RESULT = self.LAYER_RESULT + self.SUFFIX
        self.LAYER_RESULT_DIFF = self.LAYER_RESULT_DIFF + self.SUFFIX
        self.LAYER_RESULT_DIFF_PLUS = self.LAYER_RESULT_DIFF_PLUS + self.SUFFIX
        self.LAYER_RESULT_DIFF_MIN = self.LAYER_RESULT_DIFF_MIN + self.SUFFIX
        self.GROUP_LAYER = self.GROUP_LAYER + self.SUFFIX

        # write settings to project/profile
        self.write_settings()
