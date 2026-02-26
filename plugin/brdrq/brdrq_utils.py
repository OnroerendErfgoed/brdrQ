import copy
import json
import os
from enum import Enum
from pathlib import Path

# TODO QGIS4
from PyQt5.QtGui import QColor
from brdr.be.grb.enums import GRBType
from brdr.constants import (
    SYMMETRICAL_AREA_CHANGE,
    SYMMETRICAL_AREA_PERCENTAGE_CHANGE,
    METADATA_FIELD_NAME,
    STABILITY,
    ID_THEME_FIELD_NAME,
    EVALUATION_FIELD_NAME,
)
from brdr.nl.enums import BRKType
from brdr.processor import (
    AlignerGeometryProcessor,
    DieussaertGeometryProcessor,
    NetworkGeometryProcessor,
    SnapGeometryProcessor,
    TopologyProcessor,
)
from brdr.utils import (
    write_featurecollection_to_geopackage,
)
from qgis.core import Qgis
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
)
from qgis.core import QgsCoordinateTransform, QgsCoordinateReferenceSystem
from qgis.core import (
    QgsLineSymbol,
    QgsMarkerSymbol,
)
from qgis.core import QgsProcessingException
from qgis.core import QgsProcessingFeatureSourceDefinition, QgsProperty
from qgis.core import QgsProviderRegistry, QgsDataSourceUri
from qgis.core import QgsRectangle
from qgis.core import QgsSettings
from qgis.core import QgsVectorFileWriter, QgsProject, QgsVectorLayer
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
    OpenDomainStrategy,
    SnapStrategy,
    PredictionStrategy,
    FullReferenceStrategy,
    ProcessorID,
    Evaluation,
)
from brdr.typings import ProcessResult

# TODO QGIS4
from PyQt5.QtCore import pyqtSignal, QVariant
from qgis.PyQt.QtCore import Qt
from qgis import processing
from qgis.core import QgsField, QgsFeatureRequest, QgsProcessing
from qgis.core import QgsProcessingParameterFolderDestination
from qgis.core import QgsGeometry
from qgis.core import (
    QgsSimpleLineSymbolLayer,
    QgsSymbol,
    QgsFillSymbol,
    QgsSingleSymbolRenderer,
    QgsMapLayer,
    QgsLayerTreeNode,
    QgsLayerTreeGroup,
)
from qgis.core import QgsStyle
from qgis.utils import iface
from shapely import to_wkt, from_wkt, make_valid

GPKG_FILENAME = "brdrq.gpkg"


class Processor(str, Enum):
    """
    Enum for processors that can be used in brdrQ. Values based on the IDs in brdr.
    """

    AlignerGeometryProcessor = "2024:aligner2024a"
    # DieussaertGeometryProcessor = "2024:dieussaert2024a"
    SnapGeometryProcessor = "2024:snap2024a"
    NetworkGeometryProcessor = "2024:network2024a"
    # TOPOLOGY = "2024:topology2024a"


class OsmType(dict, Enum):
    """
    Enum for defining the state of a (processed) feature
    """

    osm_buildings = {"building": True}
    osm_landuse = {"landuse": True}
    osm_streets = {"highway": True}


SPLITTER = ":"
PREFIX_LOCAL_LAYER = (
    "LOCREF"  # prefix for the TOC layername, when a local layer is used
)
LOCAL_REFERENCE_LAYER = (
    PREFIX_LOCAL_LAYER
    + SPLITTER
    + " define LOCAL REF LAYER and UNIQUE ID in the next 2 fields"
)

DICT_REFERENCE_OPTIONS = dict()
DICT_REFERENCE_OPTIONS[LOCAL_REFERENCE_LAYER] = PREFIX_LOCAL_LAYER

DICT_GRB_TYPES = dict()
for e in GRBType:
    try:
        DICT_GRB_TYPES[
            "BE - GRB - " + e.name + SPLITTER + " " + e.value.split(" - ")[2]
        ] = e.name

    except:
        DICT_GRB_TYPES["BE - GRB - " + e.name + SPLITTER + " " + e.value] = e.name
