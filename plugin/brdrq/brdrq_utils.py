import os
from enum import Enum

from qgis.core import QgsProcessingException

try:
    import brdr
except:
    import brdr
try:
    import geojson
    from geojson import dump
except:
    import geojson
    from geojson import dump

import datetime
from math import ceil

import geopandas as gpd
import matplotlib.pyplot as plt
from brdr.enums import GRBType, OpenDomainStrategy, SnapStrategy, FullStrategy
from brdr.typings import ProcessResult
from brdr.utils import write_geojson
from PyQt5.QtCore import pyqtSignal
from qgis.PyQt.QtCore import Qt
from qgis import processing
from qgis.core import QgsField, QgsFeatureRequest, QgsProcessing
from qgis.core import QgsProcessingParameterFolderDestination
from qgis.core import QgsGeometry
from qgis.core import QgsProject
from qgis.core import (
    QgsSimpleLineSymbolLayer,
    QgsFillSymbol,
    QgsSingleSymbolRenderer,
    QgsMapLayer,
    QgsLayerTreeNode,
    QgsLayerTreeGroup,
)
from qgis.core import QgsStyle
from qgis.core import QgsVectorLayer
from qgis.utils import iface
from shapely import to_wkt, from_wkt, make_valid


# TODO remove enum class when available in brdr (v0.12.0)
class PredictionStrategy(str, Enum):
    """
    Enum for prediction strategy when using GRB updater

    ALL = "all"
    BEST = "best"
    ORIGINAL = "original"
    """

    ALL = "all"
    BEST = "best"
    ORIGINAL = "original"


SPLITTER = ":"
PREFIX_LOCAL_LAYER = (
    "LOCAL"  # prefix for the TOC layername, when a local layer is used
)
LOCAL_REFERENCE_LAYER = PREFIX_LOCAL_LAYER + SPLITTER + " choose LOCAL LAYER and UNIQUE ID below"
LOCAL = [LOCAL_REFERENCE_LAYER]
GRB_TYPES = [
    e.name + SPLITTER + " " + e.value for e in GRBType
]  # types of actual GRB: parcels, buildings, artwork
ADPF_VERSIONS = [
    "Adpf" + str(x) + SPLITTER + " Administratieve fiscale percelen " + str(x)
    for x in [datetime.datetime.today().year - i for i in range(6)]
]  # Fiscal parcels of past 5 years

ENUM_REFERENCE_OPTIONS = (
    LOCAL + GRB_TYPES + ADPF_VERSIONS
)  # Options for downloadable reference layers

# ENUM for choosing the OD-strategy
ENUM_OD_STRATEGY_OPTIONS = [
    e.name for e in OpenDomainStrategy  # if e.value <= 2
]  # list with od-strategy-options #if e.value<=2

# ENUM for choosing the snap-strategy
ENUM_SNAP_STRATEGY_OPTIONS = [e.name for e in SnapStrategy]

# ENUM for choosing the full-strategy when evaluating
ENUM_FULL_STRATEGY_OPTIONS = [e.name for e in FullStrategy]

# ENUM for choosing the full-strategy when evaluating
ENUM_PREDICTION_STRATEGY_OPTIONS = [e.name for e in PredictionStrategy]


def geom_shapely_to_qgis(geom_shapely):
    """
    Method to convert a Shapely-geometry to a QGIS geometry
    """
    wkt = to_wkt(make_valid(geom_shapely), rounding_precision=-1, output_dimension=2)
    geom_qgis = QgsGeometry.fromWkt(wkt)
    return geom_qgis


def remove_group_layer(group_layer_name):
    tree = QgsProject.instance().layerTreeRoot()
    node_object = tree.findGroup(group_layer_name)
    tree.removeChildNode(node_object)


def geom_qgis_to_shapely(geom_qgis):
    """
    Method to convert a QGIS-geometry to a Shapely-geometry
    """
    if geom_qgis.isNull() or geom_qgis.isEmpty():
        return None
    wkt = geom_qgis.asWkt()
    geom_shapely = from_wkt(wkt)
    return make_valid(geom_shapely)


def add_field_to_layer(layer, fieldname, fieldtype, default_value):
    layer.startEditing()
    if layer.dataProvider().fieldNameIndex(fieldname) == -1:
        layer.dataProvider().addAttributes([QgsField(fieldname, fieldtype)])
        layer.updateFields()
    id_new_col = layer.dataProvider().fieldNameIndex(fieldname)
    for feature in layer.getFeatures():
        layer.changeAttributeValue(feature.id(), id_new_col, default_value)
    layer.commitChanges()


def get_layer_by_name(layer_name):
    """
    Get the layer-object based on the layername
    """
    layers = QgsProject.instance().mapLayersByName(layer_name)
    if len(layers) > 0:
        return layers[0]
    else:
        print(f"Layer not found for layername {str(layer_name)}")
        return None


