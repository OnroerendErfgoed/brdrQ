from qgis.PyQt.QtCore import QTranslator, QCoreApplication, QLocale
import os

def load_translation():
    locale = QLocale.system().name()
    plugin_dir = os.path.dirname(__file__)
    i18n_path = os.path.join(plugin_dir, 'i18n')
    translator = QTranslator()
    translation_file = f"brdrq_{locale}.qm"
    translation_path = os.path.join(i18n_path, translation_file)
    if os.path.exists(translation_path):
        translator.load(translation_path)
        QCoreApplication.installTranslator(translator)
