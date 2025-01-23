from brdrq.brdrq_dockwidget import brdrQDockWidget
from brdrq.brdrq_utils import get_workfolder
from brdrq.brdrq_dockwidget_bulkaligner import brdrQDockWidgetBulkAligner


def _run():
    from qgis.core import QgsApplication

    app = QgsApplication([], True)
    app.initQgis()
    widget = brdrQDockWidget()
    widget_bulkaligner = brdrQDockWidgetBulkAligner()
    # iface = QgisInterface.QgsMapCanvas()
    # plugin = BrdrQPlugin(iface)
    # workfolder = get_workfolder("C:/test", "myname", temporary=True)
    # print (workfolder)
    # workfolder = get_workfolder("C:/test", "myname", temporary=False)
    # print (workfolder)
    # workfolder = get_workfolder("", "myname", temporary=True)
    # print (workfolder)
    # workfolder = get_workfolder("", "myname", temporary=False)
    # print (workfolder)
    # workfolder = get_workfolder("", "", temporary=True)
    # print (workfolder)
    # workfolder = get_workfolder("", "", temporary=False)
    # print (workfolder)
    # workfolder = get_workfolder("C:/test", "", temporary=True)
    # print (workfolder)
    # workfolder = get_workfolder("C:/test", "", temporary=False)
    # print (workfolder)
    # test = QgsProcessingOutputFolder(name="dsg")
    # foldername = QgsProcessingParameterFolderDestination(name="test")
    # print("withoutname" + foldername)
    widget_bulkaligner.show()
    widget.show()
    app.exec_()


if __name__ == "__main__":
    workfolder = get_workfolder("notwritable/", "testrun", False)
    print(workfolder)
    _run()
