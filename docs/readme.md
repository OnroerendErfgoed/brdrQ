# Welcome to the brdrQ-Documentation page

## Introduction

**brdrQ** is a QGIS plugin designed to align geometries with reference data. It helps users correct spatial discrepancies adjusting geometries to match reference sources using [`brdr`](https://github.com/OnroerendErfgoed/brdr).

## Installation

1. Open QGIS.
2. Go to `Plugins` → `Manage and Install Plugins`.
3. Search for `brdrQ`.
4. Click `Install Plugin`.
5. Once installed, the plugin will appear in the plugin toolbar.

This plugin provides tools to align geometries to reference data.

here you can find links to the different tools that are currently provided:

* [Autocorrectborders](autocorrectborders.md) - Bulk alignment to reference layer
* [Feature aligner](featurealigner.md) - Feature-by-feature alignment with predictions
* [Autoupdateborders](autoupdateborders.md) - Bulk alignment to latest GRB (Flanders - Belgium) based on predictions and provenance


## Possible workflow
1. Use [Autocorrectborders](autocorrectborders.md) to align your thematic data to a reference layer. A CORRECTION_ layer is returned that indicates the brdrq_state of the alignment.
2. Use [Feature aligner](featurealigner.md) on the CORRECTION_ layer to review/update features that are not automatically updated, according the 'brdrq_state' (to_review, to_update).