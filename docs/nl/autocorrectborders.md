---
title: "Autocorrectborders (BULK)"
lang: nl
---

# Documentatie van QGIS Python-plugin brdrQ - Autocorrectborders

## Video

{{< video src="../figures/brdrQ_autocorrectborders_bulk.mp4" muted width="600" height="400" title="BrdrQ Autocorrectborders Demo" >}}

## Beschrijving

<img src="../figures/autocorrectborders.png" width="50%" />

Het processing-algoritme **Autocorrectborders** is ontwikkeld om thematische grenzen automatisch aan te passen aan referentiegrenzen. Het zoekt relevante overlap tussen thematische grenzen en referentiegrenzen en maakt op basis daarvan een resulterende grens.

Omdat **Autocorrectborders** beschikbaar is als QGIS Processing-algoritme, kan het ook gebruikt worden in de QGIS
Model Designer.

## Snel starten

1. Kies je thematische laag en een uniek thematisch ID.
2. Kies een referentiebron: `LOCREF` voor een lokale referentielaag, of een on-the-fly referentiebron.
3. Start voorzichtig met een beperkte `RELEVANT_DISTANCE`, bijvoorbeeld `2-5` meter.
4. Kies hoe je de output wil gebruiken: rechtstreeks met `RESULT_` en `DIFF_`, of met de optionele `CORRECTION_`-reviewlaag.
5. Zet in Model Designer `LOAD_OUTPUT_LAYERS=False` wanneer het algoritme alleen een tussenstap is en je de gemaakte lagen niet in de QGIS-lagenlijst wil laden.
6. Gebruik je de `CORRECTION_`-workflow, open dan twijfelgevallen in FeatureAligner en sla een gekozen voorspelling op indien nodig.

## Parametergids
Elke parameter wordt eenduidig uitgelegd met: **Definitie**, **Waarom gebruiken**, **Mogelijke keuzes**, en **Gevolg**.

### Thematic Layer
- **Definitie**: Invoer-vectorlaag (polygoon, lijn of punt) in geprojecteerde CRS (meter).
- **Waarom gebruiken**: Bepaalt welke geometrie gecorrigeerd wordt.
- **Mogelijke keuzes**: Elke geldige laag met stabiele geometrie en geldige CRS.
- **Gevolg**: Ongeldige CRS of gemengde inputkwaliteit geeft onbetrouwbare uitlijning.

### Thematic ID
- **Definitie**: Unieke identifier van een feature in de thematische laag.
- **Waarom gebruiken**: Houdt herkomst en resultaten eenduidig traceerbaar.
- **Mogelijke keuzes**: Tekst- of numeriek veld met unieke waarden.
- **Gevolg**: Niet-unieke IDs maken interpretatie en review foutgevoeliger.

### Reference / Local reference layer / Reference ID (unique!)
- **Definitie**: Keuze van referentiebron (LOCREF of GRB on-the-fly) plus bijhorend referentie-ID-veld.
- **Waarom gebruiken**: Bepaalt de geometrische waarheid voor uitlijning.
- **Mogelijke keuzes**: Lokale referentie voor gecontroleerde workflows; GRB voor service-gebaseerde referentie.
- **Gevolg**: Betere referentie = betere outputkwaliteit.

### Relevant Distance (meters)
- **Definitie**: Maximale toegelaten geometrische verschuiving.
- **Waarom gebruiken**: Stuurt hoe ver features mogen verschuiven richting referentie.
- **Mogelijke keuzes**: Laag (`1-2`), midden (`3-5`), hoog (`>10`) afhankelijk van bronkwaliteit.
- **Gevolg**: Lage waarden zijn voorzichtiger/sneller; hoge waarden zijn krachtiger/trager en verhogen vaak review.

### Use predictions
- **Definitie**: Bepaalt of brdrQ een snelle berekening op een afstand uitvoert, of meerdere kandidaatvoorspellingen over een afstandsbereik laat evalueren.
- **Waarom gebruiken**: `PREDICTIONS` helpt om in ambigue situaties stabielere kandidaten te vinden en te evalueren.
- **Mogelijke keuzes**: `NO_PREDICTIONS` voor een snelle berekening op de opgegeven `RELEVANT_DISTANCE`; `PREDICTIONS` voor een full scan over meerdere afstandsstappen.
- **Gevolg**: `PREDICTIONS` geeft rijkere evaluatie-informatie en vaak betere kandidaten, maar verhoogt de rekentijd. Bij `NO_PREDICTIONS` blijft `brdr_evaluation` meestal `not_evaluated`.

