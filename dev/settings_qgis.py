from qgis.core import QgsSettings

qs = QgsSettings()

# We lopen door alle gesorteerde keys heen
for k in sorted(qs.allKeys()):
    # Filter op de specifieke prefix
    if k.startswith("brdrqfeaturealigner"):
        val = qs.value(k)
        print(f"{k}: {val}")