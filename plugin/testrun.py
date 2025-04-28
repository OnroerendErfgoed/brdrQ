from qgis.gui import QgisInterface
#from qgis.utils import iface

from brdrq.brdrq_dockwidget_featurealigner import brdrQDockWidgetFeatureAligner
from brdrq.brdrq_utils import get_workfolder
from brdrq.brdrq_dockwidget_bulkaligner import brdrQDockWidgetBulkAligner
from brdrq.brdrq_plugin import BrdrQPlugin


def _run():
    from qgis.core import QgsApplication

    app = QgsApplication([], True)
    app.initQgis()
    # #iface = QgisInterface().mapCanvas()
    # from qgis.utils import iface
    # print(iface)
    #brdrqplugin =BrdrQPlugin(iface)
    widget = brdrQDockWidgetFeatureAligner(None, None)
    widget_bulkaligner = brdrQDockWidgetFeatureAligner(None, None)
    widget.get_graphic()
    #widget_bulkaligner.hello()

    # iface = QgisInterface.QgsMapCanvas()
    # plugin = BrdrQPlugin(iface)
    # workfolder = get_workfolder("C:/tests", "myname", temporary=True)
    # print (workfolder)
    # workfolder = get_workfolder("C:/tests", "myname", temporary=False)
    # print (workfolder)
    # workfolder = get_workfolder("", "myname", temporary=True)
    # print (workfolder)
    # workfolder = get_workfolder("", "myname", temporary=False)
    # print (workfolder)
    # workfolder = get_workfolder("", "", temporary=True)
    # print (workfolder)
    # workfolder = get_workfolder("", "", temporary=False)
    # print (workfolder)
    # workfolder = get_workfolder("C:/tests", "", temporary=True)
    # print (workfolder)
    # workfolder = get_workfolder("C:/tests", "", temporary=False)
    # print (workfolder)
    # tests = QgsProcessingOutputFolder(name="dsg")
    # foldername = QgsProcessingParameterFolderDestination(name="tests")
    # print("withoutname" + foldername)

    # widget_bulkaligner.show()
    # widget.show()
    # app.exec_()


if __name__ == "__main__":
    # workfolder = get_workfolder("notwritable/", "testrun", False)
    # print(workfolder)
    _run()