### Prediction Strategy
- **Definitie**: Uitvoerbeleid wanneer meerdere kandidaatvoorspellingen bestaan.
- **Waarom gebruiken**: Bepaalt of output deterministisch of analysegericht is.
- **Mogelijke keuzes**: `BEST`, `ALL`, `ORIGINAL`.
- **Gevolg**: `BEST` is productiegericht, `ALL` is analysegericht, `ORIGINAL` is de veiligste fallback.

### Full Reference Strategy
- **Definitie**: Voorkeur voor voorspellingen met volledige overlap met de referentie.
- **Waarom gebruiken**: Verhoogt geometrische zekerheid indien gewenst.
- **Mogelijke keuzes**: `ONLY_FULL_REFERENCE`, `PREFER_FULL_REFERENCE`, `NO_FULL_REFERENCE`.
- **Gevolg**: Strikter verlaagt risico, maar kan bruikbare alternatieven uitsluiten.

### Processor
- **Definitie**: Keuze van de geometrische verwerkingsengine.
- **Waarom gebruiken**: Optimaliseert runtime en robuustheid per geometrietype.
- **Mogelijke keuzes**: `AlignerGeometryProcessor`, `NetworkGeometryProcessor`, `SnapGeometryProcessor`.
- **Gevolg**: Juiste processor geeft betere snelheid en stabiliteit.

### Open Domain Strategy
- **Definitie**: Gedrag voor geometrische delen die niet door referentiefeatures gedekt worden.
- **Waarom gebruiken**: Stemt output af op inhoudelijk/operationeel grensbeleid.
- **Mogelijke keuzes**: `EXCLUDE`, `ASIS`, `SNAP_INNER_SIDE`, `SNAP_ALL_SIDE`.
- **Gevolg**: Bepaalt of en hoe niet-gedekte zones behouden of aangepast worden.

### Snap Strategy
- **Definitie**: Snapbeleid naar referentievertices, vooral relevant bij lijn- en puntworkflows.
- **Waarom gebruiken**: Stuurt de strengheid van snapping naar echte referentievertices.
- **Mogelijke keuzes**: `NO_PREFERENCE`, `PREFER_VERTICES`, `PREFER_ENDS_AND_ANGLES`, `ONLY_VERTICES`.
- **Gevolg**: Strikter geeft nettere topologie, maar vaak minder kandidaten.

### Threshold overlap percentage (%)
- **Definitie**: Fallback overlapdrempel voor relevantiebeslissingen.
- **Waarom gebruiken**: Lost randgevallen op waar relevantie onduidelijk is.
- **Mogelijke keuzes**: `0-100` (standaard vaak rond `50`).
- **Gevolg**: Hogere waarden zijn strenger, lagere waarden toleranter.

### REVIEW_PERCENTAGE
- **Definitie**: Drempel om resultaten als `to_review` te classificeren.
- **Waarom gebruiken**: Stuurt de QA-werklast.
- **Mogelijke keuzes**: Lager voor strikte QA, hoger voor meer automatisatie.
- **Gevolg**: Lagere drempel geeft meer manuele review.

### Generate CORRECTION review/workflow layer
- **Definitie**: Bepaalt of brdrQ een extra `CORRECTION_`-laag met `brdrq_state` aanmaakt.
- **Waarom gebruiken**: De laag ondersteunt een reviewworkflow in QGIS en FeatureAligner.
- **Mogelijke keuzes**: True wanneer je een review-/werklaag wil; False wanneer `RESULT_` en `DIFF_` volstaan.
- **Gevolg**: Uitzetten maakt de output eenvoudiger. De berekende `RESULT_`- en `DIFF_`-lagen veranderen hierdoor niet.

