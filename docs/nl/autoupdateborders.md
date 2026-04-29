---
title: "GRB Updater (BULK)"
lang: nl
---

# Documentatie van QGIS Python-plugin brdrQ - AutoUpdateBorders - GRB Updater (Vlaanderen-specifieke dataset)

<img src="../figures/autoupdateborders.png" width="50%" />

## Beschrijving

`AutoUpdateBorders` is een QGIS-processing script om geometrieen die uitgelijnd zijn op een oude GRB-referentielaag (Vlaanderen) automatisch te updaten naar een nieuwere GRB-referentielaag. Het gebruikt voorspellingen om de resulterende uitgelijnde geometrie te bepalen. Wanneer meerdere voorspellingen gevonden worden, kan je kiezen tussen ALLE voorspellingen, de BESTE voorspelling, of de ORIGINELE geometrie (voor verdere analyse).

## Parametergids

### Thematic Layer
- **Definitie**: Invoerlaag met bestaande uitgelijnde geometrieen die geactualiseerd moeten worden.
- **Waarom gebruiken**: Bepaalt welke objecten naar een recentere referentiesituatie gemigreerd worden.
- **Mogelijke keuzes**: Vectorlaag in geprojecteerde CRS met stabiele geometrie.
- **Gevolg**: Invoerkwaliteit bepaalt rechtstreeks de betrouwbaarheid van de update.

### Thematic ID
- **Definitie**: Unique feature key.
- **Waarom gebruiken**: Houdt herkomst en opvolging stabiel over meerdere updatecycli.
- **Mogelijke keuzes**: Uniek tekst- of numeriek veld.
- **Gevolg**: Niet-unieke IDs verlagen traceerbaarheid en reviewkwaliteit.

### Reference Layer
- **Definitie**: Keuze van het GRB-referentietype voor de update.
- **Waarom gebruiken**: Zorgt dat je thematische objecten tegen de juiste referentieklasse worden geactualiseerd.
- **Mogelijke keuzes**: `ADP`, `GBG`, `KNW`.
- **Gevolg**: Een fout referentietype leidt tot inhoudelijk foutieve updates.

### Relevant Distance (meters)
- **Definitie**: Maximale verschuiving bij het zoeken naar updatekandidaten.
- **Waarom gebruiken**: Begrenst hoe agressief geometrie mag worden aangepast.
- **Mogelijke keuzes**: Meestal `3-5`; hoger voor ruwe legacydata.
- **Gevolg**: Hogere waarde geeft meer kandidaten, maar ook meer ambiguiteit.

### Prediction Strategy
- **Definitie**: Uitvoerbeleid wanneer meerdere kandidaatvoorspellingen bestaan.
- **Waarom gebruiken**: Balans tussen deterministische output en analysemogelijkheden.
- **Mogelijke keuzes**: BEST, ALL, ORIGINAL.
- **Gevolg**: `BEST` is productiegericht; `ALL` vergroot analyse/review; `ORIGINAL` is veilige fallback.

### Full Reference Strategy
- **Definitie**: Voorkeurssterkte voor kandidaten met volledige referentie-overlap.
- **Waarom gebruiken**: Verhoogt topologische zekerheid.
- **Mogelijke keuzes**: ONLY_FULL, PREFER_FULL, NO_FULL.
- **Gevolg**: Striktere instellingen beperken risico, maar kunnen alternatieven onderdrukken.

### Open Domain Strategy
- **Definitie**: Gedrag voor Open Domain buiten referentiedekking.
- **Waarom gebruiken**: Stemt resultaten af op beleid rond niet-gedekte zones.
- **Mogelijke keuzes**: `EXCLUDE`, `ASIS`, `SNAP_INNER_SIDE`, `SNAP_ALL_SIDE`.
- **Gevolg**: Bepaalt of en hoe grensdelen buiten referentie behouden of aangepast worden.

### Snap Strategy
- **Definitie**: Snap-striktheid naar referentievertices.
- **Waarom gebruiken**: Verhoogt structurele passing, vooral bij lijn/punt-achtige situaties.
- **Mogelijke keuzes**: NO_PREFERENCE, PREFER_VERTICES, ONLY_VERTICES.
- **Gevolg**: Striktere settings verbeteren vertexcorrectheid maar verkleinen flexibiliteit.