def zoom_to_feature(feature, iface):
    """
    zoom to feature
    """
    box = feature.geometry().boundingBox()
    iface.mapCanvas().setExtent(box)
    iface.mapCanvas().refresh()
    return


def move_to_group(thing, group, pos=0, expanded=False):
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


def get_renderer(fill_symbol):
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


def get_symbol(geojson, resulttype):
    geojson = geojson_to_multi(geojson)
    feature_types = get_geojson_type(geojson)
    if len(feature_types) > 1:
        raise TypeError("Geojson multiple types detected. Not supported")
    if len(feature_types) == 1:
        geometrytype = feature_types[0]
    else:
        geometrytype = "MultiPolygon"

    if geometrytype == "MultiPolygon":
        if resulttype == "result_diff":
            return QgsStyle.defaultStyle().symbol("hashed black X")
        elif resulttype == "result_diff_plus":
            return QgsStyle.defaultStyle().symbol("hashed cgreen /")
        elif resulttype == "result_diff_min":
            return QgsStyle.defaultStyle().symbol("hashed cred /")
        elif resulttype == "result":
            return QgsStyle.defaultStyle().symbol("outline green")
        elif resulttype == "reference":
            return QgsStyle.defaultStyle().symbol("outline black")
        else:
            return QgsStyle.defaultStyle().symbol("outline blue")
    elif geometrytype == "MultiLineString":
        if resulttype == "result_diff":
            return QgsStyle.defaultStyle().symbol("topo railway")
        elif resulttype == "result_diff_plus":
            return QgsStyle.defaultStyle().symbol("dash green")
        elif resulttype == "result_diff_min":
            return QgsStyle.defaultStyle().symbol("dash red")
        elif resulttype == "result":
            return QgsStyle.defaultStyle().symbol("simple green line")
        elif resulttype == "reference":
            return QgsStyle.defaultStyle().symbol("simple black line")
        else:
            return QgsStyle.defaultStyle().symbol("simple blue line")
    elif geometrytype == "MultiPoint":
        if resulttype == "result_diff":
            return QgsStyle.defaultStyle().symbol("dot white")
        elif resulttype == "result_diff_plus":
            return QgsStyle.defaultStyle().symbol("dot white")
        elif resulttype == "result_diff_min":
            return QgsStyle.defaultStyle().symbol("dot white")
        elif resulttype == "result":
            return QgsStyle.defaultStyle().symbol("dot green")
        elif resulttype == "reference":
            return QgsStyle.defaultStyle().symbol("dot black")
        else:
            return QgsStyle.defaultStyle().symbol("dot blue")
    else:
        raise TypeError("Unknown Type")


def get_geojson_type(geojson):
    if geojson.get("type") == "FeatureCollection":
        feature_types = []
        for feature in geojson.get("features", []):
            if feature["geometry"] is not None:
                feature_types.append(feature["geometry"]["type"])
        return list(set(feature_types))
    return [geojson.get("type", "Unknown")]


def geojson_to_layer(name, geojson, symbol, visible, group, tempfolder):
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
    if tempfolder is None or str(tempfolder) == "NULL" or str(tempfolder) == "":
        tempfolder = "tempfolder"
    tempfilename = tempfolder + "/" + name + ".geojson"
    write_geojson(tempfilename, geojson_to_multi(geojson))

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

    move_to_group(vl, group)
    vl.triggerRepaint()
    if iface is not None:
        iface.layerTreeView().refreshLayerSymbology(vl.id())
    return vl


def get_workfolder(folderpath="", name="", temporary=False):
    """
    Creates a workfolder-path
    *temporary:
        *If temporary =True, a temporary folder will be generated that will be removed when Qgis is closed
        *If temporary = False. The folderpath and name is used to build the foldername
    """
    if name is None or name == "":
        name = ""
    if temporary:
        # CREATE a temporary folder
        foldername = QgsProcessingParameterFolderDestination(name=name)
        foldername = foldername.generateTemporaryDestination()
        return foldername
    if folderpath is None or str(folderpath) == "NULL" or str(folderpath) == "":
        folderpath = ""
    now = datetime.datetime.now()
    date_string = now.strftime("%Y%m%d%H%M%S")
    foldername = os.path.join(folderpath, name, date_string)
    try:
        test_path_file = os.path.join(foldername, "test.txt")
        parent = os.path.dirname(test_path_file)
        os.makedirs(parent, exist_ok=True)
        with open(test_path_file, "w") as f:
            dump({}, f, default=str)
        os.remove(test_path_file)
    except:
        print("folder not writable; creating temporary folder")
        return get_workfolder(folderpath="", name=name, temporary=True)
    return foldername


