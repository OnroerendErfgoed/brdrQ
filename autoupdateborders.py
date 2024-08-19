# -*- coding: utf-8 -*-

"""
***************************************************************************
*   name: brdrQ - AutoUpdateBorders
*   author: Karel Dieussaert
*   Docs and Code- repo: https://github.com/OnroerendErfgoed/brdrQ/
*   history:
*            -initial version

MIT LICENSE:
Copyright (c) 2023-2024 Flanders Heritage Agency

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify,
merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the
following conditions:

The above copyright notice and this permission notice shall be included in all copies
or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR
THE USE OR OTHER DEALINGS IN THE SOFTWARE.
***************************************************************************
"""
import subprocess
import sys
import site
import os
import json
from qgis import processing
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtCore import QTextCodec
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsCoordinateReferenceSystem
from qgis.core import QgsFeature
from qgis.core import QgsField
from qgis.core import QgsGeometry
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingException
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingOutputVectorLayer
from qgis.core import QgsProcessingParameterDateTime


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
        unary_union
    )
except (ModuleNotFoundError):
    print("Module shapely not found. Installing from PyPi.")
    subprocess.check_call([python_exe,
                           '-m', 'pip', 'install', 'shapely'])
    from shapely import (
        Polygon,
        from_wkt,
        to_wkt,
        unary_union
    )

try:
    import brdr

    if brdr.__version__ != "0.1.1":
        raise ValueError("Version mismatch")

except (ModuleNotFoundError, ValueError):
    subprocess.check_call([python_exe,
                           '-m', 'pip', 'install', 'brdr==0.1.1'])
    import brdr

    print(brdr.__version__)

from brdr.aligner import Aligner
from brdr.utils import multipolygons_to_singles
from brdr.enums import OpenbaarDomeinStrategy
from brdr.enums import GRBType


class AutoUpdateBordersProcessingAlgorithm(QgsProcessingAlgorithm):
    """
    Script to auto-update geometries that are aligned to an old GRB-referencelayer to a newer GRB-referencelayer.
    Documentation can be found at: https://github.com/OnroerendErfgoed/brdrQ/
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    START_DATE = "START_DATE"
    END_DATE = "END_DATE"

    def flags(self):
        return super().flags() | QgsProcessingAlgorithm.FlagNoThreading

    @staticmethod
    def tr(string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        return AutoUpdateBordersProcessingAlgorithm()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return "brdrqautoupdateborders"

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr("brdrQ - AutoUpdateBorders")

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This stringgeom
        should be localised.
        """
        return self.tr("brdrQ")

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return "brdrq"

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it.
        """
        return self.tr(
            "Script to auto-update geometries that are aligned to an old GRB-referencelayer to a newer GRB-referencelayer"
            "Documentation can be found at: https://github.com/OnroerendErfgoed/brdrQ/ "
        )

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # INPUT  standard parameters
        # make your own widget is also possible!
        # https://gis.stackexchange.com/questions/432849/changing-appearence-of-datetime-input-in-qgis-processing-tool-to-international-d
        # https://www.faunalia.eu/en/blog/2019-07-02-custom-processing-widget

        # START DATETIME
        parameter = QgsProcessingParameterDateTime(
            self.START_DATE,
            'StartDate:',
            type=QgsProcessingParameterDateTime.Date
            # ,
            # defaultValue = QDateTime.currentDateTime().addDays(-31)
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

        # END DATETIME
        parameter = QgsProcessingParameterDateTime(
            self.END_DATE,
            'EndDate:',
            type=QgsProcessingParameterDateTime.Date
            # ,
            # defaultValue = QDateTime.currentDateTime().addDays(-31)
        )
        parameter.setFlags(parameter.flags())
        self.addParameter(parameter)

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """

        feedback_steps = 6
        feedback = QgsProcessingMultiStepFeedback(feedback_steps, feedback)
        feedback.pushInfo("START")

        datetime_start = self.parameterAsDateTime(
            parameters,
            self.START_DATE,
            context
        )
        print(datetime_start)
        feedback.pushInfo(str(datetime_start))
        feedback.pushInfo("END PROCESSING")
        feedback.pushInfo("EINDE: RESULTAAT BEREKEND")
        return {
        }

