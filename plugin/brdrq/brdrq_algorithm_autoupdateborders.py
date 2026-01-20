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
from brdr.be.grb.enums import GRBType
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
    ID_THEME_FIELDNAME = (
        ""  # parameters that holds the fieldname of the unique theme id
    )

    GRB_TYPE = GRBType.ADP
    # ALIGNER parameters
    CRS = "EPSG:31370"  # default CRS for the aligner,updated by CRS of thematic inputlayer
    OD_STRATEGY = (
        OpenDomainStrategy.SNAP_ALL_SIDE
    )  # default OD_STRATEGY for the aligner,updated by user-choice
    THRESHOLD_OVERLAP_PERCENTAGE = 50  # default THRESHOLD_OVERLAP_PERCENTAGE for the aligner,updated by user-choice
    RELEVANT_DISTANCE = (
        2  # default RELEVANT_DISTANCE for the aligner,updated by user-choice
    )
    PROCESSOR = Processor.ALIGNER
    CORR_DISTANCE = 0.01  # default CORR_DISTANCE for the aligner
    MULTI_AS_SINGLE_MODUS = True  # default MULTI_AS_SINGLE_MODUS for the aligner

    METADATA_FIELDNAME = BASE_METADATA_FIELD_NAME
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

    # OTHER parameters
    MAX_DISTANCE_FOR_ACTUALISATION = 3  # maximum relevant distance that is used in the predictor when trying to update to actual GRB
    WORKFOLDER = "brdrQ"
    PREDICTION_STRATEGY = PredictionStrategy.ALL
    FULL_REFERENCE_STRATEGY = FullReferenceStrategy.NO_FULL_REFERENCE
    SHOW_LOG_INFO = True

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
            "Script to auto-update geometries that are aligned to an old GRB-referencelayer to a newer GRB-referencelayer. Bulk alignment to latest GRB based on predictions and provenance"
        )

    def helpUrl(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it.
        """
        return self.tr(
            "https://github.com/OnroerendErfgoed/brdrQ/blob/main/docs/autoupdateborders.md"
        )

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it.
        """
        return self.tr(
            "Script to auto-update geometries to the actual GRB-referencelayer"
        )

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # standard parameters
        parameter = QgsProcessingParameterFeatureSource(
            self.INPUT_THEMATIC,
            "THEMATIC LAYER, with the features to align",
            [QgsProcessing.TypeVectorAnyGeometry],
            defaultValue="themelayer",
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        parameter = QgsProcessingParameterField(
            "COMBOBOX_ID_THEME",
            "Choose thematic ID (a field with unique identifiers of the thematic layer)",
            "theme_identifier",
            self.INPUT_THEMATIC,
        )

        parameter.setHelp(
            "Dit is de themalaag die als input zal worden gebruikt voor de verwerking."
        )

        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        parameter = QgsProcessingParameterEnum(
            "ENUM_REFERENCE",
            "Select actual GRB Type to align to (ADP=parcels, GBG=buildings, KNW=artwork) :",
            options=GRB_TYPES,
            defaultValue=0,  # Index of the default option (e.g., 'Option A')
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        parameter = QgsProcessingParameterNumber(
            "MAX_RELEVANT_DISTANCE",
            "MAX_RELEVANT_DISTANCE (meter) - Max distance to try to align on the actual GRB",
            type=QgsProcessingParameterNumber.Double,
            defaultValue=3,
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        parameter = QgsProcessingParameterEnum(
            "PREDICTION_STRATEGY",
            "Select PREDICTION_STRATEGY:",
            options=ENUM_PREDICTION_STRATEGY_OPTIONS,
            defaultValue=1,
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        # ADVANCED INPUT
        parameter = QgsProcessingParameterEnum(
            "ENUM_PROCESSOR",
            "Select Processing algorithm:",
            options=ENUM_PROCESSOR_OPTIONS,
            defaultValue=0,  # Index of the default option (e.g., 'ALIGNER')
        )
        parameter.setFlags(
            parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(parameter)

        parameter = QgsProcessingParameterEnum(
            "ENUM_OD_STRATEGY",
            "Select OD-STRATEGY:",
            options=ENUM_OD_STRATEGY_OPTIONS,
            defaultValue=3,  # Index of the default option (e.g., 'SNAP_ALL_SIDE')
        )
        parameter.setFlags(
            parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(parameter)

        parameter = QgsProcessingParameterNumber(
            "THRESHOLD_OVERLAP_PERCENTAGE",
            "THRESHOLD_OVERLAP_PERCENTAGE (%)",
            type=QgsProcessingParameterNumber.Double,
            defaultValue=50,
        )
        parameter.setFlags(
            parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(parameter)

        parameter = QgsProcessingParameterEnum(
            "FULL_REFERENCE_STRATEGY",
            "Select FULL_REFERENCE_STRATEGY:",
            options=ENUM_FULL_REFERENCE_STRATEGY_OPTIONS,
            defaultValue=2,
        )
        parameter.setFlags(
            parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(parameter)

        parameter = QgsProcessingParameterField(
            "FORMULA_FIELD",
            "brdr_formula field (optional; field that holds a brdr_formula, used for a better prediction)",  # (if empty, formula will be calculated based on following alignment-date)
            "brdr_formula",
            self.INPUT_THEMATIC,
            optional=True,
        )
        parameter.setFlags(
            parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(parameter)

        parameter = QgsProcessingParameterFile(
            "WORK_FOLDER",
            "Working folder (optional; folder where output will be saved)",
            behavior=QgsProcessingParameterFile.Folder,
            optional=True,
        )
        parameter.setFlags(
            parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(parameter)

        parameter = QgsProcessingParameterBoolean(
            "SHOW_LOG_INFO", "SHOW_LOG_INFO (brdr-log)", defaultValue=self.SHOW_LOG_INFO
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

            id_theme = feature.attribute(self.ID_THEME_FIELDNAME)
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
        aligner_config.log_metadata = False
        aligner_config.add_observations = False

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
        # TODO: check to improve; first finding the not changed ones; and also the capakey-equals?
        fcs_actualisation = update_featurecollection_to_actual_grb(
            fc,
            id_theme_fieldname=self.ID_THEME_FIELDNAME,
            base_metadata_field=self.METADATA_FIELDNAME,
            grb_type=self.GRB_TYPE,
            max_distance_for_actualisation=self.MAX_DISTANCE_FOR_ACTUALISATION,
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

    def prepare_parameters(self, parameters, context):
        wrkfldr = parameters["WORK_FOLDER"]
        if wrkfldr is None or str(wrkfldr) == "" or str(wrkfldr) == "NULL":
            wrkfldr = self.WORKFOLDER
        self.WORKFOLDER = get_workfolder(
            wrkfldr, name="autoupdateborders", temporary=False
        )
        param_input_thematic = parameters[self.INPUT_THEMATIC]
        if isinstance(
            param_input_thematic, QgsProcessingFeatureSourceDefinition
        ):
            self.LAYER_THEMATIC = parameters[self.INPUT_THEMATIC]
            crs = QgsProject.instance().mapLayer(
                param_input_thematic.toVariant()["source"]["val"]).sourceCrs().authid()
        else:
            self.LAYER_THEMATIC = self.parameterAsVectorLayer(
                parameters, self.INPUT_THEMATIC, context
            )
            crs = (
                self.LAYER_THEMATIC.sourceCrs().authid()
            )  # set CRS for the calculations, based on the THEMATIC input layer
        self.CRS = crs
        self.MAX_DISTANCE_FOR_ACTUALISATION = parameters["MAX_RELEVANT_DISTANCE"]
        self.THRESHOLD_OVERLAP_PERCENTAGE = parameters["THRESHOLD_OVERLAP_PERCENTAGE"]
        self.OD_STRATEGY = OpenDomainStrategy[
            ENUM_OD_STRATEGY_OPTIONS[parameters["ENUM_OD_STRATEGY"]]
        ]
        ref = GRB_TYPES[parameters["ENUM_REFERENCE"]]
        self.GRB_TYPE, layer_reference_name, ref_suffix = get_reference_params(
            ref, None, None, self.CRS
        )
        self.SHOW_LOG_INFO = parameters["SHOW_LOG_INFO"]
        self.PROCESSOR = Processor[
            ENUM_PROCESSOR_OPTIONS[parameters["ENUM_PROCESSOR"]]
        ]
        self.PREDICTION_STRATEGY = PredictionStrategy[
            ENUM_PREDICTION_STRATEGY_OPTIONS[parameters["PREDICTION_STRATEGY"]]
        ]
        self.FULL_REFERENCE_STRATEGY = FullReferenceStrategy[
            ENUM_FULL_REFERENCE_STRATEGY_OPTIONS[parameters["FULL_REFERENCE_STRATEGY"]]
        ]
        self.METADATA_FIELDNAME = parameters["FORMULA_FIELD"]
        if str(self.METADATA_FIELDNAME) == "NULL":
            self.METADATA_FIELDNAME = None
        self.ID_THEME_FIELDNAME = parameters["COMBOBOX_ID_THEME"]

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
