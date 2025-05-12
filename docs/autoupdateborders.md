
# AutoUpdateBorders

`AutoUpdateBorders`: a QGIS-processing algorithm

## Description

`AutoUpdateBorders` is a QGIS-processing plugin that aligns features (polygons) to reference borders: It searches for overlap relevance between thematic borders and reference borders,
and creates a resulting border based on the overlapping areas that are relevant.
The algorithm can make (one or more) 'predictions' so the user can compare and choose the right aligned geometry.
<img src="figures/input.png" width="100%" />
## Parameters

### Input Parameters

1. **Input Layer (INPUT)**
 - **Type**: Vector Layer
 - **Beschrijving**: De laag die als input zal worden gebruikt voor de verwerking.
 - **Voorbeeld**: `input_layer.shp`

2. **Buffer Distance (BUFFER_DISTANCE)**
 - **Type**: Number (Double)
 - **Beschrijving**: De afstand die gebruikt zal worden voor het bufferen van de inputlaag.
 - **Voorbeeld**: `10.0`
 - **Standaardwaarde**: `10.0`

3. **Output CRS (OUTPUT_CRS)**
 - **Type**: CRS (Coordinate Reference System)
 - **Beschrijving**: Het coördinatenreferentiesysteem dat gebruikt zal worden voor de outputlaag.
 - **Voorbeeld**: `EPSG:4326`

### Output Parameters

1. **Output Layer (OUTPUT)**
 - **Type**: Vector Layer
 - **Beschrijving**: De gegenereerde outputlaag na verwerking.
 - **Voorbeeld**: `output_layer.shp`

## Voorbeeld Gebruik

```python
# Voorbeeld van het aanroepen van de tool in een Python script

params = {
 'INPUT': 'path/to/input_layer.shp',
 'BUFFER_DISTANCE': 10.0,
 'OUTPUT_CRS': 'EPSG:4326',
 'OUTPUT': 'path/to/output_layer.shp'
}

processing.run('example:tool', params)


