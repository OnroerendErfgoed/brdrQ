# v0.9.9

- Upgrade to brdr version 0.5.0
- Conversion from scripts to plugin (new installation method)
- Added experimental tool to align individual features based on predictions
- Bugfixes on ID-handling in Autocorrectborders

# v0.9.8

- Upgrade to brdr version 0.4.0
- Cleanup of variables in the scripts  [#21]
- Refinement of the progressbar, ending when process is fully complete [#54]
- Added/revised error-messages for CRS & when choosing unsupported combinations of checkboxes [#55]
- Added possibility of adding the original attributes to the result (ADD_ATTRIBUTES - default True)
- Refactored saving of result-layer: memory-geojson-layer changed by saved geojson layer (WORKFOLDER introduced as
  optional input variable for saving the resulting geojsons)

# v0.9.7

- Upgrade to brdr version 0.3.0
- Move function "update_to_actual_version" to brdr-code (generic)  [#26]
- Adding 'fixed geometries' before executing tool on thematic and referencelayer [#41]
- logging error in the QGIS-python console (print) bug fixed_with new_brdr_version [#28]
- Make predicted results for multiple relevant distences unique [#42]
- Add logic that all geojson- (multi-)polygons are explicit multipolygons

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

# older change-logs (pre-v0.9.5)

- initial version based on pyQGIS
- added exclusion of circles
- more efficient merge/union-logical
- removed resulting group layer (to prevent crashing of QGIS) - extra research needed
- add logic for openbaar domein (od_strategy)
- intermediate layers added as an advanced parameter
- Native processes as child_algorithms
- Process NonThreaded to fix QGIS from crashing
- Added advanced parameter for processing input-multipolygons as single polygons
- rewriting to use Aligner (shapely-python)
- cleanup and added docs to Aligner
- resulting output made available for further QGIS-modelling
- added enum - parameter to download actual GRB (adp-gbg-knw)
- added enum - parameter for od-strategy
- refactoring of functions to brdr-functions
- possibility to use predictor-function in brdr