### Load created layers in QGIS project
- **Definitie**: Bepaalt of brdrQ de gemaakte `RESULT_`-, `DIFF_`-, optionele `CORRECTION_`- en hulplagen toevoegt aan het QGIS-project/de lagenlijst.
- **Waarom gebruiken**: Houdt interactief gebruik handig, maar laat propere Processing Model Designer-workflows toe.
- **Mogelijke keuzes**: True voor normaal QGIS-gebruik; False wanneer een volgende modelstap de outputs gebruikt en je geen tussenlagen in het lagenpaneel wil.
- **Gevolg**: Uitzetten verhindert niet dat outputs gemaakt of aan Processing teruggegeven worden. Het slaat alleen het automatisch laden in het QGIS-project over.

### Work Folder
- **Definitie**: Locatie voor output en logbestanden.
- **Waarom gebruiken**: Zorgt voor reproduceerbare outputorganisatie.
- **Mogelijke keuzes**: Leeg (standaard lokaal) of expliciet pad.
- **Gevolg**: Expliciet pad vereenvoudigt batch-audit en traceerbaarheid.

### Show Intermediate processing results
- **Definitie**: Voegt tussenlagen toe voor diagnose.
- **Waarom gebruiken**: Maakt duidelijk waarom uitlijning wel/niet slaagde.
- **Mogelijke keuzes**: False/True.
- **Gevolg**: Beter inzicht, met iets zwaardere output.

### Write extra logging (from brdr-log)
- **Definitie**: Schrijft uitgebreidere verwerkingslogs weg.
- **Waarom gebruiken**: Probleemoplossing en audit.
- **Mogelijke keuzes**: False/True.
- **Gevolg**: Meer diagnose-inzicht, met grotere logbestanden.

## Aanbevolen presets
- **Snelle scan**: `PREDICTIONS=NO_PREDICTIONS`, `Relevant Distance=2-4`, `REVIEW_PERCENTAGE=10`.
- **Gebalanceerde productie**: `PREDICTIONS=PREDICTIONS`, `Prediction Strategy=BEST`, `Full Reference Strategy=PREFER_FULL_REFERENCE`, `Relevant Distance=3-5`.
- **Strikte QA**: lagere `REVIEW_PERCENTAGE` (`5-8`), voorzichtige `Relevant Distance`, striktere full-reference-instelling.
- **Verkenning**: `PREDICTIONS=PREDICTIONS`, `Prediction Strategy=ALL`, `SHOW_INTERMEDIATE_LAYERS=True`, `LOG_INFO=True`.
- **Enkel directe output**: `GENERATE_CORRECTION_LAYER=False` wanneer je proces alleen `RESULT_`- en `DIFF_`-lagen gebruikt.
- **Tussenstap in Model Designer**: `LOAD_OUTPUT_LAYERS=False` zodat volgende modelstappen de outputs kunnen gebruiken zonder de QGIS-lagenlijst te vullen met tussenlagen.

## Uitvoerparameters

Met `LOAD_OUTPUT_LAYERS=True` genereert het script een groep in de QGIS-lagenlijst. De laagnamen krijgen een suffix volgens dit patroon: `_DIST_<relevant_distance>_<reference>_<timestamp>`. Bij `PREDICTIONS=PREDICTIONS` komt daar `_PREDICTIONS` bij.

Met `LOAD_OUTPUT_LAYERS=False` worden dezelfde outputs gemaakt en aan QGIS Processing teruggegeven, maar niet automatisch in het project geladen. Dit is nuttig wanneer Autocorrectborders een tussenstap is in Model Designer.

De belangrijkste outputlagen zijn:

* `RESULT_DIST_...`: resulterende geometrieen na uitlijning.
* `DIFF_DIST_...`: verschillen (+ en -) tussen origineel en resultaat.
* `DIFF_MIN_DIST_...`: verschillen (-) tussen origineel en resultaat.
* `DIFF_PLUS_DIST_...`: verschillen (+) tussen origineel en resultaat.
* optioneel `RLVNT_DIFF_DIST_...`: relevante verschillen (te verwijderen delen), gebruikt bij verwerken van resultaat.
* optioneel `RLVNT_ISECT_DIST_...`: relevante intersectie (op te nemen delen), gebruikt bij verwerken van resultaat.
* optioneel `CORRECTION_DIST_...`: workflowlaag op basis van de thematische laag, met aangepaste geometrieen en `brdrq_state` voor review.

