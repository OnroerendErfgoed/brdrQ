import importlib
import json
import os
import shutil
import site
import subprocess
import sys
import sysconfig
import time

from .qt_compat import (
    dialog_exec,
    qmessagebox_ok_button,
    qmessagebox_warning_icon,
)

# helper function to find embedded python
# path in windows. Based on
# https://github.com/qgis/QGIS/issues/45646


brdr_version = "0.17.4"
BRDR_RESTART_REQUIRED_FLAG = "_brdrq_brdr_restart_required"

# Windows install target for dependencies:
# False: install in the Python environment/user site, with plugin-local fallback.
# True: install directly into the brdrQ plugin's libs directory.
INSTALL_DEPENDENCIES_IN_PLUGIN_DIR = False
PIP_INSTALL_TIMEOUT_SECONDS = 120


class _PipInstallTimeout(RuntimeError):
    """Raised when pip does not finish within the configured time limit."""


def find_python():
    if sys.platform == "win32":
        for path in sys.path:
            assumed_path = os.path.join(path, "python.exe")
            if os.path.isfile(assumed_path):
                print(f"assumed path: {assumed_path}")
                return assumed_path
        raise Exception("Python executable not found")

    # QGIS launchers on macOS and Linux can be reported as sys.executable.
    # Find a runnable Python with a compatible ABI; pip installs packages
    # into the plugin's libs directory on these platforms.
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    bindir = sysconfig.get_config_var("BINDIR") or ""
    executable_names = (f"python{version}", "python3")
    candidates = [
        *(os.path.join(directory, name)
          for directory in (sys.prefix, sys.exec_prefix, bindir)
          if directory
          for name in executable_names),
        getattr(sys, "_base_executable", None),
    ]
    candidates.extend(
        [
            shutil.which(f"python{version}"),
            shutil.which("python3"),
        ]
    )

    def looks_like_python(path):
        # Do not execute a QGIS application binary; it could launch another
        # GUI instance instead of interpreting the -c argument.
        return "python" in os.path.basename(path).lower()

    if looks_like_python(sys.executable):
        candidates.insert(0, sys.executable)

    runtime_probe = (
        "import json, pip, sys, sysconfig; "
        "print(json.dumps({"
        "'version': [sys.version_info.major, sys.version_info.minor], "
        "'implementation': sys.implementation.name, "
        "'cache_tag': sys.implementation.cache_tag, "
        "'soabi': sysconfig.get_config_var('SOABI'), "
        "'platform': sysconfig.get_platform()}))"
    )
    qgis_runtime = {
        "version": [sys.version_info.major, sys.version_info.minor],
        "implementation": sys.implementation.name,
        "cache_tag": sys.implementation.cache_tag,
        "soabi": sysconfig.get_config_var("SOABI"),
        "platform": sysconfig.get_platform(),
    }

    compatible_candidates = []
    fallback_candidates = []
    timed_out_candidates = []
    probe_deadline = time.monotonic() + 20
    for candidate in dict.fromkeys(c for c in candidates if c):
        if (
            not looks_like_python(candidate)
            or not os.path.isfile(candidate)
            or not os.access(candidate, os.X_OK)
        ):
            continue
        remaining_time = probe_deadline - time.monotonic()
        if remaining_time <= 0:
            print("Python interpreter search stopped after its 20-second time limit.")
            break
        try:
            result = subprocess.check_output(
                [candidate, "-c", runtime_probe],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=remaining_time,
            )
            candidate_runtime = json.loads(result)
        except subprocess.TimeoutExpired:
            timed_out_candidates.append(candidate)
            print(f"Python runtime check timed out: {candidate}")
            continue
        except (OSError, subprocess.CalledProcessError, ValueError):
            continue
        if candidate_runtime == qgis_runtime:
            compatible_candidates.append(candidate)
        elif candidate_runtime.get("version") == qgis_runtime["version"]:
            # Prefer an ABI/platform match, but retain same-version Pythons as
            # a fallback in case QGIS has no separately runnable interpreter.
            fallback_candidates.append(candidate)

    if compatible_candidates:
        return compatible_candidates[0]
    if fallback_candidates:
        print(
            "Warning: no Python interpreter matching the QGIS ABI/platform "
            "was found; using a same-version Python with pip. Native packages "
            "installed by pip may not be compatible with QGIS."
        )
        return fallback_candidates[0]

    error = f"No Python {version} interpreter with pip was found"
    if timed_out_candidates:
        error += ". Timed out while checking: " + ", ".join(timed_out_candidates)
    raise RuntimeError(error)


def pipinstall_in_libs(python_exe, package, timeout=PIP_INSTALL_TIMEOUT_SECONDS):
    plugin_dir = os.path.dirname(__file__)
    target_dir = os.path.join(plugin_dir, "libs")

    # Make the local directory available even if it was already on sys.path.
    if target_dir in sys.path:
        sys.path.remove(target_dir)
    sys.path.insert(0, target_dir)
    _run_pip_install(python_exe, package, target_dir=target_dir, timeout=timeout)