def geojson_to_multi(geojson):
    """
    Transforms a geojson: Checks if there are single-geometry-features and transforms them into Multi-geometries, so all objects are of type 'Multi' (or null-geometry).
    It is important that geometry-type is consistent in QGIS to show and style the geojson-layer
    """

    if geojson is None or "features" not in geojson or geojson["features"] is None:
        return geojson
    for f in geojson["features"]:
        if f["geometry"] is None:
            continue
        if f["geometry"]["type"] == "Polygon":
            f["geometry"] = {
                "type": "MultiPolygon",
                "coordinates": [f["geometry"]["coordinates"]],
            }
        elif f["geometry"]["type"] == "LineString":
            f["geometry"] = {
                "type": "MultiLineString",
                "coordinates": [f["geometry"]["coordinates"]],
            }
        elif f["geometry"]["type"] == "Point":
            f["geometry"] = {
                "type": "MultiPoint",
                "coordinates": [f["geometry"]["coordinates"]],
            }
    return geojson


def _make_map(ax, processresult, thematic_dict, reference_dict):
    """
    Fills an ax with a map:
     * reference_dict
     * theme_dict
     * resulting geometry
     * plus_differences
     * min_differences
    , so it can be used in matplotlib
    """
    try:
        dicts = _processresult_to_dicts(processresult)
        results = dicts[0]
        results_diff_pos = dicts[2]
        results_diff_neg = dicts[3]
        if ax is None:
            ax = plt.subplot(1, 1, 1)
        # ax_result =
        gpd.GeoSeries(list(results.values())).plot(
            ax=ax,
            alpha=0.5,
            color="none",
            hatch=" ",
            edgecolor="green",
            linewidth=7.0,
            label="result",
            zorder=2,
        )
        ax_thematic_dict = gpd.GeoSeries(list(thematic_dict.values())).plot(
            ax=ax,
            alpha=0.8,
            color="none",
            hatch="/",
            edgecolor="#0000FF",
            linewidth=3.0,
            linestyle="dashdot",
            label="theme",
            zorder=3,
        )
        # ax_diff_pos = (
        gpd.GeoSeries(list(results_diff_pos.values())).plot(
            ax=ax,
            color="none",
            edgecolor="green",
            hatch="+",
            linewidth=0.0,
            linestyle="dashdot",
            label="diff_plus",
            zorder=4,
        )
        # ax_diff_neg =
        gpd.GeoSeries(list(results_diff_neg.values())).plot(
            ax=ax,
            color="none",
            edgecolor="red",
            hatch="+",
            linewidth=0.0,
            linestyle="dashdot",
            label="diff_min",
            zorder=5,
        )
        # save the extent of original, resulting and difference - geometries
        axis_extent = list(ax_thematic_dict.viewLim.intervalx) + list(
            ax_thematic_dict.viewLim.intervaly
        )
        # ax_reference_dict =
        gpd.GeoSeries(list(reference_dict.values())).plot(
            ax=ax,
            color="#FFF8C9",
            edgecolor="black",
            linewidth=2.0,
            label="reference",
            zorder=1,
        )
        # zoom map to saved extent
        ax.axis(axis_extent)
    except Exception:  # noqa
        print("make_map: Error while making map")
    return ax


def show_map(
    dict_results: dict[any, dict[float, ProcessResult]],
    dict_thematic,
    dict_reference,
):
    """
    Show results on a map
    """
    dict_results_by_distance = {}
    for theme_id, dist_result in dict_results.items():
        for rel_dist, processresults in dist_result.items():
            dict_results_by_distance[rel_dist] = {}
            dict_results_by_distance[rel_dist][theme_id] = processresults

    len_series = len(dict_results_by_distance.keys())
    i = 0
    # Plot data in subplots
    len_series_half = ceil(len_series / 2)  # calculate half of the length of the series
    for dist in dict_results_by_distance:
        ax = plt.subplot(len_series_half, 2, i + 1)
        ax = _make_map(
            ax,  # noqa
            dict_results_by_distance[dist],
            dict_thematic,
            dict_reference,
        )
        ax.set_title("Relevant distance (m):" + str(dist))
        i = i + 1
    # Adjust layout
    # plt.tight_layout()
    # Show figure
    plt.show()


def print_brdr_formula(dict_results, aligner):
    for theme_id, dist_results in dict_results.items():
        for rel_dist, processresults in dist_results.items():
            print(
                "--------Formula for ID  "
                + str(theme_id)
                + " with relevant distance "
                + str(rel_dist)
                + "--------------"
            )
            print(aligner.get_brdr_formula(processresults["result"]))
    return