De `RESULT_`- en `DIFF_`-lagen zijn de primaire tooloutput. Je kan die rechtstreeks gebruiken in je eigen workflow zonder iets met de `CORRECTION_`-laag te doen.

De `CORRECTION_`-laag wordt alleen aangemaakt wanneer `GENERATE_CORRECTION_LAYER=True` en de output een gekozen resultaat per feature bevat. Wanneer je `PREDICTIONS=PREDICTIONS` combineert met `Prediction Strategy=ALL`, wordt er geen `CORRECTION_`-laag aangemaakt omdat die instelling bedoeld is om alle kandidaatvoorspellingen te analyseren.

<img src="../figures/output.png" width="100%" />

## Workflow: rechtstreeks RESULT/DIFF gebruiken

Gebruik deze workflow wanneer je proces alleen de berekende geometrie en de verschillen met de originele input nodig heeft:

1. Run Autocorrectborders.
2. Gebruik `RESULT_DIST_...` als uitgelijnde geometrie-output.
3. Gebruik `DIFF_DIST_...`, `DIFF_PLUS_DIST_...` en `DIFF_MIN_DIST_...` voor QA, rapportering of filtering.
4. Zet `GENERATE_CORRECTION_LAYER` uit wanneer de extra reviewlaag alleen ruis in je project zou geven.
5. Zet in Model Designer ook `LOAD_OUTPUT_LAYERS=False` wanneer de volgende modelstap de output gebruikt en de lagen niet in het project moeten verschijnen.

Dit is vaak de duidelijkste keuze voor ETL, model builder, batchverwerking of gebruikers die al een eigen QA-proces hebben.

## Workflow: review met de CORRECTION-laag

Gebruik deze workflow wanneer je wil dat brdrQ een QGIS-werklaag klaarzet voor menselijke review.

De `CORRECTION_DIST_...`-laag bevat een kopie van de thematische laag, aangevuld met brdr/brdrQ-velden. De originele inputlaag wordt niet aangepast.

`brdrq_state` is een workflowstatus van brdrQ. Het is dus geen kwaliteits- of evaluatiescore van het onderliggende brdr-algoritme. Gebruik deze status om te bepalen welke features automatisch verwerkt zijn en welke nog manueel aandacht vragen.

| `brdrq_state` | Betekenis | Typische actie |
| :--- | :--- | :--- |
| `not_changed` | De feature wordt als ongewijzigd beschouwd. Dit gebeurt bijvoorbeeld wanneer brdr `no_change` teruggeeft of wanneer het symmetrisch verschil zeer klein is. | Geen actie nodig, tenzij je steekproefsgewijs controleert. |
| `auto_updated` | Autocorrectborders heeft een bruikbaar resultaat gevonden en de berekende geometrie automatisch in de `CORRECTION_`-laag geplaatst. | Controleer eventueel steekproefsgewijs of volgens je QA-procedure. |
| `to_review` | Er is een resultaat of voorstel, maar brdrQ markeert de feature voor controle. Dat kan bijvoorbeeld door meerdere kandidaten voor dezelfde ID, een wijzigingspercentage boven `REVIEW_PERCENTAGE`, of een stabiel maar niet automatisch af te handelen resultaat. | Open de feature in FeatureAligner en beslis of de voorgestelde geometrie inhoudelijk klopt. |
| `to_update` | Er kon geen automatisch toepasbaar resultaat worden bepaald. In de `CORRECTION_`-laag blijft de originele geometrie zichtbaar en worden verschilwaarden op `-1` gezet. | Behandel de feature manueel in FeatureAligner of in QGIS. Bekijk eventuele predicties als startpunt. |
| `manual_updated` | Een gebruiker heeft in FeatureAligner zelf een voorgestelde geometrie gekozen en opgeslagen met `Save Geometry`. Deze status wordt dus niet door Autocorrectborders zelf gezet. | Beschouw als manueel nagekeken en aangepast. |
| `none` | Technische beginwaarde voordat brdrQ een workflowstatus toekent. | Hoort normaal niet als eindstatus voor te komen. Controleer verwerking/logs als dit toch in output staat. |

