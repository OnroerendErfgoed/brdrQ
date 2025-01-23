import os

from PyQt5.QtCore import pyqtSignal
from qgis.core import QgsProcessingParameterFolderDestination

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
from brdr.enums import GRBType, OpenbaarDomeinStrategy, SnapStrategy
from brdr.geometry_utils import geojson_polygon_to_multipolygon
from brdr.typings import ProcessResult
from brdr.utils import write_geojson
from qgis.PyQt.QtCore import Qt
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

LOCAL_REFERENCE_LAYER = "LOCAL REFERENCE LAYER (choose LAYER and ID below)"

GRB_TYPES = [
    e.name for e in GRBType
]  # types of actual GRB: parcels, buildings, artwork
ADPF_VERSIONS = [
    "Adpf" + str(x) for x in [datetime.datetime.today().year - i for i in range(6)]
]  # Fiscal parcels of past 5 years

ENUM_REFERENCE_OPTIONS = (
    [LOCAL_REFERENCE_LAYER] + GRB_TYPES + ADPF_VERSIONS
)  # Options for downloadable reference layers

# ENUM for choosing the OD-strategy
ENUM_OD_STRATEGY_OPTIONS = [
    e.name for e in OpenbaarDomeinStrategy
]  # list with od-strategy-options #if e.value<=2

# ENUM for choosing the snap-strategy
ENUM_SNAP_STRATEGY_OPTIONS = [e.name for e in SnapStrategy]


def geom_shapely_to_qgis(geom_shapely):
    """
    Method to convert a Shapely-geometry to a QGIS geometry
    """
    wkt = to_wkt(make_valid(geom_shapely), rounding_precision=-1, output_dimension=2)
    geom_qgis = QgsGeometry.fromWkt(wkt)
    return geom_qgis


def geom_qgis_to_shapely(geom_qgis):
    """
    Method to convert a QGIS-geometry to a Shapely-geometry
    """
    if geom_qgis.isNull() or geom_qgis.isEmpty():
        return None
    wkt = geom_qgis.asWkt()
    geom_shapely = from_wkt(wkt)
    return make_valid(geom_shapely)


def get_layer_by_name(layer_name):
    """
    Get the layer-object based on the layername
    """
    layers = QgsProject.instance().mapLayersByName(layer_name)
    if len (layers)>0:
        return layers[0]
    else:
        print (f"Layer not found for layername {str(layer_name)}")
        return None


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
    write_geojson(tempfilename, geojson_polygon_to_multipolygon(geojson))

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
    plt.legend()
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
    def __init__(self, iface,layer):
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.layer = layer
        QgsMapToolIdentifyFeature.__init__(self, self.canvas, self.layer)

    def canvasPressEvent(self, event):
        identified_features = self.identify(event.x(), event.y(), [self.layer], QgsMapToolIdentify.TopDownAll)
        identified_features = [f.mFeature for f in identified_features]
        self.featuresIdentified.emit(identified_features)

    def deactivate(self):
        print("deactivate")
