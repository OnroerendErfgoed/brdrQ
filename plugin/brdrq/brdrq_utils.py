import os
from enum import Enum

from PyQt5.QtGui import QColor
from qgis.core import QgsCoordinateTransform, QgsCoordinateReferenceSystem
from qgis.core import QgsProcessingException
from qgis.core import QgsRectangle
from qgis.core import QgsWkbTypes
from qgis.gui import QgsMapTool
from qgis.gui import QgsRubberBand

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
from brdr.enums import (
    GRBType,
    OpenDomainStrategy,
    SnapStrategy,
    FullStrategy,
    PredictionStrategy,
)
from brdr.typings import ProcessResult
from brdr.utils import write_geojson
from PyQt5.QtCore import pyqtSignal
from qgis.PyQt.QtCore import Qt
from qgis import processing
from qgis.core import QgsField, QgsFeatureRequest, QgsProcessing
from qgis.core import QgsProcessingParameterFolderDestination
from qgis.core import QgsGeometry
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


SPLITTER = ":"
PREFIX_LOCAL_LAYER = (
    "LOCREF"  # prefix for the TOC layername, when a local layer is used
)
LOCAL_REFERENCE_LAYER = (
    PREFIX_LOCAL_LAYER + SPLITTER + " choose LOCAL LAYER and UNIQUE ID below"
)

DICT_REFERENCE_OPTIONS = dict()
DICT_REFERENCE_OPTIONS[LOCAL_REFERENCE_LAYER] = PREFIX_LOCAL_LAYER

DICT_GRB_TYPES = dict()
for e in GRBType:
    try:
        DICT_GRB_TYPES[e.name + SPLITTER + " GRB " + e.value.split(" - ")[2]] = e.name

    except:
        DICT_GRB_TYPES[e.name + SPLITTER + " " + e.value] = e.name
DICT_ADPF_VERSIONS = dict()
for x in [datetime.datetime.today().year - i for i in range(6)]:
    DICT_ADPF_VERSIONS["Administratieve fiscale percelen" + SPLITTER + " " + str(x)] = x

DICT_REFERENCE_OPTIONS.update(DICT_GRB_TYPES)
DICT_REFERENCE_OPTIONS.update(DICT_ADPF_VERSIONS)

GRB_TYPES = list(DICT_GRB_TYPES.keys())
ADPF_VERSIONS = list(DICT_ADPF_VERSIONS.keys())
ENUM_REFERENCE_OPTIONS = list(DICT_REFERENCE_OPTIONS.keys())

# ENUM for choosing the OD-strategy
ENUM_OD_STRATEGY_OPTIONS = [e.name for e in OpenDomainStrategy][
    :4
]  # list with od-strategy-options #if e.value<=2

# ENUM for choosing the snap-strategy
ENUM_SNAP_STRATEGY_OPTIONS = [e.name for e in SnapStrategy]

# ENUM for choosing the full-strategy when evaluating
ENUM_FULL_STRATEGY_OPTIONS = [e.name for e in FullStrategy]

# ENUM for choosing the full-strategy when evaluating
ENUM_PREDICTION_STRATEGY_OPTIONS = [e.name for e in PredictionStrategy]

BRDRQ_ORIGINAL_WKT_FIELDNAME = "brdrq_original_wkt"
BRDRQ_STATE_FIELDNAME = "brdrq_state"


class BrdrQState(str, Enum):
    """
    Enum for defining the state of a (processed) feature
    """

    NOT_CHANGED = "not_changed"
    AUTO_UPDATED = "auto_updated"
    MANUAL_UPDATED = "manual_updated"
    TO_REVIEW = "to_review"
    TO_UPDATE = "to_update"
    NONE = "none"


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