def _run_pip_install(
    python_exe,
    package,
    target_dir=None,
    user=False,
    timeout=PIP_INSTALL_TIMEOUT_SECONDS,
):
    """Install without cached wheels and include actionable pip errors."""
    command = [
        python_exe,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-cache-dir",
        "--upgrade",
    ]
    if user:
        command.append("--user")
    if target_dir:
        command.extend(["--target", target_dir])
    command.append(package)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise _PipInstallTimeout(
            f"pip did not finish installing {package} within "
            f"{timeout:.0f} seconds. Check the network connection "
            "and try again."
        ) from exc
    if result.returncode:
        details = "\n".join(
            part.strip() for part in (result.stdout, result.stderr) if part.strip()
        ) or "No details returned by pip."
        raise RuntimeError(
            f"pip failed to install {package} (exit code {result.returncode}).\n"
            f"Command: {' '.join(command)}\n{details}"
        )
    if result.stdout.strip():
        print(result.stdout.strip())


def pipinstall_by_subprocess(python_exe, package):
    if sys.platform != "win32":
        pipinstall_in_libs(python_exe, package)
        return

    if INSTALL_DEPENDENCIES_IN_PLUGIN_DIR:
        pipinstall_in_libs(python_exe, package)
        return

    errors = []
    install_deadline = time.monotonic() + PIP_INSTALL_TIMEOUT_SECONDS
    for install_options in ({}, {"user": True}):
        remaining_time = install_deadline - time.monotonic()
        if remaining_time <= 0:
            raise _PipInstallTimeout(
                f"Timed out installing {package} after "
                f"{PIP_INSTALL_TIMEOUT_SECONDS} seconds."
            )
        try:
            _run_pip_install(
                python_exe, package, timeout=remaining_time, **install_options
            )
            return
        except RuntimeError as exc:
            if isinstance(exc, _PipInstallTimeout):
                raise
            errors.append(str(exc))
    try:
        remaining_time = install_deadline - time.monotonic()
        if remaining_time <= 0:
            raise _PipInstallTimeout(
                f"Timed out installing {package} after "
                f"{PIP_INSTALL_TIMEOUT_SECONDS} seconds."
            )
        pipinstall_in_libs(python_exe, package, timeout=remaining_time)
        return
    except RuntimeError as exc:
        if isinstance(exc, _PipInstallTimeout):
            raise
        errors.append(str(exc))

    raise RuntimeError(
        f"Could not install dependency '{package}' using any supported method.\n\n"
        + "\n\n".join(errors)
    )


def install_brdr(python_exe, restart_required):
    if "brdr" in sys.modules:
        del sys.modules["brdr"]
        print("brdr removed from sys_module")
    pipinstall_by_subprocess(python_exe, "brdr==" + brdr_version)
    import brdr

    importlib.reload(brdr)
    import brdr

    print(f"reloaded version of brdr: {brdr.__version__}")
    if restart_required:
        setattr(sys, BRDR_RESTART_REQUIRED_FLAG, True)
    show_new_brdr_dialog(restart_required=restart_required)
    return restart_required


def install_package(python_exe, package):
    print(f"Module {package} not found. Installing from PyPi.")
    pipinstall_by_subprocess(python_exe, package)


def import_modules():
    # Keep the plugin disabled even if QGIS reloads brdrQ after the install.
    # This marker is cleared naturally when QGIS starts a fresh Python process.
    if getattr(sys, BRDR_RESTART_REQUIRED_FLAG, False):
        return True

    sys.path.insert(0, site.getusersitepackages())
    python_exe = None

    def get_python_executable():
        nonlocal python_exe
        if python_exe is None:
            python_exe = find_python()
        return python_exe

    try:
        from shapely import Polygon, from_wkt, to_wkt, unary_union, make_valid
        from shapely.geometry import shape
    except ImportError:
        install_package(get_python_executable(), "shapely")

    try:
        import pyogrio
    except ImportError:
        install_package(get_python_executable(), "pyogrio")

    try:
        import geopandas
    except ImportError:
        install_package(get_python_executable(), "geopandas")

    try:
        import matplotlib
    except ImportError:
        install_package(get_python_executable(), "matplotlib")

    brdr_was_loaded = any(
        module_name == "brdr" or module_name.startswith("brdr.")
        for module_name in sys.modules
    )
    try:
        import brdr
    except ModuleNotFoundError as exc:
        if exc.name != "brdr":
            raise
        # A missing package can be loaded immediately only when this process
        # has no cached brdr modules from an earlier installation.
        restart_required = install_brdr(
            get_python_executable(), restart_required=brdr_was_loaded
        )
    else:
        importlib.reload(brdr)
        if brdr.__version__ != brdr_version:
            # Upgrade: older submodules/references can still be live in this
            # Python process, so keep the tools disabled until QGIS restarts.
            restart_required = install_brdr(
                get_python_executable(), restart_required=True
            )
        else:
            restart_required = False

    return restart_required


def show_new_brdr_dialog(restart_required=True):
    from qgis.PyQt.QtWidgets import QMessageBox

    msg = QMessageBox()
    msg.setIcon(qmessagebox_warning_icon())
    msg.setWindowTitle("New installation of 'brdr'")
    if restart_required:
        msg.setText(
            f"brdr {brdr_version} has been installed. brdrQ tools are disabled "
            "for this QGIS session because older brdr modules may still be in memory."
        )
        msg.setInformativeText(
            "Restart QGIS to load brdrQ with the installed brdr version."
        )
    else:
        msg.setWindowTitle("brdr installed")
        msg.setText(
            f"brdr {brdr_version} has been installed. brdrQ will now finish loading."
        )
        msg.setInformativeText(
            "The brdrQ tools are available in this QGIS session."
        )
    msg.setStandardButtons(qmessagebox_ok_button())
    dialog_exec(msg)
