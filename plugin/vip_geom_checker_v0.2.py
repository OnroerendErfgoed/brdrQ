# -*- coding: utf-8 -*-

"""
***************************************************************************
*   name: VIP - geomchecker
*   version: 0.2
*   author: Karel Dieussaert
*   Docs, history & and Code- repo:

MIT LICENSE:
Copyright (c) 2025 Athumi VIP

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
import json
import requests
from osgeo import gdal
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import QgsGeometry, QgsFeature
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingException
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterFile, QgsVectorLayer, QgsProject
from qgis.core import QgsRectangle, QgsCoordinateReferenceSystem, QgsCoordinateTransform
from qgis.utils import iface
from shapely.geometry.polygon import Polygon
from shapely.io import to_wkt, from_wkt, from_geojson
from shapely.ops import unary_union
from shapely.validation import make_valid


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
    wkt = wkt.upper()
    wkt = wkt.replace("POLYGONZ", "POLYGON Z")
    wkt = wkt.replace("LINESTRINGZ", "LINESTRING Z")
    wkt = wkt.replace("POINTZ", "POINT Z")
    geom_shapely = from_wkt(wkt)
    return make_valid(geom_shapely)

def is_within_bounds(geometry, crs_epsg):
    """
    checks if a geometry is within EPSG_31370 bounds
    """
    wkt = geometry.asWkt()
    transformed_geometry = QgsGeometry().fromWkt(wkt)
    # Definieer de grenzen van EPSG:31370 (Lambert72)
    lambert72_bounds = QgsRectangle(14637.25, 20909.21, 297133.13, 246424.28)

    # Verkrijg het CRS van de layer
    crs_layer = QgsCoordinateReferenceSystem(crs_epsg)

    # Definieer het CRS van EPSG:31370 (Lambert72)
    crs_lambert72 = QgsCoordinateReferenceSystem('EPSG:31370')

    # Transformeer de geometrie naar EPSG:31370
    transform = QgsCoordinateTransform(crs_layer, crs_lambert72, QgsProject.instance())
    transformed_geometry_result = transformed_geometry.transform(transform)

    # Controleer of de getransformeerde geometrie binnen de Lambert72 grenzen ligt
    if lambert72_bounds.contains(transformed_geometry.boundingBox()):
        return True, transformed_geometry
    else:
        return False, transformed_geometry

def intersections_gemeentegrenzen(input_geom_shapely):
    """
    Functie om te controleren met welke gemeenten een geometrie intersecteert
    """
    url = "https://geo.api.vlaanderen.be/VRBG/ogc/features/v1/collections/Refgem/items?f=application%2Fgeo%2Bjson&crs=EPSG:31370"
    # Ophalen van de gemeentegrenzen
    response = requests.get(url)
    data = response.json()
    intersections = []

    for feature in data['features']:
        geom_gemeente = from_geojson(json.dumps(feature['geometry']))
        properties_gemeente = feature['properties']
        if input_geom_shapely.intersects(geom_gemeente):
            intersection = input_geom_shapely.intersection(geom_gemeente)
            if intersection.geom_type in ["Polygon","MultiPolygon"]:
                intersections.append(str(properties_gemeente['NAAM']))
    return intersections

def check_repair_geometrytype(qgsgeometry,feedback):
    """
    Logic to check the geometrytype and try to convert to a single polygon (or raise an error)
    """
    geometry_shapely = geom_qgis_to_shapely(qgsgeometry)
    if geometry_shapely.geom_type == "Polygon":
        feedback.pushInfo("Geometry is een polygon. Geen conversie nodig.")
        return qgsgeometry
    elif geometry_shapely.geom_type == "MultiPolygon":
        feedback.pushWarning("Geometry is een multipolygon. Probeer om te zetten naar polygon.")
        # Probeer de multipolygon om te zetten naar een enkel polygon
        geometry_shapely = unary_union(geometry_shapely)
        if geometry_shapely.geom_type == "Polygon":
            feedback.pushInfo("Conversie naar single polygon geslaagd.")
            return geom_shapely_to_qgis(geometry_shapely)
        else:
            raise QgsProcessingException("Conversie naar polygon mislukt.")


    elif geometry_shapely.geom_type in ["LineString", "MultiLineString"]:
        feedback.pushWarning("Geometry is een linestring of multilinestring. Probeer om te zetten naar polygon.")
        merged_linestring = geometry_shapely
        if merged_linestring.geom_type == "MultiLineString":
            merged_linestring = unary_union(merged_linestring)
        if merged_linestring.geom_type == "LineString":
            try:
                polygon = Polygon(merged_linestring)
                return geom_shapely_to_qgis(polygon)
            except:
                feedback.pushWarning("Conversie linestring naar polygon mislukt.")
                raise QgsProcessingException("Conversie linestring naar  polygon mislukt.")

        else:
            feedback.pushWarning("MultiLineString: Conversie naar polygon mislukt.")
            raise QgsProcessingException("MultiLineString: conversie naar polygon mislukt.")

    elif geometry_shapely.geom_type == "GeometryCollection":
        feedback.pushWarning("Geometry is een GeometryCollection. Probeer om te zetten naar polygon.")
        geometry_shapely = unary_union(geometry_shapely)
        if geometry_shapely.geom_type == "GeometryCollection":
            feedback.pushWarning(f"GeometryCollection: Conversie naar single polygon mislukt.")
            raise QgsProcessingException("GeometryCollection: Conversie naar single polygon mislukt.")
        return check_repair_geometrytype(geom_shapely_to_qgis(geometry_shapely),feedback)
    else:
        geom_type = geometry_shapely.geom_type
        feedback.pushWarning(f"Geometry type niet aanvaard: {str(geom_type)}")
        raise QgsProcessingException(f"Geometry type niet aanvaard: {str(geom_type)}")

class VipGeomCheckAlgorithm(QgsProcessingAlgorithm):
    """
    Script to check the input geometry for VastgoedInformatiePortaal
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    INPUTFILE = "INPUTFILE"
    OUTPUT= "OUTPUT"
    # URL van de Geo Feature API
    URL_GEMEENTEGRENZEN = "https://geo.api.vlaanderen.be/VRBG/ogc/features/v1/collections/Refgem/items"


    def flags(self):
        return super().flags() | QgsProcessingAlgorithm.FlagNoThreading

    @staticmethod
    def tr(string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        return VipGeomCheckAlgorithm()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return "geomchecker"

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr("geomchecker")

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This stringgeom
        should be localised.
        """
        return self.tr("vip")

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return "vip"

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it.
        """
        return self.tr(
            "Script to check the input geometry for VastgoedInformatiePortaal (requirement: QGIS v 3.36 or higher)"
        )

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # We add the input vector features source. It can have any kind of
        # geometry.
        parameter = QgsProcessingParameterFile(
            self.INPUTFILE,
            self.tr("INPUT FILE"),
            behavior=QgsProcessingParameterFile.File,
            optional=False,
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)


    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """

        gdal.SetConfigOption('SHAPE_RESTORE_SHX', 'YES')
        feedback_steps = 6
        feedback = QgsProcessingMultiStepFeedback(feedback_steps, feedback)
        feedback.pushInfo("START")

        input_file_path = parameters [self.INPUTFILE]

        import os
        filename = os.path.basename(input_file_path).split(".")[0]

        layer = QgsVectorLayer(input_file_path, filename, "ogr")
        if layer.isValid():
            crs = layer.crs()
            crs_code = crs.authid()
            feedback.pushInfo( "CRS laag:" + str(crs_code))
            featurecount = layer.featureCount()
            if featurecount <1:
                raise QgsProcessingException("Geen features gevonden in de file. Script afgesloten")
                return {}
            elif featurecount ==1:
                pass

            else:
                feedback.pushWarning("Aantal features in de file groter dan 1. Enkel de eerste feature wordt verwerkt")
                feedback.pushWarning("Laag met meerder features wordt toegevoegd aan laag")
                QgsProject.instance().addMapLayer(layer)
            first_feature = next(layer.getFeatures())
            # Krijg de geometrie van de eerste feature
            geometry = first_feature.geometry()

        else:
            feedback.pushWarning("File niet ingelezen als shp of geojson. Probeer als WKT")
            try:
                crs=None
                crs_code=None
                # Bestand met WKT-string lezen
                with open(input_file_path, 'r') as file:
                    wkt_string = file.read().strip()

                # Geometrie type bepalen
                geometry = QgsGeometry.fromWkt(wkt_string)
            except:
                raise QgsProcessingException("File niet geo-readable. Script afgesloten")
                return {}


        # CRS controle
        lambert72 = "EPSG:31370"
        lambert08 = "EPSG:3812"
        wgs84="EPSG:4326"
        if crs is None or not crs.isValid():
            feedback.pushWarning("Onbekend CRS. We gaan CRS bepalen op basis van de geometry boundaries")
        if is_within_bounds(geometry,lambert72)[0]:
            #crs_code= lambert72
            feedback.pushInfo("CRS gedetecteerd: " + lambert72)
        elif is_within_bounds(geometry,wgs84)[0]:
            #crs_code = wgs84
            feedback.pushWarning("CRS gedetecteerd: " + wgs84 + " - geometrieconversie naar " + lambert72)
            geometry = is_within_bounds(geometry,wgs84)[1]
        elif is_within_bounds(geometry,lambert08)[0]:
            #crs_code= lambert08
            feedback.pushWarning("CRS gedetecteerd: " + lambert08 + " - geometrieconversie naar " + lambert72)
            geometry = is_within_bounds(geometry, lambert08)[1]
        else:
            raise QgsProcessingException("CRS-error: " + crs.authid() + "geometrie kon niet getransformeerd worden. geometrie buiten Lambert72-range")
            return {}


        # Controleer het geometrytype
        geometry = check_repair_geometrytype(geometry,feedback)

        # Aanmaak van polygonlaag met geometrie:
        layer = QgsVectorLayer('Polygon?crs=EPSG:31370', "output_" + str(filename) , 'memory')
        # Maak een nieuwe feature en stel de geometrie in
        feature = QgsFeature()
        feature.setGeometry(geometry)
        # Voeg de feature toe aan de layer
        layer.dataProvider().addFeature(feature)
        layer.updateExtents()
        # Voeg de layer toe aan de TOC
        QgsProject.instance().addMapLayer(layer)
        #zoom to geometry
        iface.mapCanvas().setExtent(geometry.boundingBox())
        iface.mapCanvas().refresh()


        #controle intersectie met grenzen
        intersections = intersections_gemeentegrenzen(geom_qgis_to_shapely(geometry))
        intersection_count= len(intersections)
        if intersection_count == 1:
            feedback.pushInfo(f"De geometrie intersecteert met 1 gemeentegrens:{str(intersections)}")
        elif intersection_count == 0:
            feedback.pushWarning(f"De geometrie intersecteert niet met gemeentegrenzen:{str(intersections)}")
            raise QgsProcessingException("error gemeentegrenzen")
        else:
            feedback.pushWarning(f"De geometrie intersecteert met {intersection_count} gemeentegrenzen.:{str(intersections)}")
            raise QgsProcessingException("error gemeentegrenzen")

        feedback.pushInfo ("EINDE : SUCCES")
        return {}