def zoom_to_features(features, iface, marge_factor=0.1,features_crs=None):
    """
    Function to zoom to an array of features.
    Combines the bbox of the features and adds a margin around the feature
    """
    # Calculate the combined bounding box
    if features is None or len(features) == 0:
        return
    bbox = QgsRectangle()
    bbox.setMinimal()  # Start met een lege bbox
    for feat in features:
        bbox.combineExtentWith(feat.geometry().boundingBox())

    # Add a margin to the bbox
    width = bbox.width()
    height = bbox.height()

    bbox.setXMinimum(bbox.xMinimum() - width * marge_factor)
    bbox.setXMaximum(bbox.xMaximum() + width * marge_factor)
    bbox.setYMinimum(bbox.yMinimum() - height * marge_factor)
    bbox.setYMaximum(bbox.yMaximum() + height * marge_factor)
    if not features_crs is None:
        features_crs = QgsCoordinateReferenceSystem(features_crs)
    project_crs = QgsProject.instance().crs()
    if not features_crs is None and not project_crs is None and features_crs!=project_crs:
        # Transformeer bbox naar project CRS
        transform = QgsCoordinateTransform(features_crs, project_crs, QgsProject.instance())
        bbox_transformed = transform.transformBoundingBox(bbox)
    else:
        bbox_transformed = bbox

    # Zoom to (transformed) bbox
    iface.mapCanvas().setExtent(bbox_transformed)
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


def set_layer_visibility(layer: QgsMapLayer, visible: bool):
    """
    Sets the visibility of a layer in the legend.

    Parameters:
        layer (QgsMapLayer): The layer whose visibility you want to change.
        visible (bool): True to make the layer visible, False to hide it.
    """
    if not layer:
        print("No valid layer provided.")
        return

    layer_tree = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
    if layer_tree:
        layer_tree.setItemVisibilityChecked(visible)
    else:
        print("Layer not found in the layer tree.")


from qgis.core import QgsProject


def remove_layer_by_name(layer_name):
    """
    Removes a layer from the current QGIS project by its name.

    Parameters:
    layer_name (str): The name of the layer to remove.
    """
    project = QgsProject.instance()
    layers = project.mapLayers().values()

    for layer in layers:
        if layer.name() == layer_name:
            project.removeMapLayer(layer.id())
            return

    print(f"Layer '{layer_name}' not found.")


def is_field_in_layer(fieldname, layer):
    return fieldname in [field.name() for field in layer.fields()]


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
    xlabel="relevant distance (m)",
    ylabel="difference (m²)",
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


def get_original_geometry(feature, fieldname):
    """
    Tries to read the original wkt string form a feature (if exists). Else the feature-geometry is returned
    """
    original_geometry = None
    try:
        if fieldname in feature.fields().names():
            original_geometry = QgsGeometry.fromWkt(feature[fieldname])
    except:
        original_geometry = None
    return original_geometry


def get_reference_params(ref, layer_reference, id_reference_fieldname, thematic_crs):

    ref_id = DICT_REFERENCE_OPTIONS[ref]
    if ref in GRB_TYPES:
        selected_reference = GRBType[ref_id]
        layer_reference_name = GRBType[ref_id].name
        ref_suffix = str(ref_id)
        print(selected_reference)
    elif ref in ADPF_VERSIONS:
        selected_reference = ref
        layer_reference_name = ref
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
    return selected_reference, layer_reference_name, ref_suffix


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
    if crs is None or crs =='NULL':
        raise QgsProcessingException(
            "Thematic layer does not have a defined CRS attached to it. "
            "Please define a CRS to the Thematic layer, with units in meter (f.e. For Belgium in EPSG:31370 or EPSG:3812)"
        )
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


class PolygonSelectTool(QgsMapTool):
    def __init__(self, canvas, layer, on_polygon_finished):
        super().__init__(canvas)
        self.canvas = canvas
        self.layer = layer
        self.on_polygon_finished = on_polygon_finished  # callback functie
        self.points = []
        self.rubber_band = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self.rubber_band.setColor(QColor(255, 0, 0, 100))
        self.rubber_band.setWidth(2)

    def canvasPressEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        self.points.append(point)
        self.rubber_band.addPoint(point, True)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return and len(self.points) >= 3:
            polygon_geom = QgsGeometry.fromPolygonXY([self.points])
            self.on_polygon_finished(
                polygon_geom, self.layer, self.canvas
            )  # callback aanroepen
            self.reset()

    def canvasDoubleClickEvent(self, event):
        if len(self.points) >= 3:
            polygon_geom = QgsGeometry.fromPolygonXY([self.points])
            self.on_polygon_finished(
                polygon_geom, self.layer, self.canvas
            )  # callback aanroepen
        self.reset()

    def reset(self):
        self.points = []
        self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)
