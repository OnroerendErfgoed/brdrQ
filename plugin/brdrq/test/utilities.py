# coding=utf-8
"""Common functionality used by regression test."""

import atexit
import logging
import os
import sys

from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtWidgets import QWidget
from qgis.core import QgsApplication
from qgis.gui import QgsMapCanvas
from qgis.utils import iface

from .qgis_interface import QgisInterface

LOGGER = logging.getLogger("QGIS")
QGIS_APP = None  # Static variable used to hold hand to running QGIS app
CANVAS = None
PARENT = None
IFACE = None


def get_qgis_app(cleanup=True):  # noqa: C901
    """Start one QGIS application to test against.

    :returns: Handle to QGIS app, canvas, iface and parent. If there are any
        errors the tuple members will be returned as None.
    :rtype: (QgsApplication, CANVAS, IFACE, PARENT)

    If QGIS is already running the handle to that app will be returned.
    """

    global QGIS_APP, PARENT, IFACE, CANVAS

    if iface:
        QGIS_APP = QgsApplication
        CANVAS = iface.mapCanvas()
        PARENT = iface.mainWindow()
        IFACE = iface
        return QGIS_APP, CANVAS, IFACE, PARENT

    global QGISAPP

    try:
        QGISAPP
    except NameError:
        myGuiFlag = True  # All test will run qgis in gui mode

        # In python3 we need to convert to a bytes object (or should
        # QgsApplication accept a QString instead of const char* ?)
        try:
            argvb = list(map(os.fsencode, sys.argv))
        except AttributeError:
            argvb = sys.argv

        # Note: QGIS_PREFIX_PATH is evaluated in QgsApplication -
        # no need to mess with it here.
        QGISAPP = QgsApplication(argvb, myGuiFlag)

        QGISAPP.initQgis()
        s = QGISAPP.showSettings()
        LOGGER.debug(s)

        def debug_log_message(message, tag, level):
            """
            Prints a debug message to a log
            :param message: message to print
            :param tag: log tag
            :param level: log message level (severity)
            :return:
            """
            print("{}({}): {}".format(tag, level, message))

        QgsApplication.instance().messageLog().messageReceived.connect(
            debug_log_message
        )

        if cleanup:

            @atexit.register
            def exitQgis():
                """
                Gracefully closes the QgsApplication instance
                """
                try:
                    QGISAPP.exitQgis()  # noqa: F823
                    QGISAPP = None  # noqa: F841
                except NameError:
                    pass

    if PARENT is None:
        # noinspection PyPep8Naming
        PARENT = QWidget()

    if CANVAS is None:
        # noinspection PyPep8Naming
        CANVAS = QgsMapCanvas(PARENT)
        CANVAS.resize(QSize(400, 400))

    if IFACE is None:
        # QgisInterface is a stub implementation of the QGIS plugin interface
        # noinspection PyPep8Naming
        IFACE = QgisInterface(CANVAS)

    return QGISAPP, CANVAS, IFACE, PARENT