import unittest
from unittest.mock import MagicMock, patch

from .. import brdrq_utils


class TestLayerVisibility(unittest.TestCase):
    def test_move_to_group_preserves_visibility_state(self):
        node = MagicMock()
        node.itemVisibilityChecked.return_value = False
        node_clone = MagicMock()
        node.clone.return_value = node_clone

        parent = MagicMock()
        node.parent.return_value = parent

        group = MagicMock()

        tree = MagicMock()
        tree.findGroup.side_effect = [node, group]

        project = MagicMock()
        project.layerTreeRoot.return_value = tree

        with patch.object(brdrq_utils.QgsProject, "instance", return_value=project):
            brdrq_utils.move_to_group("thing_name", "group_name")

        node_clone.setItemVisibilityChecked.assert_called_once_with(False)

    def test_set_layer_visibility_passes_bool_to_layer_tree(self):
        layer = MagicMock()
        layer.id.return_value = "layer-id-1"

        node = MagicMock()
        root = MagicMock()
        root.findLayer.return_value = node

        project = MagicMock()
        project.layerTreeRoot.return_value = root

        with patch.object(brdrq_utils.QgsProject, "instance", return_value=project):
            brdrq_utils.set_layer_visibility(layer, False)
            node.setItemVisibilityChecked.assert_called_once_with(False)

            node.setItemVisibilityChecked.reset_mock()
            brdrq_utils.set_layer_visibility(layer, True)
            node.setItemVisibilityChecked.assert_called_once_with(True)

    def test_gpkg_layer_to_map_passes_bool_to_layer_tree(self):
        layer = MagicMock()
        layer.id.return_value = "layer-id-2"
        layer.isValid.return_value = True
        layer.renderer.return_value = None

        root = MagicMock()
        moved_node = MagicMock()

        project = MagicMock()
        project.mapLayersByName.return_value = []
        project.layerTreeRoot.return_value = root

        with patch.object(brdrq_utils.QgsProject, "instance", return_value=project), patch.object(
            brdrq_utils, "QgsVectorLayer", return_value=layer
        ), patch.object(brdrq_utils, "move_to_group", return_value=(moved_node, MagicMock())), patch.object(
            brdrq_utils, "iface", None
        ):
            brdrq_utils.gpkg_layer_to_map(
                name="dummy",
                gpkg_path="dummy.gpkg",
                layer_name="dummy",
                symbol=None,
                visible=False,
                group="test-group",
            )
            moved_node.setItemVisibilityChecked.assert_called_once_with(False)

            moved_node.setItemVisibilityChecked.reset_mock()
            brdrq_utils.gpkg_layer_to_map(
                name="dummy",
                gpkg_path="dummy.gpkg",
                layer_name="dummy",
                symbol=None,
                visible=True,
                group="test-group",
            )
            moved_node.setItemVisibilityChecked.assert_called_once_with(True)

    def test_featurecollection_to_layer_passes_bool_to_moved_node(self):
        layer = MagicMock()
        layer.id.return_value = "layer-id-3"
        layer.renderer.return_value = None

        root = MagicMock()
        moved_node = MagicMock()

        project = MagicMock()
        project.mapLayersByName.return_value = []
        project.layerTreeRoot.return_value = root

        featurecollection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "Point",
                        "coordinates": [0, 0],
                    },
                }
            ],
        }

        with patch.object(brdrq_utils.QgsProject, "instance", return_value=project), patch.object(
            brdrq_utils, "QgsVectorLayer", return_value=layer
        ), patch.object(
            brdrq_utils, "write_featurecollection_to_geopackage"
        ), patch.object(
            brdrq_utils, "move_to_group", return_value=(moved_node, MagicMock())
        ), patch.object(
            brdrq_utils, "iface", None
        ):
            brdrq_utils.featurecollection_to_layer(
                name="dummy_fc",
                featurecollection=featurecollection,
                symbol=None,
                visible=False,
                group="test-group",
                tempfolder=".",
            )

        moved_node.setItemVisibilityChecked.assert_called_once_with(False)
