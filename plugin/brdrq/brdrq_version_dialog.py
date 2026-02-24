import inspect
import os
import platform

import brdr
from PyQt5.QtGui import QIcon
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import QDialog, QLabel, QVBoxLayout, QHBoxLayout
from qgis.core import Qgis

cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]
class VersionInfoDialog(QDialog):
    def __init__(self,title,metadata):
        super().__init__()
        plugin_dir = os.path.dirname(__file__)
        icon_path = os.path.join(plugin_dir, 'icon_base.png')
        self.setWindowIcon(QIcon(icon_path))
        self.setWindowTitle(title)
        self.metadata = metadata
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Version-information

        brdrq_version_label = QLabel(f"<b>brdrQ Version:</b> {self.metadata.get("version")} - (<a href='https://onroerenderfgoed.github.io/brdrQ/'> brdrQ Documentation</a>)")
        brdrq_version_label.setOpenExternalLinks(True)
        brdr_version_label = QLabel(f"<b>brdr Version:</b> {brdr.__version__} - (<a href='https://onroerenderfgoed.github.io/brdr/'> brdr Documentation</a>)")
        brdr_version_label.setOpenExternalLinks(True)
        qgis_version_label = QLabel(f"<b>QGIS Version:</b> {Qgis.QGIS_VERSION}")
        python_version_label = QLabel(f"<b>Python Version:</b> {platform.python_version()}")
        author = f"<b>Author:</b> {self.metadata.get("author")}  [{self.metadata.get("email")}]"
        author_label = QLabel(author)
        poweredby_label = QLabel(f"<b>Powered by:</b> Athumi & Agentschap Onroerend Erfgoed")

        layout.addWidget(brdrq_version_label)
        layout.addWidget(brdr_version_label)
        layout.addWidget(qgis_version_label)
        layout.addWidget(python_version_label)
        layout.addWidget(author_label)
        layout.addWidget(poweredby_label)

        # Images
        image_layout = QHBoxLayout()
        icon_athumi = os.path.join(os.path.join(cmd_folder, "icon_athumi.png"))
        icon_oe = os.path.join(os.path.join(cmd_folder, "icon_oe.png"))
        pixmap1 = QPixmap(icon_athumi).scaledToHeight(60)
        pixmap2 = QPixmap(icon_oe).scaledToHeight(60)

        image_label1 = QLabel()
        image_label1.setPixmap(pixmap1)

        image_label2 = QLabel()
        image_label2.setPixmap(pixmap2)

        image_layout.addWidget(image_label1)
        image_layout.addWidget(image_label2)

        layout.addLayout(image_layout)
        self.setLayout(layout)