`brdr_evaluation` is iets anders dan `brdrq_state`. Dit veld komt uit de evaluatiefase van brdr en beschrijft hoe brdr een voorspelling inhoudelijk categoriseert. brdrQ vertaalt die evaluatie daarna naar een praktische workflowstatus in `brdrq_state`.

Mogelijke waarden zijn onder meer:

| `brdr_evaluation` | Interpretatie |
| :--- | :--- |
| `no_change` | brdr beoordeelt dat de geometrie niet hoeft te wijzigen. |
| `prediction_unique`, `prediction_unique_full` | Er is een unieke kandidaatvoorspelling gevonden; `full` wijst op volledige referentie-overlap. |
| `equality_by_id`, `equality_by_full_reference`, `equality_by_id_and_full_reference` | brdr vindt gelijkheid op basis van ID, volledige referentie-overlap, of beide. |
| `to_check_prediction_full`, `to_check_prediction_multi`, `to_check_prediction_multi_full` | Er zijn kandidaten, maar menselijke controle is nodig. |
| `to_check_original`, `to_check_no_prediction` | De originele geometrie of het ontbreken van een voorspelling vraagt controle. |
| `not_evaluated` | Er is geen volledige evaluatiefase uitgevoerd of geen bruikbare evaluatiewaarde beschikbaar. |

Als je alleen `not_evaluated` ziet, is dat meestal verwacht bij `PREDICTIONS=NO_PREDICTIONS`. Autocorrectborders voert dan een snelle berekening uit voor de opgegeven `RELEVANT_DISTANCE` en doorloopt niet de volledige evaluatie en selectie van alle voorspellingen. Kies `PREDICTIONS=PREDICTIONS` als je de brdr-evaluaties van kandidaatvoorspellingen wil gebruiken.

## Gebruik buiten QGIS, bijvoorbeeld FME

Autocorrectborders is een QGIS Processing-algoritme rond de Python-bibliotheek `brdr`. Voor FME, ETL-pijplijnen of andere software is de aanbevolen integratie daarom om `brdr` rechtstreeks aan te roepen, bijvoorbeeld via een FME PythonCaller of een custom transformer.

Dat vermijdt een onnodige afhankelijkheid van QGIS en brdrQ in een geautomatiseerde datastroom. De bulklogica van Autocorrectborders kan inhoudelijk gereproduceerd worden door `brdr` met dezelfde conceptuele parameters aan te roepen: thematische geometrie, referentiegeometrie, relevante afstand, prediction-instellingen, open-domainstrategie, snapstrategie en evaluatiestrategie. brdrQ blijft vooral de kant-en-klare QGIS-interface en QGIS-workflow voor die functionaliteit.

Er is geen aparte brdrQ-API die je vanuit FME moet aanspreken. Als je een API-gebaseerde integratie nodig hebt, bouw je die best als een lichte service rond `brdr` zelf.

## Voorbeeldgebruik

Voorbeeld van gebruik in Python:

```python
params = {
    "INPUT_THEMATIC": themelayername,
    "COMBOBOX_ID_THEME": "theme_identifier",
    "RELEVANT_DISTANCE": 2,
    "ENUM_REFERENCE": 1,
    "INPUT_REFERENCE": None,
    "COMBOBOX_ID_REFERENCE": None,
    "WORK_FOLDER": 'brdrq',
    "ENUM_OD_STRATEGY": 1,
    "ENUM_SNAP_STRATEGY": 1,
    "ENUM_PROCESSOR": 0,
    "THRESHOLD_OVERLAP_PERCENTAGE": 50,
    "PREDICTIONS": 0,
    "FULL_REFERENCE_STRATEGY": 2,
    "PREDICTION_STRATEGY": 0,
    "REVIEW_PERCENTAGE": 10,
    "GENERATE_CORRECTION_LAYER": True,
    "LOAD_OUTPUT_LAYERS": True,
    "ADD_METADATA": True,
    "ADD_ATTRIBUTES": True,
    "SHOW_INTERMEDIATE_LAYERS": True,
    "LOG_INFO": False,
}

processing.run('brdrqprovider:brdrqautocorrectborders', params)
```

