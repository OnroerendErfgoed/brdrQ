import importlib
import os
import site
import subprocess
import sys


# helper function to find embedded python
# path in windows. Based on
# https://github.com/qgis/QGIS/issues/45646


brdr_version = "0.13.0"


def find_python():
    if sys.platform != "win32":
        return sys.executable

    for path in sys.path:
        assumed_path = os.path.join(path, "python.exe")
        if os.path.isfile(assumed_path):
            return assumed_path

    raise Exception("Python executable not found")


def import_modules():
    sys.path.insert(0, site.getusersitepackages())
    python_exe = find_python()

    try:
        from shapely import Polygon, from_wkt, to_wkt, unary_union, make_valid
        from shapely.geometry import shape
    except ModuleNotFoundError:
        print("Module shapely not found. Installing from PyPi.")
        subprocess.check_call([python_exe, "-m", "pip", "install", "shapely"])
        from shapely import Polygon, from_wkt, to_wkt, unary_union, make_valid
        from shapely.geometry import shape

    try:
        import brdr

        importlib.reload(brdr)
        import brdr

        if brdr.__version__ != brdr_version:
            raise ValueError("Version mismatch")

    except (ModuleNotFoundError, ValueError):

        if "brdr" in sys.modules:
            del sys.modules["brdr"]
            print ("brdr removed from sys_module")

        subprocess.check_call(
            [python_exe, "-m", "pip", "install", "brdr==" + brdr_version]
        )
        # show_new_brdr_dialog()
        import brdr
        #print(f"version of brdr before reload: {brdr.__version__}")
        importlib.reload(brdr)
        import brdr

        print(f"reloaded version of brdr: {brdr.__version__}")


def show_new_brdr_dialog():
    from PyQt5.QtWidgets import QMessageBox

    msg = QMessageBox()
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle("New installation of 'brdr'")
    msg.setText(
        f"A new version of 'brdr'({brdr_version}) is installed for the calculations in the brdrQ-plugin: . A restart of QGIS is required to ensure correct functioning of brdrQ"
    )
    msg.setInformativeText("Please restart QGIS before using brdrQ.")
    msg.setStandardButtons(QMessageBox.Ok)
    msg.exec_()