DICT_ADPF_VERSIONS = dict()
for x in [datetime.datetime.today().year - i for i in range(6)]:
    DICT_ADPF_VERSIONS[
        "BE - GRB - Administratieve fiscale percelen" + SPLITTER + " " + str(x)
    ] = x

DICT_OSM_TYPES = dict()
for x in OsmType:
    DICT_OSM_TYPES["OSM - " + x.name] = x.value

# DICT_BE_TYPES = dict()
# DICT_BE_TYPES["BE - Cadastral Parcels"]="BE_CADASTRAL"

DICT_NL_TYPES = dict()
for e in BRKType:
    DICT_NL_TYPES["NL - BRK - " + e.value] = e.name

DICT_REFERENCE_OPTIONS.update(DICT_GRB_TYPES)
DICT_REFERENCE_OPTIONS.update(DICT_ADPF_VERSIONS)
DICT_REFERENCE_OPTIONS.update(DICT_OSM_TYPES)
# DICT_REFERENCE_OPTIONS.update(DICT_BE_TYPES)
DICT_REFERENCE_OPTIONS.update(DICT_NL_TYPES)

GRB_TYPES = list(DICT_GRB_TYPES.keys())
ADPF_VERSIONS = list(DICT_ADPF_VERSIONS.keys())
OSM_TYPES = list(DICT_OSM_TYPES.keys())
# BE_TYPES = list(DICT_BE_TYPES.keys())
NL_TYPES = list(DICT_NL_TYPES.keys())
ENUM_REFERENCE_OPTIONS = list(DICT_REFERENCE_OPTIONS.keys())

# ENUM for choosing the OD-strategy
ENUM_OD_STRATEGY_OPTIONS = [e.name for e in OpenDomainStrategy][
    :4
]  # list with od-strategy-options #if e.value<=2

# ENUM for choosing the snap-strategy
ENUM_SNAP_STRATEGY_OPTIONS = [e.name for e in SnapStrategy]

# ENUM for choosing the full-strategy when evaluating
ENUM_FULL_REFERENCE_STRATEGY_OPTIONS = [e.name for e in FullReferenceStrategy]

# ENUM for choosing the full-strategy when evaluating
ENUM_PREDICTION_STRATEGY_OPTIONS = [e.name for e in PredictionStrategy]

# ENUM for choosing the Processing-algorithm
ENUM_PROCESSOR_OPTIONS = [
    e.name for e in Processor
]  # list with all processing-algorithm-options

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


def get_processor_by_id(processor_id, config):
    """
    Function that returns a Processor, based on the ID
    """
    # AlignerGeometryProcessor as default processor
    processor = AlignerGeometryProcessor(config=config)
    try:
        processor_id = ProcessorID(processor_id)
    except ValueError:
        return processor
    if processor_id == ProcessorID.DIEUSSAERT:
        return DieussaertGeometryProcessor(config=config)
    if processor_id == ProcessorID.NETWORK:
        return NetworkGeometryProcessor(config=config)
    if processor_id == ProcessorID.SNAP:
        return SnapGeometryProcessor(config=config)
    if processor_id == ProcessorID.TOPOLOGY:
        return TopologyProcessor(config=config)
    return processor


def read_setting(prefix, key, fallback, scope="auto"):
    """
    Reads a value based on the specified scope.

    :param prefix: The group or plugin prefix.
    :param key: The specific setting name.
    :param fallback: The default value if the setting is not found.
    :param scope:
        'auto'    -> Checks Project first, then Global (Default).
        'project' -> Checks ONLY the current QGIS Project.
        'global'  -> Checks ONLY the QgsSettings (User Profile).
    """

    # 1. Try to read from the Project file
    if scope in ["auto", "project"]:
        # readEntry returns a tuple: (value, boolean_success)
        value, exists = QgsProject.instance().readEntry(prefix, key)
        if exists and value is not None:
            return deserialize_setting(value, fallback)

    # 2. Try to read from Global Settings (QgsSettings)
    if scope in ["auto", "global"]:
        settings = QgsSettings()
        # If scope is 'auto' and we reached here, it means the project entry didn't exist.
        value = settings.value(f"{prefix}/{key}", fallback)

        # If the global setting returns the fallback, we still pass it through
        # deserialize_setting to ensure type consistency.
        return deserialize_setting(value, fallback)

    return fallback