def plot_series(
    series,
    dictionary,
    xlabel="relevant distance",
    ylabel="difference",
    title="Relevant distance vs difference",
):
    for key in dictionary:
        if len(dictionary[key]) == len(series):
            lst_diffs = list(dictionary[key].values())
            plt.plot(series, lst_diffs, label=str(key))
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    # plt.legend()
    plt.show()
    return


def _processresult_to_dicts(processresult):
    """
    Transforms a dictionary with all ProcessResults to individual dictionaries of the
    results
    Args:
        processresult:

    Returns:

    """
    results = {}
    results_diff = {}
    results_diff_plus = {}
    results_diff_min = {}
    results_relevant_intersection = {}
    results_relevant_diff = {}
    for key in processresult:
        processresult = processresult[key]
        results[key] = processresult["result"]
        results_diff[key] = processresult["result_diff"]
        results_diff_plus[key] = processresult["result_diff_plus"]
        results_diff_min[key] = processresult["result_diff_min"]
        results_relevant_intersection[key] = processresult[
            "result_relevant_intersection"
        ]
        results_relevant_diff[key] = processresult["result_relevant_diff"]

    return (
        results,
        results_diff,
        results_diff_plus,
        results_diff_min,
        results_relevant_intersection,
        results_relevant_diff,
    )

def get_reference_params(ref, layer_reference, id_reference_fieldname,thematic_crs):

    ref_id = ref.split(SPLITTER)[0]
    print (ref)
    print (ref_id)
    if ref in GRB_TYPES:
        selected_reference = GRBType[ref_id]
        layer_reference_name = GRBType[ref_id].name
        ref_suffix = str(ref_id)
        print(selected_reference)
    elif ref in ADPF_VERSIONS:
        selected_reference = ref_id
        layer_reference_name = ref_id
        ref_suffix = str(ref_id)
    else:
        selected_reference = 0
        if layer_reference is None or id_reference_fieldname == "NULL":
            raise QgsProcessingException(
                "Please choose a REFERENCELAYER from the table of contents, and the associated unique REFERENCE ID"
            )
        layer_reference_name = layer_reference.name()
        ref_suffix = PREFIX_LOCAL_LAYER + "_" + layer_reference_name
        if layer_reference.sourceCrs().authid() != thematic_crs:
            raise QgsProcessingException(
                "Thematic layer and ReferenceLayer are in a different CRS. "
                "Please provide them in the same CRS, with units in meter (f.e. For Belgium in EPSG:31370 or EPSG:3812)"
            )
    return selected_reference,layer_reference_name, ref_suffix


def thematic_preparation(input_thematic_layer, relevant_distance, context, feedback):
    input_thematic_name = "thematic_preparation"
    outputs = {}
    # THEMATIC PREPARATION
    context.setInvalidGeometryCheck(QgsFeatureRequest.GeometryNoCheck)

    outputs[input_thematic_name + "_fixed"] = processing.run(
        "native:fixgeometries",
        {
            "INPUT": input_thematic_layer,
            "METHOD": 1,
            "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
        },
        context=context,
        feedback=feedback,
        is_child_algorithm=True,
    )
    thematic = context.getMapLayer(outputs[input_thematic_name + "_fixed"]["OUTPUT"])
    crs = (
        thematic.sourceCrs().authid()
    )  # set CRS for the calculations, based on the THEMATIC input layer

    outputs[input_thematic_name + "_dropMZ"] = processing.run(
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
    thematic = context.getMapLayer(outputs[input_thematic_name + "_dropMZ"]["OUTPUT"])
    # buffer the thematic layer to select all plots around it that are relevant to
    # the calculations
    outputs[input_thematic_name + "_buffered"] = processing.run(
        "native:buffer",
        {
            "INPUT": thematic,
            "DISTANCE": 1.01 * relevant_distance,
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
        outputs[input_thematic_name + "_buffered"]["OUTPUT"]
    )
    return thematic, thematic_buffered, crs


# https://www.pythonguis.com/tutorials/plotting-matplotlib/
import matplotlib

matplotlib.use("Qt5Agg")

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure


class MplCanvas(FigureCanvasQTAgg):

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)


from qgis.gui import QgsMapToolIdentifyFeature, QgsMapToolIdentify


class SelectTool(QgsMapToolIdentifyFeature):
    featuresIdentified = pyqtSignal(object)

    def __init__(self, iface, layer):
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.layer = layer
        QgsMapToolIdentifyFeature.__init__(self, self.canvas, self.layer)

    def canvasPressEvent(self, event):
        identified_features = self.identify(
            event.x(), event.y(), [self.layer], QgsMapToolIdentify.TopDownAll
        )
        identified_features = [f.mFeature for f in identified_features]
        self.featuresIdentified.emit(identified_features)

    def deactivate(self):
        print("deactivate")
