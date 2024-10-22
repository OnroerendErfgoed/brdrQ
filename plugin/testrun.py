from brdrq.brdrq_dockwidget import brdrQDockWidget


def _run():
    from qgis.core import QgsApplication
    app = QgsApplication([], True)
    app.initQgis()
    widget = brdrQDockWidget()
    widget.show()
    app.exec_()

if __name__ == '__main__':
    _run()