def write_setting(prefix, key, value, scope="both"):
    """
    Writes a value to the QGIS Project, Global Settings, or both.

    :param prefix: The group or plugin prefix.
    :param key: The specific setting name.
    :param value: The value to be stored.
    :param scope:
        'both'    -> Writes to Project AND Global Settings (Default).
        'project' -> Writes ONLY to the current QGIS Project.
        'global'  -> Writes ONLY to QgsSettings (User Profile).
    """

    # 1. Prepare the value (serialize if it's not a primitive type)
    if not isinstance(value, (str, int, bool)):
        try:
            serializable_data = serialize_value(value)
            storage_value = json.dumps(serializable_data)
        except Exception as e:
            print(f"Error serializing key {key}: {e}")
            return
    else:
        storage_value = value

    # 2. Write to Project
    if scope in ["both", "project"]:
        try:
            QgsProject.instance().writeEntry(prefix, key, storage_value)
        except Exception as e:
            print(f"Error writing key {key} to Project: {e}")

    # 3. Write to Global Settings (QgsSettings)
    if scope in ["both", "global"]:
        try:
            settings = QgsSettings()
            settings.setValue(f"{prefix}/{key}", storage_value)
        except Exception as e:
            print(f"Error writing key {key} to Global Settings: {e}")

    return


def deserialize_setting(raw_value, default=None, enum_classes=None):
    """
    Converts a raw string (JSON) from QGIS back into objects.
    Returns 'default' if the raw_value is empty or None.
    """
    # 1. Fallback if the value doesn't exist in the project
    if raw_value is None or raw_value == "":
        return default

    # 2. If it's not our special JSON format, it's a standard type (str, int, bool)
    if not isinstance(raw_value, str):
        return raw_value
    try:
        data = json.loads(raw_value)
        return _reconstruct_object(data, enum_classes)
    except (json.JSONDecodeError, TypeError):
        return raw_value


def _reconstruct_object(data, enum_classes=None):
    """Internal recursive function to rebuild objects."""
    if not isinstance(data, dict) or "_type" not in data:
        return data

    obj_type = data.get("_type")

    if obj_type == "qgs_property":
        prop = QgsProperty()
        prop.loadVariant(data.get("value"))
        return prop

    if obj_type == "enum":
        val_name = data.get("value")
        if enum_classes:
            for cls in enum_classes.values():
                if val_name in cls.__members__:
                    return cls[val_name]
        return val_name

    if obj_type == "qgs_source_def":
        source_val = data.get("source")
        # Recursively rebuild if the source is also a complex object
        if isinstance(source_val, dict) and "_type" in source_val:
            source_val = _reconstruct_object(source_val, enum_classes)

        source_def = QgsProcessingFeatureSourceDefinition(
            source_val, data.get("selectedFeaturesOnly", False)
        )
        source_def.featureLimit = data.get("featureLimit", -1)
        source_def.flags = QgsProcessingFeatureSourceDefinition.Flags(
            data.get("flags", 0)
        )
        return source_def

    return data.get("value", data)