## Tips

- Zet `PREDICTIONS` aan voor de beste resultaten. Dan wordt het volledige bereik van `RELEVANT_DISTANCE` geanalyseerd (FULL SCAN) en worden de beste stabiele resultaten gekozen. Nadeel: trager.

- Analyseer je thematische dataset en probeer inzicht te krijgen in de afwijking (precisie en accuratesse t.o.v. referentie):
  - Waar komt de thematische data vandaan?
  - Wanneer is ze aangemaakt?
  - Op basis van welke referentiegrenzen werd ze getekend?
  - Welke tekenregels/nauwkeurigheid werden toegepast (bv. 0.5 m)?

Dit helpt om een passende `RELEVANT_DISTANCE` te kiezen.

- De huidige versie van het script gaat ervan uit dat thematische laag en referentielaag in dezelfde geprojecteerde CRS staan met meter als eenheid.
- Thematische grenzen met 1 of enkele referentiepolygonen worden meestal in seconden verwerkt. Voor zeer grote gebieden (~1000+ referentiepolygonen) kan de berekening minuten duren.
- In de praktijk zijn grote afbakeningen soms ruwer getekend, waardoor een hogere `RELEVANT_DISTANCE` nodig is (bv. >10 m):
  - `OD-strategy EXCLUDE`: volledig open domein uitsluiten
  - `OD-strategy AS_IS`: bedekt open domein ongewijzigd meenemen
  - `OD-strategy SNAP_INNER_SIDE`: open domein behouden, randen naar binnenzijde verplaatsen
  - `OD-strategy SNAP_ALL_SIDE`: open domein behouden, randen naar binnen- en buitenzijde verplaatsen

## OUTPUT - VELDEN

Deze sectie geeft veldnamen van de outputlaag en hun betekenis.

| Attribuut | Type | Beschrijving |
| :--- | :--- | :--- |
| **brdr_id** | Integer | Interne unieke identificatie van de verwerkte feature. |
| **brdr_area** | Double | Berekende oppervlakte van de resulterende geometrie ($m^2$). |
| **brdr_perimeter** | Double | Totale grenslengte van de resulterende geometrie ($m$). |
| **brdr_shape_index** | Double | Complexiteitsmaat van de vorm (bv. compactheidsratio). |
| **brdr_stability** | Boolean | Geeft aan of geometrie stabiel blijft over meerdere berekeningen. |
| **brdr_prediction_score** | Double | Betrouwbaarheidsscore (%) van de uitlijningsvoorspelling. |
| **brdr_prediction_count** | Integer | Aantal kandidaatmatches gevonden voor de uitlijning. |
| **brdr_evaluation** | String | Categorie van het resultaat (bv. `prediction_unique`, `to_check_prediction_multi`). |
| **brdrq_state** | String | brdrQ-workflowstatus in de optionele `CORRECTION_`-laag: `not_changed`, `auto_updated`, `to_review`, `to_update`, `manual_updated` of `none`. |
| **brdrq_original_wkt** | String | WKT van de originele geometrie voordat de optionele correctielaag werd aangepast. Wordt gebruikt voor review en reset-workflows. |
| **brdr_relevant_distance** | Double | Gebruikte buffer/zoekafstand tijdens uitlijning ($m$). |
| **brdr_sym_diff_area_index** | Double | Absolute oppervlakte van het symmetrisch verschil tussen basis en target ($m^2$). |
| **brdr_sym_diff_area_index_perc** | Double | Symmetrisch verschil uitgedrukt als percentage van totale oppervlakte. |
| **brdr_diff_area_index** | Double | Absolute oppervlakteverschil tussen input- en outputgeometrieen ($m^2$). |
| **brdr_diff_length_index** | Double | Absoluut verschil in grenslengte ($m$). |
| **brdr_full_actual** | Boolean | Vlag die aangeeft of uitlijning de volledige actuele feature dekt. |
| **brdr_remark** | String | Automatische logs of waarschuwingen uit geometrieverwerking. |
| **brdr_metadata** | JSON/Object | Ingesloten SOSA/SSN-metadata met lineage, sensoren en procedures. |



