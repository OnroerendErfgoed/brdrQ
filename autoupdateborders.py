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
from qgis.PyQt.QtCore import QVariant, QDateTime
from qgis.PyQt.QtCore import QTextCodec
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor

from qgis.utils import iface
from qgis.core import QgsProject
from qgis.core import QgsCoordinateReferenceSystem
from qgis.core import QgsFeature
from qgis.core import QgsField
from qgis.core import QgsGeometry
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingException
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingOutputVectorLayer, QgsFillSymbol
from qgis.core import QgsProcessingParameterDateTime, QgsProcessingParameterFeatureSource, QgsProcessingParameterField, \
    QgsProcessingParameterBoolean
from qgis.core import QgsProject
from qgis.core import QgsStyle
from qgis.core import QgsVectorLayer
from qgis.core import QgsSimpleFillSymbolLayer, QgsMarkerLineSymbolLayer, QgsSimpleLineSymbolLayer, QgsFillSymbol, \
    QgsSingleSymbolRenderer, QgsLayerTreeLayer, QgsMapLayer, QgsLayerTreeNode, QgsLayerTreeGroup


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
from brdr.loader import DictLoader, GRBActualLoader
from brdr.utils import multipolygons_to_singles, get_series_geojson_dict
from brdr.enums import OpenbaarDomeinStrategy
from brdr.enums import GRBType
from brdr.grb import get_geoms_affected_by_grb_change, get_last_version_date, evaluate


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
    PROCESS_MULTI_AS_SINGLE_POLYGONS = True
    FORMULA_FIELD = "FORMULA_FIELD"
    RESULT = "RESULT"
    OUTPUT_RESULT = "OUTPUT_RESULT"
    LAYER_RESULT = "brdrQ_RESULT"
    LAYER_RESULT_DIFF = "brdrQ_RESULT_DIFF"

    FORMULA = True

    GROUP_LAYER = "BRDRQ_UPDATES"

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

    def geom_qgis_to_shapely(self, geom_qgis):
        """
        Method to convert a QGIS-geometry to a Shapely-geometry
        """
        wkt = geom_qgis.asWkt()
        geom_shapely = from_wkt(wkt)
        return geom_shapely

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
            return QgsSingleSymbolRenderer(fill_symbol)
        return None

    def geojson_to_layer(self, name, geojson, renderer, visible):
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
        fcString = json.dumps(geojson)

        vl = QgsVectorLayer(fcString, name, "ogr")
        print(vl)
        vl.setCrs(QgsCoordinateReferenceSystem(self.CRS))
        pr = vl.dataProvider()
        vl.updateFields()
        # styling
        # vl.setOpacity(0.5)

        if renderer is not None:
            vl.setRenderer(renderer)

        # adding layer to TOC
        qinst.addMapLayer(
            vl, False
        )  # False so that it doesn't get inserted at default position

        root.insertLayer(0, vl)

        node = root.findLayer(vl.id())
        if node:
            new_state = Qt.Checked if visible else Qt.Unchecked
            node.setItemVisibilityChecked(new_state)

        self.move_to_group(vl, self.GROUP_LAYER)
        vl.triggerRepaint()
        iface.layerTreeView().refreshLayerSymbology(vl.id())
        return vl

    def check_business_equality(self, base_formula, actual_formula):
        """
        function that checks if 2 formulas are equal (determined by business-logic)
        """
        try:
            # TODO: research and implementation of following ideas
            # ideas:
            # * If result_diff smaller than 0.x --> automatic update
            # * big polygons: If 'outer ring' has same formula (do net check inner side) --> automatic update
            # ** outer ring can be calculated: 1) nageative buffer 2) original - buffered
            if base_formula.keys() != actual_formula.keys():
                return False
            for key in base_formula.keys():
                if base_formula[key]["full"] != actual_formula[key]["full"]:
                    return False
                # if abs(base_formula[key]['area'] - actual_formula[key]['area'])>1: #area changed by 1 m²
                #     return False
                # if abs(base_formula[key]['area'] - actual_formula[key]['area'])/base_formula[key]['area'] > 0.01: #area changed by 1%
                #     return False
            return True
        except:
            return False

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

        parameter = QgsProcessingParameterField(
            self.FORMULA_FIELD,
            "Formula field",
            "formula",
            self.INPUT_THEMATIC,
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)
        # INPUT  standard parameters
        # make your own widget is also possible!
        # https://gis.stackexchange.com/questions/432849/changing-appearence-of-datetime-input-in-qgis-processing-tool-to-international-d
        # https://www.faunalia.eu/en/blog/2019-07-02-custom-processing-widget

        # START DATETIME
        parameter = QgsProcessingParameterDateTime(
            self.START_DATE,
            'Alignment-Date (date of version of reference layer where the thematic is aligned on):',
            type=QgsProcessingParameterDateTime.Date
            ,
            defaultValue=QDateTime.currentDateTime().addDays(2 * -365)
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        parameter = QgsProcessingParameterBoolean(
            "PROCESS_MULTI_AS_SINGLE_POLYGONS",
            "PROCESS_MULTI_AS_SINGLE_POLYGONS",
            defaultValue=True,
        )
        # parameter.setFlags(parameter.flags() |
        # QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(parameter)

        ## END DATETIME
        # parameter = QgsProcessingParameterDateTime(
        #    self.END_DATE,
        #    'EndDate:',
        #    type=QgsProcessingParameterDateTime.Date
        #    # ,
        #    # defaultValue = QDateTime.currentDateTime().addDays(-31)
        # )
        # parameter.setFlags(parameter.flags())
        # self.addParameter(parameter)

        self.addOutput(
            QgsProcessingOutputVectorLayer(
                self.OUTPUT_RESULT,
                self.LAYER_RESULT,
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
        outputs = {}

        self.prepare_parameters(parameters)

        thematic, thematic_buffered = self._thematic_preparation(
            context, feedback, outputs, parameters
        )
        if thematic is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.test))

        # Load thematic into a shapely_dict:
        dict_thematic = {}
        dict_thematic_formula = {}
        features = thematic.getFeatures()
        for current, feature in enumerate(features):
            if feedback.isCanceled():
                return {}
            id_theme = feature.attribute(self.ID_THEME)
            dict_thematic[id_theme] = self.geom_qgis_to_shapely(feature.geometry())
            dict_thematic_formula[id_theme] = json.loads(feature.attribute(self.FORMULA_FIELD))
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
        datetime_start = datetime_start.toPyDateTime()

        # datetime_end = self.parameterAsDateTime(
        #    parameters,
        #    self.END_DATE,
        #    context
        # )
        datetime_end = now = QDateTime.currentDateTime().toPyDateTime()
        print(datetime_start)
        dict_affected = get_geoms_affected_by_grb_change(
            dict_thematic,
            grb_type=GRBType.ADP,
            date_start=datetime_start,
            date_end=datetime_end,
            one_by_one=False,
        )
        feedback.pushInfo("Number of possible affected OE-thematic during timespan: " + str(len(dict_affected)))
        for key in dict_affected.keys():
            print(key)
            print(dict_affected[key])
        feedback.pushInfo(str(datetime_start))
        feedback.pushInfo(str(self.FORMULA_FIELD))

        # Initiate a Aligner to reference thematic features to the actual borders
        actual_aligner = Aligner()
        loader = DictLoader(dict_affected)
        actual_aligner.load_thematic_data(loader)
        loader = GRBActualLoader(grb_type=GRBType.ADP, partition=0, aligner=actual_aligner)
        actual_aligner.load_reference_data(loader)

        dict_evaluated, prop_dictionary = evaluate(actual_aligner, dict_thematic_formula)
        fcs = get_series_geojson_dict(
            dict_evaluated,
            crs=actual_aligner.CRS,
            id_field=actual_aligner.name_thematic_id,
            series_prop_dict=prop_dictionary,
        )

        # fcs = actual_aligner.get_predictions_as_geojson(formula=self.FORMULA)

        # Add RESULT TO TOC
        self.geojson_to_layer(self.LAYER_RESULT, fcs["result"], self.get_renderer(QgsFillSymbol(
            [QgsSimpleLineSymbolLayer.create({'line_style': 'dash', 'color': QColor(0, 255, 0), 'line_width': '1'})])),
                              True)
        self.geojson_to_layer(self.LAYER_RESULT_DIFF, fcs["result_diff"], self.get_renderer(QgsFillSymbol(
            [QgsSimpleLineSymbolLayer.create(
                {'line_style': 'dash', 'color': QColor(255, 255, 0), 'line_width': '0.5'})])),
                              False)

        self.RESULT = QgsProject.instance().mapLayersByName(self.LAYER_RESULT)[0]

        QgsProject.instance().reloadAllLayers()

        feedback.pushInfo("Resulterende geometrie berekend")
        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}

        feedback.pushInfo("END PROCESSING")
        feedback.pushInfo("EINDE: RESULTAAT BEREKEND")
        return {
            self.OUTPUT_RESULT: self.RESULT
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
        # self.RELEVANT_DISTANCE = parameters["RELEVANT_DISTANCE"]
        # self.BUFFER_DISTANCE = self.RELEVANT_DISTANCE / 2
        # self.THRESHOLD_OVERLAP_PERCENTAGE = parameters["THRESHOLD_OVERLAP_PERCENTAGE"]
        # self.OD_STRATEGY = OpenbaarDomeinStrategy[self.ENUM_OD_STRATEGY_OPTIONS[parameters[self.ENUM_OD_STRATEGY]]]
        # self.SHOW_INTERMEDIATE_LAYERS = parameters["SHOW_INTERMEDIATE_LAYERS"]
        self.PROCESS_MULTI_AS_SINGLE_POLYGONS = parameters["PROCESS_MULTI_AS_SINGLE_POLYGONS"]
        self.FORMULA_FIELD = parameters["FORMULA_FIELD"]
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