def serialize_value(value):
    """Hulpfunctie om complexe QGIS objecten om te zetten naar JSON-vriendelijke dicts."""
    if isinstance(value, float):
        return str(value)
    if isinstance(value, Enum):
        return {"_type": "enum", "value": value.name}

    if isinstance(value, QgsProperty):
        return {"_type": "qgs_property", "value": value.toVariant()}

    if isinstance(value, QgsProcessingFeatureSourceDefinition):
        # Check of de source zelf een QgsProperty is!
        source_val = value.source
        if isinstance(source_val, QgsProperty):
            source_val = serialize_value(source_val)  # Recursion

        return {
            "_type": "qgs_source_def",
            "source": source_val,
            "selectedFeaturesOnly": value.selectedFeaturesOnly,
            "featureLimit": value.featureLimit,
            "flags": int(value.flags),
        }

    return value


def get_string_type(val):
    try:
        int(val)
        return "integer"
    except ValueError:
        try:
            float(val)
            return "float"
        except ValueError:
            return "string"


# def make_path_safe(path):
#     """Vervangt het absolute pad door een placeholder als het binnen het project valt."""
#     p_dir = QgsProject.instance().homePath()
#     if path.startswith(p_dir):
#         return path.replace(p_dir, "@project")
#     return path
#
# def restore_path(safe_path):
#     """Herstelt het pad naar de huidige machine-specifieke locatie."""
#     if safe_path.startswith("@project"):
#         return safe_path.replace("@project", QgsProject.instance().homePath())
#     return safe_path


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


def zoom_to_features(features, iface, marge_factor=0.1, features_crs=None):
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
    if (
        not features_crs is None
        and not project_crs is None
        and features_crs != project_crs
    ):
        # Transformeer bbox naar project CRS
        transform = QgsCoordinateTransform(
            features_crs, project_crs, QgsProject.instance()
        )
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

    feature_types = get_geojson_type(geojson)
    if len(feature_types) > 1:
        raise TypeError("Geojson multiple types detected. Not supported")
    if len(feature_types) == 1:
        geometrytype = feature_types[0]
    else:
        geometrytype = "MultiPolygon"

    if geometrytype in ("Polygon", "MultiPolygon"):
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
    elif geometrytype in ("LineString", "MultiLineString"):
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
    elif geometrytype in ("Point", "MultiPoint"):
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
        raise TypeError("Unknown GeometryType")


def get_geojson_type(geojson):
    if geojson.get("type") == "FeatureCollection":
        feature_types = []
        for feature in geojson.get("features", []):
            if feature["geometry"] is not None:
                feature_types.append(feature["geometry"]["type"])
        return list(set(feature_types))
    return [geojson.get("type", "Unknown")]


def gpkg_layer_to_map(name, gpkg_path, layer_name, symbol, visible, group):
    """
    Laadt een specifieke laag uit een GeoPackage en voegt deze toe aan de TOC.
    """
    qinst = QgsProject.instance()

    # 1. Bestaande lagen met dezelfde naam verwijderen uit de TOC
    lyrs = qinst.mapLayersByName(name)
    root = qinst.layerTreeRoot()
    for lyr in lyrs:
        qinst.removeMapLayer(lyr.id())

    # 2. Definieer de URI voor de GeoPackage laag
    # De syntax is: pad_naar_gpkg|layername=naam_van_de_tabel
    uri = f"{gpkg_path}|layername={layer_name}"

    # 3. Maak de laag aan
    vl = QgsVectorLayer(uri, name, "ogr")

    if not vl.isValid():
        print(f"Fout: Laag {layer_name} kon niet worden geladen uit {gpkg_path}")
        return None

    # 4. Styling (overgenomen uit je originele code)
    if symbol is not None:
        # Let op: get_symbol moet nu werken op de 'vl' of metadata,
        # niet meer op de ruwe geojson dict.
        if isinstance(symbol, str):
            # Je zult je get_symbol functie wellicht iets moeten aanpassen
            pass

        if vl.renderer() is not None and isinstance(symbol, QgsSymbol):
            vl.renderer().setSymbol(symbol)

    # 5. Toevoegen aan de TOC op de juiste plek
    qinst.addMapLayer(vl, False)
    root.insertLayer(0, vl)

    # 6. Zichtbaarheid instellen
    node = root.findLayer(vl.id())
    if node:
        new_state = Qt.Checked if visible else Qt.Unchecked
        node.setItemVisibilityChecked(new_state)

    # 7. Verplaatsen naar groep en refreshen
    move_to_group(vl, group)
    vl.triggerRepaint()

    if iface is not None:
        iface.layerTreeView().refreshLayerSymbology(vl.id())

    return vl


