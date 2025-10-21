# Documentation of QGIS Python Script: Autocorrectborders

<img src="figures/autocorrectborders.png" width="50%" />

## Description

The processing algorithm, named **Autocorrectborders**, is developed to automatically adjust thematic boundaries to
reference boundaries. It searches for relevant overlap between thematic boundaries and reference boundaries, and creates
a resulting boundary based on the relevant overlapping areas.

## Input Parameters

The script requires the following input parameters:

| Parameter                                             | Description                                                                                                                                                                                                                                                                                                                                                                                                                                      | Default                                         | Optional |
|-------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------|----------|
| Thematic Layer                                        | A (MULTI)POLYGON layer with a projected CRS (unit: meter) and a unique ID.                                                                                                                                                                                                                                                                                                                                                                       | No default value, must be provided by the user. | No.      |
| Thematic ID                                           | Textual or numeric ID of the thematic layer used as a reference to the objects. This must be unique.                                                                                                                                                                                                                                                                                                                                             | No default value, must be provided by the user. | No.      |
| SELECT Reference Layer:                               | Selection of REFERENCE LAYER: The user can choose between a LOCAL REFERENCE LAYER (see parameters below), or on-the fly reference layers from GRB (Flanders, Belgium)                                                                                                                                                                                                                                                                            | LOCREF: use of a LOCAL REFERENCE LAYER          | Yes.     |
| Reference Layer (when LOCREF selected)                | A (MULTI)POLYGON layer with the same projected CRS (unit: meter).                                                                                                                                                                                                                                                                                                                                                                                | No default value, must be provided by the user. | Yes.     |
| Reference ID (when LOCREF selected)                   | Textual or numeric ID of the reference layer used as a reference to the objects.                                                                                                                                                                                                                                                                                                                                                                 | No default value, must be provided by the user. | Yes.     |
| Relevant Distance (meters)                            | Positive (decimal) number in meters. This indicates the maximum distance that the geometry is allowed to change.                                                                                                                                                                                                                                                                                                                                 | 3 (meters)                                      | No.      |
| OD_STRATEGY                                           | This parameter determines how the algorithm deals with parts of the geometry that is not covered by reference data. Different strategies are available: EXCLUDE, ASIS, SNAP_INNER_SIDE, SNAP_ALL_SIDE                                                                                                                                                                                                                                            | SNAP_ALL_SIDE (2)                               | No       |
| FULL_OVERLAP_PERCENTAGE % (0-100)                     | Backup-parameter when the algorithm cannot decide if a reference is relevant to be taken into account. It falls back to the covered percentage.                                                                                                                                                                                                                                                                                                  | 50%                                             | No       |
| REVIEW_PERCENTAGE % (0-100)                           | Resulting geometries that change more than REVIEW_PERCENTAGE are categorised as 'to_review'                                                                                                                                                                                                                                                                                                                                                      | 10 (%)                                          | No.      |
| WORKING FOLDER                                        | Folder to save the resulting geojson-files. By default empty, resulting in saving the geojson-files in a created folder.                                                                                                                                                                                                                                                                                                                         | Empty - a local folder is used                  | No       |
| SHOW_INTERMEDIATE_LAYERS                              | If True, 2 additional layers are generated as output that visually represent the significant intersections and significant differences                                                                                                                                                                                                                                                                                                           | False                                           | No.      |
| GET_BEST_PREDICTION_FOR_RELEVANT_DISTANCES (!slower!) | If True, the code will do a FULL SCAN of all relevant distances with an interval of 10cm to try to search for the best 'predictions'.These are results where the output geometry is a stable result that could be the possible wanted result.- The resulting layer will use the prediction with the highest prediction score. Warning : When this option is used, the processing will be much slower, as a multitude of calculations are needed. | False                                           | No       |
| SHOW_LOG_INFO                                         | If True, the logging of brdr is shown in the feedback-window.                                                                                                                                                                                                                                                                                                                                                                                    | False                                           | No       |

## Output Parameters

The script generates a GROUP layer with several output layers in the TOC:

* CORRECTION_X_Y: a copy of the thematic layer with updated geometries, divided into categories (brdrq_state)
* brdrQ_RESULT_X_Y: resulting geometries after alignment
* brdrQ_DIFF_X_Y: differences (+ and -) between original and resulting geometry
* brdrQ_DIFF_MIN_X_Y:differences (-) between original and resulting geometry
* brdrQ_DIFF_PLUS_X_Y:differences (+) between original and resulting geometry
* (optional) brdrQ_RLVNT_DIFF_X_Y: relevant differences (parts to exclude), used when processing the resulting geometry
* (optional) brdrQ_RLVNT_ISECT_X_Y: relevant intersection (parts to include), used when processing the resulting
  geometry

The name includes which 'RELEVANT_DISTANCE (X)' and 'REFERENCE (Y)' is used
<img src="docs/figures/output.png" width="100%" />

## Example of Usage

Here is an example of how to use the script in Python:

```python

params = {
    "INPUT_THEMATIC": themelayername,
    "COMBOBOX_ID_THEME": "theme_identifier",
    "RELEVANT_DISTANCE": 2,
    "ENUM_REFERENCE": 1,
    "INPUT_REFERENCE": None,
    "COMBOBOX_ID_REFERENCE": "",
    "WORK_FOLDER": "",
    "ENUM_OD_STRATEGY": 3,
    "THRESHOLD_OVERLAP_PERCENTAGE": 50,
    "ADD_FORMULA": True,
    "ADD_ATTRIBUTES": True,
    "SHOW_INTERMEDIATE_LAYERS": True,
    "PREDICTIONS": False,
    "SHOW_LOG_INFO": False,
}

processing.run('brdrqprovider:brdrqautocorrectborders', params)

```

## TIPS

- Set GET_BEST_PREDICTION_FOR_RELEVANT_DISTANCES = True for the best results. This will analyse the full range of
  RELEVANT_DISTANCES (FULL SCAN), and returns the best stable results. A side-effect is that the processing-time is much
  slower. By default this parameter is set to False to have quicker results (QUICK SCAN), missing the better results.

- Analyse your thematic dataset and try to gain insight into the 'deviation' (precision and accuracy from the reference
  layer):
    - Where does the thematic data come from?
    - when was it created,
    - on what reference limits was it drawn at the time,
    - Which drawing rules have been applied (e.g. accuracy of 0.5m)
    - …

This allows you to gain insight into the 'deviation' and which RELEVANT_DISTANCE value can best be applied.

- The RELEVANT_DISTANCE must be chosen according to the 'deviation' of the thematic data compared to the reference
  layer. If the thematic data contains different geometries that show large differences in 'deviation', it is best to
  split the thematic data and process it separately with an appropriate RELEVANT_DISTANCE so that the RELEVANT_DISTANCE
  can be kept as small as possible.
- The current version of the script assumes that both the thematic layer and reference layer are in the same projected
  CRS with units in meter.
- Thematic boundaries consisting of 1 or a few reference polygons are processed by the script in a few seconds. If the
  thematic boundaries cover a very large area (~1000 and reference polygons), it may take several minutes for the OUTPUT
  to be calculated. It's best to let QGIS finish this processing before proceeding
- In practice, we notice that large thematic demarcations are sometimes drawn more roughly (less precisely or
  inaccurately), so that a high RELEVANT DISTANCE is required to shift them to the reference file. For large areas that
  are drawn 'roughly', it is best to use a high RELEVANT_DISTANCE (e.g. >10 meters) and:
    - OD-strategy EXCLUDE: if you want to completely exclude all public domain
    - OD-strategy AS_IS: if you want to include all the covered public domain AS IS in the result
    - OD strategy SNAP_SINGLE_SIDE: if you want to keep the public domain within the demarcation, but move the edges to
      the inner side of the thematic polygon
    - OD strategy SNAP_ALL_SIDE: if you want to keep the public domain within the demarcation, but move the edges to
      the inner & outer side of the thematic polygon
