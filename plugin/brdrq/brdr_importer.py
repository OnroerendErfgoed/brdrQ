
import sys
import os
import site
import subprocess

# helper function to find embedded python
# path in windows. Based on
# https://github.com/qgis/QGIS/issues/45646

def find_python():
    if sys.platform != "win32":
        return sys.executable

    for path in sys.path:
        assumed_path = os.path.join(path, "python.exe")
        if os.path.isfile(assumed_path):
            return assumed_path

    raise Exception("Python executable not found")

sys.path.insert(0, site.getusersitepackages())
python_exe = find_python()

try:
    from shapely import (
        Polygon,
        from_wkt,
        to_wkt,
        unary_union,
        make_valid
    )
    from shapely.geometry import shape
except (ModuleNotFoundError):
    print("Module shapely not found. Installing from PyPi.")
    subprocess.check_call([python_exe,
                           '-m', 'pip', 'install', 'shapely'])
    from shapely import (
        Polygon,
        from_wkt,
        to_wkt,
        unary_union,
        make_valid
    )
    from shapely.geometry import shape

try:
    import brdr

    if brdr.__version__ != "0.4.0":
        raise ValueError("Version mismatch")

except (ModuleNotFoundError, ValueError):
    subprocess.check_call([python_exe,
                           '-m', 'pip', 'install', 'brdr==0.4.0'])
    import brdr

    print(brdr.__version__)