def load_full_gpkg_with_styles(gpkg_path, group_name):
    layers = get_all_layer_names_in_gpkg(gpkg_path)

    for lyr_name in layers:
        # Laad de laag in QGIS
        vl = gpkg_layer_to_map(
            name=lyr_name,
            gpkg_path=gpkg_path,
            layer_name=lyr_name,
            symbol=None,  # We doen styling hieronder
            visible=True,
            group=group_name,
        )

        if vl and vl.isValid():
            # Probeer stijl uit DB te laden
            style_applied = apply_style_from_gpkg(vl)

            if not style_applied:
                # Optioneel: Fallback naar handmatige styling als er geen DB-stijl is
                print(
                    f"Geen stijl gevonden in GPKG voor {lyr_name}, gebruik standaard."
                )


def get_all_layer_names_in_gpkg(gpkg_path):
    """
    Geeft een lijst terug met alle tabelnamen (layers) in een GeoPackage.
    """
    metadata = QgsProviderRegistry.instance().providerMetadata("ogr")
    # Gebruik de URI van de container om de sublagen te vinden
    conn = metadata.decodeUri(gpkg_path)

    # We gebruiken de OGR provider om de lagen te scannen
    layer_list = []
    source = QgsDataSourceUri(gpkg_path)

    # Een slimme manier via de metadata van de provider:
    options = metadata.querySublayers(gpkg_path)
    for option in options:
        layer_list.append(option.name())

    return layer_list


def load_full_gpkg_to_qgis(gpkg_path, group_name, visible=True):
    """
    Scant een GeoPackage en voegt elke laag toe aan een specifieke groep in de TOC.
    """
    layers = get_all_layer_names_in_gpkg(gpkg_path)

    for lyr_name in layers:
        # We gebruiken de naam van de laag uit de GPKG ook als displaynaam in QGIS
        # Je kunt hier eventueel symboliek-logica toevoegen
        gpkg_layer_to_map(
            name=lyr_name,
            gpkg_path=gpkg_path,
            layer_name=lyr_name,
            symbol=None,
            visible=visible,
            group=group_name,
        )

    print(f"Klaar! {len(layers)} lagen geladen uit {gpkg_path}")


def apply_style_from_gpkg(layer):
    """
    Controleert of er een stijl is opgeslagen in de GeoPackage voor deze laag
    en past de standaardstijl toe.
    """
    # Haal de lijst met stijlen op uit de database (GeoPackage)
    # De methode geeft (aantal_stijlen, ids, namen, descriptions) terug
    count, ids, names, descriptions = layer.listStylesInDatabase()

    if count > 0:
        # We laden de eerste stijl (meestal de 'default')
        # Je kunt ook zoeken naar een specifieke naam in 'names'
        layer.loadNamedStyle(layer.styleURI())
        layer.triggerRepaint()
        return True
    return False


