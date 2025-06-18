# v0.11.1

- Added auto-reload mechanism of brdr when upgrading plugin

# v0.11.0

- Upgrade to brdr version 0.11.0
- Added parameter ODStrategy and threshold to the GRB-Updater [#152]
- bugfix: when using a selection (subset) of a layer the brdrQ-processing tools crashed [#158]
- bugfix: featurealigner - settings: local reference layer not saved [#155]
- Added support for lines and points as thematic and reference geometry (experimental - slow)
- Adding extra snapping parameters to the featurealigner - settings dialog for line-point alignment (experimental) [#105]

# v0.10.2

- documentation fix
- fix for ID when using local reference layer

# v0.10.1

- version fix

# v0.10.0

- Upgrade to brdr version 0.10.0
- UI adapted
- Added parameter to autoupdateboders: Prediction-strategy
- Updated docs
- Added test structure

# v0.9.14

- Upgrade to brdr version 0.9.0
- Removed unused parameters for partial snapping
- Fixed bug when brdr_formula cannot be resolved

# v0.9.13

- Upgrade to brdr version 0.8.1
- issue when closing plugin (bug) [#120]
- function _thematic_preparation() to brdrQ_utils (refactoring) [#114]
- unblock processing screen when open (enhancement) [#118]
- GRB Updater: added choice of GRB-type and working without brdr_formula (enhancement) [#117]
- GRB Updater, fixed a non-existing function (bug) [#115]


# v0.9.12

- selection handling enhancement in plugin [#86]
- selectTool for selecting feature(s) on map in the plugin [#111]
- Added buttons in toolbar for version and autoupdateborders to the toolbar/menu [#107]
- clearing list of features and predictions when choosing a new layer in combobox [#108]
- warning on spinbox-change fixed (bug)  [#109]

# v0.9.11

- Optimize and block the calculation of big features when using the feature-by-feature tool, to prevent crashing [#99]
- Show waiting-icon and progressbar when waiting/calculating when using the feature-by-feature tool [#89]
- Add settings-parameter to add brdr_formula to the results of the feature-by-feature tool [#88]
- Add a control-check that a manually chosen working-foldr is writeble, (and use temp-folder if so) [#84]
- Saving the settings of the feature-by-feature tool when closing and opening tool [#94]
- Adding extra snapping parameters to the settings (disabled because of slowness on bigger features) [#105]
- Adding a evaluation-status and prediction-score to the predicted features in the feature-by-feature tool [#90]

# v0.9.10

- Upgrade to brdr version 0.6.0
- fix for handling IDs[#97]
- fix on visualisation[#85]

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

