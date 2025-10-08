from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTableView, QAbstractItemView
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from qgis.core import QgsExpression, QgsFeatureRequest
from qgis.utils import iface

class FeatureTableWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.table_view = QTableView()
        layout = QVBoxLayout()
        layout.addWidget(self.table_view)
        self.setLayout(layout)

        self.feature_ids = []
        self.model = QStandardItemModel()
        self.table_view.setModel(self.model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SingleSelection)

        self.table_view.selectionModel().selectionChanged.connect(self.on_selection_changed)

    def reset(self):
        self.model.clear()

    def load_features(self, layer):
        if not layer:
            return

        features = list(layer.getFeatures())
        fields = layer.fields()

        # Kies het veld dat je eerst wil tonen
        first_field_name = "brdrq_state"

        # Maak een lijst van veldnamen met 'naam' eerst
        all_field_names = [first_field_name] + [
            f.name() for f in fields if f.name() != first_field_name
        ]

        self.model.clear()
        self.model.setColumnCount(len(fields))
        self.model.setHorizontalHeaderLabels([field.name() for field in all_field_names])
        self.feature_ids = []

        self._populate_model(layer.getFeatures())

    def _populate_model(self, features):
        self.model.removeRows(0, self.model.rowCount())
        self.feature_ids.clear()

        for feature in features:
            row = []
            for field_name in self.field_names:
                value = str(feature[field_name])
                item = QStandardItem(value)
                row.append(item)
            self.model.appendRow(row)
            self.feature_ids.append(feature.id())

    def apply_filter(self):
        if not self.layer:
            return

        filter_text = self.filter_input.text().strip().lower()
        if not filter_text:
            self._populate_model(self.layer.getFeatures())
            return

        # Pas hier aan op welk veld je wil filteren, bv. 'naam'
        filter_field = "naam"

        expr = QgsExpression(f"lower(\"{filter_field}\") LIKE '%{filter_text}%'")
        request = QgsFeatureRequest(expr)
        filtered_features = self.layer.getFeatures(request)

        self._populate_model(filtered_features)

    def on_selection_changed(self, selected, deselected):
        indexes = self.table_view.selectionModel().selectedRows()
        ids = [self.feature_ids[index.row()] for index in indexes]
        print(ids)