def featurecollection_to_layer(
    name, featurecollection, symbol, visible, group, tempfolder
):
    """
    Add a featurecollection to a QGIS-layer to add it to the TOC. If featurecollection has multiple types (point,line, polygon) these types are added seperately.
    """
    featurecollection = featurecollection_to_multi(featurecollection)
    feature_types = get_geojson_type(featurecollection)
    if len(feature_types) > 1:
        for x in feature_types:
            name_x = name + "_" + str(x)
            geojson_x = filter_geojson_by_geometry_type(featurecollection, x)
            featurecollection_to_layer(
                name_x, geojson_x, symbol, visible, group, tempfolder
            )
        return

    qinst = QgsProject.instance()
    lyrs = qinst.mapLayersByName(name)
    root = qinst.layerTreeRoot()

    if len(lyrs) != 0:
        for lyr in lyrs:
            root.removeLayer(lyr)
            qinst.removeMapLayer(lyr.id())
    if tempfolder is None or str(tempfolder) == "NULL" or str(tempfolder) == "":
        tempfolder = "tempfolder"
    gpkg_path = tempfolder + "/" + GPKG_FILENAME
    write_featurecollection_to_geopackage(gpkg_path, featurecollection, layer_name=name)

    uri = f"{gpkg_path}|layername={name}"

    # 3. Maak de laag aan
    vl = QgsVectorLayer(uri, name, "ogr")
    # styling
    if symbol is not None and isinstance(symbol, str):
        symbol = get_symbol(featurecollection, symbol)
    if (
        symbol is not None
        and vl.renderer() is not None
        and isinstance(symbol, QgsSymbol)
    ):
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


def filter_geojson_by_geometry_type(input_geojson, geometry_type):
    """
    Filter features in a GeoJSON file by geometry type and save to a new file.

    Parameters:
    - input_geojson: str, path to the input GeoJSON file
    - geometry_type: str, e.g. 'Point', 'LineString', 'Polygon'
    """

    # Filter features by geometry type
    filtered_features = [
        feature
        for feature in input_geojson.get("features", [])
        if feature.get("geometry", {}).get("type") == geometry_type
    ]
    output_geojson = copy.deepcopy(input_geojson)
    output_geojson["features"] = filtered_features
    # Create new GeoJSON structure
    return output_geojson


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


def featurecollection_to_multi(geojson):
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
    plt.show(block=False)


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
    plt.show(block=False)
    return


def get_valid_layer(layer_id_or_name):
    """
    Checks if the layer_id exists in the current project.
    Returns the layer object if valid, otherwise returns None.
    """
    if (
        layer_id_or_name is None
        or not layer_id_or_name
        or layer_id_or_name == -1
        or not isinstance(layer_id_or_name, str)
    ):
        return None
    project = QgsProject.instance()
    # Zoek de laag in het huidige project
    layer = project.mapLayer((layer_id_or_name))

    # Controleer of de laag echt is gevonden en 'valid' is (bijv. bronbestand niet verwijderd)
    if layer and layer.isValid():
        return layer

    return None


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


def save_layer_to_gpkg(layer, gpkg_path, layer_name=None):
    """
    Writes a layer to  (existing) GeoPackage.
    """
    # 1. Clean Path
    path_str = str(Path(gpkg_path))

    # 2. Options
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = layer_name if layer_name else layer.name()

    # --- EXPLICIT ENCODING ---
    options.fileEncoding = "UTF-8"

    # CRS from source-layer - default

    # Check if exists
    folder = os.path.dirname(path_str)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
    if Path(path_str).exists():
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    else:
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile

    # 3. Write
    return QgsVectorFileWriter.writeAsVectorFormatV3(
        layer, path_str, QgsProject.instance().transformContext(), options
    )


