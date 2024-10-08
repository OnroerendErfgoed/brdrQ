# -*- coding: utf-8 -*-

"""
***************************************************************************
*   name: brdrQ - AutoUpdateBorders
*   version: v0.9.8
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
import datetime
import os
import site
import subprocess
import sys

from geojson import dump
from qgis import processing
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtCore import Qt, QDate, QDateTime
from qgis.core import QgsFeatureRequest
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingException
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingOutputVectorLayer
from qgis.core import QgsProcessingParameterFeatureSource, QgsProcessingParameterField, \
    QgsProcessingParameterNumber
from qgis.core import QgsProcessingParameterFile
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
        unary_union, make_valid
    )
except (ModuleNotFoundError):
    print("Module shapely not found. Installing from PyPi.")
    subprocess.check_call([python_exe,
                           '-m', 'pip', 'install', 'shapely'])
    from shapely import (
        Polygon,
        from_wkt,
        to_wkt,
        unary_union, make_valid
    )

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
from brdr.geometry_utils import geojson_polygon_to_multipolygon
from brdr.enums import AlignerInputType
from brdr.constants import BASE_FORMULA_FIELD_NAME
from brdr.grb import update_to_actual_grb


class AutoUpdateBordersProcessingAlgorithm(QgsProcessingAlgorithm):
    """
    Script to auto-update geometries that are aligned to an old GRB-referencelayer the actual GRB-referencelayer.
    Documentation can be found at: https://github.com/OnroerendErfgoed/brdrQ/
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    INPUT_THEMATIC = "INPUT_THEMATIC"  # reference to the combobox for choosing the thematic input layer
    ID_THEME_FIELDNAME = ""  # parameters that holds the fieldname of the unique theme id

    # ALIGNER parameters
    CRS = "EPSG:31370"  # default CRS for the aligner,updated by CRS of thematic inputlayer
    OD_STRATEGY = 0  # default OD_STRATEGY for the aligner,updated by user-choice
    THRESHOLD_OVERLAP_PERCENTAGE = 50  # default THRESHOLD_OVERLAP_PERCENTAGE for the aligner,updated by user-choice
    RELEVANT_DISTANCE = 1  # default RELEVANT_DISTANCE for the aligner,updated by user-choice
    CORR_DISTANCE = 0.01  # default CORR_DISTANCE for the aligner
    MULTI_AS_SINGLE_MODUS = True  # default MULTI_AS_SINGLE_MODUS for the aligner

    FORMULA_FIELDNAME = BASE_FORMULA_FIELD_NAME
    LAYER_RESULT = "brdrQ_RESULT"  # parameter that holds the TOC layername of the result
    LAYER_RESULT_DIFF = "brdrQ_RESULT_DIFF"  # parameter that holds the TOC layername of the resulting diff

    GROUP_LAYER = "BRDRQ_UPDATES"

    # OTHER parameters
    MAX_DISTANCE_FOR_ACTUALISATION = 3  # maximum relevant distance that is used in the predictor when trying to update to actual GRB
    TEMPFOLDER = ""

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

    def write_geojson(self, path_to_file, geojson):
        """
        Write a GeoJSON object to a file.

        Args:
            path_to_file (str): Path to the output file.
            geojson (FeatureCollection): The GeoJSON object to write.
        """
        parent = os.path.dirname(path_to_file)
        os.makedirs(parent, exist_ok=True)
        with open(path_to_file, "w") as f:
            dump(geojson, f, default=str)

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

        tempfilename = self.TEMPFOLDER + "/" + name + ".geojson"
        self.write_geojson(tempfilename, geojson_polygon_to_multipolygon(geojson))

        vl = QgsVectorLayer(tempfilename, name, "ogr")
        # styling
        if symbol is not None and vl.renderer() is not None:
            vl.renderer().setSymbol(symbol)
        # vl.setOpacity(0.5)

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

        parameter = QgsProcessingParameterField(
            "FORMULA_FIELD",
            "Formula field",  # (if empty, formula will be calculated based on following alignment-date)
            "brdr_formula",
            self.INPUT_THEMATIC,
            # optional=True
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        parameter = QgsProcessingParameterNumber(
            "RELEVANT_DISTANCE_FOR_FORMULA",
            "RELEVANT_DISTANCE_FOR_FORMULA (meter) - If no formula-field is stated, a formula-field will be calculated with this relevant distance",
            type=QgsProcessingParameterNumber.Double,
            optional=True
        )
        parameter.setFlags(parameter.flags())

        parameter = QgsProcessingParameterNumber(
            "MAX_RELEVANT_DISTANCE",
            "MAX-RELEVANT_DISTANCE (meter) - Max distance to try to align on the actual GRB",
            type=QgsProcessingParameterNumber.Double,
            defaultValue=3,
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        parameter = QgsProcessingParameterFile(
            "WORK_FOLDER",
            self.tr("Working folder"),
            behavior=QgsProcessingParameterFile.Folder,
            optional=True, )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        self.addOutput(
            QgsProcessingOutputVectorLayer(
                "OUTPUT_RESULT",
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
        dict_thematic_properties = {}
        features = thematic.getFeatures()

        BRDR_ID_FIELDNAME = "brdr_id"  # TODO fix
        for current, feature in enumerate(features):
            if feedback.isCanceled():
                return {}

            # id_theme = feature.attribute(self.ID_THEME_FIELDNAME)
            # dict_thematic[id_theme] = self.geom_qgis_to_shapely(feature.geometry())
            # dict_thematic_properties[id_theme] = feature.__geo_interface__["properties"]
            # TODO: remove str when bugfix in brdr is released
            id_theme = str(feature.attribute(self.ID_THEME_FIELDNAME))
            dict_thematic[id_theme] = self.geom_qgis_to_shapely(feature.geometry())
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

            dict_thematic_properties[id_theme][BRDR_ID_FIELDNAME] = id_theme
            # END fix

        self.ID_THEME_FIELDNAME = BRDR_ID_FIELDNAME  # todo fix -remove after new brdr

        aligner = Aligner()
        aligner.load_thematic_data(DictLoader(data_dict=dict_thematic, data_dict_properties=dict_thematic_properties))
        fc = aligner.get_input_as_geojson(inputtype=AlignerInputType.THEMATIC)

        feedback.pushInfo("START ACTUALISATION")

        fcs_actualisation = update_to_actual_grb(fc, id_theme_fieldname=self.ID_THEME_FIELDNAME,
                                                 base_formula_field=self.FORMULA_FIELDNAME,
                                                 max_distance_for_actualisation=self.MAX_DISTANCE_FOR_ACTUALISATION,
                                                 feedback=None)
        if fcs_actualisation is None or fcs_actualisation == {}:
            feedback.pushInfo("Geen wijzigingen gedetecteerd binnen tijdspanne in referentielaag (GRB-percelen)")
            feedback.pushInfo("Proces wordt afgesloten")
            return {}

        # Add RESULT TO TOC
        self.geojson_to_layer(self.LAYER_RESULT, fcs_actualisation["result"],
                              QgsStyle.defaultStyle().symbol("outline blue"),
                              True, self.GROUP_LAYER)
        self.geojson_to_layer(self.LAYER_RESULT_DIFF, fcs_actualisation["result_diff"],
                              QgsStyle.defaultStyle().symbol("hashed black cblue /"),
                              False, self.GROUP_LAYER)
        feedback.pushInfo("Resulterende geometrie berekend")
        feedback.pushInfo("END ACTUALISATION")
        result = QgsProject.instance().mapLayersByName(self.LAYER_RESULT)[0]
        QgsProject.instance().reloadAllLayers()
        feedback.pushInfo("Resulterende geometrie berekend")
        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}

        feedback.pushInfo("END PROCESSING")
        feedback.pushInfo("EINDE: RESULTAAT BEREKEND")
        return {
            "OUTPUT_RESULT": result
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
        self.CRS = (
            thematic.sourceCrs().authid()
        )  # set CRS for the calculations, based on the THEMATIC input layer

        # outputs[self.INPUT_THEMATIC + "_enriched"] = processing.run(
        #     "qgis:exportaddgeometrycolumns",
        #     {"INPUT": thematic, "CALC_METHOD": 0, "OUTPUT": "TEMPORARY_OUTPUT"},
        #     context=context,
        #     feedback=feedback,
        #     is_child_algorithm=True,
        # )
        # thematic = context.getMapLayer(
        #     outputs[self.INPUT_THEMATIC + "_enriched"]["OUTPUT"]
        # )
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

    def prepare_parameters(self, parameters):
        self.TEMPFOLDER = parameters["WORK_FOLDER"]
        now = datetime.datetime.now()
        date_string = now.strftime("%Y%m%d%H%M%S")
        if self.TEMPFOLDER is None or str(self.TEMPFOLDER) == 'NULL' or str(self.TEMPFOLDER) == "":
            self.TEMPFOLDER = "brdrQ"
            # dest =QgsProcessingParameterFolderDestination (name="brdrQ")
            # self.TEMPFOLDER =dest.generateTemporaryDestination()
        self.TEMPFOLDER = os.path.join(self.TEMPFOLDER, date_string)

        self.FORMULA_FIELDNAME = parameters["FORMULA_FIELD"]
        self.ID_THEME_FIELDNAME = parameters["COMBOBOX_ID_THEME"]
