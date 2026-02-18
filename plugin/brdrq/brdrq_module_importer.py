import importlib
import os
import site
import subprocess
import sys

# TODO QGIS4
from PyQt5.QtWidgets import QMessageBox

# helper function to find embedded python
# path in windows. Based on
# https://github.com/qgis/QGIS/issues/45646


brdr_version = "0.15.5"


def find_python():
    if sys.platform != "win32":
        print (sys.platform)
        return sys.executable

    for path in sys.path:
        assumed_path = os.path.join(path, "python.exe")
        if os.path.isfile(assumed_path):
            print(f"assumed path: {assumed_path}")
            return assumed_path

    raise Exception("Python executable not found")

def pipinstall_in_libs(python_exe,package):
    plugin_dir = os.path.dirname(__file__)
    target_dir = os.path.join(plugin_dir, "libs")

    # Add target_dir to sys.path
    if target_dir not in sys.path:
        sys.path.append(target_dir)
        subprocess.check_call(
            [python_exe, "-m", "pip", "install", package,"--target",target_dir]
        )

def pipinstall_by_subprocess(python_exe,package):
    if sys.platform != "win32":
        try:
            pipinstall_in_libs(python_exe,package)
        except:
            QMessageBox.error(None, "Error", f"This plugin needs external dependency '{package}', automatically installed for Windows. For Linux/Mac, the correct version ({package}) has to be installed manually")

    else:
        try:
            subprocess.check_call(
                [python_exe, "-m", "pip", "install", package]
            )
        except:
            try:
                subprocess.check_call(
                    [python_exe, "-m", "pip", "install", "--user", package]
                )
            except:
                pipinstall_in_libs(python_exe,package)


def install_brdr(python_exe):
    if "brdr" in sys.modules:
        del sys.modules["brdr"]
        print("brdr removed from sys_module")
    pipinstall_by_subprocess(python_exe,"brdr==" + brdr_version)
    import brdr
    importlib.reload(brdr)
    import brdr
    print(f"reloaded version of brdr: {brdr.__version__}")
    show_new_brdr_dialog()

def install_shapely(python_exe):
    print("Module shapely not found. Installing from PyPi.")
    pipinstall_by_subprocess(python_exe,"shapely")


def import_modules():
    sys.path.insert(0, site.getusersitepackages())
    python_exe = find_python()

    try:
        from shapely import Polygon, from_wkt, to_wkt, unary_union, make_valid
        from shapely.geometry import shape
    except ModuleNotFoundError:
        install_shapely(python_exe)

    try:
        import brdr
        importlib.reload(brdr)
        import brdr

        if brdr.__version__ != brdr_version:
            raise ValueError("Version mismatch")

    except (ModuleNotFoundError, ValueError):
        install_brdr(python_exe)


def show_new_brdr_dialog():
    # TODO QGIS4
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