def generate_correction_layer(
    input,
    result,
    correction_layer_name,
    id_theme_brdrq_fieldname,
    workfolder,
    review_percentage=5,
    add_metadata=False,
):

    source_layer = input
    results_layer = result

    # Copy source layer to gpkg-layers

    remove_layer_by_name(correction_layer_name)

    path = os.path.join(workfolder, GPKG_FILENAME)

    res = save_layer_to_gpkg(source_layer, path, correction_layer_name)
    correction_layer = QgsVectorLayer(
        res[2] + "|layername=" + res[3], correction_layer_name, "ogr"
    )

    geom_type = correction_layer.geometryType()

    # Make a dictionary with ID to geometry from the resultslayer
    id_geom_map = {}
    id_diff_index_map = {}
    id_diff_perc_index_map = {}
    id_metadata_map = {}
    id_evaluation_map = {}
    ids_to_review = []
    ids_to_align = []
    ids_not_changed = []
    stability_field_available = False
    if is_field_in_layer(STABILITY, results_layer):
        stability_field_available = True
    for feat in results_layer.getFeatures():
        key = feat[ID_THEME_FIELD_NAME]
        geom = feat.geometry()
        if key in id_geom_map.keys():
            # when key not unique and multiple predictions, the last prediction is added to the list and the status is set to review
            ids_to_review.append(key)
        id_geom_map[key] = geom
        if add_metadata:
            id_metadata_map[key] = feat[METADATA_FIELD_NAME]
        id_diff_index_map[key] = feat[SYMMETRICAL_AREA_CHANGE]
        id_diff_perc_index_map[key] = feat[SYMMETRICAL_AREA_PERCENTAGE_CHANGE]
        try:
            evaluation = Evaluation(feat[EVALUATION_FIELD_NAME])
        except:
            evaluation = Evaluation.NOT_EVALUATED
        id_evaluation_map[key] = evaluation
        if evaluation == Evaluation.NO_CHANGE:
            ids_not_changed.append(key)
        elif evaluation in (
            Evaluation.EQUALITY_BY_ID,
            Evaluation.EQUALITY_BY_FULL_REFERENCE,
            Evaluation.EQUALITY_BY_ID_AND_FULL_REFERENCE,
        ):
            pass
        elif geom is None or geom.isEmpty():
            ids_to_align.append(key)
        elif (
            geom_type != Qgis.GeometryType.Polygon
            and stability_field_available
            and not feat[STABILITY]
        ):
            ids_to_align.append(key)
        elif (
            geom_type != Qgis.GeometryType.Polygon
            and stability_field_available
            and feat[STABILITY]
        ):
            ids_to_review.append(key)
        elif stability_field_available and not feat[STABILITY]:
            ids_to_align.append(key)
        elif feat[SYMMETRICAL_AREA_PERCENTAGE_CHANGE] > review_percentage:
            ids_to_review.append(key)
        elif feat[SYMMETRICAL_AREA_CHANGE] < 0.01:
            ids_not_changed.append(key)

    # 4. Update geometries in duplicated layer
    correction_layer.startEditing()
    fields_to_add = [
        QgsField(METADATA_FIELD_NAME, QVariant.String),
        QgsField(EVALUATION_FIELD_NAME, QVariant.String),
        QgsField(BRDRQ_STATE_FIELDNAME, QVariant.String),
        QgsField(BRDRQ_ORIGINAL_WKT_FIELDNAME, QVariant.String),
        QgsField(SYMMETRICAL_AREA_CHANGE, QVariant.Double),
        QgsField(SYMMETRICAL_AREA_PERCENTAGE_CHANGE, QVariant.Double),
    ]

    # Iterate fields
    for field in fields_to_add:
        # Check if exists
        if correction_layer.fields().indexFromName(field.name()) == -1:
            success = correction_layer.dataProvider().addAttributes([field])
            if success:
                print(f"Field '{field.name()}' succesfully added.")
            else:
                print(f"Error adding field '{field.name()}'.")
        else:
            print(f"Field '{field.name()}' already exists...")

    # Update Fields-cache
    correction_layer.updateFields()
    for feat in correction_layer.getFeatures():
        fid = feat[id_theme_brdrq_fieldname]
        if add_metadata:
            feat[METADATA_FIELD_NAME] = id_metadata_map[fid]
        feat[EVALUATION_FIELD_NAME] = id_evaluation_map[fid]
        feat[SYMMETRICAL_AREA_CHANGE] = id_diff_index_map[fid]
        feat[SYMMETRICAL_AREA_PERCENTAGE_CHANGE] = id_diff_perc_index_map[fid]
        feat[BRDRQ_ORIGINAL_WKT_FIELDNAME] = feat.geometry().asWkt()
        state = str(BrdrQState.NONE.value)
        if fid in id_geom_map and fid not in ids_to_align:
            feat.setGeometry(id_geom_map[fid])
            state = str(BrdrQState.AUTO_UPDATED.value)
        if fid in ids_not_changed:
            state = str(BrdrQState.NOT_CHANGED.value)
        if fid in ids_to_review:
            state = str(BrdrQState.TO_REVIEW.value)
        if fid in ids_to_align:
            feat[SYMMETRICAL_AREA_CHANGE] = -1
            feat[SYMMETRICAL_AREA_PERCENTAGE_CHANGE] = -1
            state = str(BrdrQState.TO_UPDATE.value)
        feat[BRDRQ_STATE_FIELDNAME] = state
        correction_layer.updateFeature(feat)
    correction_layer.commitChanges()

    style_outputlayer(correction_layer, BRDRQ_STATE_FIELDNAME)
    return correction_layer