### Processor
- **Definitie**: Keuze van de verwerkingsengine.
- **Waarom gebruiken**: Optimaliseert runtime en performantie.
- **Mogelijke keuzes**: Prefer AlignerGeometryProcessor.
- **Gevolg**: Juiste keuze geeft stabielere doorlooptijd.

### Threshold overlap percentage (%)
- **Definitie**: Fallback overlapdrempel bij onduidelijke relevantie.
- **Waarom gebruiken**: Maakt randgeval-beslissingen consistenter.
- **Mogelijke keuzes**: 0-100.
- **Gevolg**: Hogere drempel = strengere acceptatie.

### REVIEW_PERCENTAGE
- **Definitie**: Wijzigingsdrempel voor classificatie naar review.
- **Waarom gebruiken**: Stuurt de QA-werklast.
- **Mogelijke keuzes**: Lager voor striktere controle, hoger voor meer automatisatie.
- **Gevolg**: Bepaalt direct hoeveel records in review terechtkomen.

### Work Folder
- **Definitie**: Uitvoermap voor gegenereerde resultaten en logs.
- **Waarom gebruiken**: Centraliseert output per run.
- **Mogelijke keuzes**: Leeg (standaard lokale map) of expliciet pad.
- **Gevolg**: Verbetert reproduceerbaarheid en auditbaarheid.

### brdr_metadata field
- **Definitie**: Veld met bestaande `brdr_metadata` uit eerdere runs.
- **Waarom gebruiken**: Hergebruikt historiek en herkomstinformatie voor betere context.
- **Mogelijke keuzes**: Leeg of bestaand metadata-veld.
- **Gevolg**: Kan voorspellingskwaliteit en verklaarbaarheid verbeteren.

### Write extra logging (from brdr-log)
- **Definitie**: Uitgebreide logging van het algoritme.
- **Waarom gebruiken**: Ondersteunt diagnose en troubleshooting.
- **Mogelijke keuzes**: False/True.
- **Gevolg**: Meer inzicht bij fouten, met grotere logbestanden.

## Aanbevolen presets
- **Stabiele productie-update**: PREDICTION_STRATEGY=BEST, FULL_REFERENCE_STRATEGY=PREFER_FULL, Relevant Distance=3-5.
- **Strikte grens-QA**: FULL_REFERENCE_STRATEGY=ONLY_FULL, lower REVIEW_PERCENTAGE, conservative distance.
- **Analyse van ambiguiteit**: PREDICTION_STRATEGY=ALL, higher distance, LOG_INFO=True.
- **Veilige fallback**: PREDICTION_STRATEGY=ORIGINAL when preserving source geometry is preferred over uncertain shifts.


### Uitvoerparameters

Het script genereert meerdere outputlagen in een gecombineerde groeplaag:

* `brdrQ_RESULT`: resulterende geometrieen na uitlijning
* `brdrQ_DIFF`: verschillen (+ en -) tussen originele en resulterende geometrie
* `brdrQ_DIFF_PLUS`: verschillen (+)
* `brdrQ_DIFF_MIN`: verschillen (-)

## Voorbeeldgebruik

Voorbeeld in Python:

```python
output = processing.run(
    "brdrqprovider:brdrqautoupdateborders",
    {
        "INPUT_THEMATIC": themelayername,
        "COMBOBOX_ID_THEME": "theme_identifier",
        "ENUM_REFERENCE": 0,
        "METADATA_FIELD": "",
        "RELEVANT_DISTANCE": 5,
        "WORK_FOLDER": "",
        "ENUM_OD_STRATEGY": 2,
        "ENUM_SNAP_STRATEGY": 1,
        "ENUM_PROCESSOR": 0,
        "THRESHOLD_OVERLAP_PERCENTAGE": 50,
        "REVIEW_PERCENTAGE": 10,
        "PREDICTION_STRATEGY": 2,
        "FULL_REFERENCE_STRATEGY": 2,
        "LOG_INFO": True,
    },
)
```



