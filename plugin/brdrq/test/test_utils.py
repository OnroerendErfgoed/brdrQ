import os
import unittest

from processing.core.Processing import Processing
from qgis.gui import QgsMapCanvas

from .utilities import get_qgis_app
from ..brdrq_utils import get_workfolder

CANVAS: QgsMapCanvas
QGISAPP, CANVAS, IFACE, PARENT = get_qgis_app()
Processing.initialize()


class TestUtils(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        print("setup TestClass")

    @classmethod
    def tearDownClass(cls) -> None:
        print("start tearDown TestClass")
        print("end tearDown TestClass")

    def test_workfolder(self):
        folderpath = os.path.dirname(__file__)
        foldername = "testfoldername"
        # workfolder = get_workfolder(folderpath, foldername, temporary =False)
        workfolder = get_workfolder(folderpath, foldername, temporary=True)

        # #folder_to_remove
        # folder_to_remove = os.path.join(folderpath, foldername)
        # print (folder_to_remove)
        # shutil.rmtree(folder_to_remove)
        assert True