def style_outputlayer(layer, field_name):
    # Determine the geometry type (Point=0, Line=1, Polygon=2)
    geom_type = layer.geometryType()

    # Configuration for each state
    state_config = {
        str(BrdrQState.NOT_CHANGED.value): {
            "color": "#b2df8a",
            "width": "0.6",
            "size": "2.0",
        },
        str(BrdrQState.AUTO_UPDATED.value): {
            "color": "green",
            "width": "0.8",
            "size": "3.0",
        },
        str(BrdrQState.MANUAL_UPDATED.value): {
            "color": "blue",
            "width": "0.8",
            "size": "3.0",
        },
        str(BrdrQState.TO_REVIEW.value): {
            "color": "orange",
            "width": "1.0",
            "size": "4.0",
        },
        str(BrdrQState.TO_UPDATE.value): {
            "color": "red",
            "width": "1.0",
            "size": "4.0",
        },
    }

    categories = []

    for value, settings in state_config.items():
        if geom_type == Qgis.GeometryType.Polygon:
            symbol = QgsFillSymbol.createSimple(
                {
                    "outline_color": settings["color"],
                    "outline_style": "solid",
                    "outline_width": settings["width"],
                    "color": "transparent",
                }
            )
        elif geom_type == Qgis.GeometryType.Line:
            symbol = QgsLineSymbol.createSimple(
                {
                    "line_color": settings["color"],
                    "line_style": "solid",
                    "line_width": settings["width"],
                }
            )
        elif geom_type == Qgis.GeometryType.Point:
            # Point settings: colored circle with a white outline for contrast
            symbol = QgsMarkerSymbol.createSimple(
                {
                    "name": "circle",
                    "color": settings["color"],
                    "outline_color": "white",
                    "size": settings["size"],
                    "outline_width": "0.4",
                }
            )
        else:
            continue

        categories.append(QgsRendererCategory(value, symbol, value))

    # Apply the Categorized Renderer
    renderer = QgsCategorizedSymbolRenderer(field_name, categories)
    layer.setRenderer(renderer)
    layer.triggerRepaint()


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
    elif ref in (OSM_TYPES + NL_TYPES):  # BE_TYPES +
        selected_reference = ref
        layer_reference_name = ref
        ref_suffix = str(ref)
    else:
        print("idref: " + str(id_reference_fieldname))
        selected_reference = 0
        if (
            layer_reference is None
            or id_reference_fieldname is None
            or str(id_reference_fieldname) == "NULL"
        ):
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


def setFilterOnLayer(layername, filter):
    layer = get_layer_by_name(layername)
    if not layer is None:
        layer.setSubsetString(filter)
    return


def remove_empty_features_from_diff_layers(layers_to_filter):
    supported_geom_types = [Qgis.GeometryType.Line, Qgis.GeometryType.Polygon]
    filter = (
        f"brdr_perimeter != 0"  # we use brdr_perimeter so it works for polygons & lines
    )
    for lyr in layers_to_filter:
        if not lyr:
            continue
        try:
            g_type = get_layer_by_name(lyr).geometryType()
        except:
            g_type = Qgis.GeometryType.Unknown

        if g_type in supported_geom_types:
            setFilterOnLayer(lyr, filter)


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
    if crs is None or str(crs) == "NULL":
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
