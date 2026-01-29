import os
import sys

# TODO QGIS4

# helper function to find embedded python
# path in windows. Based on
# https://github.com/qgis/QGIS/issues/45646

brdr_version = "0.15.3"

def import_modules():
    plugin_dir = os.path.dirname(__file__)
    libs_path = os.path.join(plugin_dir, "libs")

    # if libs_path not in sys.path:
    #     sys.path.insert(0, libs_path)
    if libs_path not in sys.path:
        sys.path.append(libs_path)

    try:
        import brdr
        if brdr.__version__ != brdr_version:
            raise ValueError("Version mismatch")
        import shapely

    except (ModuleNotFoundError, ValueError):
        raise ModuleNotFoundError("brdr not found to do the calculations")
