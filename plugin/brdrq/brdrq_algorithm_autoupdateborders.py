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


from brdr.aligner import Aligner
from brdr.constants import BASE_FORMULA_FIELD_NAME
from brdr.enums import AlignerInputType, GRBType, FullStrategy
from brdr.grb import update_to_actual_grb
from brdr.loader import DictLoader
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtCore import QDate, QDateTime
from qgis._core import QgsProcessingParameterEnum
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingException
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingOutputVectorLayer
from qgis.core import QgsProcessingParameterBoolean
from qgis.core import (
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
)
from qgis.core import QgsProcessingParameterFile
from qgis.core import QgsProject
from qgis.core import QgsStyle

from .brdrq_utils import (
    geom_qgis_to_shapely,
    geojson_to_layer,
    get_workfolder,
    GRB_TYPES,
    thematic_preparation,
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
    THEMATIC_LAYER = None #reference to the thematic input QgisVectorLayer
    ID_THEME_FIELDNAME = (
        ""  # parameters that holds the fieldname of the unique theme id
    )

    GRB_TYPE = GRBType.ADP
    # ALIGNER parameters
    CRS = "EPSG:31370"  # default CRS for the aligner,updated by CRS of thematic inputlayer
    OD_STRATEGY = 2  # default OD_STRATEGY for the aligner,updated by user-choice
    THRESHOLD_OVERLAP_PERCENTAGE = 50  # default THRESHOLD_OVERLAP_PERCENTAGE for the aligner,updated by user-choice
    RELEVANT_DISTANCE = (
        2  # default RELEVANT_DISTANCE for the aligner,updated by user-choice
    )
    CORR_DISTANCE = 0.01  # default CORR_DISTANCE for the aligner
    MULTI_AS_SINGLE_MODUS = True  # default MULTI_AS_SINGLE_MODUS for the aligner

    FORMULA_FIELDNAME = BASE_FORMULA_FIELD_NAME
    LAYER_RESULT = (
        "brdrQ_RESULT"  # parameter that holds the TOC layername of the result
    )
    LAYER_RESULT_DIFF = (
        "DIFF"  # parameter that holds the TOC layername of the resulting diff
    )
    LAYER_RESULT_DIFF_PLUS = (
        "DIFF_PLUS"  # parameter that holds the TOC layername of the resulting diff_plus
    )
    LAYER_RESULT_DIFF_MIN = (
        "DIFF_MIN"  # parameter that holds the TOC layername of the resulting diff_min
    )
    GROUP_LAYER = "BRDRQ_GRB_UPDATE"

    # OTHER parameters
    MAX_DISTANCE_FOR_ACTUALISATION = 3  # maximum relevant distance that is used in the predictor when trying to update to actual GRB
    WORKFOLDER = "brdrQ"
    BEST_PREDICTION = True
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
            [QgsProcessing.TypeVectorPolygon],
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

        parameter = QgsProcessingParameterEnum(
            "ENUM_REFERENCE",
            "Select GRB Type to align to:",
            options=GRB_TYPES,
            defaultValue=0,  # Index of the default option (e.g., 'Option A')
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        parameter = QgsProcessingParameterField(
            "FORMULA_FIELD",
            "Formula field",  # (if empty, formula will be calculated based on following alignment-date)
            "brdr_formula",
            self.INPUT_THEMATIC,
            optional=True,
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

        parameter = QgsProcessingParameterFile(
            "WORK_FOLDER",
            self.tr("Working folder"),
            behavior=QgsProcessingParameterFile.Folder,
            optional=True,
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        parameter = QgsProcessingParameterBoolean(
            "BEST_PREDICTION",
            "Best prediction (when multiple predictions)",
            defaultValue=self.BEST_PREDICTION,
        )
        self.addParameter(parameter)

        parameter = QgsProcessingParameterBoolean(
            "SHOW_LOG_INFO", "SHOW_LOG_INFO (brdr-log)", defaultValue=self.SHOW_LOG_INFO
        )
        self.addParameter(parameter)

        self.addOutput(
            QgsProcessingOutputVectorLayer(
                "OUTPUT_RESULT",
                self.LAYER_RESULT,
                QgsProcessing.TypeVectorPolygon,
            )
        )
        self.addOutput(
            QgsProcessingOutputVectorLayer(
                "OUTPUT_RESULT_DIFF",
                self.LAYER_RESULT_DIFF,
                QgsProcessing.TypeVectorPolygon,
            )
        )
        self.addOutput(
            QgsProcessingOutputVectorLayer(
                "OUTPUT_RESULT_DIFF_PLUS",
                self.LAYER_RESULT_DIFF_PLUS,
                QgsProcessing.TypeVectorPolygon,
            )
        )
        self.addOutput(
            QgsProcessingOutputVectorLayer(
                "OUTPUT_RESULT_DIFF_MIN",
                self.LAYER_RESULT_DIFF_MIN,
                QgsProcessing.TypeVectorPolygon,
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """

        feedback_steps = 6
        feedback = QgsProcessingMultiStepFeedback(feedback_steps, feedback)
        feedback.pushInfo("START")

        self.prepare_parameters(parameters,context)

        thematic, thematic_buffered, self.CRS = thematic_preparation(
            self.THEMATIC_LAYER,
            self.RELEVANT_DISTANCE,
            context,
            feedback,
        )
        if thematic is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT_THEMATIC))

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

        aligner = Aligner(od_strategy=self.OD_STRATEGY)
        aligner.load_thematic_data(
            DictLoader(
                data_dict=dict_thematic, data_dict_properties=dict_thematic_properties
            )
        )
        fc = aligner.get_input_as_geojson(inputtype=AlignerInputType.THEMATIC)

        feedback.pushInfo("START ACTUALISATION")
        if self.SHOW_LOG_INFO:
            log_info = feedback
        else:
            log_info = None

        if self.BEST_PREDICTION:
            max_predictions = 1
            multi_to_best_prediction = True
        else:
            max_predictions = -1
            multi_to_best_prediction = False

        print(str(self.FORMULA_FIELDNAME))
        fcs_actualisation = update_to_actual_grb(
            fc,
            id_theme_fieldname=self.ID_THEME_FIELDNAME,
            base_formula_field=self.FORMULA_FIELDNAME,
            grb_type=self.GRB_TYPE,
            max_distance_for_actualisation=self.MAX_DISTANCE_FOR_ACTUALISATION,
            feedback=log_info,
            max_predictions=max_predictions,
            full_strategy=FullStrategy.NO_FULL,
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
            geojson_to_layer(
                self.LAYER_RESULT_DIFF_MIN,
                fcs_actualisation["result_diff_min"],
                QgsStyle.defaultStyle().symbol("hashed cred /"),
                True,
                self.GROUP_LAYER,
                self.WORKFOLDER,
            )
        if "result_diff_plus" in fcs_actualisation:
            geojson_to_layer(
                self.LAYER_RESULT_DIFF_PLUS,
                fcs_actualisation["result_diff_plus"],
                QgsStyle.defaultStyle().symbol("gradient green fill"),
                True,
                self.GROUP_LAYER,
                self.WORKFOLDER,
            )
        if "result_diff" in fcs_actualisation:
            geojson_to_layer(
                self.LAYER_RESULT_DIFF,
                fcs_actualisation["result_diff"],
                QgsStyle.defaultStyle().symbol("hashed black X"),
                False,
                self.GROUP_LAYER,
                self.WORKFOLDER,
            )
        geojson_to_layer(
            self.LAYER_RESULT,
            fcs_actualisation["result"],
            QgsStyle.defaultStyle().symbol("outline green"),
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

    def prepare_parameters(self, parameters,context):
        wrkfldr = parameters["WORK_FOLDER"]
        if wrkfldr is None or str(wrkfldr) == "" or str(wrkfldr) == "NULL":
            wrkfldr = self.WORKFOLDER
        self.WORKFOLDER = get_workfolder(
            wrkfldr, name="autoupdateborders", temporary=False
        )
        self.THEMATIC_LAYER = self.parameterAsVectorLayer(parameters, self.INPUT_THEMATIC, context)
        self.CRS = (
            self.THEMATIC_LAYER.sourceCrs().authid()
        )  # set CRS for the calculations, based on the THEMATIC input layer
        self.MAX_DISTANCE_FOR_ACTUALISATION = parameters["MAX_RELEVANT_DISTANCE"]
        self.GRB_TYPE = GRBType[GRB_TYPES[parameters["ENUM_REFERENCE"]]]
        self.SHOW_LOG_INFO = parameters["SHOW_LOG_INFO"]
        self.BEST_PREDICTION = parameters["BEST_PREDICTION"]
        self.FORMULA_FIELDNAME = parameters["FORMULA_FIELD"]
        if str(self.FORMULA_FIELDNAME) == "NULL":
            self.FORMULA_FIELDNAME = None
        self.ID_THEME_FIELDNAME = parameters["COMBOBOX_ID_THEME"]
