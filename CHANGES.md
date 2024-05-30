
# v0.9.5 

 - initial version based on pyQGIS
 - added exclusion of circles
 - more efficient merge/union-logical
 - removed resulting group layer (to prevent crashing of QGIS) - extra research needed
 - add logic for openbaar domein (od_strategy)
 - intermediate layers added as an advanced parameter
 - Native processes as child_algorithms
 - Process NonThreaded to fix QGIS from crashing
 - Added advanced parameter for processing input-multipolygons as single polygon
 - rewriting to use Aligner (shapely-python)
 - cleanup and added docs to Aligner
 - Resulting output made available for further QGIS-modelling
 - added enum - parameter to download actual GRB (adp-gbg-knw)
 - added enum - parameter for od-strategy
 - changes implemented for refactored brdr
