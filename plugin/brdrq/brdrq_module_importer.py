import importlib
import os
import site
import subprocess
import sys

from qgis.PyQt.QtWidgets import QMessageBox

from .qt_compat import (
    dialog_exec,
    qmessagebox_ok_button,
    qmessagebox_warning_icon,
)

# helper function to find embedded python
# path in windows. Based on
# https://github.com/qgis/QGIS/issues/45646


brdr_version = "0.17.4"


def find_python():
    if sys.platform != "win32":
        print(sys.platform)
        return sys.executable

    for path in sys.path:
        assumed_path = os.path.join(path, "python.exe")
        if os.path.isfile(assumed_path):
            print(f"assumed path: {assumed_path}")
            return assumed_path

    raise Exception("Python executable not found")


def pipinstall_in_libs(python_exe, package):
    plugin_dir = os.path.dirname(__file__)
    target_dir = os.path.join(plugin_dir, "libs")

    # Add target_dir to sys.path
    if target_dir not in sys.path:
        sys.path.append(target_dir)
        subprocess.check_call(
            [python_exe, "-m", "pip", "install", package, "--target", target_dir]
        )


def pipinstall_by_subprocess(python_exe, package):
    if sys.platform != "win32":
        try:
            pipinstall_in_libs(python_exe, package)
        except:
            QMessageBox.critical(
                None,
                "Dependency Error",
                f"This plugin needs external dependency '{package}'. "
                f"Automatic installation is only supported on Windows. "
                f"For Linux/Mac, install {package} manually.",
            )

    else:
        try:
            subprocess.check_call([python_exe, "-m", "pip", "install", package])
        except:
            try:
                subprocess.check_call(
                    [python_exe, "-m", "pip", "install", "--user", package]
                )
            except:
                pipinstall_in_libs(python_exe, package)


def install_brdr(python_exe, installed_version=None):
    if "brdr" in sys.modules:
        del sys.modules["brdr"]
        print("brdr removed from sys_module")
    pipinstall_by_subprocess(python_exe, "brdr==" + brdr_version)
    import brdr

    importlib.reload(brdr)
    import brdr

    print(f"reloaded version of brdr: {brdr.__version__}")
    show_new_brdr_dialog(installed_version=installed_version)


def install_package(python_exe, package):
    print(f"Module {package} not found. Installing from PyPi.")
    pipinstall_by_subprocess(python_exe, package)


def import_modules():
    sys.path.insert(0, site.getusersitepackages())
    python_exe = find_python()
    installed_version = None

    try:
        from shapely import Polygon, from_wkt, to_wkt, unary_union, make_valid
        from shapely.geometry import shape
    except ModuleNotFoundError:
        install_package(python_exe, "shapely")

    try:
        import pyogrio
    except ModuleNotFoundError:
        install_package(python_exe, "pyogrio")

    try:
        import geopandas
    except ModuleNotFoundError:
        install_package(python_exe, "geopandas")

    try:
        import matplotlib
    except ModuleNotFoundError:
        install_package(python_exe, "matplotlib")

    try:
        import brdr

        importlib.reload(brdr)
        import brdr

        if brdr.__version__ != brdr_version:
            installed_version = brdr.__version__
            raise ValueError(
                f"brdr version mismatch: installed {installed_version}, "
                f"expected {brdr_version}"
            )

    except ModuleNotFoundError:
        install_brdr(python_exe)
    except ValueError:
        install_brdr(python_exe, installed_version=installed_version)


def show_new_brdr_dialog(installed_version=None):
    from qgis.PyQt.QtWidgets import QMessageBox

    msg = QMessageBox()
    msg.setIcon(qmessagebox_warning_icon())
    msg.setWindowTitle("brdrQ dependency updated")
    version_text = f"Required brdr version: <b>{brdr_version}</b>."
    if installed_version:
        version_text = (
            f"Previous brdr version: <b>{installed_version}</b><br>"
            f"Required brdr version: <b>{brdr_version}</b>."
        )
    msg.setText(
        "<b>brdrQ has updated the required brdr library.</b>"
    )
    msg.setInformativeText(
        f"{version_text}<br><br>"
        "QGIS may still have the previous Python library loaded in memory. "
        "Please close and reopen QGIS before using brdrQ, so the plugin starts "
        "with the correct brdr version.<br><br>"
        "Your QGIS project and data were not changed by this dependency update."
    )
    msg.setStandardButtons(qmessagebox_ok_button())
    dialog_exec(msg)
